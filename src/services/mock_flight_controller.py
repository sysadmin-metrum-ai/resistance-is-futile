"""Mock flight controller for testing without real drones.

Provides simulated flight operations: connect, disconnect, kill switch,
health checks, mission execution, and abort.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from src.core.config import Settings, get_settings
from src.services.mission_models import Waypoint3D


@dataclass
class MockHealthStatus:
    """Mock drone health status."""

    battery: int
    connection_quality: int
    is_healthy: bool
    message: str


@dataclass
class MockMissionResult:
    """Mock result of a mission execution."""

    success: bool
    message: str
    waypoints_completed: int
    duration_seconds: int


def _coerce_waypoint(waypoint) -> Waypoint3D:
    if isinstance(waypoint, Waypoint3D):
        return waypoint
    if isinstance(waypoint, dict):
        return Waypoint3D(**waypoint)
    if isinstance(waypoint, (tuple, list)) and len(waypoint) >= 3:
        return Waypoint3D(x=waypoint[0], y=waypoint[1], z=waypoint[2])
    raise TypeError(f"unsupported waypoint type: {type(waypoint)!r}")


@dataclass
class MockDroneState:
    """Mock state for a simulated drone."""

    uri: str
    connected: bool = False
    state: str = "idle"  # idle, taking_off, flying, landing, error
    position: dict = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    battery: int = 85
    connection_quality: int = 100


class MockFlightController:
    """Simulates Crazyflie drone operations without hardware."""

    MIN_BATTERY_THRESHOLD = 20
    MIN_CONNECTION_QUALITY = 70

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize mock flight controller."""
        self.settings = settings or get_settings()
        self._drones: dict[str, MockDroneState] = {}

    async def connect_swarm(self, uris: list[str]) -> None:
        """Simulate connecting to a swarm of drones."""
        await asyncio.sleep(0.1)  # Simulate connection delay
        for uri in uris:
            self._drones[uri] = MockDroneState(
                uri=uri,
                connected=True,
                state="idle",
                battery=85,
                connection_quality=100,
            )

    async def disconnect(self) -> None:
        """Simulate disconnecting all drones."""
        await asyncio.sleep(0.05)
        for drone in self._drones.values():
            drone.connected = False
            drone.state = "idle"

    async def kill_switch(self) -> None:
        """Emergency land all drones (simulated)."""
        await asyncio.sleep(0.05)
        for drone in self._drones.values():
            drone.state = "idle"
            drone.position = {"x": 0, "y": 0, "z": 0}

    async def health_check(self, uri: str) -> MockHealthStatus:
        """Simulate health check - always returns healthy in mock mode."""
        await asyncio.sleep(0.02)

        if uri not in self._drones:
            return MockHealthStatus(
                battery=0,
                connection_quality=0,
                is_healthy=False,
                message=f"Drone {uri} not connected (mock)",
            )

        drone = self._drones[uri]

        is_healthy = (
            drone.battery >= self.MIN_BATTERY_THRESHOLD
            and drone.connection_quality >= self.MIN_CONNECTION_QUALITY
        )

        return MockHealthStatus(
            battery=drone.battery,
            connection_quality=drone.connection_quality,
            is_healthy=is_healthy,
            message="Mock health check passed"
            if is_healthy
            else "Mock health check failed",
        )

    async def execute_mission(
        self, drone_uri: str, waypoints: list, duration_seconds: int
    ) -> MockMissionResult:
        """Simulate mission execution with waypoints."""
        await asyncio.sleep(0.1)

        if drone_uri not in self._drones:
            return MockMissionResult(
                success=False,
                message=f"Drone {drone_uri} not connected (mock)",
                waypoints_completed=0,
                duration_seconds=duration_seconds,
            )

        drone = self._drones[drone_uri]

        # Health check
        health = await self.health_check(drone_uri)
        if not health.is_healthy:
            return MockMissionResult(
                success=False,
                message=f"Pre-flight check failed: {health.message}",
                waypoints_completed=0,
                duration_seconds=duration_seconds,
            )

        # Simulate executing waypoints
        waypoints_completed = 0
        for waypoint in waypoints:
            wp = _coerce_waypoint(waypoint)
            drone.position = {"x": wp.x, "y": wp.y, "z": wp.z}
            drone.state = "flying"
            await asyncio.sleep(0.05 + wp.hold_seconds)  # Simulate flight time
            waypoints_completed += 1

        # Return to idle
        drone.state = "idle"
        drone.position = {"x": 0, "y": 0, "z": 0}

        return MockMissionResult(
            success=True,
            message="Mock mission completed successfully",
            waypoints_completed=waypoints_completed,
            duration_seconds=duration_seconds,
        )

    async def takeoff(self, uri: str, height: float = 0.5) -> bool:
        """Simulate takeoff to specified height."""
        await asyncio.sleep(0.05)

        if uri not in self._drones:
            return False

        drone = self._drones[uri]
        drone.state = "taking_off"
        drone.position = {"x": 0, "y": 0, "z": height}
        drone.state = "flying"
        return True

    async def land(self, uri: str) -> bool:
        """Simulate landing."""
        await asyncio.sleep(0.05)

        if uri not in self._drones:
            return False

        drone = self._drones[uri]
        drone.state = "landing"
        drone.position = {"x": 0, "y": 0, "z": 0}
        drone.state = "idle"
        return True

    async def go_to(self, uri: str, x: float, y: float, z: float) -> bool:
        """Simulate go to position."""
        await asyncio.sleep(0.05)

        if uri not in self._drones:
            return False

        drone = self._drones[uri]
        drone.position = {"x": x, "y": y, "z": z}
        return True

    async def abort_mission(self, drone_uri: str) -> None:
        """Simulate abort - return to home and land."""
        await asyncio.sleep(0.05)

        if drone_uri not in self._drones:
            return

        drone = self._drones[drone_uri]
        drone.position = {"x": 0, "y": 0, "z": 0}
        drone.state = "idle"

    def get_state(self, uri: str) -> Optional[dict]:
        """Get current state of a drone."""
        if uri not in self._drones:
            return None

        drone = self._drones[uri]
        return {
            "uri": drone.uri,
            "state": drone.state,
            "position": drone.position,
            "battery": drone.battery,
            "connection_quality": drone.connection_quality,
        }


async def get_flight_controller():
    """Get flight controller - real or mock based on settings."""
    settings = get_settings()

    if settings.mock_mode:
        return MockFlightController(settings)
    else:
        from src.services.flight_controller import FlightController

        return FlightController(settings)
