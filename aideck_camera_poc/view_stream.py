from __future__ import annotations

import argparse
import socket
import struct
import time

import cv2
import numpy as np


CPX_HEADER = struct.Struct("<HBB")
IMG_HEADER = struct.Struct("<BHHBBI")
IMG_MAGIC = 0xBC
RAW_ENCODING = 0
JPEG_ENCODING = 1


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("AI deck socket closed")
        data.extend(chunk)
    return bytes(data)


def read_frame(sock: socket.socket) -> tuple[np.ndarray, str]:
    image_type: int | None = None
    image_size = 0
    width = 0
    height = 0
    image = bytearray()

    while image_type is None or len(image) < image_size:
        length, _routing, _function = CPX_HEADER.unpack(recv_exact(sock, CPX_HEADER.size))
        payload = recv_exact(sock, length - 2)

        if len(payload) >= IMG_HEADER.size and payload[0] == IMG_MAGIC:
            _magic, width, height, _depth, image_type, image_size = IMG_HEADER.unpack(payload[: IMG_HEADER.size])
            payload = payload[IMG_HEADER.size :]

        if image_type is not None:
            image.extend(payload[: image_size - len(image)])

    if image_type == RAW_ENCODING:
        frame = np.frombuffer(bytes(image), dtype=np.uint8).reshape((height, width))
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), "RAW"

    if image_type == JPEG_ENCODING:
        frame = cv2.imdecode(np.frombuffer(bytes(image), dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Could not decode JPEG frame")
        return frame, "JPEG"

    raise RuntimeError(f"Unsupported AI deck frame type: {image_type}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="View AI deck WiFi stream with FPS overlay")
    parser.add_argument("-n", "--host", default="192.168.4.1")
    parser.add_argument("-p", "--port", type=int, default=5000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"Connecting to AI deck stream on {args.host}:{args.port}...", flush=True)

    with socket.create_connection((args.host, args.port), timeout=8.0) as sock:
        sock.settimeout(8.0)
        print("Socket connected. Press q in the viewer window to quit.", flush=True)
        start = time.monotonic()
        frames = 0

        while True:
            frame, image_type = read_frame(sock)
            frames += 1
            elapsed = max(time.monotonic() - start, 0.001)
            fps = frames / elapsed
            overlay = f"{image_type}  {frame.shape[1]}x{frame.shape[0]}  {fps:.1f} FPS  frame {frames}"
            cv2.putText(frame, overlay, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            cv2.imshow("AI Deck Stream", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
