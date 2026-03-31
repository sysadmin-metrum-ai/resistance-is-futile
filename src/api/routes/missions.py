"""Mission API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel
import uuid

from src.core.config import get_settings
from src.core.postgrest import PostgRESTClient
from src.services.drone_manager import DroneManager
from src.services.event_broadcaster import get_broadcaster
from src.services.flight_readiness import evaluate_drone_readiness
from src.services.mission_models import (
    MissionRequest,
    MissionType,
    PlannedDroneMission,
    ServerInspectionPlan,
    ServerInspectionRequest,
)
from src.services.mission_queue import MissionQueue
from src.services.swarm_planner import build_server_inspection_plan
from src.services.mission_cancellation import (
    cancel_mission,
    estimate_queue_wait,
)


router = APIRouter()


class MissionResponse(BaseModel):
    """Response for mission submission."""

    mission_id: str
    assigned_drone: Optional[int] = None
    status: str
    estimated_wait: Optional[int] = None


class ServerInspectionPlanResponse(BaseModel):
    """Response for deterministic server inspection planning."""

    plan: ServerInspectionPlan


class ServerInspectionLaunchResponse(BaseModel):
    """Response for launching a server inspection mission set."""

    mission_type: MissionType
    status: str
    plan: ServerInspectionPlan
    mission_ids: list[str]


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
        readiness = evaluate_drone_readiness(
            drone,
            duration_seconds=mission.duration_seconds,
            waypoints=mission.waypoints,
        )
        if not readiness.ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": f"Drone {assigned_drone_id} is not ready for mission launch",
                    "checks": readiness.checks,
                    "warnings": list(readiness.warnings),
                },
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
        "waypoints": [waypoint.model_dump() for waypoint in mission.waypoints],
        "duration_seconds": mission.duration_seconds,
        "status": "pending",
        "callback_url": mission.callback_url,
        "mission_type": MissionType.SINGLE.value,
    }

    try:
        await postgrest.post("/missions", mission_data)
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
        "waypoints": [waypoint.model_dump() for waypoint in mission.waypoints],
        "duration_seconds": mission.duration_seconds,
        "callback_url": mission.callback_url,
        "mission_type": MissionType.SINGLE.value,
    })

    # Emit mission created event
    try:
        broadcaster = await get_broadcaster()
        await broadcaster.publish(
            broadcaster.CHANNEL_MISSION_UPDATES,
            {
                "type": "created",
                "mission_id": mission_id,
                "drone_id": assigned_drone_id,
            }
        )
    except Exception:
        pass  # Event emission is best-effort

    # Update drone state to busy
    await drone_manager.update_drone_state(assigned_drone_id, "busy")

    return MissionResponse(
        mission_id=mission_id,
        assigned_drone=assigned_drone_id,
        status="pending"
    )


@router.post("/swarm-inspect-server/plan", response_model=ServerInspectionPlanResponse)
async def plan_server_inspection(
    request: ServerInspectionRequest,
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Plan a deterministic front-of-server inspection mission for 1-3 drones."""
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    available_drone_ids: list[int] = []
    for drone_id in request.drone_ids:
        try:
            drone = await drone_manager.get_drone(drone_id)
        except ValueError:
            continue
        readiness = evaluate_drone_readiness(drone)
        if readiness.ready:
            available_drone_ids.append(drone_id)

    try:
        plan = build_server_inspection_plan(request, available_drone_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ServerInspectionPlanResponse(plan=plan)


@router.post("/swarm-inspect-server", response_model=ServerInspectionLaunchResponse)
async def launch_server_inspection(
    request: ServerInspectionRequest,
    drone_manager: DroneManager = Depends(get_drone_manager),
    mission_queue: MissionQueue = Depends(get_mission_queue),
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Create deterministic per-drone missions for a front-of-server inspection."""
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    available_drone_ids: list[int] = []
    uri_by_drone_id: dict[int, str] = {}
    for drone_id in request.drone_ids:
        try:
            drone = await drone_manager.get_drone(drone_id)
        except ValueError:
            continue
        readiness = evaluate_drone_readiness(drone)
        if readiness.ready and drone.get("uri"):
            available_drone_ids.append(drone_id)
            uri_by_drone_id[drone_id] = drone["uri"]

    try:
        plan = build_server_inspection_plan(request, available_drone_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    mission_ids: list[str] = []
    swarm_id = str(uuid.uuid4())
    for drone_plan in plan.drone_missions:
        mission_id = str(uuid.uuid4())
        mission_payload = {
            "mission_id": mission_id,
            "swarm_id": swarm_id,
            "mission_type": MissionType.SWARM_INSPECT_SERVER.value,
            "drone_id": drone_plan.drone_id,
            "drone_uri": uri_by_drone_id[drone_plan.drone_id],
            "role": drone_plan.role,
            "waypoints": [waypoint.model_dump() for waypoint in drone_plan.waypoints],
            "duration_seconds": _estimate_duration_seconds(drone_plan),
            "status": "pending",
            "callback_url": request.callback_url,
        }
        try:
            await postgrest.post("/missions", mission_payload)
        except Exception:
            # PostgREST is best effort in current local-dev mode; queue remains source of truth.
            pass
        await mission_queue.enqueue(mission_payload)
        await drone_manager.update_drone_state(drone_plan.drone_id, "busy")
        mission_ids.append(mission_id)

    return ServerInspectionLaunchResponse(
        mission_type=MissionType.SWARM_INSPECT_SERVER,
        status="pending",
        plan=plan,
        mission_ids=mission_ids,
    )


@router.get("", response_model=list[MissionDetailResponse])
async def get_missions(
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """List all missions."""
    settings = get_settings()

    # Validate API key
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    try:
        # Get all missions ordered by creation (newest first)
        result = await postgrest.get("/missions?order=id.desc&select=*")
        return [MissionDetailResponse(**mission) for mission in result]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list missions: {str(e)}"
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
        # Emit mission cancelled event
        try:
            broadcaster = await get_broadcaster()
            await broadcaster.publish(
                broadcaster.CHANNEL_MISSION_UPDATES,
                {
                    "type": "cancelled",
                    "mission_id": mission_id,
                }
            )
        except Exception:
            pass  # Event emission is best-effort

        return CancelResponse(mission_id=mission_id, status="cancelled")
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission cannot be cancelled (already completed or cancelled)"
        )


def _estimate_duration_seconds(drone_plan: PlannedDroneMission) -> int:
    """Use waypoint holds plus a small transit budget to estimate duration."""
    hold_seconds = sum(waypoint.hold_seconds for waypoint in drone_plan.waypoints)
    transit_seconds = max(6, len(drone_plan.waypoints) * 3)
    return int(hold_seconds + transit_seconds)
