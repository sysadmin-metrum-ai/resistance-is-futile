"""Pydantic schemas for swarm and remote-agent drone endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.swarm.models import CRAZY_PINWHEEL_COMPACT_SWARM_SIZE
from src.swarm.models import CRAZY_PINWHEEL_SWARM_SIZE
from src.swarm.models import DEFAULT_MIN_SEPARATION_M
from src.swarm.models import DEFAULT_SWARM_SIZE
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.roster import DEFAULT_DISCOVERY_FLEET

DronePhase = Literal["preflight", "health_failed", "ready_to_deploy", "taking_off", "returning", "completed", "failed"]


class SwarmDeployRequest(BaseModel):
    """One deploy-style request for a full swarm mission."""

    swarm_size: int = Field(DEFAULT_SWARM_SIZE, ge=MIN_SWARM_SIZE, le=MAX_SWARM_SIZE)
    formation: Literal["line", "triangle", "diamond", "v"] = "triangle"
    pattern: Literal["line_shift", "square", "hold", "up_forward", "launch_up", "captured_path", "crazy_pinwheel"] = "up_forward"
    final_pose: tuple[float, float, float] = (0.50, 0.0, 0.55)
    slot_spacing_m: float = Field(0.49, gt=0)
    min_separation_m: float = Field(DEFAULT_MIN_SEPARATION_M, gt=0)
    enable_collision_avoidance: bool = True
    no_fly_zone_paths: tuple[str, ...] = ()
    captured_path: str | None = None
    yaw_rad: float = 0.0
    hover_z: float = Field(0.55, gt=0)
    landing_settle_s: float = Field(0.25, ge=0)
    dry_run: bool = True
    arm: bool = False
    allowed_uris: tuple[str, ...] = ()
    denied_uris: tuple[str, ...] = ()
    health_timeout_s: float = Field(40.0, gt=0)
    max_concurrent_checks: int = Field(1, ge=1, le=MAX_SWARM_SIZE)
    require_full_swarm: bool = False
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
            require_full_swarm=self.require_full_swarm,
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
    max_concurrent_checks: int = Field(1, ge=1, le=MAX_SWARM_SIZE)


class SwarmHealthResponse(BaseModel):
    results: list[dict]


class SwarmBatteryTelemetryResponse(BaseModel):
    mission_id: str
    telemetry: dict[str, dict]


class EmergencyLandRequest(BaseModel):
    target_uris: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_DISCOVERY_FLEET)
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


__all__ = [
    "CRAZY_PINWHEEL_COMPACT_SWARM_SIZE",
    "CRAZY_PINWHEEL_SWARM_SIZE",
    "DronePhase",
    "DroneResultResponse",
    "DroneStatusResponse",
    "DroneTriggerResponse",
    "EmergencyLandRequest",
    "EmergencyLandResponse",
    "SwarmBatteryTelemetryResponse",
    "SwarmDeployRequest",
    "SwarmDeployResponse",
    "SwarmHealthRequest",
    "SwarmHealthResponse",
]
