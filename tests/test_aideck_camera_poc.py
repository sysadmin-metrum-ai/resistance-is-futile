from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1] / "aideck_camera_poc"
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))

from camera_socket import AiDeckJpegStream  # noqa: E402
from camera_socket import pop_jpeg_frames  # noqa: E402


def load_demo_module():
    spec = importlib.util.spec_from_file_location("single_drone_demo_camera", POC_DIR / "single_drone_demo_camera.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pop_jpeg_frames_keeps_partial_frame() -> None:
    buffer = bytearray(b"noise\xff\xd8abc")

    assert pop_jpeg_frames(buffer) == []
    assert buffer == bytearray(b"\xff\xd8abc")

    buffer.extend(b"def\xff\xd9tail")
    assert pop_jpeg_frames(buffer) == [b"\xff\xd8abcdef\xff\xd9"]
    assert buffer == bytearray()


def test_parse_args_defaults_to_demo_apex_path() -> None:
    module = load_demo_module()

    args = module.parse_args([])

    assert args.uri == "radio://0/80/2M/E7E7E7E701"
    assert args.aideck_ip == "192.168.4.1"
    assert args.home == [-0.5, 0.0]
    assert args.role == "apex"
    assert args.captures == 3


def test_target_for_role_matches_pyramid_targets() -> None:
    module = load_demo_module()
    args = module.parse_args(["--role", "base-my"])

    assert module.target_for_role(args) == (0.5, -0.5, 0.5, 6.5)


def test_stream_saves_raw_frames_as_pgm(tmp_path) -> None:
    stream = AiDeckJpegStream("127.0.0.1")
    stream._handle_payload(bytes([0xBC]) + (2).to_bytes(2, "little") + (2).to_bytes(2, "little") + bytes([1, 0]) + (4).to_bytes(4, "little"))
    stream._handle_payload(b"\x00\x40\x80\xff")

    saved = stream.save_latest(tmp_path / "capture.jpg")

    assert saved.name == "capture.pgm"
    assert saved.read_bytes() == b"P5\n2 2\n255\n\x00\x40\x80\xff"
