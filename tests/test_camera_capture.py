from __future__ import annotations

from src.core.config import Settings
from src.services.camera_capture import CameraCapture


class FakeAiDeckStream:
    def __init__(self, host: str, *, port: int, timeout_s: float):
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.started = False

    def start(self) -> None:
        self.started = True

    def wait_for_frame(self, timeout_s: float) -> bytes:
        assert self.started is True
        assert timeout_s == self.timeout_s
        return b"\xff\xd8real-frame\xff\xd9"

    def stop(self) -> None:
        self.started = False


async def test_camera_capture_uses_aideck_stream_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr("src.services.camera_capture.AiDeckJpegStream", FakeAiDeckStream)
    settings = Settings(
        image_storage_path=str(tmp_path),
        aideck_camera_host="192.168.4.1",
        aideck_camera_port=5000,
        aideck_camera_timeout_s=1.5,
    )
    camera = CameraCapture(settings)

    filepath = await camera.capture("mission-1", drone_id="drone-a")

    assert filepath is not None
    assert filepath.endswith(".jpg")
    assert b"real-frame" in tmp_path.joinpath(filepath.split("/")[-1]).read_bytes()


async def test_camera_capture_falls_back_to_placeholder_without_aideck_host(tmp_path):
    settings = Settings(image_storage_path=str(tmp_path), aideck_camera_host="")
    camera = CameraCapture(settings)

    filepath = await camera.capture("mission-1")

    assert filepath is not None
    assert tmp_path.joinpath(filepath.split("/")[-1]).read_bytes().startswith(b"\xff\xd8")
