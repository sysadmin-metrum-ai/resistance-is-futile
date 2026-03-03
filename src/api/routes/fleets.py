"""Fleet management API endpoints.

Provides REST API for fleet operations: creating, updating, deleting fleets,
managing drone assignments to fleets.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient, get_postgrest_client


router = APIRouter()


# Pydantic models
class FleetCreateRequest(BaseModel):
    """Request body for fleet creation."""

    name: str = Field(..., description="Fleet name (unique)")
    description: Optional[str] = Field(None, description="Fleet description")
    category: str = Field(
        "general",
        description="Fleet category: inventory, security, cable-monitoring, inspection, emergency, general",
    )
    color: Optional[str] = Field("#3b82f6", description="UI color for fleet")
    max_drones: Optional[int] = Field(10, description="Maximum drones allowed")


class FleetUpdateRequest(BaseModel):
    """Request body for fleet update."""

    name: Optional[str] = Field(None, description="Fleet name")
    description: Optional[str] = Field(None, description="Fleet description")
    category: Optional[str] = Field(None, description="Fleet category")
    color: Optional[str] = Field(None, description="UI color")
    max_drones: Optional[int] = Field(None, description="Maximum drones")
    enabled: Optional[bool] = Field(None, description="Enable/disable fleet")


class FleetResponse(BaseModel):
    """Fleet information response."""

    id: int
    name: str
    description: Optional[str]
    category: str
    color: str
    max_drones: int
    enabled: bool
    drone_count: Optional[int] = 0
    created_at: str
    updated_at: str


class FleetListResponse(BaseModel):
    """List of fleets response."""

    fleets: List[FleetResponse]


class DroneFleetAssignmentRequest(BaseModel):
    """Request to assign drone to fleet."""

    drone_id: int = Field(..., description="Drone ID to assign")
    notes: Optional[str] = Field(None, description="Assignment notes")


class DroneFleetAssignmentResponse(BaseModel):
    """Response for drone assignment."""

    success: bool
    fleet_id: int
    drone_id: int
    message: str


class BulkFleetAssignmentRequest(BaseModel):
    """Request to assign multiple drones to fleet."""

    drone_ids: List[int] = Field(..., description="List of drone IDs")
    notes: Optional[str] = Field(None, description="Assignment notes")


# Dependencies
def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """Verify API key from header."""
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def get_postgrest() -> PostgRESTClient:
    """Get PostgREST client instance."""
    return await get_postgrest_client()


# Helper functions
async def get_fleet_drone_count(postgrest: PostgRESTClient, fleet_id: int) -> int:
    """Get count of drones in a fleet."""
    try:
        result = await postgrest.get(f"/drones?fleet_id=eq.{fleet_id}&select=id")
        return len(result) if result else 0
    except Exception:
        return 0


# API endpoints
@router.get("", response_model=FleetListResponse)
async def list_fleets(
    category: Optional[str] = None,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    List all fleets with optional category filter.

    Returns all fleets with drone counts.
    """
    verify_api_key(x_api_key)

    try:
        # Build query
        query = "select=*&order=id.asc"
        if category:
            query += f"&category=eq.{category}"

        result = await postgrest.get(f"/fleets?{query}")
        fleets = result if result else []

        # Enrich with drone counts
        for fleet in fleets:
            fleet["drone_count"] = await get_fleet_drone_count(postgrest, fleet["id"])

        return FleetListResponse(fleets=fleets)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list fleets: {str(e)}",
        )


@router.get("/{fleet_id}", response_model=FleetResponse)
async def get_fleet(
    fleet_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Get details for a specific fleet including drone count."""
    verify_api_key(x_api_key)

    try:
        result = await postgrest.get(f"/fleets?id=eq.{fleet_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet {fleet_id} not found",
            )

        fleet = result[0]
        fleet["drone_count"] = await get_fleet_drone_count(postgrest, fleet_id)
        return FleetResponse(**fleet)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fleet: {str(e)}",
        )


@router.post("", response_model=FleetResponse, status_code=status.HTTP_201_CREATED)
async def create_fleet(
    fleet_req: FleetCreateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Create a new fleet.

    Validates category and creates the fleet with specified parameters.
    """
    verify_api_key(x_api_key)

    # Validate category
    valid_categories = [
        "inventory",
        "security",
        "cable-monitoring",
        "inspection",
        "emergency",
        "general",
    ]
    if fleet_req.category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}",
        )

    try:
        fleet_data = {
            "name": fleet_req.name,
            "description": fleet_req.description,
            "category": fleet_req.category,
            "color": fleet_req.color,
            "max_drones": fleet_req.max_drones,
            "enabled": True,
        }

        result = await postgrest.post("/fleets", fleet_data)
        result["drone_count"] = 0
        return FleetResponse(**result)
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Fleet with name '{fleet_req.name}' already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create fleet: {str(e)}",
        )


@router.patch("/{fleet_id}", response_model=FleetResponse)
async def update_fleet(
    fleet_id: int,
    fleet_req: FleetUpdateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Update fleet properties."""
    verify_api_key(x_api_key)

    # Build update data
    update_data = {}
    if fleet_req.name is not None:
        update_data["name"] = fleet_req.name
    if fleet_req.description is not None:
        update_data["description"] = fleet_req.description
    if fleet_req.category is not None:
        valid_categories = [
            "inventory",
            "security",
            "cable-monitoring",
            "inspection",
            "emergency",
            "general",
        ]
        if fleet_req.category not in valid_categories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}",
            )
        update_data["category"] = fleet_req.category
    if fleet_req.color is not None:
        update_data["color"] = fleet_req.color
    if fleet_req.max_drones is not None:
        update_data["max_drones"] = fleet_req.max_drones
    if fleet_req.enabled is not None:
        update_data["enabled"] = fleet_req.enabled

    if not update_data:
        # Return current fleet if no updates
        result = await postgrest.get(f"/fleets?id=eq.{fleet_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet {fleet_id} not found",
            )
        fleet = result[0]
        fleet["drone_count"] = await get_fleet_drone_count(postgrest, fleet_id)
        return FleetResponse(**fleet)

    try:
        result = await postgrest.patch(f"/fleets?id=eq.{fleet_id}", update_data)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fleet {fleet_id} not found",
            )

        result["drone_count"] = await get_fleet_drone_count(postgrest, fleet_id)
        return FleetResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update fleet: {str(e)}",
        )


@router.delete("/{fleet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fleet(
    fleet_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Delete a fleet.

    Note: Drones assigned to this fleet will have their fleet_id set to NULL.
    """
    verify_api_key(x_api_key)

    # Check if fleet exists
    result = await postgrest.get(f"/fleets?id=eq.{fleet_id}&select=id")
    if not result or len(result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet {fleet_id} not found"
        )

    try:
        # Unassign all drones from this fleet
        await postgrest.patch(f"/drones?fleet_id=eq.{fleet_id}", {"fleet_id": None})

        # Delete the fleet
        await postgrest.delete(f"/fleets?id=eq.{fleet_id}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete fleet: {str(e)}",
        )


@router.get("/{fleet_id}/drones")
async def get_fleet_drones(
    fleet_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Get all drones assigned to a fleet."""
    verify_api_key(x_api_key)

    # Check if fleet exists
    fleet_result = await postgrest.get(f"/fleets?id=eq.{fleet_id}&select=*")
    if not fleet_result or len(fleet_result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet {fleet_id} not found"
        )

    try:
        drones = await postgrest.get(f"/drones?fleet_id=eq.{fleet_id}&select=*")
        return {
            "fleet_id": fleet_id,
            "fleet_name": fleet_result[0]["name"],
            "drones": drones if drones else [],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fleet drones: {str(e)}",
        )


@router.post("/{fleet_id}/assign", response_model=DroneFleetAssignmentResponse)
async def assign_drone_to_fleet(
    fleet_id: int,
    assignment: DroneFleetAssignmentRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Assign a drone to a fleet.

    Checks fleet capacity and drone existence before assignment.
    """
    verify_api_key(x_api_key)

    # Check fleet exists and has capacity
    fleet_result = await postgrest.get(f"/fleets?id=eq.{fleet_id}&select=*")
    if not fleet_result or len(fleet_result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet {fleet_id} not found"
        )

    fleet = fleet_result[0]
    current_count = await get_fleet_drone_count(postgrest, fleet_id)

    if current_count >= fleet["max_drones"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fleet '{fleet['name']}' is at capacity ({fleet['max_drones']} drones)",
        )

    # Check drone exists
    drone_result = await postgrest.get(f"/drones?id=eq.{assignment.drone_id}&select=id")
    if not drone_result or len(drone_result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {assignment.drone_id} not found",
        )

    try:
        # Update drone's fleet_id
        await postgrest.patch(
            f"/drones?id=eq.{assignment.drone_id}", {"fleet_id": fleet_id}
        )

        # Record assignment in fleet_assignments table
        await postgrest.post(
            "/fleet_assignments",
            {
                "fleet_id": fleet_id,
                "drone_id": assignment.drone_id,
                "notes": assignment.notes,
            },
        )

        return DroneFleetAssignmentResponse(
            success=True,
            fleet_id=fleet_id,
            drone_id=assignment.drone_id,
            message=f"Drone {assignment.drone_id} assigned to fleet '{fleet['name']}'",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign drone: {str(e)}",
        )


@router.post("/{fleet_id}/assign-bulk")
async def bulk_assign_drones_to_fleet(
    fleet_id: int,
    assignment: BulkFleetAssignmentRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Assign multiple drones to a fleet at once.
    """
    verify_api_key(x_api_key)

    # Check fleet exists and has capacity
    fleet_result = await postgrest.get(f"/fleets?id=eq.{fleet_id}&select=*")
    if not fleet_result or len(fleet_result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Fleet {fleet_id} not found"
        )

    fleet = fleet_result[0]
    current_count = await get_fleet_drone_count(postgrest, fleet_id)
    available_slots = fleet["max_drones"] - current_count

    if len(assignment.drone_ids) > available_slots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fleet '{fleet['name']}' can only accept {available_slots} more drones (max: {fleet['max_drones']})",
        )

    successful = []
    failed = []

    for drone_id in assignment.drone_ids:
        try:
            # Check drone exists
            drone_result = await postgrest.get(f"/drones?id=eq.{drone_id}&select=id")
            if not drone_result or len(drone_result) == 0:
                failed.append({"drone_id": drone_id, "reason": "Drone not found"})
                continue

            # Update drone's fleet_id
            await postgrest.patch(f"/drones?id=eq.{drone_id}", {"fleet_id": fleet_id})

            # Record assignment
            await postgrest.post(
                "/fleet_assignments",
                {"fleet_id": fleet_id, "drone_id": drone_id, "notes": assignment.notes},
            )

            successful.append(drone_id)
        except Exception as e:
            failed.append({"drone_id": drone_id, "reason": str(e)})

    return {
        "fleet_id": fleet_id,
        "fleet_name": fleet["name"],
        "successful": successful,
        "failed": failed,
        "total_assigned": len(successful),
        "total_failed": len(failed),
    }


@router.post(
    "/{fleet_id}/unassign/{drone_id}", response_model=DroneFleetAssignmentResponse
)
async def unassign_drone_from_fleet(
    fleet_id: int,
    drone_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Remove a drone from a fleet."""
    verify_api_key(x_api_key)

    # Check drone is actually in this fleet
    drone_result = await postgrest.get(
        f"/drones?id=eq.{drone_id}&fleet_id=eq.{fleet_id}&select=*"
    )
    if not drone_result or len(drone_result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drone {drone_id} is not assigned to fleet {fleet_id}",
        )

    try:
        # Remove fleet_id from drone
        await postgrest.patch(f"/drones?id=eq.{drone_id}", {"fleet_id": None})

        # Remove from fleet_assignments
        await postgrest.delete(
            f"/fleet_assignments?fleet_id=eq.{fleet_id}&drone_id=eq.{drone_id}"
        )

        return DroneFleetAssignmentResponse(
            success=True,
            fleet_id=fleet_id,
            drone_id=drone_id,
            message=f"Drone {drone_id} unassigned from fleet",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unassign drone: {str(e)}",
        )
