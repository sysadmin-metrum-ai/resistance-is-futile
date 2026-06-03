"""Compatibility wrapper for the packaged AI deck camera stream reader."""

from src.services.aideck_camera import AiDeckJpegStream
from src.services.aideck_camera import CPX_HEADER
from src.services.aideck_camera import IMG_HEADER
from src.services.aideck_camera import IMG_MAGIC
from src.services.aideck_camera import JPEG_ENCODING
from src.services.aideck_camera import JPEG_EOI
from src.services.aideck_camera import JPEG_SOI
from src.services.aideck_camera import RAW_ENCODING
from src.services.aideck_camera import pop_jpeg_frames
from src.services.aideck_camera import recv_exact
from src.services.aideck_camera import status

__all__ = [
    "AiDeckJpegStream",
    "CPX_HEADER",
    "IMG_HEADER",
    "IMG_MAGIC",
    "JPEG_ENCODING",
    "JPEG_EOI",
    "JPEG_SOI",
    "RAW_ENCODING",
    "pop_jpeg_frames",
    "recv_exact",
    "status",
]
