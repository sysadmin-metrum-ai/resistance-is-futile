"""Safety API endpoints.

Provides REST API for safety operations: kill switch, health checks,
pre-flight validation, and mission abort.
"""

from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient
from src.services.drone_manager import DroneManager
from src.services.flight_controller import FlightController
from src.services.mission_queue import MissionQueue
from src.services.mission_cancellation import cancel_mission


router = APIRouter()


# Pydantic models
class KillSwitchResponse(BaseModel):
    """Response for kill switch activation."""

    status: str


class HealthCheckResponse(BaseModel):
    """Response for drone health check."""

    ready: bool
    battery: Optional[int] = None
    connection_quality: Optional[int] = None
    reason: Optional[str] = None


class BulkHealthCheckResponse(BaseModel):
    """Response for bulk health check."""

    results: List[HealthCheckResponse]


class PreFlightCheckResponse(BaseModel):
    """Response for pre-flight check."""

    ready: bool
    checks: dict


class MissionAbortResponse(BaseModel):
    """Response for mission abort."""

    mission_id: str
    status: str


# Dependencies
async def get_drone_manager() -> DroneManager:
    """Get drone manager instance."""
    return DroneManager()


async def get_flight_controller() -> FlightController:
    """Get flight controller instance."""
    return FlightController()


async def get_mission_queue() -> MissionQueue:
    """Get mission queue instance."""
    return MissionQueue()


async def get_postgrest() -> PostgRESTClient:
    """Get PostgREST client instance."""
    return PostgRESTClient()


def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key from header."""
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )


# API endpoints
@router.post("/kill-switch", response_model=KillSwitchResponse)
async def trigger_kill_switch(
    background_tasks: BackgroundTasks,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller: FlightController = Depends(get_flight_controller),
    mission_queue: MissionQueue = Depends(get_mission_queue),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Emergency kill switch - immediately land all drones.

    Triggers emergency landing on all connected drones and updates
    their state in Redis to "landed".
    """
    verify_api_key(x_api_key)

    # Trigger kill switch in background to not block response
    async def execute_kill_switch():
        try:
            # Execute actual kill switch on drones
            await flight_controller.kill_switch()
        except Exception:
            pass  # Best effort - continue even if drone command fails

        # Update all drone states in Redis to landed
        try:
            all_drones = await drone_manager.list_drones()
            for drone in all_drones:
                drone_id = str(drone.get("id"))
                await mission_queue.update_drone_status(drone_id, "landed")
                # Also update in PostgREST
                await drone_manager.update_drone_state(drone.get("id"), "landed")
        except Exception:
            pass

    background_tasks.add_task(execute_kill_switch)

    return KillSwitchResponse(status="kill_switch_triggered")


@router.get("/health-check/{drone_id}", response_model=HealthCheckResponse)
async def health_check_drone(
    drone_id: int,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller: FlightController = Depends(get_flight_controller),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Check health status of a specific drone.

    Returns readiness based on battery (>= 20%) and connection quality (>= 70%).
    """
    verify_api_key(x_api_key)

    # Get drone details
    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    # Check if drone is enabled
    if not drone.get("enabled", True):
        return HealthCheckResponse(
            ready=False,
            reason=f"Drone {drone_id} is disabled"
        )

    # Check if drone is available
    if drone.get("state") not in ["idle", "offline"]:
        return HealthCheckResponse(
            ready=False,
            reason=f"Drone {drone_id} is not available (state: {drone.get('state')})"
        )

    # Get drone URI for health check
    drone_uri = drone.get("uri")
    if not drone_uri:
        return HealthCheckResponse(
            ready=False,
            reason=f"Drone {drone_id} has no URI configured"
        )

    # Perform health check via flight controller
    try:
        health = await flight_controller.health_check(drone_uri)
        return HealthCheckResponse(
            ready=health.is_healthy,
            battery=health.battery,
            connection_quality=health.connection_quality,
            reason=health.message if not health.is_healthy else None
        )
    except Exception as e:
        return HealthCheckResponse(
            ready=False,
            reason=f"Health check failed: {str(e)}"
        )


@router.post("/health-check", response_model=BulkHealthCheckResponse)
async def health_check_all_drones(
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller: FlightController = Depends(get_flight_controller),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Run health check on all registered drones.

    Returns a list of health statuses for each drone.
    """
    verify_api_key(x_api_key)

    try:
        all_drones = await drone_manager.list_drones()
        results = []

        for drone in all_drones:
            drone_id = drone.get("id")
            drone_uri = drone.get("uri")

            if not drone_uri:
                results.append(HealthCheckResponse(
                    ready=False,
                    reason=f"Drone {drone_id} has no URI"
                ))
                continue

            # Check if drone is enabled
            if not drone.get("enabled", True):
                results.append(HealthCheckResponse(
                    ready=False,
                    reason=f"Drone {drone_id} is disabled"
                ))
                continue

            try:
                health = await flight_controller.health_check(drone_uri)
                results.append(HealthCheckResponse(
                    ready=health.is_healthy,
                    battery=health.battery,
                    connection_quality=health.connection_quality,
                    reason=health.message if not health.is_healthy else None
                ))
            except Exception as e:
                results.append(HealthCheckResponse(
                    ready=False,
                    reason=f"Error: {str(e)}"
                ))

        return BulkHealthCheckResponse(results=results)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/pre-flight/{drone_id}", response_model=PreFlightCheckResponse)
async def pre_flight_check(
    drone_id: int,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller: FlightController = Depends(get_flight_controller),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Run full pre-flight validation on a drone.

    Checks: battery, connection, state, enabled status.
    """
    verify_api_key(x_api_key)

    checks = {}

    # Get drone details
    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    # Check 1: Enabled status
    checks["enabled"] = drone.get("enabled", True)

    # Check 2: State is idle
    drone_state = drone.get("state", "offline")
    checks["state_idle"] = drone_state == "idle"
    checks["state"] = drone_state

    # Check 3: Battery threshold
    battery = drone.get("battery", 0)
    checks["battery_ok"] = battery >= DroneManager.MIN_BATTERY_THRESHOLD
    checks["battery"] = battery

    # Check 4: Connection quality (if we can connect)
    drone_uri = drone.get("uri")
    if drone_uri:
        try:
            health = await flight_controller.health_check(drone_uri)
            checks["connection_ok"] = health.connection_quality >= DroneManager.MIN_CONNECTION_QUALITY
            checks["connection_quality"] = health.connection_quality
        except Exception:
            checks["connection_ok"] = False
            checks["connection_quality"] = 0
    else:
        checks["connection_ok"] = False
        checks["connection_quality"] = 0

    # Determine overall readiness
    ready = all([
        checks["enabled"],
        checks["state_idle"],
        checks["battery_ok"],
        checks["connection_ok"]
    ])

    return PreFlightCheckResponse(ready=ready, checks=checks)


@router.post("/missions/{mission_id}/abort", response_model=MissionAbortResponse)
async def abort_mission(
    mission_id: str,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller: FlightController = Depends(get_flight_controller),
    mission_queue: MissionQueue = Depends(get_mission_queue),
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Abort a running mission.

    Stops the mission on the drone, returns drone to idle state.
    """
    verify_api_key(x_api_key)

    # Get mission details
    try:
        result = await postgrest.get(f"/missions?mission_id=eq.{mission_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found"
            )
        mission = result[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mission: {str(e)}"
        )

    # Check mission is running
    if mission.get("status") != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mission {mission_id} is not running (status: {mission.get('status')})"
        )

    # Get drone details
    drone_id = mission.get("drone_id")
    if not drone_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mission has no assigned drone"
        )

    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    # Abort mission on drone
    drone_uri = drone.get("uri")
    if drone_uri:
        try:
            await flight_controller.abort_mission(drone_uri)
        except Exception:
            pass  # Best effort

    # Update mission status
    try:
        await postgrest.patch(
            f"/missions?mission_id=eq.{mission_id}",
            {"status": "cancelled", "result": {"aborted": True}}
        )
    except Exception:
        pass

    # Release drone back to idle
    await drone_manager.update_drone_state(drone_id, "idle")
    await mission_queue.release_drone(str(drone_id))

    return MissionAbortResponse(mission_id=mission_id, status="cancelled")
