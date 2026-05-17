"""Deploy-style API endpoints for whole-swarm flight."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.swarm.health import CflibHealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.models import DroneCandidate
from src.swarm.models import HealthThresholds
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.roster import DEFAULT_DISCOVERY_FLEET
from src.swarm.service import SwarmDeployService
from src.swarm.service import get_swarm_deploy_service

router = APIRouter()
dtw_router = APIRouter()
_DRONE_ESTIMATED_DURATION_SECONDS = 30
_EMERGENCY_LAND_URIS = DEFAULT_DISCOVERY_FLEET
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CAPTURED_PATH = _PROJECT_ROOT / "config/demo_path.json"
_dtw_sequences: dict[str, dict] = {}
DronePhase = Literal["preflight", "health_failed", "ready_to_deploy", "taking_off", "returning", "completed", "failed"]


class SwarmDeployRequest(BaseModel):
    """One deploy-style request for a full 3-5 drone swarm mission."""

    swarm_size: int = Field(MAX_SWARM_SIZE, ge=MIN_SWARM_SIZE, le=MAX_SWARM_SIZE)
    formation: Literal["line", "triangle", "diamond", "v"] = "triangle"
    pattern: Literal["line_shift", "square", "hold", "up_forward", "captured_path", "crazy_pinwheel"] = "up_forward"
    final_pose: tuple[float, float, float] = (0.50, 0.0, 0.55)
    slot_spacing_m: float = Field(0.49, gt=0)
    min_separation_m: float = Field(0.10, gt=0)
    enable_collision_avoidance: bool = True
    no_fly_zone_paths: tuple[str, ...] = ()
    captured_path: str | None = None
    yaw_rad: float = 0.0
    hover_z: float = Field(0.55, gt=0)
    landing_settle_s: float = Field(0.5, ge=0)
    dry_run: bool = True
    arm: bool = False
    allowed_uris: tuple[str, ...] = ()
    denied_uris: tuple[str, ...] = ()
    health_timeout_s: float = Field(40.0, gt=0)
    max_concurrent_checks: int = Field(1, ge=1, le=5)
    callback_url: str | None = Field(None, description="Optional infra callback URL for terminal deploy status")

    def to_spec(self) -> MissionSpec:
        return MissionSpec(
            swarm_size=self.swarm_size,
            formation=self.formation,
            pattern=self.pattern,
            final_pose=self.final_pose,
            slot_spacing_m=self.slot_spacing_m,
            min_separation_m=self.min_separation_m,
            enable_collision_avoidance=self.enable_collision_avoidance,
            no_fly_zone_paths=self.no_fly_zone_paths,
            captured_path=self.captured_path,
            yaw_rad=self.yaw_rad,
            hover_z=self.hover_z,
            landing_settle_s=self.landing_settle_s,
            dry_run=self.dry_run,
            arm=self.arm,
            allowed_uris=self.allowed_uris,
            denied_uris=self.denied_uris,
            health_timeout_s=self.health_timeout_s,
            max_concurrent_checks=self.max_concurrent_checks,
            callback_url=self.callback_url,
        )


class SwarmDeployResponse(BaseModel):
    mission_id: str
    state: str
    success: bool = True
    infra_status: str
    infra_continue: bool
    swarm_success: bool
    swarm_safe_to_fly: bool
    selected: list[dict]
    rejected: list[dict]
    plan: dict | None = None
    events: list[str] = []
    telemetry: dict[str, dict] = Field(default_factory=dict)
    message: str
    phase: str | None = None
    phase_started_at: str | None = None
    phase_updated_at: str | None = None
    phase_details: dict = Field(default_factory=dict)
    phase_history: list[dict] = Field(default_factory=list)


class SwarmHealthRequest(BaseModel):
    allowed_uris: tuple[str, ...] = DEFAULT_DISCOVERY_FLEET
    health_timeout_s: float = Field(40.0, gt=0)
    max_concurrent_checks: int = Field(1, ge=1, le=5)


class SwarmHealthResponse(BaseModel):
    results: list[dict]


class SwarmBatteryTelemetryResponse(BaseModel):
    mission_id: str
    telemetry: dict[str, dict]


class EmergencyLandRequest(BaseModel):
    target_uris: tuple[str, ...] = Field(default_factory=lambda: _EMERGENCY_LAND_URIS)
    land_duration_s: float = Field(2.0, gt=0)
    stop_delay_s: float = Field(2.5, ge=0)


class EmergencyLandTargetResponse(BaseModel):
    uri: str
    status: Literal["landed", "failed"]
    error: str | None = None


class EmergencyLandResponse(BaseModel):
    status: Literal["emergency_land_sent"]
    active_stopped: list[str]
    results: list[EmergencyLandTargetResponse]


class DroneTriggerResponse(BaseModel):
    sequence_id: str
    status: str = "dispatched"
    phase: DronePhase = "preflight"
    estimated_duration_seconds: int


class DroneStatusResponse(BaseModel):
    sequence_id: str
    status: Literal["dispatched", "in_progress", "completed", "failed"]
    current_stage: DronePhase
    phase: DronePhase
    elapsed_seconds: int
    phase_started_at: str | None = None
    phase_updated_at: str | None = None
    phase_details: dict = Field(default_factory=dict)
    phase_history: list[dict] = Field(default_factory=list)
    health_failure_details: dict | None = None


class DroneResultResponse(BaseModel):
    sequence_id: str
    status: Literal["confirmed", "unconfirmed", "error"]
    finding: str
    led_status: str
    thermal_anomaly: bool
    image_url: str
    timestamp: datetime


def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


def get_service() -> SwarmDeployService:
    return get_swarm_deploy_service()


@router.post("/deploy", response_model=SwarmDeployResponse)
async def deploy_swarm(
    request: SwarmDeployRequest,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Run concurrent health checks, select the healthiest swarm, and deploy."""

    verify_api_key(x_api_key)
    try:
        result = await service.deploy(request.to_spec())
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _response_from_result(service.result_payload(result))


@router.post("/health", response_model=SwarmHealthResponse)
async def check_swarm_health(
    request: SwarmHealthRequest,
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Run concurrent cflib health checks without planning or arming."""

    verify_api_key(x_api_key)
    candidates = [DroneCandidate(uri=uri) for uri in request.allowed_uris]
    thresholds = HealthThresholds(
        health_timeout_s=request.health_timeout_s,
        max_concurrent_checks=request.max_concurrent_checks,
    )
    results = await check_candidates_concurrently(
        candidates,
        probe=CflibHealthProbe(),
        thresholds=thresholds,
    )
    return SwarmHealthResponse(results=[result.to_dict() for result in results])


@router.get("/status")
async def get_swarm_status(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Read-only snapshot of whether a swarm flight is active."""
    verify_api_key(x_api_key)
    return service.current_status()


@router.get("/deploy/{mission_id}", response_model=SwarmDeployResponse)
async def get_swarm_deploy_status(
    mission_id: str,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    result = await service.get_status(mission_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="swarm mission not found")
    return _response_from_result(service.result_payload(result))


@router.get("/deploy/{mission_id}/battery", response_model=SwarmBatteryTelemetryResponse)
async def get_swarm_battery_telemetry(
    mission_id: str,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Read only the 1Hz in-flight battery watchdog samples for a swarm mission."""
    verify_api_key(x_api_key)
    telemetry = service.battery_telemetry(mission_id)
    if telemetry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="swarm mission not found")
    return SwarmBatteryTelemetryResponse(mission_id=mission_id, telemetry=telemetry)


@router.post("/abort", response_model=EmergencyLandResponse)
async def abort_swarm(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Global abort: safe-land all known drones, regardless of mission state."""
    verify_api_key(x_api_key)
    return await _global_emergency_land(service, EmergencyLandRequest())


@router.post("/emergency-land", response_model=EmergencyLandResponse)
async def emergency_land_swarm(
    request: EmergencyLandRequest = EmergencyLandRequest(),
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Force land known drones, even if API mission state was lost."""
    verify_api_key(x_api_key)
    return await _global_emergency_land(service, request)


@dtw_router.post("/drone/trigger", response_model=DroneTriggerResponse)
async def trigger_drone(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """DTW-compatible wrapper that starts preflight without taking off."""
    verify_api_key(x_api_key)
    sequence_id = f"SEQ-{uuid4().hex[:8].upper()}"
    _dtw_sequences[sequence_id] = {
        "swarm_mission_id": None,
        "state": "accepted",
        "phase": "preflight",
        "message": "preflight",
        "started_at": datetime.now(timezone.utc),
    }
    asyncio.create_task(_run_dtw_sequence(sequence_id, service))
    return DroneTriggerResponse(
        sequence_id=sequence_id,
        phase="preflight",
        estimated_duration_seconds=_DRONE_ESTIMATED_DURATION_SECONDS,
    )


@dtw_router.post("/drone/crazy-trigger", response_model=DroneTriggerResponse)
async def trigger_crazy_drone(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Prepare a higher-energy geometric swarm path without changing the default trigger."""
    verify_api_key(x_api_key)
    sequence_id = f"SEQ-{uuid4().hex[:8].upper()}"
    _dtw_sequences[sequence_id] = {
        "swarm_mission_id": None,
        "state": "accepted",
        "phase": "preflight",
        "message": "crazy_preflight",
        "started_at": datetime.now(timezone.utc),
    }
    asyncio.create_task(_run_crazy_dtw_sequence(sequence_id, service))
    return DroneTriggerResponse(
        sequence_id=sequence_id,
        phase="preflight",
        estimated_duration_seconds=_DRONE_ESTIMATED_DURATION_SECONDS,
    )


@dtw_router.post("/drone/launch/{sequence_id}", response_model=DroneStatusResponse)
async def launch_drone(
    sequence_id: str,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    sequence = _dtw_sequences.get(sequence_id)
    if sequence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="drone sequence not found")
    mission_id = sequence.get("swarm_mission_id")
    if not mission_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="drone sequence is still in preflight")
    try:
        await service.launch_prepared(mission_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    payload = await _dtw_sequence_payload(sequence_id, service)
    return _drone_status_response(sequence_id, payload)


@dtw_router.post("/drone/abort", response_model=EmergencyLandResponse)
async def abort_drone_global(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Global DTW abort. Does not require a sequence id."""
    verify_api_key(x_api_key)
    return await _global_emergency_land(service, EmergencyLandRequest())


@dtw_router.post("/drone/abort/{sequence_id}", response_model=EmergencyLandResponse)
async def abort_drone_sequence(
    sequence_id: str,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Compatibility abort: ignore sequence id and safe-land all known drones."""
    verify_api_key(x_api_key)
    return await _global_emergency_land(service, EmergencyLandRequest())


@dtw_router.get("/drone/status/{sequence_id}", response_model=DroneStatusResponse)
async def get_drone_status(
    sequence_id: str,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    payload = await _dtw_sequence_payload(sequence_id, service)
    return _drone_status_response(sequence_id, payload)


@dtw_router.get("/drone/result/{sequence_id}", response_model=DroneResultResponse)
async def get_drone_result(
    sequence_id: str,
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    result = await _dtw_sequence_result(sequence_id, service)
    return DroneResultResponse(
        sequence_id=sequence_id,
        status=_confirmation_status(result),
        finding=result.message or result.state,
        led_status="completed" if _confirmation_status(result) == "confirmed" else "unknown",
        thermal_anomaly=False,
        image_url="",
        timestamp=datetime.now(timezone.utc),
    )


async def _run_dtw_sequence(sequence_id: str, service: SwarmDeployService) -> None:
    try:
        request = SwarmDeployRequest(dry_run=False, arm=True, health_timeout_s=40.0, max_concurrent_checks=5)
        if _DEFAULT_CAPTURED_PATH.exists():
            request = request.model_copy(
                update={"pattern": "captured_path", "captured_path": str(_DEFAULT_CAPTURED_PATH)}
            )
        result = await service.prepare_for_launch(request.to_spec())
        _dtw_sequences[sequence_id].update(
            swarm_mission_id=result.mission_id,
            state=result.state,
            message=result.message,
        )
    except Exception as exc:
        _dtw_sequences[sequence_id].update(state="failed", phase="failed", message=str(exc))


async def _run_crazy_dtw_sequence(sequence_id: str, service: SwarmDeployService) -> None:
    try:
        spec = MissionSpec(
            dry_run=False,
            arm=True,
            health_timeout_s=40.0,
            max_concurrent_checks=5,
            formation="diamond",
            pattern="crazy_pinwheel",
            final_pose=(0.45, 0.0, 0.62),
            slot_spacing_m=0.42,
            hover_z=0.55,
            move_s=3.0,
            pattern_s=1.2,
            hold_s=0.6,
        )
        result = await service.prepare_for_launch(spec)
        _dtw_sequences[sequence_id].update(
            swarm_mission_id=result.mission_id,
            state=result.state,
            message=result.message,
        )
    except Exception as exc:
        _dtw_sequences[sequence_id].update(state="failed", phase="failed", message=str(exc))


async def _dtw_sequence_result(sequence_id: str, service: SwarmDeployService) -> SwarmDeployResponse:
    sequence = _dtw_sequences.get(sequence_id)
    if sequence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="drone sequence not found")

    mission_id = sequence.get("swarm_mission_id")
    if mission_id:
        result = await service.get_status(mission_id)
        if result is not None:
            return _response_from_result(service.result_payload(result))

    return _dtw_pending_response(sequence_id, sequence)


async def _dtw_sequence_payload(sequence_id: str, service: SwarmDeployService) -> dict:
    result = await _dtw_sequence_result(sequence_id, service)
    return result.model_dump()


async def _post_swarm_deploy(base_url: str, headers: dict[str, str], request: SwarmDeployRequest) -> SwarmDeployResponse:
    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(f"{base_url}/api/swarm/deploy", headers=headers, json=request.model_dump(mode="json"))
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return SwarmDeployResponse(**response.json())


async def _get_swarm_deploy_status(base_url: str, headers: dict[str, str], mission_id: str) -> SwarmDeployResponse:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{base_url}/api/swarm/deploy/{mission_id}", headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return SwarmDeployResponse(**response.json())


def _forward_headers(x_api_key: str | None) -> dict[str, str]:
    return {"X-API-Key": x_api_key} if x_api_key else {}


def _emergency_stop_active_connections(service: SwarmDeployService) -> list[str]:
    executor = getattr(getattr(service, "runner", None), "executor", None)
    stop_active = getattr(executor, "emergency_stop_active", None)
    if not callable(stop_active):
        return []
    return list(stop_active())


async def _global_emergency_land(service: SwarmDeployService, request: EmergencyLandRequest) -> EmergencyLandResponse:
    active_stopped = await asyncio.to_thread(_emergency_stop_active_connections, service)
    results = await asyncio.to_thread(
        _emergency_land_uris,
        request.target_uris,
        request.land_duration_s,
        request.stop_delay_s,
    )
    await service.abort()
    _mark_dtw_sequences_aborted()
    return EmergencyLandResponse(status="emergency_land_sent", active_stopped=active_stopped, results=results)


def _mark_dtw_sequences_aborted() -> None:
    for sequence in _dtw_sequences.values():
        if sequence.get("phase") == "completed" or sequence.get("state") in {"completed", "dry_run"}:
            continue
        sequence.update(state="aborted", phase="failed", message="global_abort_requested")


def _emergency_land_uris(target_uris: tuple[str, ...], land_duration_s: float, stop_delay_s: float) -> list[dict]:
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

    cflib.crtp.init_drivers()
    results: list[dict] = []
    for uri in dict.fromkeys(target_uris):
        try:
            with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
                cf = scf.cf
                try:
                    cf.param.set_value("commander.enHighLevel", "1")
                    time.sleep(0.1)
                except Exception:
                    pass
                commander = cf.high_level_commander
                commander.land(0.0, land_duration_s)
                time.sleep(stop_delay_s)
                commander.stop()
                _turn_off_known_led_decks(cf)
            results.append({"uri": uri, "status": "landed", "error": None})
        except Exception as exc:
            results.append({"uri": uri, "status": "failed", "error": str(exc)})
    return results


def _turn_off_known_led_decks(cf) -> None:
    for group, name, value in (
        ("colorLedBot", "wrgb8888", "0"),
        ("ring", "effect", "0"),
    ):
        try:
            cf.param.set_value(f"{group}.{name}", value)
        except Exception:
            pass


def _dtw_pending_response(sequence_id: str, sequence: dict) -> SwarmDeployResponse:
    phase = sequence.get("phase", "failed" if sequence["state"] == "failed" else "preflight")
    now = datetime.now(timezone.utc).isoformat()
    return SwarmDeployResponse(
        mission_id=sequence_id,
        state=sequence["state"],
        success=sequence["state"] != "failed",
        infra_status="pending",
        infra_continue=False,
        swarm_success=False,
        swarm_safe_to_fly=False,
        selected=[],
        rejected=[],
        plan=None,
        events=[],
        telemetry={},
        message=sequence["message"],
        phase=phase,
        phase_started_at=sequence.get("started_at", datetime.now(timezone.utc)).isoformat(),
        phase_updated_at=now,
        phase_details={"message": sequence["message"]},
        phase_history=[{"phase": phase, "started_at": sequence.get("started_at", datetime.now(timezone.utc)).isoformat()}],
    )


def _response_from_result(data: dict) -> SwarmDeployResponse:
    selection = data["selection"]
    return SwarmDeployResponse(
        mission_id=data["mission_id"],
        state=data["state"],
        success=data["success"],
        infra_status=data["infra_status"],
        infra_continue=data["infra_continue"],
        swarm_success=data["swarm_success"],
        swarm_safe_to_fly=data["swarm_safe_to_fly"],
        selected=selection["selected"],
        rejected=selection["rejected"],
        plan=data["plan"],
        events=data["events"],
        telemetry=data.get("telemetry", {}),
        message=data["message"],
        phase=data.get("phase"),
        phase_started_at=data.get("phase_started_at"),
        phase_updated_at=data.get("phase_updated_at"),
        phase_details=data.get("phase_details", {}),
        phase_history=data.get("phase_history", []),
    )


def _drone_status_from_payload(payload: dict) -> Literal["dispatched", "in_progress", "completed", "failed"]:
    phase = payload.get("phase")
    if phase == "completed" or payload.get("state") in {"completed", "dry_run"}:
        return "completed"
    if phase in {"failed", "health_failed"} or payload.get("state") in {"failed", "refused", "aborted"}:
        return "failed"
    if phase in {"preflight", "ready_to_deploy"}:
        return "dispatched"
    return "in_progress"


def _drone_phase_from_payload(payload: dict) -> DronePhase:
    phase = payload.get("phase")
    if phase in {"preflight", "health_failed", "ready_to_deploy", "taking_off", "returning", "completed", "failed"}:
        return phase
    if payload.get("state") in {"completed", "dry_run"}:
        return "completed"
    if payload.get("state") in {"failed", "refused", "aborted"}:
        return "failed"
    return "preflight"


def _drone_status_response(sequence_id: str, payload: dict) -> DroneStatusResponse:
    sequence = _dtw_sequences.get(sequence_id, {})
    started_at = sequence.get("started_at")
    elapsed_seconds = (
        int((datetime.now(timezone.utc) - started_at).total_seconds()) if isinstance(started_at, datetime) else 0
    )
    phase = _drone_phase_from_payload(payload)
    return DroneStatusResponse(
        sequence_id=sequence_id,
        status=_drone_status_from_payload(payload),
        current_stage=phase,
        phase=phase,
        elapsed_seconds=elapsed_seconds,
        phase_started_at=payload.get("phase_started_at"),
        phase_updated_at=payload.get("phase_updated_at"),
        phase_details=payload.get("phase_details") or {},
        phase_history=payload.get("phase_history") or [],
        health_failure_details=(payload.get("phase_details") or {}) if phase == "health_failed" else None,
    )


def _confirmation_status(result: SwarmDeployResponse) -> Literal["confirmed", "unconfirmed", "error"]:
    if result.state in {"completed", "dry_run"}:
        return "confirmed"
    if result.state in {"failed", "aborted"}:
        return "error"
    return "unconfirmed"
