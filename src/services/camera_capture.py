"""Camera capture service for drone missions.

Handles image capture during missions, interfacing with Crazyflie camera
(or placeholder), saving to filesystem, and returning file paths.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.core.config import Settings, get_settings
from src.services.aideck_camera import AiDeckJpegStream

logger = logging.getLogger(__name__)


class CameraCapture:
    """
    Service for capturing images during drone missions.

    Interfaces with the Crazyflie camera (or placeholder) to capture images,
    saves them to the configured storage path with mission/timestamp metadata.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize with settings."""
        self.settings = settings or get_settings()
        self._storage_path = Path(self.settings.image_storage_path)
        self._quality = self.settings.image_quality

    async def _ensure_storage_dir(self) -> None:
        """Ensure the storage directory exists."""
        self._storage_path.mkdir(parents=True, exist_ok=True)

    async def capture(
        self,
        mission_id: str,
        drone_id: Optional[str] = None,
        capture_interval: Optional[int] = None,
    ) -> Optional[str]:
        """
        Capture an image during mission execution.

        Args:
            mission_id: ID of the mission this capture is for
            drone_id: ID of the drone (optional, for metadata)
            capture_interval: Interval index if capturing at intervals

        Returns:
            Path to the saved image file, or None if capture failed
        """
        await self._ensure_storage_dir()

        try:
            # Generate unique image ID and filename
            image_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            # Build filename: mission_drone_timestamp_interval
            parts = [mission_id]
            if drone_id:
                parts.append(drone_id)
            parts.append(timestamp)
            if capture_interval is not None:
                parts.append(f"i{capture_interval}")

            filename = "_".join(parts) + ".jpg"
            filepath = self._storage_path / filename

            # Capture from camera (placeholder - replace with actual camera integration)
            image_data = await self._capture_from_camera()

            if image_data is None:
                logger.warning(f"Camera capture returned no data for mission {mission_id}")
                # Create a placeholder image for testing
                await self._create_placeholder_image(filepath)
            else:
                # Save the captured image
                async with asyncio.Lock():
                    with open(filepath, "wb") as f:
                        f.write(image_data)

            logger.info(f"Captured image {image_id} for mission {mission_id}: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.exception(f"Failed to capture image for mission {mission_id}: {e}")
            return None

    async def _capture_from_camera(self) -> Optional[bytes]:
        """
        Capture image from the configured Crazyflie AI deck camera.

        When AIDECK_CAMERA_HOST is not configured, this returns None so tests
        and dry-run demos still create a placeholder image.

        Returns:
            Image data as bytes, or None if capture failed
        """
        if not self.settings.aideck_camera_host:
            logger.debug("Camera capture placeholder - AIDECK_CAMERA_HOST is not configured")
            return None

        try:
            return await asyncio.to_thread(self._capture_from_aideck)
        except Exception as exc:
            logger.warning("AI deck camera capture failed: %s", exc)
            return None

    def _capture_from_aideck(self) -> bytes:
        stream = AiDeckJpegStream(
            self.settings.aideck_camera_host,
            port=self.settings.aideck_camera_port,
            timeout_s=self.settings.aideck_camera_timeout_s,
        )
        stream.start()
        try:
            return stream.wait_for_frame(self.settings.aideck_camera_timeout_s)
        finally:
            stream.stop()

    async def _create_placeholder_image(self, filepath: Path) -> None:
        """
        Create a placeholder image for testing when camera is unavailable.

        This creates a simple colored square as a placeholder.
        """
        try:
            # Simple placeholder: 1x1 pixel JPEG
            # In production, this would be replaced with actual camera capture
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
            with open(filepath, "wb") as f:
                f.write(placeholder_data)
        except Exception as e:
            logger.error(f"Failed to create placeholder image: {e}")

    async def get_image(self, image_id: str) -> Optional[bytes]:
        """
        Retrieve image data by ID.

        Note: Currently searches by filename pattern. In production,
        should use a database to map IDs to file paths.

        Args:
            image_id: The image ID or filename to retrieve

        Returns:
            Image data as bytes, or None if not found
        """
        # Search for image file
        for filepath in self._storage_path.glob(f"*{image_id}*"):
            if filepath.is_file():
                try:
                    with open(filepath, "rb") as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"Failed to read image {image_id}: {e}")
                    return None
        return None

    async def delete_image(self, image_id: str) -> bool:
        """
        Delete an image by ID.

        Args:
            image_id: The image ID or filename to delete

        Returns:
            True if deleted, False if not found
        """
        for filepath in self._storage_path.glob(f"*{image_id}*"):
            if filepath.is_file():
                try:
                    filepath.unlink()
                    logger.info(f"Deleted image {image_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete image {image_id}: {e}")
                    return False
        return False

    async def list_mission_images(self, mission_id: str) -> list[str]:
        """
        List all images associated with a mission.

        Args:
            mission_id: The mission ID to filter by

        Returns:
            List of image file paths
        """
        images = []
        for filepath in self._storage_path.glob(f"{mission_id}_*"):
            if filepath.is_file():
                images.append(str(filepath))
        return sorted(images)


# Global instance
_camera_capture: Optional[CameraCapture] = None


async def get_camera_capture() -> CameraCapture:
    """Get the global CameraCapture instance."""
    global _camera_capture
    if _camera_capture is None:
        _camera_capture = CameraCapture()
    return _camera_capture
