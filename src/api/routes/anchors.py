"""Loco Positioning Anchor management API endpoints.

Provides REST API for UWB anchor operations: configuration, status monitoring,
position calibration, and fleet management.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Header, status
from pydantic import BaseModel, Field

from src.core.config import Settings, get_settings
from src.core.postgrest import PostgRESTClient, get_postgrest_client


router = APIRouter()


# Pydantic models
class AnchorCreateRequest(BaseModel):
    """Request body for anchor creation."""

    anchor_id: int = Field(
        ..., ge=0, le=7, description="Hardware anchor ID (0-7 for TWR mode)"
    )
    name: str = Field(..., description="Anchor name (e.g., 'anchor-northwest')")
    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")
    z: float = Field(..., description="Z coordinate in meters (NED: positive = down)")
    mode: str = Field("TWR", description="Positioning mode: TWR, TDoA2, TDoA3")
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    notes: Optional[str] = Field(None, description="Installation notes")


class AnchorUpdateRequest(BaseModel):
    """Request body for anchor update."""

    name: Optional[str] = Field(None, description="Anchor name")
    x: Optional[float] = Field(None, description="X coordinate in meters")
    y: Optional[float] = Field(None, description="Y coordinate in meters")
    z: Optional[float] = Field(None, description="Z coordinate in meters (NED: positive = down)")
    mode: Optional[str] = Field(None, description="Positioning mode: TWR, TDoA2, TDoA3")
    status: Optional[str] = Field(
        None, description="Status: online, offline, calibrating, error"
    )
    battery_level: Optional[int] = Field(
        None, ge=0, le=100, description="Battery level (0-100)"
    )
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    notes: Optional[str] = Field(None, description="Installation notes")
    enabled: Optional[bool] = Field(None, description="Enable/disable anchor")


class AnchorPositionUpdateRequest(BaseModel):
    """Request body for updating anchor position only."""

    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")
    z: float = Field(..., description="Z coordinate in meters (NED: positive = down)")


class AnchorResponse(BaseModel):
    """Anchor information response."""

    id: int
    anchor_id: int
    name: str
    x: float
    y: float
    z: float
    mode: str
    status: str
    last_seen: Optional[str]
    battery_level: Optional[int]
    firmware_version: Optional[str]
    notes: Optional[str]
    enabled: bool
    created_at: str
    updated_at: str


class AnchorListResponse(BaseModel):
    """List of anchors response."""

    anchors: List[AnchorResponse]
    total_count: int
    online_count: int
    offline_count: int


class AnchorSystemStatusResponse(BaseModel):
    """Overall anchor system status."""

    total_anchors: int
    online_anchors: int
    offline_anchors: int
    calibrating_anchors: int
    error_anchors: int
    positioning_mode: str
    system_ready: bool
    coverage_area: Optional[dict] = None  # min/max x,y,z


class BulkAnchorCreateRequest(BaseModel):
    """Request to create multiple anchors."""

    anchors: List[AnchorCreateRequest]


class BulkAnchorCreateResponse(BaseModel):
    """Response for bulk anchor creation."""

    successful: List[AnchorResponse]
    failed: List[dict]


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


# API endpoints
@router.get("", response_model=AnchorListResponse)
async def list_anchors(
    anchor_status: Optional[str] = None,
    mode: Optional[str] = None,
    enabled_only: bool = True,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    List all Loco Positioning anchors with optional filters.

    Returns anchor positions, status, and battery levels.
    """
    verify_api_key(x_api_key)

    try:
        # Build query
        query_parts = ["select=*&order=anchor_id.asc"]

        if enabled_only:
            query_parts.append("enabled=eq.true")

        if anchor_status:
            query_parts.append(f"status=eq.{anchor_status}")

        if mode:
            query_parts.append(f"mode=eq.{mode}")

        query = "&".join(query_parts)

        result = await postgrest.get(f"/anchors?{query}")
        anchors = result if result else []

        # Calculate counts
        online_count = sum(1 for a in anchors if a.get("status") == "online")
        offline_count = sum(1 for a in anchors if a.get("status") == "offline")

        return AnchorListResponse(
            anchors=anchors,
            total_count=len(anchors),
            online_count=online_count,
            offline_count=offline_count,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list anchors: {str(e)}",
        )


@router.get("/system-status", response_model=AnchorSystemStatusResponse)
async def get_system_status(
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Get overall Loco Positioning system status.

    Returns coverage area, anchor counts by status, and system readiness.
    """
    verify_api_key(x_api_key)

    try:
        anchors = await postgrest.get("/anchors?select=*")
        anchors = anchors if anchors else []

        if not anchors:
            return AnchorSystemStatusResponse(
                total_anchors=0,
                online_anchors=0,
                offline_anchors=0,
                calibrating_anchors=0,
                error_anchors=0,
                positioning_mode="unknown",
                system_ready=False,
            )

        # Calculate status counts
        online = sum(1 for a in anchors if a.get("status") == "online")
        offline = sum(1 for a in anchors if a.get("status") == "offline")
        calibrating = sum(1 for a in anchors if a.get("status") == "calibrating")
        error = sum(1 for a in anchors if a.get("status") == "error")

        # Determine positioning mode (use most common mode)
        modes = {}
        for a in anchors:
            mode = a.get("mode", "TWR")
            modes[mode] = modes.get(mode, 0) + 1
        positioning_mode = max(modes, key=modes.get) if modes else "TWR"

        # Calculate coverage area
        xs = [a["x"] for a in anchors]
        ys = [a["y"] for a in anchors]
        zs = [a["z"] for a in anchors]

        coverage_area = None
        if xs and ys and zs:
            coverage_area = {
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
                "z_min": min(zs),
                "z_max": max(zs),
            }

        # System is ready if we have at least 4 online anchors in TWR mode
        # or 6+ for TDoA modes
        min_anchors = 4 if positioning_mode == "TWR" else 6
        system_ready = online >= min_anchors

        return AnchorSystemStatusResponse(
            total_anchors=len(anchors),
            online_anchors=online,
            offline_anchors=offline,
            calibrating_anchors=calibrating,
            error_anchors=error,
            positioning_mode=positioning_mode,
            system_ready=system_ready,
            coverage_area=coverage_area,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}",
        )


@router.get("/{anchor_id}", response_model=AnchorResponse)
async def get_anchor(
    anchor_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Get details for a specific anchor."""
    verify_api_key(x_api_key)

    try:
        result = await postgrest.get(f"/anchors?anchor_id=eq.{anchor_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor {anchor_id} not found",
            )
        return AnchorResponse(**result[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get anchor: {str(e)}",
        )


@router.post("", response_model=AnchorResponse, status_code=status.HTTP_201_CREATED)
async def create_anchor(
    anchor_req: AnchorCreateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Register a new Loco Positioning anchor.

    Validates anchor_id is unique and mode is valid.
    """
    verify_api_key(x_api_key)

    # Validate mode
    valid_modes = ["TWR", "TDoA2", "TDoA3"]
    if anchor_req.mode not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
        )

    try:
        anchor_data = {
            "anchor_id": anchor_req.anchor_id,
            "name": anchor_req.name,
            "x": anchor_req.x,
            "y": anchor_req.y,
            "z": anchor_req.z,
            "mode": anchor_req.mode,
            "status": "offline",  # New anchors start offline
            "firmware_version": anchor_req.firmware_version,
            "notes": anchor_req.notes,
            "enabled": True,
        }

        result = await postgrest.post("/anchors", anchor_data)
        return AnchorResponse(**result)
    except Exception as e:
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Anchor with ID {anchor_req.anchor_id} already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create anchor: {str(e)}",
        )


@router.post(
    "/bulk",
    response_model=BulkAnchorCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_anchors_bulk(
    bulk_req: BulkAnchorCreateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Register multiple anchors at once.

    Useful for initial setup of the positioning system.
    """
    verify_api_key(x_api_key)

    valid_modes = ["TWR", "TDoA2", "TDoA3"]
    successful = []
    failed = []

    for anchor_req in bulk_req.anchors:
        # Validate mode
        if anchor_req.mode not in valid_modes:
            failed.append(
                {
                    "anchor_id": anchor_req.anchor_id,
                    "reason": f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
                }
            )
            continue

        try:
            anchor_data = {
                "anchor_id": anchor_req.anchor_id,
                "name": anchor_req.name,
                "x": anchor_req.x,
                "y": anchor_req.y,
                "z": anchor_req.z,
                "mode": anchor_req.mode,
                "status": "offline",
                "firmware_version": anchor_req.firmware_version,
                "notes": anchor_req.notes,
                "enabled": True,
            }

            result = await postgrest.post("/anchors", anchor_data)
            successful.append(AnchorResponse(**result))
        except Exception as e:
            failed.append({"anchor_id": anchor_req.anchor_id, "reason": str(e)})

    return BulkAnchorCreateResponse(successful=successful, failed=failed)


@router.patch("/{anchor_id}", response_model=AnchorResponse)
async def update_anchor(
    anchor_id: int,
    anchor_req: AnchorUpdateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Update anchor properties."""
    verify_api_key(x_api_key)

    # Build update data
    update_data = {}
    if anchor_req.name is not None:
        update_data["name"] = anchor_req.name
    if anchor_req.x is not None:
        update_data["x"] = anchor_req.x
    if anchor_req.y is not None:
        update_data["y"] = anchor_req.y
    if anchor_req.z is not None:
        update_data["z"] = anchor_req.z
    if anchor_req.mode is not None:
        valid_modes = ["TWR", "TDoA2", "TDoA3"]
        if anchor_req.mode not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
            )
        update_data["mode"] = anchor_req.mode
    if anchor_req.status is not None:
        valid_statuses = ["online", "offline", "calibrating", "error"]
        if anchor_req.status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        update_data["status"] = anchor_req.status
        if anchor_req.status == "online":
            update_data["last_seen"] = "now()"
    if anchor_req.battery_level is not None:
        update_data["battery_level"] = anchor_req.battery_level
    if anchor_req.firmware_version is not None:
        update_data["firmware_version"] = anchor_req.firmware_version
    if anchor_req.notes is not None:
        update_data["notes"] = anchor_req.notes
    if anchor_req.enabled is not None:
        update_data["enabled"] = anchor_req.enabled

    if not update_data:
        # Return current anchor if no updates
        result = await postgrest.get(f"/anchors?anchor_id=eq.{anchor_id}&select=*")
        if not result or len(result) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor {anchor_id} not found",
            )
        return AnchorResponse(**result[0])

    try:
        result = await postgrest.patch(
            f"/anchors?anchor_id=eq.{anchor_id}", update_data
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor {anchor_id} not found",
            )
        return AnchorResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update anchor: {str(e)}",
        )


@router.patch("/{anchor_id}/position", response_model=AnchorResponse)
async def update_anchor_position(
    anchor_id: int,
    position_req: AnchorPositionUpdateRequest,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Update only the position coordinates of an anchor.

    This is a specialized endpoint for recalibration.
    """
    verify_api_key(x_api_key)

    try:
        update_data = {"x": position_req.x, "y": position_req.y, "z": position_req.z}

        result = await postgrest.patch(
            f"/anchors?anchor_id=eq.{anchor_id}", update_data
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor {anchor_id} not found",
            )
        return AnchorResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update anchor position: {str(e)}",
        )


@router.post("/{anchor_id}/heartbeat")
async def anchor_heartbeat(
    anchor_id: int,
    battery_level: Optional[int] = None,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Update anchor heartbeat - marks anchor as online.

    Called by anchor monitoring system or manual check.
    """
    verify_api_key(x_api_key)

    try:
        update_data = {"status": "online", "last_seen": "now()"}
        if battery_level is not None:
            update_data["battery_level"] = battery_level

        result = await postgrest.patch(
            f"/anchors?anchor_id=eq.{anchor_id}", update_data
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Anchor {anchor_id} not found",
            )
        return {
            "anchor_id": anchor_id,
            "status": "online",
            "last_seen": result.get("last_seen"),
            "message": "Heartbeat received",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update heartbeat: {str(e)}",
        )


@router.delete("/{anchor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_anchor(
    anchor_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """Remove an anchor from the system."""
    verify_api_key(x_api_key)

    # Check if anchor exists
    result = await postgrest.get(f"/anchors?anchor_id=eq.{anchor_id}&select=anchor_id")
    if not result or len(result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anchor {anchor_id} not found",
        )

    try:
        await postgrest.delete(f"/anchors?anchor_id=eq.{anchor_id}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete anchor: {str(e)}",
        )


@router.get("/{anchor_id}/neighbors")
async def get_anchor_neighbors(
    anchor_id: int,
    postgrest: PostgRESTClient = Depends(get_postgrest),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Get neighboring anchors within range.

    Useful for understanding positioning coverage and debugging.
    """
    verify_api_key(x_api_key)

    # Get this anchor's position
    anchor_result = await postgrest.get(f"/anchors?anchor_id=eq.{anchor_id}&select=*")
    if not anchor_result or len(anchor_result) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anchor {anchor_id} not found",
        )

    anchor = anchor_result[0]

    # Get all other anchors
    all_anchors = await postgrest.get("/anchors?select=*")
    all_anchors = all_anchors if all_anchors else []

    # Calculate distances
    import math

    neighbors = []
    for other in all_anchors:
        if other["anchor_id"] == anchor_id:
            continue

        dx = other["x"] - anchor["x"]
        dy = other["y"] - anchor["y"]
        dz = other["z"] - anchor["z"]
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        neighbors.append(
            {
                "anchor_id": other["anchor_id"],
                "name": other["name"],
                "distance_meters": round(distance, 2),
                "status": other["status"],
            }
        )

    # Sort by distance
    neighbors.sort(key=lambda x: x["distance_meters"])

    return {
        "anchor_id": anchor_id,
        "position": {"x": anchor["x"], "y": anchor["y"], "z": anchor["z"]},
        "neighbors": neighbors,
    }
