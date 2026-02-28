"""Mission worker service for processing queued missions.

Background worker that dequeues missions, acquires drones, executes them,
and handles the complete mission lifecycle.
"""

import asyncio
import logging
from typing import Optional

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient
from src.services.camera_capture import CameraCapture, get_camera_capture
from src.services.drone_manager import DroneManager, DroneState
from src.services.event_broadcaster import get_broadcaster
from src.services.flight_controller import FlightController
from src.services.mission_queue import MissionQueue


logger = logging.getLogger(__name__)


class MissionWorker:
    """
    Background worker that processes missions from the queue.

    Implements FIFO processing with per-drone locking for sequential execution.
    """

    # Mission statuses
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    def __init__(
        self,
        settings: Optional[Settings] = None,
        drone_manager: Optional[DroneManager] = None,
        flight_controller: Optional[FlightController] = None,
        mission_queue: Optional[MissionQueue] = None,
        camera_capture: Optional[CameraCapture] = None,
    ):
        """Initialize with optional dependencies for testing."""
        self.settings = settings or get_settings()
        self.drone_manager = drone_manager or DroneManager(self.settings)
        self.flight_controller = flight_controller or FlightController(self.settings)
        self.mission_queue = mission_queue or MissionQueue(self.settings)
        self.camera_capture = camera_capture
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def process_next_mission(self) -> bool:
        """
        Dequeue and execute the next mission.

        Process:
        1. Dequeue next mission from Redis (blocking)
        2. Acquire drone using MissionQueue.acquire_drone() - atomic
        3. Update mission status to "running" in PostgreSQL
        4. Run pre-flight health check
        5. If health check fails: mark failed, release drone, continue
        6. Execute mission using FlightController
        7. On completion: update status, store result, send callback
        8. Release drone back to idle

        Returns:
            True if a mission was processed, False if queue was empty
        """
        # Step 1: Dequeue next mission
        mission = await self.mission_queue.dequeue(timeout=5)
        if not mission:
            return False

        mission_id = mission.get("id")
        logger.info(f"Processing mission {mission_id}")

        # Step 2: Get available drone and acquire it
        drone = await self.drone_manager.get_available_drone()
        if not drone:
            # No drone available - re-queue and return
            await self.mission_queue.enqueue(mission)
            logger.warning(f"No available drone for mission {mission_id}")
            return False

        drone_id = str(drone["id"])

        # Atomic acquire - prevents race conditions
        acquired = await self.mission_queue.acquire_drone(
            drone_id, mission_id, ttl=mission.get("duration_seconds", 300) + 60
        )
        if not acquired:
            # Could not acquire - drone already taken, re-queue
            await self.mission_queue.enqueue(mission)
            return False

        try:
            # Step 3: Update mission status to running
            await self._update_mission_status(mission_id, self.STATUS_RUNNING, drone_id)

            # Step 4: Update drone state to busy
            await self.drone_manager.update_drone_state(
                drone["id"], DroneState.BUSY, drone.get("battery")
            )

            # Step 5: Pre-flight health check
            health = await self.flight_controller.health_check(drone["uri"])
            if not health.is_healthy:
                logger.error(f"Pre-flight check failed for drone {drone_id}: {health.message}")
                await self._update_mission_status(
                    mission_id,
                    self.STATUS_FAILED,
                    error=f"Pre-flight check failed: {health.message}"
                )
                await self.drone_manager.update_drone_state(
                    drone["id"], DroneState.ERROR, health.battery
                )
                await self.mission_queue.release_drone(drone_id)
                return True

            # Step 6: Execute mission
            waypoints = mission.get("waypoints", [])
            duration = mission.get("duration_seconds", 300)

            # Capture initial image at mission start (graceful failure - log and continue)
            await self._capture_image_at_interval(mission_id, drone_id, capture_interval=0)

            result = await self.flight_controller.execute_mission(
                drone["uri"], waypoints, duration
            )

            # Step 7: Update status based on result
            if result.success:
                await self._update_mission_status(
                    mission_id,
                    self.STATUS_COMPLETED,
                    result=result.__dict__
                )
                await self.drone_manager.update_drone_state(
                    drone["id"], DroneState.IDLE, health.battery
                )
            else:
                await self._update_mission_status(
                    mission_id,
                    self.STATUS_FAILED,
                    error=result.message
                )
                await self.drone_manager.update_drone_state(
                    drone["id"], DroneState.ERROR, health.battery
                )

            # Send callback if URL provided
            callback_url = mission.get("callback_url")
            if callback_url:
                await self._send_callback(callback_url, mission_id, result)

        except Exception as e:
            logger.exception(f"Error processing mission {mission_id}: {e}")
            await self._update_mission_status(mission_id, self.STATUS_FAILED, error=str(e))
            await self.drone_manager.update_drone_state(drone["id"], DroneState.ERROR)

        finally:
            # Step 8: Release drone
            await self.mission_queue.release_drone(drone_id)

        return True

    async def _update_mission_status(
        self,
        mission_id: str,
        status: str,
        drone_id: Optional[str] = None,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ) -> None:
        """Update mission status in PostgreSQL via PostgREST."""
        postgrest = PostgRESTClient(self.settings)

        update_data = {"status": status}
        if drone_id:
            update_data["drone_id"] = drone_id
        if result:
            update_data["result"] = result
        if error:
            update_data["result"] = {"error": error}

        try:
            await postgrest.patch(f"/missions?id=eq.{mission_id}", update_data)

            # Emit mission update event
            await self._emit_mission_event(mission_id, status, error)
        except Exception as e:
            logger.error(f"Failed to update mission {mission_id}: {e}")

    async def _emit_mission_event(
        self, mission_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """Emit a mission update event."""
        try:
            broadcaster = await get_broadcaster()
            event_data = {
                "type": status,
                "mission_id": mission_id,
            }
            if error:
                event_data["error"] = error
            await broadcaster.publish(
                broadcaster.CHANNEL_MISSION_UPDATES,
                event_data
            )
        except Exception:
            # Event emission is best-effort, don't fail the main operation
            pass

    async def _send_callback(self, callback_url: str, mission_id: str, result) -> None:
        """Send callback notification when mission completes."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    callback_url,
                    json={
                        "mission_id": mission_id,
                        "success": result.success,
                        "message": result.message,
                        "waypoints_completed": result.waypoints_completed,
                    },
                    timeout=10.0,
                )
        except Exception as e:
            logger.error(f"Failed to send callback for mission {mission_id}: {e}")

    async def _capture_image_at_interval(
        self,
        mission_id: str,
        drone_id: Optional[str] = None,
        capture_interval: Optional[int] = None,
    ) -> None:
        """
        Capture an image at mission start or intervals.

        Handles capture failures gracefully - logs and continues without
        blocking the mission.

        Args:
            mission_id: ID of the mission
            drone_id: ID of the drone
            capture_interval: Interval index (0 for start, 1+ for subsequent)
        """
        if self.camera_capture is None:
            try:
                self.camera_capture = await get_camera_capture()
            except Exception as e:
                logger.warning(f"Failed to initialize camera capture: {e}")
                return

        try:
            filepath = await self.camera_capture.capture(
                mission_id=mission_id,
                drone_id=drone_id,
                capture_interval=capture_interval,
            )
            if filepath:
                logger.info(f"Mission {mission_id}: Captured image at interval {capture_interval}")
            else:
                logger.warning(f"Mission {mission_id}: Image capture returned no filepath")
        except Exception as e:
            # Log and continue - capture failure should not block mission
            logger.warning(f"Mission {mission_id}: Image capture failed: {e}")

    async def run_continuously(self) -> None:
        """
        Run the mission processing loop in background.

        Continuously dequeues and processes missions.
        Handles exceptions gracefully - logs and continues.
        """
        self._running = True
        logger.info("Mission worker started")

        while self._running:
            try:
                await self.process_next_mission()
            except asyncio.CancelledError:
                # Worker cancelled - exit gracefully
                break
            except Exception as e:
                logger.exception(f"Error in mission worker loop: {e}")
                await asyncio.sleep(1)  # Brief pause before retry

        logger.info("Mission worker stopped")

    async def start(self) -> None:
        """Start the background worker."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self.run_continuously())

    async def stop(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


async def get_mission_worker() -> MissionWorker:
    """Dependency for FastAPI to get mission worker instance."""
    return MissionWorker()
