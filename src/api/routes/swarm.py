"""Deploy-style API endpoints for whole-swarm flight."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import DroneCandidate
from src.swarm.models import HealthThresholds
from src.swarm.models import MissionSpec
from src.swarm.health import CflibHealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.service import SwarmDeployService
from src.swarm.service import get_swarm_deploy_service
from src.swarm.session import cache_health_results

router = APIRouter()


class SwarmDeployRequest(BaseModel):
    """One deploy-style request for a full 3-5 drone swarm mission."""

    swarm_size: int = Field(MIN_SWARM_SIZE, ge=MIN_SWARM_SIZE, le=MAX_SWARM_SIZE)
    formation: Literal["line", "triangle", "diamond", "v"] = "line"
    pattern: Literal["line_shift", "square", "hold", "up_forward"] = "line_shift"
    final_pose: tuple[float, float, float] = (0.50, 0.0, 0.55)
    slot_spacing_m: float = Field(0.45, gt=0)
    min_separation_m: float = Field(0.10, gt=0)
    enable_collision_avoidance: bool = True
    no_fly_zone_paths: tuple[str, ...] = ("config/no_fly_zones/server_box.json",)
    hover_z: float = Field(0.55, gt=0)
    dry_run: bool = True
    arm: bool = False
    allowed_uris: tuple[str, ...] = ()
    denied_uris: tuple[str, ...] = ()

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
        )


class SwarmDeployResponse(BaseModel):
    mission_id: str
    state: str
    selected: list[dict]
    rejected: list[dict]
    plan: dict | None = None
    events: list[str] = []
    message: str


class SwarmHealthRequest(BaseModel):
    allowed_uris: tuple[str, ...] = (
        "radio://0/80/2M/E7E7E7E701",
        "radio://0/80/2M/E7E7E7E702",
        "radio://0/80/2M/E7E7E7E703",
    )
    health_timeout_s: float = Field(12.0, gt=0)
    max_concurrent_checks: int = Field(1, ge=1, le=5)


class SwarmHealthResponse(BaseModel):
    results: list[dict]


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
    return _response_from_result(result.to_dict())


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
    cache_health_results(results)
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
    return _response_from_result(result.to_dict())


@router.post("/abort", response_model=SwarmDeployResponse | dict)
async def abort_swarm(
    service: SwarmDeployService = Depends(get_service),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    verify_api_key(x_api_key)
    result = await service.abort()
    if result is None:
        return {"state": "idle", "message": "no active swarm mission"}
    return _response_from_result(result.to_dict())


def _response_from_result(data: dict) -> SwarmDeployResponse:
    selection = data["selection"]
    return SwarmDeployResponse(
        mission_id=data["mission_id"],
        state=data["state"],
        selected=selection["selected"],
        rejected=selection["rejected"],
        plan=data["plan"],
        events=data["events"],
        message=data["message"],
    )
