import pytest

from src.core.config import Settings
from src.services.camera_capture import CameraCapture


@pytest.mark.asyncio
async def test_camera_capture_limits_concurrent_sessions(tmp_path):
    settings = Settings(
        image_storage_path=str(tmp_path),
        camera_backend="placeholder",
        camera_max_concurrent_streams=2,
    )
    camera = CameraCapture(settings)

    camera.register_drone_feed("drone-1")
    camera.register_drone_feed("drone-2")
    camera.register_drone_feed("drone-3")

    await camera.start_stream_session("mission-a", "drone-1")
    await camera.start_stream_session("mission-a", "drone-2")

    with pytest.raises(RuntimeError):
        await camera.start_stream_session("mission-a", "drone-3")


@pytest.mark.asyncio
async def test_camera_capture_creates_placeholder_artifact(tmp_path):
    settings = Settings(
        image_storage_path=str(tmp_path),
        camera_backend="placeholder",
    )
    camera = CameraCapture(settings)
    camera.register_drone_feed("drone-1")

    result = await camera.capture(mission_id="mission-a", drone_id="drone-1")

    assert result is not None
    assert result.fallback_used is True
    assert tmp_path.joinpath(result.filepath.split("/")[-1]).exists()


@pytest.mark.asyncio
async def test_camera_capture_reuses_existing_session(tmp_path):
    settings = Settings(
        image_storage_path=str(tmp_path),
        camera_backend="placeholder",
    )
    camera = CameraCapture(settings)
    camera.register_drone_feed("drone-1")

    session_a = await camera.start_stream_session("mission-a", "drone-1")
    session_b = await camera.start_stream_session("mission-a", "drone-1")

    assert session_a.session_id == session_b.session_id
    assert len(camera.list_sessions()) == 1
