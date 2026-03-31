"""Shared mission models for API routes and runtime services."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


ApproachAxis = Literal["x+", "x-", "y+", "y-"]


class MissionType(str, Enum):
    """Supported mission types."""

    SINGLE = "single"
    SWARM_INSPECT_SERVER = "swarm_inspect_server"


class Waypoint3D(BaseModel):
    """A typed 3D waypoint with optional hold/capture metadata."""

    x: float
    y: float
    z: float = Field(..., ge=0.0, description="Altitude in meters")
    yaw_degrees: float = 0.0
    hold_seconds: float = Field(0.0, ge=0.0)
    capture: bool = False
    label: Optional[str] = None


class DroneHomePosition(BaseModel):
    """Home/landing position for a specific drone."""

    drone_id: int
    home: Waypoint3D


class MissionRequest(BaseModel):
    """Request body for single-drone waypoint missions."""

    waypoints: list[Waypoint3D] = Field(
        ..., description="Ordered list of 3D waypoints"
    )
    duration_seconds: int = Field(..., gt=0)
    target_drone_id: Optional[int] = None
    callback_url: Optional[str] = None


class ServerInspectionRequest(BaseModel):
    """Request body for a deterministic server-inspection mission."""

    drone_ids: list[int] = Field(
        ..., min_length=1, description="Candidate drones ordered by preference"
    )
    home_positions: list[DroneHomePosition] = Field(
        ..., min_length=1, description="Home pads for candidate drones"
    )
    server_position: Waypoint3D
    inspection_distance: float = Field(0.8, gt=0.2, le=3.0)
    inspection_height: float = Field(1.1, gt=0.1, le=3.0)
    staging_height: float = Field(0.7, gt=0.1, le=2.0)
    preferred_drone_count: int = Field(3, ge=1, le=3)
    allow_degraded: bool = True
    approach_axis: ApproachAxis = "y-"
    lateral_spacing: float = Field(0.8, gt=0.2, le=3.0)
    hold_seconds: float = Field(2.0, ge=0.0, le=30.0)
    callback_url: Optional[str] = None

    @model_validator(mode="after")
    def validate_home_positions(self) -> "ServerInspectionRequest":
        home_ids = {item.drone_id for item in self.home_positions}
        missing = [drone_id for drone_id in self.drone_ids if drone_id not in home_ids]
        if missing:
            raise ValueError(f"missing home positions for drones: {missing}")
        return self


class PlannedDroneMission(BaseModel):
    """Mission plan for a single drone inside a server inspection."""

    drone_id: int
    role: Literal["left", "center", "right", "solo", "left_then_center", "right_then_center"]
    home: Waypoint3D
    waypoints: list[Waypoint3D]


class ServerInspectionPlan(BaseModel):
    """A dynamic plan for 1-3 drones inspecting the server face."""

    mission_type: MissionType = MissionType.SWARM_INSPECT_SERVER
    selected_drone_ids: list[int]
    degraded: bool
    approach_axis: ApproachAxis
    server_position: Waypoint3D
    drone_missions: list[PlannedDroneMission]
