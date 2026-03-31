"""Image and stream API routes for mission-facing camera operations."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.services.camera_capture import CaptureResult, DroneFeedConfig, StreamSession, get_camera_capture


router = APIRouter()


class FeedRegistrationRequest(BaseModel):
    drone_id: str
    backend: Optional[str] = Field(default=None, description="placeholder or aideck-wifi")
    wifi_host: Optional[str] = None
    snapshot_url: Optional[str] = None
    stream_url: Optional[str] = None
    enabled: bool = True
    notes: str = ""


class FeedResponse(BaseModel):
    drone_id: str
    backend: str
    wifi_host: Optional[str] = None
    snapshot_url: Optional[str] = None
    stream_url: Optional[str] = None
    enabled: bool
    notes: str = ""


class StreamSessionRequest(BaseModel):
    mission_id: str
    drone_id: str


class StreamSessionResponse(BaseModel):
    session_id: str
    mission_id: str
    drone_id: str
    backend: str
    status: str
    started_at: str
    fallback_used: bool
    stream_url: Optional[str] = None
    notes: str = ""


class CaptureResponse(BaseModel):
    image_id: str
    filepath: str
    mission_id: str
    drone_id: Optional[str] = None
    backend: str
    fallback_used: bool
    session_id: Optional[str] = None
    captured_at: str


class ImageListResponse(BaseModel):
    mission_id: str
    images: list[str]
    count: int


class DeleteResponse(BaseModel):
    success: bool
    image_id: str


@router.post("/feeds/register", response_model=FeedResponse)
async def register_feed(request: FeedRegistrationRequest):
    camera = await get_camera_capture()
    config = camera.register_drone_feed(
        drone_id=request.drone_id,
        backend=request.backend,
        wifi_host=request.wifi_host,
        snapshot_url=request.snapshot_url,
        stream_url=request.stream_url,
        enabled=request.enabled,
        notes=request.notes,
    )
    return FeedResponse(**config.__dict__)


@router.get("/feeds", response_model=list[FeedResponse])
async def list_feeds():
    camera = await get_camera_capture()
    return [FeedResponse(**item.__dict__) for item in camera.list_drone_feeds()]


@router.post("/sessions/start", response_model=StreamSessionResponse)
async def start_stream_session(request: StreamSessionRequest):
    camera = await get_camera_capture()
    try:
        session = await camera.start_stream_session(mission_id=request.mission_id, drone_id=request.drone_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return StreamSessionResponse(**session.__dict__)


@router.post("/sessions/{session_id}/stop")
async def stop_stream_session(session_id: str):
    camera = await get_camera_capture()
    stopped = await camera.stop_stream_session(session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"stopped": True, "session_id": session_id}


@router.get("/sessions", response_model=list[StreamSessionResponse])
async def list_stream_sessions():
    camera = await get_camera_capture()
    return [StreamSessionResponse(**item.__dict__) for item in camera.list_sessions()]


@router.get("/streams/{drone_id}", response_model=StreamSessionResponse)
async def get_stream_info(drone_id: str):
    camera = await get_camera_capture()
    session = camera.get_drone_session(drone_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No active stream for drone {drone_id}")
    return StreamSessionResponse(**session.__dict__)


@router.post("/capture", response_model=CaptureResponse)
async def capture_image(
    mission_id: str,
    drone_id: Optional[str] = None,
    capture_interval: Optional[int] = None,
    session_id: Optional[str] = None,
):
    camera = await get_camera_capture()
    result = await camera.capture(
        mission_id=mission_id,
        drone_id=drone_id,
        capture_interval=capture_interval,
        session_id=session_id,
    )
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to capture image")
    return CaptureResponse(**result.__dict__)


@router.get("/mission/{mission_id}", response_model=ImageListResponse)
async def list_mission_images(mission_id: str):
    camera = await get_camera_capture()
    images = await camera.list_mission_images(mission_id)
    return ImageListResponse(mission_id=mission_id, images=images, count=len(images))


@router.get("/{image_id}")
async def get_image(image_id: str):
    settings = get_settings()
    storage_path = Path(settings.image_storage_path)
    filepath = None
    for candidate in storage_path.glob(f"*{image_id}*"):
        if candidate.is_file():
            filepath = candidate
            break

    if filepath is None or not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")

    content_type = "image/jpeg"
    if filepath.suffix.lower() == ".png":
        content_type = "image/png"
    elif filepath.suffix.lower() == ".gif":
        content_type = "image/gif"

    with open(filepath, "rb") as handle:
        image_data = handle.read()
    return Response(
        content=image_data,
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={filepath.name}"},
    )


@router.delete("/{image_id}", response_model=DeleteResponse)
async def delete_image(image_id: str):
    camera = await get_camera_capture()
    deleted = await camera.delete_image(image_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Image {image_id} not found")
    return DeleteResponse(success=True, image_id=image_id)
