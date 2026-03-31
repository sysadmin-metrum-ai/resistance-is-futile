"""Mission cancellation handler.

Provides functions to cancel pending or running missions,
and estimate queue wait times.
"""

from typing import Optional

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient
from src.services.flight_controller_factory import build_flight_controller
from src.services.mission_queue import MissionQueue


# Mission statuses
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

# Terminal statuses that cannot be cancelled
TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED}


async def cancel_mission(mission_id: str, settings: Optional[Settings] = None) -> bool:
    """
    Cancel a mission by ID.

    Args:
        mission_id: ID of the mission to cancel
        settings: Optional settings (uses global if not provided)

    Returns:
        True if mission was cancelled, False if already in terminal state
    """
    settings = settings or get_settings()
    postgrest = PostgRESTClient(settings)
    mission_queue = MissionQueue(settings)
    flight_controller = build_flight_controller(settings)

    try:
        # Get current mission status
        result = await postgrest.get(f"/missions?mission_id=eq.{mission_id}&select=*")
        if not result or len(result) == 0:
            return False

        mission = result[0]
        status = mission.get("status")

        # Check if already in terminal state
        if status in TERMINAL_STATUSES:
            return False

        if status == STATUS_PENDING:
            # Remove from Redis queue - O(1) using tracked ID
            await _remove_from_queue(mission_id, mission_queue)

            # Update status in PostgreSQL
            await postgrest.patch(
                f"/missions?mission_id=eq.{mission_id}",
                {"status": STATUS_CANCELLED}
            )
            return True

        elif status == STATUS_RUNNING:
            # Get drone URI
            drone_id = mission.get("drone_id")
            if not drone_id:
                return False

            # Get drone details
            drone_result = await postgrest.get(f"/drones?id=eq.{drone_id}&select=uri")
            if not drone_result or len(drone_result) == 0:
                return False

            drone_uri = drone_result[0].get("uri")

            # Abort mission on drone
            await flight_controller.abort_mission(drone_uri)

            # Update status in PostgreSQL
            await postgrest.patch(
                f"/missions?mission_id=eq.{mission_id}",
                {"status": STATUS_CANCELLED, "result": {"cancelled": True}}
            )

            # Release drone
            await mission_queue.release_drone(str(drone_id))

            return True

        # Any other status - cannot cancel
        return False

    except Exception:
        # Log error but don't expose internals
        return False


async def _remove_from_queue(mission_id: str, mission_queue: MissionQueue) -> None:
    """
    Remove a mission from the pending queue.

    Uses Redis LREM for O(n) removal - acceptable for mission queues.
    For high-scale, consider a separate pending set with O(1) removal.

    Args:
        mission_id: ID of mission to remove
        mission_queue: MissionQueue instance
    """
    client = await mission_queue._get_client()
    queue_key = mission_queue.PENDING_MISSIONS_KEY

    # Get all items and filter
    items = await client.lrange(queue_key, 0, -1)
    import json

    for item in items:
        mission = json.loads(item)
        if mission.get("mission_id") == mission_id or mission.get("id") == mission_id:
            # Remove this specific item
            await client.lrem(queue_key, 1, item)
            break


async def estimate_queue_wait(
    average_mission_duration: int = 300,
    settings: Optional[Settings] = None
) -> int:
    """
    Estimate wait time for a new mission.

    Args:
        average_mission_duration: Average mission duration in seconds (default 5 min)
        settings: Optional settings

    Returns:
        Estimated wait time in seconds
    """
    settings = settings or get_settings()
    postgrest = PostgRESTClient(settings)
    mission_queue = MissionQueue(settings)

    # Get count of pending missions
    try:
        result = await postgrest.get_missions(
            "select=id,status&status=eq.pending&select=count"
        )
        pending_count = len(result) if result else 0
    except Exception:
        pending_count = 0

    # Also check Redis queue
    try:
        client = await mission_queue._get_client()
        redis_count = await client.llen(mission_queue.PENDING_MISSIONS_KEY)
        pending_count = max(pending_count, redis_count)
    except Exception:
        pass

    # Estimate wait based on average duration
    # Assumes single worker processing FIFO
    wait_time = pending_count * average_mission_duration

    return wait_time


async def get_mission_status(
    mission_id: str,
    settings: Optional[Settings] = None
) -> Optional[dict]:
    """
    Get current mission status and details.

    Args:
        mission_id: ID of the mission
        settings: Optional settings

    Returns:
        Mission dict or None if not found
    """
    settings = settings or get_settings()
    postgrest = PostgRESTClient(settings)

    result = await postgrest.get(f"/missions?mission_id=eq.{mission_id}&select=*")
    if result and len(result) > 0:
        return result[0]
    return None
