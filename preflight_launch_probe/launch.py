from __future__ import annotations

import threading
import time

from probe import PreparedDrone


def launch_and_land(prepared: list[PreparedDrone], args) -> dict[str, float]:
    launch_called: dict[str, float] = {}
    start = time.monotonic()
    takeoff_at = start + args.schedule_buffer_s

    def worker(drone: PreparedDrone) -> None:
        delay = takeoff_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        drone.commander.takeoff(args.height_m, args.takeoff_s, yaw=None)
        launch_called[drone.uri] = time.monotonic() - start

    threads = [threading.Thread(target=worker, args=(drone,), name=f"probe-{drone.uri}") for drone in prepared]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    time.sleep(args.takeoff_s + args.hover_s)
    for drone in prepared:
        drone.commander.land(0.0, args.land_s, yaw=None)
    time.sleep(args.land_s + 0.3)
    for drone in prepared:
        drone.commander.stop()
    return launch_called


def close_all(prepared: list[PreparedDrone]) -> None:
    for drone in prepared:
        try:
            drone.scf.close_link()
        except Exception:
            pass
