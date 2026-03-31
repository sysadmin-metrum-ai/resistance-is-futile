"""Mission-facing camera and streaming service for Crazyflie AI-deck feeds."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from src.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class DroneFeedConfig:
    """Configuration for one drone's AI-deck camera endpoint."""

    drone_id: str
    backend: str
    wifi_host: Optional[str] = None
    snapshot_url: Optional[str] = None
    stream_url: Optional[str] = None
    enabled: bool = True
    notes: str = ""


@dataclass
class StreamSession:
    """Runtime state for an active or fallback camera session."""

    session_id: str
    mission_id: str
    drone_id: str
    backend: str
    status: str
    started_at: str
    fallback_used: bool
    stream_url: Optional[str] = None
    notes: str = ""


@dataclass
class CaptureResult:
    """Result of a single mission capture."""

    image_id: str
    filepath: str
    mission_id: str
    drone_id: Optional[str]
    backend: str
    fallback_used: bool
    session_id: Optional[str]
    captured_at: str


class CameraBackend:
    """Interface for snapshot and stream-capable camera backends."""

    backend_name = "base"

    async def start_session(self, config: DroneFeedConfig, mission_id: str, settings: Settings) -> StreamSession:
        raise NotImplementedError

    async def stop_session(self, session: StreamSession) -> None:
        raise NotImplementedError

    async def capture_frame(self, config: DroneFeedConfig, session: Optional[StreamSession], settings: Settings) -> Optional[bytes]:
        raise NotImplementedError


class PlaceholderBackend(CameraBackend):
    """Predictable fallback backend used when hardware streaming is unavailable."""

    backend_name = "placeholder"

    async def start_session(self, config: DroneFeedConfig, mission_id: str, settings: Settings) -> StreamSession:
        session_id = str(uuid.uuid4())
        return StreamSession(
            session_id=session_id,
            mission_id=mission_id,
            drone_id=config.drone_id,
            backend=self.backend_name,
            status="fallback",
            started_at=_utc_now(),
            fallback_used=True,
            stream_url=f"{settings.camera_placeholder_stream_base}/{config.drone_id}/{session_id}",
            notes="Placeholder stream session; no live AI-deck transport connected.",
        )

    async def stop_session(self, session: StreamSession) -> None:
        return None

    async def capture_frame(
        self, config: DroneFeedConfig, session: Optional[StreamSession], settings: Settings
    ) -> Optional[bytes]:
        return None


class AIDeckWiFiBackend(CameraBackend):
    """HTTP-friendly AI-deck WiFi backend.

    This backend is shaped for production but intentionally conservative:
    - if a snapshot URL is configured, it will fetch a frame over HTTP
    - if only a stream URL is configured, it exposes session metadata but does not
      pretend to proxy live video without validated transport handling
    """

    backend_name = "aideck-wifi"

    async def start_session(self, config: DroneFeedConfig, mission_id: str, settings: Settings) -> StreamSession:
        session_id = str(uuid.uuid4())
        fallback = not bool(config.stream_url or config.snapshot_url)
        return StreamSession(
            session_id=session_id,
            mission_id=mission_id,
            drone_id=config.drone_id,
            backend=self.backend_name,
            status="active" if not fallback else "fallback",
            started_at=_utc_now(),
            fallback_used=fallback,
            stream_url=config.stream_url,
            notes=(
                "AI-deck WiFi session active."
                if not fallback
                else "No AI-deck WiFi endpoints configured; using fallback behavior."
            ),
        )

    async def stop_session(self, session: StreamSession) -> None:
        return None

    async def capture_frame(
        self, config: DroneFeedConfig, session: Optional[StreamSession], settings: Settings
    ) -> Optional[bytes]:
        if not config.snapshot_url:
            return None

        timeout = httpx.Timeout(
            connect=settings.camera_connect_timeout_seconds,
            read=settings.camera_read_timeout_seconds,
            write=settings.camera_read_timeout_seconds,
            pool=settings.camera_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(config.snapshot_url)
            response.raise_for_status()
            return response.content


class CameraCapture:
    """Capture and session manager for up to 3 concurrent drone video feeds."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._storage_path = Path(self.settings.image_storage_path)
        self._quality = self.settings.image_quality
        self._feeds: dict[str, DroneFeedConfig] = {}
        self._sessions: dict[str, StreamSession] = {}
        self._lock = asyncio.Lock()
        self._backends: dict[str, CameraBackend] = {
            "placeholder": PlaceholderBackend(),
            "aideck-wifi": AIDeckWiFiBackend(),
        }

    async def _ensure_storage_dir(self) -> None:
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def register_drone_feed(
        self,
        drone_id: str,
        backend: Optional[str] = None,
        wifi_host: Optional[str] = None,
        snapshot_url: Optional[str] = None,
        stream_url: Optional[str] = None,
        enabled: bool = True,
        notes: str = "",
    ) -> DroneFeedConfig:
        """Register or update the camera config for a drone feed."""

        chosen_backend = backend or self.settings.camera_backend
        config = DroneFeedConfig(
            drone_id=str(drone_id),
            backend=chosen_backend,
            wifi_host=wifi_host,
            snapshot_url=snapshot_url,
            stream_url=stream_url,
            enabled=enabled,
            notes=notes,
        )
        self._feeds[config.drone_id] = config
        return config

    def get_drone_feed(self, drone_id: str) -> Optional[DroneFeedConfig]:
        return self._feeds.get(str(drone_id))

    def list_drone_feeds(self) -> list[DroneFeedConfig]:
        return sorted(self._feeds.values(), key=lambda item: item.drone_id)

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        return self._sessions.get(session_id)

    def get_drone_session(self, drone_id: str) -> Optional[StreamSession]:
        for session in self._sessions.values():
            if session.drone_id == str(drone_id):
                return session
        return None

    def list_sessions(self) -> list[StreamSession]:
        return sorted(self._sessions.values(), key=lambda item: item.started_at)

    async def start_stream_session(self, mission_id: str, drone_id: str) -> StreamSession:
        """Start or reuse a stream session for a drone."""

        async with self._lock:
            existing = self.get_drone_session(drone_id)
            if existing and existing.status in {"active", "fallback"}:
                return existing

            if len(self._sessions) >= self.settings.camera_max_concurrent_streams:
                raise RuntimeError(
                    f"max concurrent camera streams reached ({self.settings.camera_max_concurrent_streams})"
                )

            config = self._feeds.get(str(drone_id))
            if config is None:
                config = self.register_drone_feed(str(drone_id), backend=self.settings.camera_backend)
            if not config.enabled:
                raise RuntimeError(f"camera feed disabled for drone {drone_id}")

            backend = self._backends.get(config.backend, self._backends["placeholder"])
            session = await backend.start_session(config, mission_id, self.settings)
            self._sessions[session.session_id] = session
            return session

    async def stop_stream_session(self, session_id: str) -> bool:
        """Stop and remove a stream session."""

        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            backend = self._backends.get(session.backend, self._backends["placeholder"])
            await backend.stop_session(session)
            session.status = "stopped"
            self._sessions.pop(session_id, None)
            return True

    async def capture(
        self,
        mission_id: str,
        drone_id: Optional[str] = None,
        capture_interval: Optional[int] = None,
        session_id: Optional[str] = None,
        prefer_session: bool = True,
    ) -> Optional[CaptureResult]:
        """Capture a mission image from a live or fallback session."""

        await self._ensure_storage_dir()

        active_session = self._resolve_session(session_id=session_id, drone_id=drone_id)
        if drone_id and prefer_session and active_session is None:
            active_session = await self.start_stream_session(mission_id=mission_id, drone_id=str(drone_id))

        async with self._lock:
            config = self._resolve_feed_config(
                drone_id=str(drone_id) if drone_id else None,
                session=active_session,
            )
        backend = self._backends.get(
            config.backend if config else self.settings.camera_backend,
            self._backends["placeholder"],
        )

        image_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filepath = self._build_capture_path(
            mission_id=mission_id,
            drone_id=drone_id,
            timestamp=timestamp,
            image_id=image_id,
            capture_interval=capture_interval,
        )

        try:
            image_data = await backend.capture_frame(config, active_session, self.settings) if config else None
            fallback_used = active_session.fallback_used if active_session else backend.backend_name == "placeholder"

            if image_data is None:
                logger.warning(
                    "Camera capture returned no data for mission %s drone %s; creating placeholder artifact",
                    mission_id,
                    drone_id,
                )
                await self._create_placeholder_image(filepath)
                fallback_used = True
            else:
                with open(filepath, "wb") as handle:
                    handle.write(image_data)

            return CaptureResult(
                image_id=image_id,
                filepath=str(filepath),
                mission_id=mission_id,
                drone_id=str(drone_id) if drone_id is not None else None,
                backend=backend.backend_name,
                fallback_used=fallback_used,
                session_id=active_session.session_id if active_session else None,
                captured_at=_utc_now(),
            )
        except Exception as exc:
            logger.exception("Failed to capture image for mission %s: %s", mission_id, exc)
            return None

    def _resolve_feed_config(
        self, drone_id: Optional[str], session: Optional[StreamSession]
    ) -> Optional[DroneFeedConfig]:
        if session:
            return self._feeds.get(session.drone_id) or DroneFeedConfig(
                drone_id=session.drone_id,
                backend=session.backend,
            )
        if drone_id is None:
            return None
        return self._feeds.get(drone_id)

    def _resolve_session(
        self, session_id: Optional[str], drone_id: Optional[str]
    ) -> Optional[StreamSession]:
        if session_id:
            return self._sessions.get(session_id)
        if drone_id is None:
            return None
        return self.get_drone_session(str(drone_id))

    def _build_capture_path(
        self,
        mission_id: str,
        drone_id: Optional[str],
        timestamp: str,
        image_id: str,
        capture_interval: Optional[int],
    ) -> Path:
        parts = [mission_id]
        if drone_id:
            parts.append(str(drone_id))
        parts.extend([timestamp, image_id])
        if capture_interval is not None:
            parts.append(f"i{capture_interval}")
        return self._storage_path / ("_".join(parts) + ".jpg")

    async def _create_placeholder_image(self, filepath: Path) -> None:
        try:
            placeholder_data = (
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00"
                b"\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08"
                b"\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12"
                b"\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c"
                b"\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00"
                b"\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
                b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03"
                b"\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01"
                b"\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03"
                b"\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08"
                b"#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'"
                b"()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86"
                b"\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3"
                b"\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9"
                b"\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6"
                b"\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1"
                b"\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01"
                b"\x00\x00?\x00\xfb\xd5\xff\xd9"
            )
            with open(filepath, "wb") as handle:
                handle.write(placeholder_data)
        except Exception as exc:
            logger.error("Failed to create placeholder image %s: %s", filepath, exc)

    async def get_image(self, image_id: str) -> Optional[bytes]:
        for filepath in self._storage_path.glob(f"*{image_id}*"):
            if filepath.is_file():
                try:
                    with open(filepath, "rb") as handle:
                        return handle.read()
                except Exception as exc:
                    logger.error("Failed to read image %s: %s", image_id, exc)
                    return None
        return None

    async def delete_image(self, image_id: str) -> bool:
        for filepath in self._storage_path.glob(f"*{image_id}*"):
            if filepath.is_file():
                try:
                    filepath.unlink()
                    logger.info("Deleted image %s", image_id)
                    return True
                except Exception as exc:
                    logger.error("Failed to delete image %s: %s", image_id, exc)
                    return False
        return False

    async def list_mission_images(self, mission_id: str) -> list[str]:
        images = []
        for filepath in self._storage_path.glob(f"{mission_id}_*"):
            if filepath.is_file():
                images.append(str(filepath))
        return sorted(images)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_camera_capture: Optional[CameraCapture] = None


async def get_camera_capture() -> CameraCapture:
    global _camera_capture
    if _camera_capture is None:
        _camera_capture = CameraCapture()
    return _camera_capture
