"""Drone API endpoints.

Provides REST API for drone management: listing, querying, registering,
and unregistering drones.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field
from typing import List

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient
from src.services.drone_manager import DroneManager
from src.services.mission_queue import MissionQueue


router = APIRouter()


# Pydantic models
class DroneCreateRequest(BaseModel):
    """Request body for drone registration."""

    uri: str = Field(..., description="Crazyflie URI (e.g., 'radio://0/80/1M/100M')")
    name: str = Field(..., description="Human-readable name (e.g., 'drone-1')")


class DroneUpdateRequest(BaseModel):
    """Request body for drone update."""

    enabled: Optional[bool] = Field(None, description="Enable or disable drone")


class DroneResponse(BaseModel):
    """Drone information response."""

    id: int
    uri: str
    name: str
    state: str
    battery: Optional[int] = None
    connection_quality: Optional[int] = None
    enabled: bool


class DroneListResponse(BaseModel):
    """List of drones response."""

    drones: List[DroneResponse]


class DiscoverResponse(BaseModel):
    """Response for drone discovery."""

    uris: List[str]


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
            detail="Invalid or missing API key"
        )


# API endpoints
@router.get("", response_model=List[DroneResponse])
async def list_drones(
    postgrest: PostgRESTClient = Depends(get_postgrest),
    mission_queue: MissionQueue = Depends(get_mission_queue),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    List all drones in the fleet.

    Returns drones from PostgREST merged with real-time state from Redis.
    """
    verify_api_key(x_api_key)

    try:
        # Get all drones from PostgREST
        result = await postgrest.get_drones("select=*")
        drones = result if result else []

        # Merge with Redis real-time state
        enriched_drones = []
        for drone in drones:
            drone_id = str(drone.get("id"))
            try:
                redis_state = await mission_queue.get_drone_status(drone_id)
                drone["state"] = redis_state.get("state", drone.get("state"))
                drone["battery"] = redis_state.get("battery", drone.get("battery"))
            except Exception:
                pass  # Use PostgREST data if Redis fails
            enriched_drones.append(drone)

        return enriched_drones
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list drones: {str(e)}"
        )


@router.get("/{drone_id}", response_model=DroneResponse)
async def get_drone(
    drone_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    mission_queue: MissionQueue = Depends(get_mission_queue),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Get details for a specific drone."""
    verify_api_key(x_api_key)

    try:
        # Get drone from PostgREST
        result = await postgrest.get_drones(f"id=eq.{drone_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Drone {drone_id} not found"
            )
        drone = result[0]

        # Merge with Redis real-time state
        drone_id_str = str(drone_id)
        try:
            redis_state = await mission_queue.get_drone_status(drone_id_str)
            drone["state"] = redis_state.get("state", drone.get("state"))
            drone["battery"] = redis_state.get("battery", drone.get("battery"))
        except Exception:
            pass

        return drone
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drone: {str(e)}"
        )


@router.post("/discover", response_model=DiscoverResponse)
async def discover_drones(
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Discover available Crazyflie drones on the network.

    Scans for drones using cflib and returns their URIs.
    """
    verify_api_key(x_api_key)

    try:
        uris = await drone_manager.discover_drones()
        return DiscoverResponse(uris=uris)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover drones: {str(e)}"
        )


@router.post("", response_model=DroneResponse, status_code=status.HTTP_201_CREATED)
async def register_drone(
    drone_req: DroneCreateRequest,
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Register a new drone in the fleet.

    Adds the drone to PostgREST and initializes its state in Redis.
    """
    verify_api_key(x_api_key)

    try:
        drone = await drone_manager.register_drone(drone_req.uri, drone_req.name)
        return drone
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register drone: {str(e)}"
        )


@router.delete("/{drone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_drone(
    drone_id: int,
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Unregister a drone from the fleet."""
    verify_api_key(x_api_key)

    # Check if drone exists first
    try:
        await drone_manager.get_drone(drone_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    try:
        await drone_manager.unregister_drone(drone_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unregister drone: {str(e)}"
        )


@router.patch("/{drone_id}", response_model=DroneResponse)
async def update_drone(
    drone_id: int,
    drone_req: DroneUpdateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Update drone properties (e.g., enabled status)."""
    verify_api_key(x_api_key)

    # Check if drone exists
    result = await postgrest.get_drones(f"id=eq.{drone_id}&select=*")
    if not result or len(result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} not found"
        )

    # Build update data
    update_data = {}
    if drone_req.enabled is not None:
        update_data["enabled"] = drone_req.enabled

    if not update_data:
        return result[0]

    try:
        updated = await postgrest.patch(f"/drones?id=eq.{drone_id}", update_data)
        return updated
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update drone: {str(e)}"
        )
