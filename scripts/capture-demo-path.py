#!/usr/bin/env python3
"""Capture a hand-carried Lighthouse path and write swarm replay waypoints."""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from pathlib import Path
from threading import Event

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

Vec3 = tuple[float, float, float]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uri", help="Crazyflie URI used as the Lighthouse probe")
    parser.add_argument("--output", default="config/demo_path.json")
    parser.add_argument("--sample-period-ms", type=int, default=100)
    parser.add_argument("--max-waypoints", type=int, default=8)
    parser.add_argument("--min-spacing-m", type=float, default=0.04)
    parser.add_argument("--pattern-s", type=float, default=0.4, help="Replay seconds per captured waypoint")
    parser.add_argument("--pattern-hold-s", type=float, default=0.0, help="Replay hold seconds between captured waypoints")
    parser.add_argument("--pattern-final-hold-s", type=float, default=3.0, help="Hold seconds after final captured waypoint")
    parser.add_argument("--force-z", type=float, default=None, help="Replace captured Z with this flight altitude")
    return parser.parse_args(argv)


def capture_samples(cf, stop: Event, period_ms: int) -> list[dict]:
    samples: list[dict] = []
    log = LogConfig(name=f"DemoPath{int(time.time() * 1000) % 100000}", period_in_ms=period_ms)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")
    log.add_variable("stabilizer.yaw", "float")

    started = time.monotonic()

    def on_data(_ts, data, _conf) -> None:
        samples.append(
            {
                "t": round(time.monotonic() - started, 3),
                "x": float(data["kalman.stateX"]),
                "y": float(data["kalman.stateY"]),
                "z": float(data["kalman.stateZ"]),
                "yaw_deg": float(data.get("stabilizer.yaw", 0.0)),
            }
        )

    cf.log.add_config(log)
    log.data_received_cb.add_callback(on_data)
    log.start()
    try:
        while not stop.wait(0.1):
            pass
    finally:
        log.stop()
        try:
            log.delete()
        except Exception:
            pass
    return samples


def distance(a: Vec3, b: Vec3) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def sample_point(sample: dict, force_z: float | None) -> Vec3:
    return (float(sample["x"]), float(sample["y"]), float(sample["z"] if force_z is None else force_z))


def simplify(samples: list[dict], *, force_z: float | None, min_spacing_m: float, max_waypoints: int) -> list[dict]:
    if not samples:
        return []

    deduped = [samples[0]]
    for sample in samples[1:]:
        if distance(sample_point(sample, force_z), sample_point(deduped[-1], force_z)) >= min_spacing_m:
            deduped.append(sample)
    if samples[-1] is not deduped[-1]:
        deduped.append(samples[-1])

    if len(deduped) <= max_waypoints + 1:
        return deduped

    step = (len(deduped) - 1) / max_waypoints
    selected = [deduped[round(i * step)] for i in range(max_waypoints + 1)]
    selected[-1] = deduped[-1]
    return selected


def write_path(args: argparse.Namespace, samples: list[dict]) -> Path:
    selected = simplify(
        samples,
        force_z=args.force_z,
        min_spacing_m=args.min_spacing_m,
        max_waypoints=args.max_waypoints,
    )
    waypoints = [sample_point(sample, args.force_z) for sample in selected]
    if len(waypoints) < 2:
        raise RuntimeError("not enough movement captured; need at least a start and final point")

    start = waypoints[0]
    relative_points = [(x - start[0], y - start[1], z - start[2]) for x, y, z in waypoints[1:]]
    start_yaw_rad = math.radians(float(selected[0].get("yaw_deg", 0.0)))
    yaw_points_rad = [math.radians(float(sample.get("yaw_deg", 0.0))) for sample in selected[1:]]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "version": 1,
                "start": start,
                "start_yaw_rad": start_yaw_rad,
                "pattern_s": args.pattern_s,
                "pattern_hold_s": args.pattern_hold_s,
                "pattern_final_hold_s": args.pattern_final_hold_s,
                "yaw_rad": yaw_points_rad[-1],
                "waypoints": waypoints,
                "relative_points": relative_points,
                "yaw_points_rad": yaw_points_rad,
            },
            indent=2,
        )
        + "\n"
    )
    return output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    stop = Event()
    print(f"Connecting {args.uri}", flush=True)
    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache/capture-demo-path")) as scf:
        cf = scf.cf
        cf.param.set_value("stabilizer.estimator", "2")
        time.sleep(0.5)
        input("Hold the drone at the pyramid start point, then press Enter to start logging.")
        print("Logging. Walk the drone through the curve, hold final position, then press Enter to stop.", flush=True)
        samples_holder: list[dict] = []

        def run_capture() -> None:
            samples_holder.extend(capture_samples(cf, stop, args.sample_period_ms))

        thread = threading.Thread(target=run_capture, name="capture-demo-path")
        thread.start()
        input()
        stop.set()
        thread.join()

    output = write_path(args, samples_holder)
    print(f"Wrote {output} with {len(samples_holder)} samples.", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
