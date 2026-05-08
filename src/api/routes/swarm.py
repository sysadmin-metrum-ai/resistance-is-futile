"""Deploy-style API endpoints for whole-swarm flight."""

from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.swarm.health import CflibHealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.models import DroneCandidate
from src.swarm.models import HealthThresholds
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.service import SwarmDeployService
from src.swarm.service import get_swarm_deploy_service

router = APIRouter()
dtw_router = APIRouter()
_DRONE_ESTIMATED_DURATION_SECONDS = 30
_dtw_sequences: dict[str, dict] = {}


class SwarmDeployRequest(BaseModel):
    """One deploy-style request for a full 3-5 drone swarm mission."""

    swarm_size: int = Field(MIN_SWARM_SIZE, ge=MIN_SWARM_SIZE, le=MAX_SWARM_SIZE)
    formation: Literal["line", "triangle", "diamond", "v"] = "triangle"
    pattern: Literal["line_shift", "square", "hold", "up_forward"] = "up_forward"
    final_pose: tuple[float, float, float] = (0.50, 0.0, 0.55)
    slot_spacing_m: float = Field(0.49, gt=0)
    min_separation_m: float = Field(0.10, gt=0)
    enable_collision_avoidance: bool = True
    no_fly_zone_paths: tuple[str, ...] = ("config/no_fly_zones/server_box.json",)
    hover_z: float = Field(0.55, gt=0)
    dry_run: bool = True
    arm: bool = False
    allowed_uris: tuple[str, ...] = ()
    denied_uris: tuple[str, ...] = ()
    health_timeout_s: float = Field(25.0, gt=0)
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
            hover_z=self.hover_z,
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


class SwarmHealthRequest(BaseModel):
    allowed_uris: tuple[str, ...] = (
        "radio://0/80/2M/E7E7E7E701",
        "radio://0/80/2M/E7E7E7E702",
        "radio://0/80/2M/E7E7E7E703",
    )
    health_timeout_s: float = Field(25.0, gt=0)
    max_concurrent_checks: int = Field(1, ge=1, le=5)


class SwarmHealthResponse(BaseModel):
    results: list[dict]


class SwarmBatteryTelemetryResponse(BaseModel):
    mission_id: str
    telemetry: dict[str, dict]


class DroneTriggerResponse(BaseModel):
    sequence_id: str
    status: str = "dispatched"
    estimated_duration_seconds: int


class DroneStatusResponse(BaseModel):
    sequence_id: str
    status: Literal["dispatched", "in_progress", "completed", "failed"]
    current_stage: Literal["flying_to_target", "inspecting", "returning", "docked"]
    elapsed_seconds: int


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


@router.post("/abort", response_model=SwarmDeployResponse | dict)
async def abort_swarm(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    result = await service.abort()
    if result is None:
        return {"state": "idle", "message": "no active swarm mission"}
    return _response_from_result(service.result_payload(result))


@dtw_router.post("/drone/trigger", response_model=DroneTriggerResponse)
async def trigger_drone(
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """DTW-compatible wrapper that asynchronously forwards to the deploy API."""
    verify_api_key(x_api_key)
    sequence_id = f"SEQ-{uuid4().hex[:8].upper()}"
    base_url = str(request.base_url).rstrip("/")
    headers = _forward_headers(x_api_key)
    _dtw_sequences[sequence_id] = {
        "swarm_mission_id": None,
        "state": "accepted",
        "message": "dispatched",
        "started_at": datetime.now(timezone.utc),
    }
    asyncio.create_task(_run_dtw_sequence(sequence_id, base_url, headers))
    return DroneTriggerResponse(
        sequence_id=sequence_id,
        estimated_duration_seconds=_DRONE_ESTIMATED_DURATION_SECONDS,
    )


@dtw_router.get("/drone/status/{sequence_id}", response_model=DroneStatusResponse)
async def get_drone_status(
    sequence_id: str,
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    result = await _dtw_sequence_status(sequence_id, str(request.base_url).rstrip("/"), _forward_headers(x_api_key))
    return DroneStatusResponse(
        sequence_id=sequence_id,
        status=_drone_status(result),
        current_stage=_drone_stage(result),
        elapsed_seconds=0,
    )


@dtw_router.get("/drone/result/{sequence_id}", response_model=DroneResultResponse)
async def get_drone_result(
    sequence_id: str,
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    result = await _dtw_sequence_status(sequence_id, str(request.base_url).rstrip("/"), _forward_headers(x_api_key))
    return DroneResultResponse(
        sequence_id=sequence_id,
        status=_confirmation_status(result),
        finding=result.message or result.state,
        led_status="completed" if _confirmation_status(result) == "confirmed" else "unknown",
        thermal_anomaly=False,
        image_url="",
        timestamp=datetime.now(timezone.utc),
    )


async def _run_dtw_sequence(sequence_id: str, base_url: str, headers: dict[str, str]) -> None:
    try:
        result = await _post_swarm_deploy(base_url, headers, SwarmDeployRequest(dry_run=False, arm=True))
        _dtw_sequences[sequence_id].update(
            swarm_mission_id=result.mission_id,
            state=result.state,
            message=result.message,
        )
    except Exception as exc:
        _dtw_sequences[sequence_id].update(state="failed", message=str(exc))


async def _dtw_sequence_status(
    sequence_id: str,
    base_url: str,
    headers: dict[str, str],
) -> SwarmDeployResponse:
    sequence = _dtw_sequences.get(sequence_id)
    if sequence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="drone sequence not found")

    mission_id = sequence.get("swarm_mission_id")
    if mission_id:
        try:
            return await _get_swarm_deploy_status(base_url, headers, mission_id)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise

    return _dtw_pending_response(sequence_id, sequence)


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


def _dtw_pending_response(sequence_id: str, sequence: dict) -> SwarmDeployResponse:
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
    )


def _drone_status(result: SwarmDeployResponse) -> Literal["dispatched", "in_progress", "completed", "failed"]:
    if result.state == "accepted":
        return "dispatched"
    if result.state == "running":
        return "in_progress"
    if result.state in {"completed", "dry_run"}:
        return "completed"
    return "failed"


def _drone_stage(result: SwarmDeployResponse) -> Literal["flying_to_target", "inspecting", "returning", "docked"]:
    if result.state in {"accepted", "running"}:
        return "flying_to_target"
    return "docked"


def _confirmation_status(result: SwarmDeployResponse) -> Literal["confirmed", "unconfirmed", "error"]:
    if result.state in {"completed", "dry_run"}:
        return "confirmed"
    if result.state in {"failed", "aborted"}:
        return "error"
    return "unconfirmed"
