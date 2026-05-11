from __future__ import annotations

import socket
import struct
import threading
import time
from pathlib import Path


CPX_HEADER = struct.Struct("<HBB")
IMG_HEADER = struct.Struct("<BHHBBI")
IMG_MAGIC = 0xBC
RAW_ENCODING = 0
JPEG_ENCODING = 1
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


def status(message: str) -> None:
    print(message, flush=True)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("AI deck socket closed")
        data.extend(chunk)
    return bytes(data)


def pop_jpeg_frames(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []

    while True:
        start = buffer.find(JPEG_SOI)
        if start < 0:
            buffer.clear()
            return frames

        if start > 0:
            del buffer[:start]

        end = buffer.find(JPEG_EOI, 2)
        if end < 0:
            return frames

        frame_end = end + len(JPEG_EOI)
        frames.append(bytes(buffer[:frame_end]))
        del buffer[:frame_end]


class AiDeckJpegStream:
    """Background reader for the AI deck WiFi image streamer."""

    def __init__(self, host: str, port: int = 5000, timeout_s: float = 5.0):
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self._buffer = bytearray()
        self._latest: bytes | None = None
        self._latest_suffix = ".jpg"
        self._latest_time = 0.0
        self._image_type: int | None = None
        self._image_size = 0
        self._image_width = 0
        self._image_height = 0
        self._image_buffer = bytearray()
        self._error: BaseException | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="aideck-jpeg-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def wait_for_frame(self, timeout_s: float) -> bytes:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            with self._lock:
                if self._latest is not None:
                    return self._latest
                error = self._error
            if error is not None:
                raise RuntimeError(f"AI deck stream failed: {error}") from error
            time.sleep(0.05)
        raise TimeoutError("Timed out waiting for AI deck image frame")

    def save_latest(self, output_path: Path, max_age_s: float = 2.0) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            frame = self._latest
            frame_age = time.time() - self._latest_time
            error = self._error
            suffix = self._latest_suffix

        if error is not None:
            raise RuntimeError(f"AI deck stream failed: {error}") from error
        if frame is None:
            raise RuntimeError("No AI deck image frame has been received yet")
        if frame_age > max_age_s:
            raise RuntimeError(f"Latest AI deck frame is stale ({frame_age:.1f}s old)")

        if output_path.suffix.lower() != suffix:
            output_path = output_path.with_suffix(suffix)
        output_path.write_bytes(frame)
        return output_path

    def _handle_payload(self, payload: bytes) -> None:
        if len(payload) >= IMG_HEADER.size and payload[0] == IMG_MAGIC:
            _magic, width, height, _depth, image_type, image_size = IMG_HEADER.unpack(payload[: IMG_HEADER.size])
            self._image_type = image_type
            self._image_size = image_size
            self._image_width = width
            self._image_height = height
            self._image_buffer.clear()
            payload = payload[IMG_HEADER.size :]

        if self._image_type is None or not payload:
            return

        remaining = self._image_size - len(self._image_buffer)
        self._image_buffer.extend(payload[:remaining])

        if len(self._image_buffer) >= self._image_size:
            self._store_frame(bytes(self._image_buffer[: self._image_size]))
            self._image_type = None
            self._image_buffer.clear()

    def _store_frame(self, image_data: bytes) -> None:
        if self._image_type == RAW_ENCODING:
            frame = f"P5\n{self._image_width} {self._image_height}\n255\n".encode("ascii") + image_data
            suffix = ".pgm"
        elif self._image_type == JPEG_ENCODING:
            frame = image_data
            suffix = ".jpg"
        else:
            return

        with self._lock:
            self._latest = frame
            self._latest_suffix = suffix
            self._latest_time = time.time()

    def _run(self) -> None:
        try:
            status(f"[camera] Connecting to AI deck {self.host}:{self.port}...")
            with socket.create_connection((self.host, self.port), timeout=self.timeout_s) as sock:
                sock.settimeout(self.timeout_s)
                self._sock = sock
                status("[camera] Connected. Reading image stream...")
                while not self._stop.is_set():
                    header = recv_exact(sock, CPX_HEADER.size)
                    length, _routing, _function = CPX_HEADER.unpack(header)
                    payload_size = length - 2
                    if payload_size < 0:
                        raise ValueError(f"Invalid CPX packet length: {length}")
                    payload = recv_exact(sock, payload_size)
                    self._handle_payload(payload)

                    if self._image_type is None:
                        self._buffer.extend(payload)
                        for frame in pop_jpeg_frames(self._buffer):
                            with self._lock:
                                self._latest = frame
                                self._latest_suffix = ".jpg"
                                self._latest_time = time.time()
        except BaseException as exc:
            if not self._stop.is_set():
                with self._lock:
                    self._error = exc
