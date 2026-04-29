"""Capture a server no-fly box from four Lighthouse top-corner poses.

Usage:
    uv run python scripts/capture-server-box.py --uri radio://0/80/2M/E7E7E7E701
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from lighthouse_dual_x_step import cache_dir_for_uri
from lighthouse_dual_x_step import reset_estimator
from lighthouse_dual_x_step import status
from lighthouse_dual_x_step import wait_for_estimator
from src.safety.geofence import Point3
from src.safety.geofence import box_from_top_corners
from src.safety.geofence import save_box


DEFAULT_URI = "radio://0/80/2M/E7E7E7E701"
DEFAULT_OUTPUT = "config/no_fly_zones/server_box.json"


def collect_pose_samples(cf, duration_s: float, period_ms: int) -> list[Point3]:
    samples: list[Point3] = []
    log = LogConfig(name=f"ServerCorner{int(time.time() * 1000)}", period_in_ms=period_ms)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")

    def on_data(_timestamp, data, _logconf) -> None:
        samples.append(
            (
                float(data["kalman.stateX"]),
                float(data["kalman.stateY"]),
                float(data["kalman.stateZ"]),
            )
        )

    cf.log.add_config(log)
    log.data_received_cb.add_callback(on_data)
    log.start()
    try:
        time.sleep(duration_s)
    finally:
        log.stop()
    return samples


def average_pose(samples: list[Point3], min_samples: int) -> Point3:
    if len(samples) < min_samples:
        raise RuntimeError(f"Too few pose samples: got {len(samples)}, need {min_samples}")

    xs = [point[0] for point in samples]
    ys = [point[1] for point in samples]
    zs = [point[2] for point in samples]
    pose = (mean(xs), mean(ys), mean(zs))
    spread = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    status(
        "Captured corner: "
        f"x={pose[0]:.3f} y={pose[1]:.3f} z={pose[2]:.3f} "
        f"spread=({spread[0]:.3f}, {spread[1]:.3f}, {spread[2]:.3f})"
    )
    return pose


def capture_corners(cf, args: argparse.Namespace) -> list[Point3]:
    corners: list[Point3] = []
    for index in range(1, 5):
        status("")
        status(f"Move the drone/Lighthouse deck to TOP corner {index}/4.")
        status(f"Capturing automatically in {args.corner_delay:.1f}s...")
        time.sleep(args.corner_delay)
        samples = collect_pose_samples(cf, args.sample_duration, args.period_ms)
        corners.append(average_pose(samples, args.min_samples))
    return corners


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture four top corners for a server no-fly box")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--name", default="server")
    parser.add_argument("--floor-z", type=float, default=0.0)
    parser.add_argument("--margin", type=float, default=0.35)
    parser.add_argument("--corner-delay", type=float, default=5.0)
    parser.add_argument("--sample-duration", type=float, default=1.0)
    parser.add_argument("--period-ms", type=int, default=100)
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()

    try:
        status(f"Connecting to {args.uri}...")
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri))) as scf:
            status("Connected. Configuring Lighthouse estimator...")
            scf.cf.param.set_value("stabilizer.estimator", "2")
            time.sleep(0.5)
            reset_estimator(scf.cf, "capture")
            wait_for_estimator(scf.cf, "capture", args.estimator_timeout)

            corners = capture_corners(scf.cf, args)
            box = box_from_top_corners(
                corners,
                floor_z=args.floor_z,
                margin=args.margin,
                name=args.name,
            )
            save_box(box, args.output)

        status("")
        status(f"Wrote geofence box to {args.output}")
        status(f"raw min={box.minimum} max={box.maximum}")
        status(f"inflated min={box.inflated_minimum} max={box.inflated_maximum}")
        return 0
    except KeyboardInterrupt:
        status("Interrupted.")
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
