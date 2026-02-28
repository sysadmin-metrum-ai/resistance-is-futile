"""Drone fleet management service.

Manages drone discovery, registration, state tracking, and auto-assignment.
Uses PostgREST for persistence and Redis for real-time state.
"""

from typing import Optional
import redis.asyncio as redis

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient
from src.services.mission_queue import MissionQueue


# Drone states
class DroneState:
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class DroneManager:
    """Manages drone fleet operations: discovery, registration, and state."""

    # Battery and connection thresholds per CONTEXT.md and research
    MIN_BATTERY_THRESHOLD = 20
    MIN_CONNECTION_QUALITY = 70

    def __init__(
        self,
        settings: Optional[Settings] = None,
        postgrest_client: Optional[PostgRESTClient] = None,
        mission_queue: Optional[MissionQueue] = None,
    ):
        """Initialize with optional dependencies for testing."""
        self.settings = settings or get_settings()
        self.postgrest = postgrest_client or PostgRESTClient(self.settings)
        self.mission_queue = mission_queue or MissionQueue(self.settings)

    async def discover_drones(self) -> list[str]:
        """
        Scan for available Crazyflie drones using cflib.

        Returns:
            List of discovered drone URIs (e.g., ['radio://0/80/1M/100M'])
        """
        # Import cflib here to avoid import errors when not available
        try:
            import cflib.crtp

            # Initialize cflib drivers
            cflib.crtp.init_drivers()

            # Scan for available interfaces
            available = cflib.crtp.scan_interfaces()
            return [interface[0] for interface in available]
        except ImportError:
            # cflib not available, return empty list
            return []

    async def register_drone(self, uri: str, name: str) -> dict:
        """
        Register a new drone in the fleet.

        Args:
            uri: Crazyflie URI (e.g., 'radio://0/80/1M/100M')
            name: Human-readable name (e.g., 'drone-1')

        Returns:
            Created drone record from PostgREST
        """
        drone_data = {
            "uri": uri,
            "name": name,
            "state": DroneState.IDLE,
            "battery": 0,
            "connection_quality": 0,
            "enabled": True,
        }

        result = await self.postgrest.post("/drones", drone_data)
        return result

    async def unregister_drone(self, drone_id: int) -> None:
        """
        Remove a drone from the fleet.

        Args:
            drone_id: ID of the drone to remove
        """
        await self.postgrest.delete(f"/drones?id=eq.{drone_id}")

        # Also clear Redis state
        await self.mission_queue.update_drone_status(str(drone_id), DroneState.OFFLINE)

    async def get_available_drone(self) -> Optional[dict]:
        """
        Find an available drone for auto-assignment.

        Per CONTEXT.md: Available = connected + healthy battery + not busy + not disabled

        Returns:
            Drone record or None if no drones available
        """
        # Query for available drones: idle state, enabled, battery > threshold
        filters = (
            "state=eq.idle"
            "&enabled=eq.true"
            f"&battery=gt.{self.MIN_BATTERY_THRESHOLD}"
            "&connection_quality=gt.70"
            "&select=*"
            "&limit=1"
        )

        result = await self.postgrest.get_drones(filters=filters)

        if result and len(result) > 0:
            return result[0]
        return None

    async def get_drone(self, drone_id: int) -> dict:
        """
        Get a single drone by ID.

        Args:
            drone_id: Drone ID

        Returns:
            Drone record
        """
        filters = f"id=eq.{drone_id}&select=*"
        result = await self.postgrest.get_drones(filters=filters)
        if result and len(result) > 0:
            return result[0]
        raise ValueError(f"Drone {drone_id} not found")

    async def list_drones(self) -> list[dict]:
        """
        List all drones in the fleet.

        Returns:
            List of all drone records
        """
        result = await self.postgrest.get_drones("select=*")
        return result if result else []

    async def update_drone_state(
        self, drone_id: int, state: str, battery: Optional[int] = None
    ) -> None:
        """
        Update drone state in both PostgREST and Redis.

        Args:
            drone_id: Drone ID
            state: New state (idle, busy, offline, error)
            battery: Optional battery level (0-100)
        """
        # Update PostgreSQL via PostgREST
        update_data = {"state": state}
        if battery is not None:
            update_data["battery"] = battery

        await self.postgrest.patch(f"/drones?id=eq.{drone_id}", update_data)

        # Update Redis for real-time queries
        await self.mission_queue.update_drone_status(str(drone_id), state, battery)


async def get_drone_manager() -> DroneManager:
    """Dependency for FastAPI to get drone manager instance."""
    return DroneManager()
