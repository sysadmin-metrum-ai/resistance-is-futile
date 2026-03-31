"""Safety API endpoints.

Provides REST API for safety operations: kill switch, health checks,
pre-flight validation, and mission abort.
"""

from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Header, status
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.postgrest import PostgRESTClient
from src.services.drone_manager import DroneManager
from src.services.flight_controller_factory import get_flight_controller
from src.services.flight_readiness import DEFAULT_MAX_RADIUS_M, evaluate_drone_readiness
from src.services.mission_models import Waypoint3D
from src.services.mission_queue import MissionQueue


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


class MissionValidationRequest(BaseModel):
    """Request body for mission validation."""

    drone_id: int
    waypoints: list[Waypoint3D]
    duration_seconds: int


class MissionValidationResponse(BaseModel):
    """Response for mission validation."""

    valid: bool
    checks: dict
    warnings: list[str]


# Dependencies
async def get_drone_manager() -> DroneManager:
    """Get drone manager instance."""
    return DroneManager()


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
            detail="Invalid or missing API key",
        )


# API endpoints
@router.post("/kill-switch", response_model=KillSwitchResponse)
async def trigger_kill_switch(
    background_tasks: BackgroundTasks,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller=Depends(get_flight_controller),
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
    flight_controller=Depends(get_flight_controller),
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
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Drone {drone_id} not found"
        )

    live_health = None
    try:
        if drone.get("uri"):
            live_health = await flight_controller.health_check(drone["uri"])
    except Exception:
        live_health = None

    readiness = evaluate_drone_readiness(drone, live_health=live_health)
    return HealthCheckResponse(
        ready=readiness.ready,
        battery=readiness.checks.get("battery"),
        connection_quality=readiness.checks.get("connection_quality"),
        reason="; ".join(readiness.warnings) if readiness.warnings else None,
    )


@router.post("/health-check", response_model=BulkHealthCheckResponse)
async def health_check_all_drones(
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller=Depends(get_flight_controller),
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
            live_health = None
            try:
                if drone.get("uri"):
                    live_health = await flight_controller.health_check(drone["uri"])
            except Exception:
                live_health = None

            readiness = evaluate_drone_readiness(drone, live_health=live_health)
            results.append(
                HealthCheckResponse(
                    ready=readiness.ready,
                    battery=readiness.checks.get("battery"),
                    connection_quality=readiness.checks.get("connection_quality"),
                    reason="; ".join(readiness.warnings) if readiness.warnings else None,
                )
            )

        return BulkHealthCheckResponse(results=results)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}",
        )


@router.get("/pre-flight/{drone_id}", response_model=PreFlightCheckResponse)
async def pre_flight_check(
    drone_id: int,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller=Depends(get_flight_controller),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Run full pre-flight validation on a drone.

    Checks: battery, connection, state, enabled status.
    """
    verify_api_key(x_api_key)

    # Get drone details
    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Drone {drone_id} not found"
        )

    live_health = None
    if drone.get("uri"):
        try:
            live_health = await flight_controller.health_check(drone["uri"])
        except Exception:
            live_health = None

    readiness = evaluate_drone_readiness(drone, live_health=live_health)
    return PreFlightCheckResponse(ready=readiness.ready, checks=readiness.checks)


@router.post("/validate-mission", response_model=MissionValidationResponse)
async def validate_mission(
    request: MissionValidationRequest,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller=Depends(get_flight_controller),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Validate if a planned mission can be executed.

    Checks:
    1. Drone ready: drone exists, enabled, state is idle
    2. Battery sufficient: battery >= (duration_seconds / 30) + 20 (conservative estimate)
    3. Waypoints in range: all waypoints within max operational radius
    """
    verify_api_key(x_api_key)

    # Get drone details
    try:
        drone = await drone_manager.get_drone(request.drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {request.drone_id} not found",
        )

    live_health = None
    if drone.get("uri"):
        try:
            live_health = await flight_controller.health_check(drone["uri"])
        except Exception:
            live_health = None

    readiness = evaluate_drone_readiness(
        drone,
        duration_seconds=request.duration_seconds,
        waypoints=request.waypoints,
        live_health=live_health,
        max_radius_m=DEFAULT_MAX_RADIUS_M,
    )
    checks = dict(readiness.checks)
    checks["drone_ready"] = readiness.ready
    return MissionValidationResponse(
        valid=readiness.ready,
        checks=checks,
        warnings=list(readiness.warnings),
    )


@router.post("/missions/{mission_id}/abort", response_model=MissionAbortResponse)
async def abort_mission(
    mission_id: str,
    drone_manager: DroneManager = Depends(get_drone_manager),
    flight_controller=Depends(get_flight_controller),
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
                detail=f"Mission {mission_id} not found",
            )
        mission = result[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mission: {str(e)}",
        )

    # Check mission is running
    if mission.get("status") != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mission {mission_id} is not running (status: {mission.get('status')})",
        )

    # Get drone details
    drone_id = mission.get("drone_id")
    if not drone_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mission has no assigned drone",
        )

    try:
        drone = await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Drone {drone_id} not found"
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
            {"status": "cancelled", "result": {"aborted": True}},
        )
    except Exception:
        pass

    # Release drone back to idle
    await drone_manager.update_drone_state(drone_id, "idle")
    await mission_queue.release_drone(str(drone_id))

    return MissionAbortResponse(mission_id=mission_id, status="cancelled")
