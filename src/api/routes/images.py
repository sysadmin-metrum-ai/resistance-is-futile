"""Images API routes for camera capture and retrieval.

Provides endpoints for:
- POST /images/capture - trigger capture, returns image_id
- GET /images/{image_id} - download image file
- GET /images/mission/{mission_id} - list images for mission
- DELETE /images/{image_id} - remove image
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.core.config import get_settings
from src.services.camera_capture import CameraCapture, get_camera_capture


router = APIRouter()


# Response models
class CaptureResponse(BaseModel):
    """Response for image capture endpoint."""
    image_id: str
    filepath: str
    mission_id: str


class ImageListResponse(BaseModel):
    """Response for listing images."""
    mission_id: str
    images: list[str]
    count: int


class DeleteResponse(BaseModel):
    """Response for delete endpoint."""
    success: bool
    image_id: str


class ImageNotFoundError(BaseModel):
    """Error response for missing image."""
    detail: str


@router.post(
    "/capture",
    response_model=CaptureResponse,
    summary="Capture an image",
    description="Trigger a camera capture during mission execution",
)
async def capture_image(
    mission_id: str,
    drone_id: Optional[str] = None,
    capture_interval: Optional[int] = None,
):
    """
    Capture an image for a mission.

    Args:
        mission_id: ID of the mission
        drone_id: ID of the drone (optional)
        capture_interval: Interval index if capturing at intervals

    Returns:
        CaptureResponse with image_id and filepath
    """
    camera = await get_camera_capture()

    filepath = await camera.capture(
        mission_id=mission_id,
        drone_id=drone_id,
        capture_interval=capture_interval,
    )

    if filepath is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to capture image"
        )

    # Extract image_id from filepath (last part of path without extension)
    image_id = Path(filepath).stem

    return CaptureResponse(
        image_id=image_id,
        filepath=filepath,
        mission_id=mission_id,
    )


@router.get(
    "/{image_id}",
    summary="Download an image",
    description="Download an image file by ID",
)
async def get_image(image_id: str):
    """
    Retrieve an image by ID.

    Returns the image file directly with appropriate content type.
    """
    camera = await get_camera_capture()

    # Try to find the image
    filepath = None
    settings = get_settings()
    storage_path = Path(settings.image_storage_path)

    # Search for the image file
    for candidate in storage_path.glob(f"*{image_id}*"):
        if candidate.is_file():
            filepath = candidate
            break

    if filepath is None or not filepath.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Image {image_id} not found"
        )

    # Determine content type
    content_type = "image/jpeg"
    if filepath.suffix.lower() in [".png"]:
        content_type = "image/png"
    elif filepath.suffix.lower() in [".gif"]:
        content_type = "image/gif"

    # Read and return the file
    with open(filepath, "rb") as f:
        image_data = f.read()

    from fastapi.responses import Response
    return Response(
        content=image_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename={filepath.name}"
        }
    )


@router.get(
    "/mission/{mission_id}",
    response_model=ImageListResponse,
    summary="List mission images",
    description="List all images captured during a mission",
)
async def list_mission_images(mission_id: str):
    """
    List all images associated with a mission.

    Args:
        mission_id: The mission ID to filter by

    Returns:
        List of image file paths
    """
    camera = await get_camera_capture()
    images = await camera.list_mission_images(mission_id)

    return ImageListResponse(
        mission_id=mission_id,
        images=images,
        count=len(images),
    )


@router.delete(
    "/{image_id}",
    response_model=DeleteResponse,
    summary="Delete an image",
    description="Delete an image by ID",
)
async def delete_image(image_id: str):
    """
    Delete an image by ID.

    Args:
        image_id: The image ID to delete

    Returns:
        Success status
    """
    camera = await get_camera_capture()
    deleted = await camera.delete_image(image_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Image {image_id} not found"
        )

    return DeleteResponse(
        success=True,
        image_id=image_id,
    )
