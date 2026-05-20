"""Single-Crazyflie Lighthouse demo: orbit above a captured server box.

Usage:
    uv run python lighthouse_single_server_orbit.py
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from statistics import mean

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from lighthouse_dual_x_step import cache_dir_for_uri
from lighthouse_dual_x_step import configure_drone
from lighthouse_dual_x_step import status
from src.safety.geofence import Point3
from src.safety.geofence import load_box


DEFAULT_URI = "radio://0/80/2M/E7E7E7E701"
DEFAULT_BOX = "config/no_fly_zones/server_box.json"


def collect_pose_samples(cf, duration_s: float, period_ms: int = 100) -> list[Point3]:
    samples: list[Point3] = []
    log = LogConfig(name=f"HomePose{int(time.time() * 1000)}", period_in_ms=period_ms)
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


def average_pose(samples: list[Point3]) -> Point3:
    if len(samples) < 5:
        raise RuntimeError(f"Too few home pose samples: {len(samples)}")
    return (
        mean(point[0] for point in samples),
        mean(point[1] for point in samples),
        mean(point[2] for point in samples),
    )


def orbit_points(cx: float, cy: float, z: float, radius: float, count: int) -> list[Point3]:
    return [
        (
            cx + radius * math.cos(2.0 * math.pi * index / count),
            cy + radius * math.sin(2.0 * math.pi * index / count),
            z,
        )
        for index in range(count)
    ]


def square_points(cx: float, cy: float, z: float, half_side: float) -> list[Point3]:
    return [
        (cx + half_side, cy - half_side, z),
        (cx + half_side, cy + half_side, z),
        (cx - half_side, cy + half_side, z),
        (cx - half_side, cy - half_side, z),
    ]


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def append_unique(points: list[Point3], point: Point3) -> None:
    if not points or points[-1] != point:
        points.append(point)


def square_path_from_home(cx: float, cy: float, z: float, half_side: float, home: Point3) -> list[Point3]:
    left = cx - half_side
    right = cx + half_side
    bottom = cy - half_side
    top = cy + half_side
    home_x, home_y, _home_z = home

    candidates = [
        ("right", (right, clamp(home_y, bottom, top), z)),
        ("top", (clamp(home_x, left, right), top, z)),
        ("left", (left, clamp(home_y, bottom, top), z)),
        ("bottom", (clamp(home_x, left, right), bottom, z)),
    ]
    side, entry = min(candidates, key=lambda item: (item[1][0] - home_x) ** 2 + (item[1][1] - home_y) ** 2)

    if side == "right":
        path = [entry, (right, top, z), (left, top, z), (left, bottom, z), (right, bottom, z)]
    elif side == "top":
        path = [entry, (left, top, z), (left, bottom, z), (right, bottom, z), (right, top, z)]
    elif side == "left":
        path = [entry, (left, bottom, z), (right, bottom, z), (right, top, z), (left, top, z)]
    else:
        path = [entry, (right, bottom, z), (right, top, z), (left, top, z), (left, bottom, z)]

    deduped: list[Point3] = []
    for point in path:
        append_unique(deduped, point)
    return deduped


def approach_points(home: Point3, entry: Point3) -> list[Point3]:
    home_x, home_y, _home_z = home
    entry_x, entry_y, entry_z = entry
    points: list[Point3] = []
    if home_x != entry_x and home_y != entry_y:
        points.append((entry_x, home_y, entry_z))
    points.append(entry)
    return points


def flight_path(
    args: argparse.Namespace,
    cx: float,
    cy: float,
    z: float,
    radius: float,
    count: int,
    home: Point3,
) -> list[Point3]:
    if args.path == "circle":
        return orbit_points(cx, cy, z, radius, count)
    return square_path_from_home(cx, cy, z, radius, home)


def wait_after(duration_s: float, settle_s: float, pad_s: float) -> None:
    time.sleep(duration_s + settle_s + pad_s)


def fly_demo(scf: SyncCrazyflie, args: argparse.Namespace) -> None:
    box = load_box(args.box)
    center_x, center_y, _center_z = box.center
    orbit_z = max(args.min_height, box.inflated_maximum[2] + args.clearance)
    radius = max(box.inflated_width, box.inflated_depth) / 2.0 + args.radius_margin
    point_count = max(8, args.points_per_loop)

    status(f"Loaded box {args.box}")
    status(f"Path={args.path} center=({center_x:.3f}, {center_y:.3f}) half_side/radius={radius:.3f} z={orbit_z:.3f}")

    home = average_pose(collect_pose_samples(scf.cf, args.home_sample_duration))
    status(f"Home pose x={home[0]:.3f} y={home[1]:.3f} z={home[2]:.3f}")
    if box.contains(home):
        raise RuntimeError("Home pose is inside the inflated no-fly box.")

    commander = scf.cf.high_level_commander
    status(f"Taking off to z={orbit_z:.2f}m...")
    commander.takeoff(orbit_z, args.takeoff_time, yaw=None)
    wait_after(args.takeoff_time, args.settle, args.trajectory_pad)

    points = flight_path(args, center_x, center_y, orbit_z, radius, point_count, home)
    start = points[0]
    status("Moving to nearest path edge...")
    for point in approach_points(home, start):
        commander.go_to(point[0], point[1], point[2], 0.0, args.move_time, relative=False, linear=True)
        wait_after(args.move_time, args.settle, args.trajectory_pad)

    for loop_index in range(args.loops):
        status(f"{args.path.capitalize()} loop {loop_index + 1}/{args.loops}")
        for point in points[1:] + points[:1]:
            commander.go_to(point[0], point[1], point[2], 0.0, args.segment_time, relative=False, linear=True)
            wait_after(args.segment_time, args.settle, args.trajectory_pad)

    status("Returning above home...")
    commander.go_to(home[0], home[1], orbit_z, 0.0, args.move_time, relative=False)
    wait_after(args.move_time, args.settle, args.trajectory_pad)
    status("Landing at original XY...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-drone server-box orbit demo")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--box", default=DEFAULT_BOX)
    parser.add_argument("--min-height", type=float, default=0.45)
    parser.add_argument("--clearance", type=float, default=0.35)
    parser.add_argument("--radius-margin", type=float, default=0.35)
    parser.add_argument("--path", choices=("square", "circle"), default="square")
    parser.add_argument("--loops", type=int, default=1)
    parser.add_argument("--points-per-loop", type=int, default=12)
    parser.add_argument("--takeoff-time", type=float, default=3.0)
    parser.add_argument("--move-time", type=float, default=3.0)
    parser.add_argument("--segment-time", type=float, default=1.5)
    parser.add_argument("--settle", type=float, default=0.3)
    parser.add_argument("--trajectory-pad", type=float, default=0.3)
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--home-sample-duration", type=float, default=1.0)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    scf = None
    try:
        status(f"Connecting to {args.uri}...")
        scf = SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri)))
        scf.open_link()
        status("Connected.")
        configure_drone(scf, "drone", args.estimator_timeout)
        fly_demo(scf, args)
        status("Done.")
        return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt: landing/stopping now.")
        if scf is not None:
            scf.cf.high_level_commander.land(0.0, 1.0, yaw=None)
            time.sleep(1.0)
            scf.cf.high_level_commander.stop()
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        if scf is not None:
            try:
                scf.cf.high_level_commander.stop()
            except Exception:
                pass
        return 1
    finally:
        if scf is not None:
            scf.close_link()


if __name__ == "__main__":
    sys.exit(main())
