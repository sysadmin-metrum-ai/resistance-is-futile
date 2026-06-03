"""Two-Crazyflie Lighthouse demo: orbit a captured server box at two heights.

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_dual_server_orbit.py
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from tools.lighthouse_demos.lighthouse_dual_x_step import cache_dir_for_uri
from tools.lighthouse_demos.lighthouse_dual_x_step import configure_drone
from tools.lighthouse_demos.lighthouse_dual_x_step import set_bottom_color_led_blue
from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_dual_x_step import stop_all
from tools.lighthouse_demos.lighthouse_dual_x_step import takeoff_stagger_drone_b
from tools.lighthouse_demos.lighthouse_single_server_orbit import average_pose
from tools.lighthouse_demos.lighthouse_single_server_orbit import collect_pose_samples
from tools.lighthouse_demos.lighthouse_single_server_orbit import orbit_points
from tools.lighthouse_demos.lighthouse_single_server_orbit import wait_after
from src.safety.geofence import Point3
from src.safety.geofence import load_box


DEFAULT_BOX = "config/no_fly_zones/server_box.json"


def shifted_reverse_path(points: list[Point3]) -> list[Point3]:
    half = len(points) // 2
    shifted = points[half:] + points[:half]
    return list(reversed(shifted))


def fly_orbit(
    scf: SyncCrazyflie,
    name: str,
    is_drone_a: bool,
    args: argparse.Namespace,
    barrier: threading.Barrier,
    homes: dict[str, Point3],
    paths: dict[str, list[Point3]],
    orbit_z: float,
) -> None:
    commander = scf.cf.high_level_commander
    path = paths[name]
    home = homes[name]

    status(f"[{name}] Ready.")
    barrier.wait()
    takeoff_stagger_drone_b(name, args.takeoff_stagger_b)

    status(f"[{name}] Taking off to z={orbit_z:.2f}m...")
    commander.takeoff(orbit_z, args.takeoff_time, yaw=None)
    wait_after(args.takeoff_time, args.settle, args.trajectory_pad)

    if args.blue_led and is_drone_a:
        set_bottom_color_led_blue(scf.cf, name)

    start = path[0]
    status(f"[{name}] Moving to orbit start at z={start[2]:.2f}m...")
    commander.go_to(start[0], start[1], start[2], 0.0, args.move_time, relative=False)
    wait_after(args.move_time, args.settle, args.trajectory_pad)

    barrier.wait()
    for loop_index in range(args.loops):
        status(f"[{name}] Orbit loop {loop_index + 1}/{args.loops}")
        for point in path[1:] + path[:1]:
            commander.go_to(point[0], point[1], point[2], 0.0, args.segment_time, relative=False)
            wait_after(args.segment_time, args.settle, args.trajectory_pad)

    barrier.wait()
    status(f"[{name}] Returning above home...")
    commander.go_to(home[0], home[1], orbit_z, 0.0, args.move_time, relative=False)
    wait_after(args.move_time, args.settle, args.trajectory_pad)

    status(f"[{name}] Landing...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()
    status(f"[{name}] Done.")


def capture_home(scf: SyncCrazyflie, name: str, sample_duration: float) -> Point3:
    home = average_pose(collect_pose_samples(scf.cf, sample_duration))
    status(f"[{name}] Home pose x={home[0]:.3f} y={home[1]:.3f} z={home[2]:.3f}")
    return home


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Two-drone server-box orbit demo")
    parser.add_argument("--uri-a", default="radio://0/80/2M/E7E7E7E701")
    parser.add_argument("--uri-b", default="radio://0/80/2M/E7E7E7E702")
    parser.add_argument("--box", default=DEFAULT_BOX)
    parser.add_argument("--min-height-a", type=float, default=0.45)
    parser.add_argument("--z-gap", type=float, default=0.35)
    parser.add_argument("--clearance", type=float, default=0.35)
    parser.add_argument("--radius-margin", type=float, default=0.35)
    parser.add_argument("--loops", type=int, default=1)
    parser.add_argument("--points-per-loop", type=int, default=12)
    parser.add_argument("--takeoff-time", type=float, default=3.0)
    parser.add_argument("--move-time", type=float, default=3.0)
    parser.add_argument("--segment-time", type=float, default=1.5)
    parser.add_argument("--settle", type=float, default=0.3)
    parser.add_argument("--trajectory-pad", type=float, default=0.3)
    parser.add_argument("--takeoff-stagger-b", type=float, default=1.0)
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--home-sample-duration", type=float, default=1.0)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    parser.add_argument("--no-blue-led", dest="blue_led", action="store_false")
    parser.set_defaults(blue_led=True)
    return parser.parse_args(argv)


def build_paths(args: argparse.Namespace) -> tuple[dict[str, list[Point3]], tuple[float, float]]:
    box = load_box(args.box)
    center_x, center_y, _center_z = box.center
    z_a = max(args.min_height_a, box.inflated_maximum[2] + args.clearance)
    z_b = z_a + args.z_gap
    radius = max(box.inflated_width, box.inflated_depth) / 2.0 + args.radius_margin
    point_count = max(8, args.points_per_loop)

    path_a = orbit_points(center_x, center_y, z_a, radius, point_count)
    path_b_xy = orbit_points(center_x, center_y, z_b, radius, point_count)
    path_b = shifted_reverse_path(path_b_xy)

    status(f"Loaded box {args.box}")
    status(f"Orbit center=({center_x:.3f}, {center_y:.3f}) radius={radius:.3f}")
    status(f"drone-a z={z_a:.3f}, drone-b z={z_b:.3f}")
    return {"drone-a": path_a, "drone-b": path_b}, (z_a, z_b)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    scfs: list[SyncCrazyflie] = []

    try:
        paths, (z_a, z_b) = build_paths(args)

        status(f"[drone-a] Connecting to {args.uri_a}...")
        scf_a = SyncCrazyflie(args.uri_a, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri_a)))
        scf_a.open_link()
        scfs.append(scf_a)
        status("[drone-a] Connected.")

        status(f"[drone-b] Connecting to {args.uri_b}...")
        scf_b = SyncCrazyflie(args.uri_b, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri_b)))
        scf_b.open_link()
        scfs.append(scf_b)
        status("[drone-b] Connected.")

        configure_drone(scf_a, "drone-a", args.estimator_timeout)
        configure_drone(scf_b, "drone-b", args.estimator_timeout)

        box = load_box(args.box)
        homes = {
            "drone-a": capture_home(scf_a, "drone-a", args.home_sample_duration),
            "drone-b": capture_home(scf_b, "drone-b", args.home_sample_duration),
        }
        for name, home in homes.items():
            if box.contains(home):
                raise RuntimeError(f"{name} home pose is inside the inflated no-fly box.")

        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(target=fly_orbit, args=(scf_a, "drone-a", True, args, barrier, homes, paths, z_a)),
            threading.Thread(target=fly_orbit, args=(scf_b, "drone-b", False, args, barrier, homes, paths, z_b)),
        ]

        status("Starting two-height server orbit...")
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        status("Both drones complete.")
        return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt: landing/stopping both drones now.")
        stop_all(scfs)
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        stop_all(scfs)
        return 1
    finally:
        for scf in scfs:
            try:
                scf.close_link()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
