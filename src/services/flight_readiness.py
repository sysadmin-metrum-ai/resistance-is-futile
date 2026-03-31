"""Shared drone readiness checks for API gating and operator workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from src.services.drone_manager import DroneManager
from src.services.mission_models import Waypoint3D


DEFAULT_MAX_RADIUS_M = 5.0


@dataclass(frozen=True)
class FlightReadinessResult:
    """Structured readiness result shared across API routes."""

    ready: bool
    checks: dict[str, Any]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def estimate_required_battery(duration_seconds: int) -> int:
    """Conservative battery estimate used for mission gating."""

    return int((duration_seconds / 30) + DroneManager.MIN_BATTERY_THRESHOLD)


def evaluate_drone_readiness(
    drone: dict[str, Any],
    *,
    duration_seconds: int | None = None,
    waypoints: Iterable[Waypoint3D] | None = None,
    live_health: Any | None = None,
    max_radius_m: float = DEFAULT_MAX_RADIUS_M,
) -> FlightReadinessResult:
    """Evaluate whether a drone is ready for health, preflight, or mission launch."""

    warnings: list[str] = []
    checks: dict[str, Any] = {}

    enabled = bool(drone.get("enabled", True))
    state = drone.get("state", "offline")
    uri = drone.get("uri")

    battery = int(drone.get("battery", 0) or 0)
    connection_quality = int(drone.get("connection_quality", 0) or 0)

    if live_health is not None:
        if getattr(live_health, "battery", 0):
            battery = int(live_health.battery)
        if getattr(live_health, "connection_quality", 0):
            connection_quality = int(live_health.connection_quality)
        checks["live_probe_ok"] = bool(getattr(live_health, "is_healthy", False))
        checks["live_probe_message"] = getattr(live_health, "message", "")
        if not checks["live_probe_ok"] and checks["live_probe_message"]:
            warnings.append(checks["live_probe_message"])

    checks["enabled"] = enabled
    checks["state"] = state
    checks["state_idle"] = state == "idle"
    checks["uri_configured"] = bool(uri)
    checks["battery"] = battery
    checks["connection_quality"] = connection_quality
    checks["battery_ok"] = battery >= DroneManager.MIN_BATTERY_THRESHOLD
    checks["connection_ok"] = connection_quality >= DroneManager.MIN_CONNECTION_QUALITY

    if not enabled:
        warnings.append("drone is disabled")
    if state != "idle":
        warnings.append(f"drone is not idle (state: {state})")
    if not uri:
        warnings.append("drone has no URI configured")
    if not checks["battery_ok"]:
        warnings.append(
            f"battery {battery}% is below minimum {DroneManager.MIN_BATTERY_THRESHOLD}%"
        )
    if not checks["connection_ok"]:
        warnings.append(
            "connection quality "
            f"{connection_quality}% is below minimum {DroneManager.MIN_CONNECTION_QUALITY}%"
        )

    if duration_seconds is not None:
        required_battery = estimate_required_battery(duration_seconds)
        checks["battery_required"] = required_battery
        checks["battery_sufficient"] = battery >= required_battery
        if not checks["battery_sufficient"]:
            warnings.append(
                f"battery {battery}% is below required {required_battery}% "
                f"for {duration_seconds}s mission"
            )

    if waypoints is not None:
        waypoint_list = list(waypoints)
        checks["waypoints_count"] = len(waypoint_list)
        waypoints_in_range = True
        for index, wp in enumerate(waypoint_list):
            distance = (wp.x**2 + wp.y**2 + wp.z**2) ** 0.5
            if distance > max_radius_m:
                waypoints_in_range = False
                warnings.append(
                    f"waypoint {index} at ({wp.x}, {wp.y}, {wp.z}) is {distance:.1f}m "
                    f"from origin (max: {max_radius_m:.1f}m)"
                )
        checks["waypoints_in_range"] = waypoints_in_range

    required_checks = [
        checks["enabled"],
        checks["state_idle"],
        checks["uri_configured"],
        checks["battery_ok"],
        checks["connection_ok"],
    ]
    if "battery_sufficient" in checks:
        required_checks.append(checks["battery_sufficient"])
    if "waypoints_in_range" in checks:
        required_checks.append(checks["waypoints_in_range"])

    return FlightReadinessResult(
        ready=all(required_checks),
        checks=checks,
        warnings=tuple(warnings),
    )
