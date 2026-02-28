"""Mission API endpoints.

Provides REST API for mission submission, status queries, and cancellation.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Header, status
from pydantic import BaseModel, Field
import uuid

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient
from src.services.drone_manager import DroneManager
from src.services.mission_queue import MissionQueue
from src.services.mission_cancellation import (
    cancel_mission,
    estimate_queue_wait,
    get_mission_status,
)


router = APIRouter()


# Pydantic models
class MissionRequest(BaseModel):
    """Request body for mission submission."""

    waypoints: list[dict] = Field(
        ...,
        description="List of waypoint coordinates, e.g. [{'x': 1.0, 'y': 2.0, 'z': 1.5}]"
    )
    duration_seconds: int = Field(..., gt=0, description="Expected mission duration in seconds")
    target_drone_id: Optional[int] = Field(
        None, description="Specific drone ID to assign (None = auto-assign)"
    )
    callback_url: Optional[str] = Field(
        None, description="Webhook URL to call on mission completion"
    )


class MissionResponse(BaseModel):
    """Response for mission submission."""

    mission_id: str
    assigned_drone: Optional[int] = None
    status: str
    estimated_wait: Optional[int] = None


class MissionDetailResponse(BaseModel):
    """Detailed mission information."""

    id: int
    mission_id: str
    drone_id: Optional[int]
    waypoints: list[dict]
    duration_seconds: int
    status: str
    callback_url: Optional[str]
    result: Optional[dict] = None


class CancelResponse(BaseModel):
    """Response for mission cancellation."""

    mission_id: str
    status: str


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


# API endpoints
@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_mission(
    mission: MissionRequest,
    background_tasks: BackgroundTasks,
    drone_manager: DroneManager = Depends(get_drone_manager),
    mission_queue: MissionQueue = Depends(get_mission_queue),
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Submit a new mission for execution.

    - If target_drone_id specified: verifies drone is available (idle, enabled)
    - If no target: auto-assigns an available drone
    - If no drones available: returns 503 with estimated wait time
    """
    settings = get_settings()

    # Validate API key
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    # Determine drone assignment
    assigned_drone_id = mission.target_drone_id
    drone_uri = None

    if assigned_drone_id:
        # Validate specific drone is available
        try:
            drone = await drone_manager.get_drone(assigned_drone_id)
            if drone.get("state") != "idle":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Drone {assigned_drone_id} is not available (state: {drone.get('state')})"
                )
            if not drone.get("enabled", True):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Drone {assigned_drone_id} is disabled"
                )
            drone_uri = drone.get("uri")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Drone {assigned_drone_id} not found"
            )
    else:
        # Auto-assign available drone
        available_drone = await drone_manager.get_available_drone()
        if not available_drone:
            # No drones available - estimate wait time
            wait_time = await estimate_queue_wait()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "No drones available",
                    "estimated_wait_seconds": wait_time
                }
            )
        assigned_drone_id = available_drone.get("id")
        drone_uri = available_drone.get("uri")

    # Create mission record in database
    mission_id = str(uuid.uuid4())
    mission_data = {
        "mission_id": mission_id,
        "drone_id": assigned_drone_id,
        "waypoints": mission.waypoints,
        "duration_seconds": mission.duration_seconds,
        "status": "pending",
        "callback_url": mission.callback_url,
    }

    try:
        result = await postgrest.post("/missions", mission_data)
        db_mission_id = result.get("id")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create mission: {str(e)}"
        )

    # Enqueue mission in Redis
    await mission_queue.enqueue({
        "mission_id": mission_id,
        "drone_id": assigned_drone_id,
        "drone_uri": drone_uri,
        "waypoints": mission.waypoints,
        "duration_seconds": mission.duration_seconds,
        "callback_url": mission.callback_url,
    })

    # Update drone state to busy
    await drone_manager.update_drone_state(assigned_drone_id, "busy")

    return MissionResponse(
        mission_id=mission_id,
        assigned_drone=assigned_drone_id,
        status="pending"
    )


@router.get("/{mission_id}", response_model=MissionDetailResponse)
async def get_mission(
    mission_id: str,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Get mission details and status."""
    settings = get_settings()

    # Validate API key
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    try:
        result = await postgrest.get(f"/missions?mission_id=eq.{mission_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found"
            )
        mission = result[0]
        return MissionDetailResponse(**mission)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get mission: {str(e)}"
        )


@router.post("/{mission_id}/cancel", response_model=CancelResponse)
async def cancel_mission_endpoint(
    mission_id: str,
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Cancel a pending or running mission."""
    settings = get_settings()

    # Validate API key
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    # Check if mission exists first
    postgrest = PostgRESTClient()
    try:
        result = await postgrest.get(f"/missions?mission_id=eq.{mission_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mission {mission_id} not found"
            )
    except HTTPException:
        raise
    except Exception:
        pass

    # Attempt cancellation
    success = await cancel_mission(mission_id)
    if success:
        return CancelResponse(mission_id=mission_id, status="cancelled")
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission cannot be cancelled (already completed or cancelled)"
        )
