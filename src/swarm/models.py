"""Shared data models for swarm selection and execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

Vec3 = tuple[float, float, float]

MIN_EXECUTION_SWARM_SIZE = 1
MIN_SWARM_SIZE = 3
DEFAULT_SWARM_SIZE = 5
MAX_SWARM_SIZE = 10
CRAZY_PINWHEEL_SWARM_SIZE = 10
CRAZY_PINWHEEL_COMPACT_SWARM_SIZE = 5
DEFAULT_CRAZY_PINWHEEL_OUTER_DELTA_M = 0.25
DEFAULT_MIN_SEPARATION_M = 0.10


class MissionState(str, Enum):
    """Lifecycle states exposed by the deploy API."""

    ACCEPTED = "accepted"
    DRY_RUN = "dry_run"
    RUNNING = "running"
    COMPLETED = "completed"
    REFUSED = "refused"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass(frozen=True)
class DroneCandidate:
    """A discovered or configured drone that may join a swarm."""

    uri: str
    name: str | None = None


@dataclass(frozen=True)
class HealthThresholds:
    """Minimum health needed before a drone can be selected."""

    min_voltage: float = 3.75
    min_battery_percent: float = 12.5
    min_connection_quality: int = 70
    health_timeout_s: float = 40.0
    estimator_timeout_s: float = 5.0
    max_concurrent_checks: int = 1


@dataclass(frozen=True)
class DroneHealth:
    """Health snapshot used for roster scoring."""

    uri: str
    ready: bool
    score: float
    reasons: tuple[str, ...] = ()
    voltage: float | None = None
    battery_percent: int | None = None
    connection_quality: int | None = None
    battery_pass: bool | None = None
    estimator_ready: bool = False
    lighthouse_ready: bool = False
    pose: Vec3 | None = None
    elapsed_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "ready": self.ready,
            "score": self.score,
            "reasons": list(self.reasons),
            "voltage": self.voltage,
            "battery_percent": self.battery_percent,
            "connection_quality": self.connection_quality,
            "battery_pass": self.battery_pass,
            "estimator_ready": self.estimator_ready,
            "lighthouse_ready": self.lighthouse_ready,
            "pose": list(self.pose) if self.pose is not None else None,
            "elapsed_s": self.elapsed_s,
        }


@dataclass(frozen=True)
class SwarmSelection:
    """Result of choosing the best viable drones."""

    selected: tuple[DroneHealth, ...]
    rejected: tuple[DroneHealth, ...]
    required_size: int

    @property
    def ready(self) -> bool:
        return len(self.selected) >= self.required_size

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "required_size": self.required_size,
            "selected": [health.to_dict() for health in self.selected],
            "rejected": [health.to_dict() for health in self.rejected],
        }


@dataclass(frozen=True)
class MissionSpec:
    """Code-owned swarm mission definition.

    Edit these defaults to change the final swarm pose or movement pattern
    without touching executor internals.
    """

    swarm_size: int = DEFAULT_SWARM_SIZE
    formation: Literal["line", "triangle", "diamond", "v"] = "triangle"
    pattern: Literal["line_shift", "square", "hold", "up_forward", "launch_up", "captured_path", "crazy_pinwheel"] = "up_forward"
    final_pose: Vec3 = (0.50, 0.0, 0.55)
    slot_spacing_m: float = 0.49
    min_separation_m: float = DEFAULT_MIN_SEPARATION_M
    enable_collision_avoidance: bool = True
    no_fly_zone_paths: tuple[str, ...] = ()
    captured_path: str | None = None
    yaw_rad: float = 0.0
    hover_z: float = 0.55
    takeoff_s: float = 2.5
    move_s: float = 4.0
    pattern_s: float = 3.0
    hold_s: float = 3.0
    landing_settle_s: float = 0.25
    land_s: float = 3.0
    dry_run: bool = True
    arm: bool = False
    allowed_uris: tuple[str, ...] = ()
    denied_uris: tuple[str, ...] = ()
    health_timeout_s: float = 40.0
    max_concurrent_checks: int = 1
    crazy_pinwheel_compact: bool = False
    crazy_pinwheel_outer_delta_m: float = DEFAULT_CRAZY_PINWHEEL_OUTER_DELTA_M
    callback_url: str | None = None
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        if not MIN_EXECUTION_SWARM_SIZE <= self.swarm_size <= MAX_SWARM_SIZE:
            raise ValueError(f"swarm_size must be {MIN_EXECUTION_SWARM_SIZE}..{MAX_SWARM_SIZE}")
        if self.pattern == "crazy_pinwheel" and self.swarm_size != CRAZY_PINWHEEL_SWARM_SIZE:
            raise ValueError(f"crazy_pinwheel requires swarm_size={CRAZY_PINWHEEL_SWARM_SIZE}")
        if self.pattern == "crazy_pinwheel" and self.crazy_pinwheel_outer_delta_m <= 0:
            raise ValueError("crazy_pinwheel_outer_delta_m must be positive")
        if self.slot_spacing_m <= 0:
            raise ValueError("slot_spacing_m must be positive")
        if self.min_separation_m <= 0:
            raise ValueError("min_separation_m must be positive")
        if self.slot_spacing_m < self.min_separation_m:
            raise ValueError("slot_spacing_m must be >= min_separation_m")
        if self.hover_z <= 0:
            raise ValueError("hover_z must be positive")
        if self.pattern == "captured_path" and not self.captured_path:
            raise ValueError("captured_path is required for captured_path pattern")
        if self.takeoff_s <= 0 or self.move_s <= 0 or self.land_s <= 0:
            raise ValueError("flight durations must be positive")
        if self.landing_settle_s < 0:
            raise ValueError("landing_settle_s must be >= 0")
        if self.health_timeout_s <= 0:
            raise ValueError("health_timeout_s must be positive")
        if self.max_concurrent_checks < 1:
            raise ValueError("max_concurrent_checks must be >= 1")
