"""Flight controller service for Crazyflie drone control.

Provides high-level flight operations: connect, disconnect, kill switch,
health checks, mission execution, and abort.
"""

from typing import Optional
import asyncio
from dataclasses import dataclass

from src.core.config import Settings, get_settings


@dataclass
class HealthStatus:
    """Drone health status from pre-flight checks."""
    battery: int
    connection_quality: int
    is_healthy: bool
    message: str


@dataclass
class MissionResult:
    """Result of a mission execution."""
    success: bool
    message: str
    waypoints_completed: int
    duration_seconds: int


class FlightController:
    """Controls Crazyflie drones via cflib."""

    # Safety thresholds per research (SAFE-02)
    MIN_BATTERY_THRESHOLD = 20
    MIN_CONNECTION_QUALITY = 70

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize flight controller."""
        self.settings = settings or get_settings()
        self._swarm = None
        self._drones = {}  # uri -> Crazyflie instance

    async def connect_swarm(self, uris: list[str]) -> None:
        """
        Connect to multiple drones as a swarm.

        Args:
            uris: List of Crazyflie URIs (e.g., ['radio://0/80/1M/100M'])
        """
        try:
            from cflib.swarm import Swarm
            from cflib.crazyflie import Crazyflie
            from cflib.crtp import CachedCfFactory

            # Initialize drivers
            import cflib.crtp
            cflib.crtp.init_drivers()

            # Create swarm with cached factory for faster reconnect
            self._swarm = Swarm(uris, factory=CachedCfFactory())

            # Connect to all drones
            await asyncio.to_thread(self._swarm.fully_connected)

            # Store individual drone references
            for uri in uris:
                cf = Crazyflie(uri)
                self._drones[uri] = cf

        except ImportError:
            # cflib not available - raise error
            raise RuntimeError("cflib not installed - cannot connect to drones")

    async def disconnect(self) -> None:
        """Disconnect all drones in the swarm."""
        if self._swarm:
            await asyncio.to_thread(self._swarm.close)
            self._swarm = None
            self._drones = {}

    async def kill_switch(self) -> None:
        """
        Emergency land all drones immediately.

        Uses swarm.parallel_safe to send commands to all drones concurrently.
        """
        if not self._swarm:
            return

        def _emergency_land(cf):
            """Emergency land a single drone."""
            cf.commander.send_setpoint(0, 0, 0, 0)
            # The emergency land sequence: cut motors
            cf.param.set_value("motor.motor1", 0)
            cf.param.set_value("motor.motor2", 0)
            cf.param.set_value("motor.motor3", 0)
            cf.param.set_value("motor.motor4", 0)

        # Execute on all drones in parallel
        await asyncio.to_thread(self._swarm.parallel_safe, _emergency_land)

    async def health_check(self, uri: str) -> HealthStatus:
        """
        Check drone health status (battery, connection quality).

        Args:
            uri: Drone URI to check

        Returns:
            HealthStatus with battery, connection quality, and is_healthy flag
        """
        if uri not in self._drones:
            return HealthStatus(
                battery=0,
                connection_quality=0,
                is_healthy=False,
                message=f"Drone {uri} not connected"
            )

        cf = self._drones[uri]

        try:
            # Get battery from telemetry
            battery = getattr(cf, 'battery', 0) or 0

            # Get connection quality from link quality
            connection_quality = getattr(cf, 'link_quality', 0) or 0

            is_healthy = (
                battery >= self.MIN_BATTERY_THRESHOLD and
                connection_quality >= self.MIN_CONNECTION_QUALITY
            )

            if not is_healthy:
                message = f"Health check failed: battery={battery}%, connection={connection_quality}%"
            else:
                message = "Health check passed"

            return HealthStatus(
                battery=battery,
                connection_quality=connection_quality,
                is_healthy=is_healthy,
                message=message
            )

        except Exception as e:
            return HealthStatus(
                battery=0,
                connection_quality=0,
                is_healthy=False,
                message=f"Health check error: {str(e)}"
            )

    async def execute_mission(
        self,
        drone_uri: str,
        waypoints: list,
        duration_seconds: int
    ) -> MissionResult:
        """
        Execute a mission with waypoints on a specific drone.

        Args:
            drone_uri: URI of the drone to command
            waypoints: List of waypoint coordinates [(x, y, z), ...]
            duration_seconds: Expected mission duration

        Returns:
            MissionResult with success status and details
        """
        if drone_uri not in self._drones:
            return MissionResult(
                success=False,
                message=f"Drone {drone_uri} not connected",
                waypoints_completed=0,
                duration_seconds=duration_seconds
            )

        cf = self._drones[drone_uri]

        try:
            # Pre-flight health check
            health = await self.health_check(drone_uri)
            if not health.is_healthy:
                return MissionResult(
                    success=False,
                    message=f"Pre-flight check failed: {health.message}",
                    waypoints_completed=0,
                    duration_seconds=duration_seconds
                )

            # Execute waypoint sequence
            waypoints_completed = 0

            for waypoint in waypoints:
                x, y, z = waypoint
                await self._fly_to_position(cf, x, y, z)
                waypoints_completed += 1

            return MissionResult(
                success=True,
                message="Mission completed successfully",
                waypoints_completed=waypoints_completed,
                duration_seconds=duration_seconds
            )

        except Exception as e:
            return MissionResult(
                success=False,
                message=f"Mission error: {str(e)}",
                waypoints_completed=waypoints_completed,
                duration_seconds=duration_seconds
            )

    async def _fly_to_position(self, cf, x: float, y: float, z: float) -> None:
        """
        Fly to a specific position using high-level commander.

        Args:
            cf: Crazyflie instance
            x, y, z: Target coordinates in meters
        """
        # Use the high-level commander for position hold
        from cflib.positioning import PositionHolder

        # Note: This is a simplified implementation
        # In practice, you'd use the MotionCommander or PositionCommander
        # from cflib's high-level commander

        # Simple implementation: send position setpoints
        for _ in range(50):  # ~5 seconds per waypoint at 10Hz
            cf.commander.send_position_setpoint(x, y, z, 0)
            await asyncio.sleep(0.1)

    async def abort_mission(self, drone_uri: str) -> None:
        """
        Abort current mission: return to home and land.

        Args:
            drone_uri: URI of the drone to abort
        """
        if drone_uri not in self._drones:
            return

        cf = self._drones[drone_uri]

        # Return to origin (0, 0, 0)
        await self._fly_to_position(cf, 0, 0, 0)

        # Land by descending slowly
        for z in range(10, 0, -1):
            cf.commander.send_position_setpoint(0, 0, z / 10.0, 0)
            await asyncio.sleep(0.5)

        # Cut motors
        cf.commander.send_setpoint(0, 0, 0, 0)


async def get_flight_controller() -> FlightController:
    """Dependency for FastAPI to get flight controller instance."""
    return FlightController()
