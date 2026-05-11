from __future__ import annotations

import threading
import time

from camera_socket import status


BLUE_WRGB_DEC = "255"
OFF_WRGB_DEC = "0"


class BlueBlinker:
    def __init__(self, cf, interval_s: float = 0.35):
        self._cf = cf
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._available = True

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="blue-led-blink", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._available:
            try:
                self._cf.param.set_value("colorLedBot.wrgb8888", OFF_WRGB_DEC)
            except Exception:
                pass

    def _run(self) -> None:
        on = False
        while not self._stop.is_set():
            try:
                self._cf.param.set_value("colorLedBot.wrgb8888", BLUE_WRGB_DEC if on else OFF_WRGB_DEC)
                on = not on
            except Exception as exc:
                self._available = False
                status(f"[led] Blue blink unavailable: {exc}")
                return
            self._stop.wait(self._interval_s)
