"""Two-Crazyflie coordinated square flight using Lighthouse positioning.

The drones should start separated diagonally. Drone A starts +X/+Y, Drone B
starts -X/-Y, creating a mirrored square while keeping the bottom Color LED
logic on A.

Usage:
    uv run python lighthouse_dual_square.py
    uv run python lighthouse_dual_square.py --side 0.50 --height 0.40
"""

import argparse
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from lighthouse_dual_x_step import cache_dir_for_uri
from lighthouse_dual_x_step import configure_drone
from lighthouse_dual_x_step import set_bottom_color_led_blue
from lighthouse_dual_x_step import status
from lighthouse_dual_x_step import stop_all
from lighthouse_dual_x_step import takeoff_stagger_drone_b


def square_steps(side: float, mirrored: bool = False) -> list[tuple[float, float, float]]:
    x = -side if mirrored else side
    y = -side if mirrored else side
    return [
        (x, 0.0, 0.0),
        (0.0, y, 0.0),
        (-x, 0.0, 0.0),
        (0.0, -y, 0.0),
    ]


def fly_square(
    scf: SyncCrazyflie,
    name: str,
    args: argparse.Namespace,
    barrier: threading.Barrier,
) -> None:
    commander = scf.cf.high_level_commander

    status(f"[{name}] Ready for synchronized square.")
    barrier.wait()
    takeoff_stagger_drone_b(name, args.takeoff_stagger_b)

    status(f"[{name}] Taking off to z={args.height:.2f}m...")
    commander.takeoff(args.height, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.settle)

    if args.blue_led and name == "drone-a":
        set_bottom_color_led_blue(scf.cf, name)

    for index, (dx, dy, dz) in enumerate(square_steps(args.side, mirrored=name == "drone-b"), start=1):
        status(f"[{name}] Square leg {index}: dx={dx:+.2f}, dy={dy:+.2f}")
        commander.go_to(dx, dy, dz, 0.0, args.leg_time, relative=True)
        time.sleep(args.leg_time + args.settle)

    status(f"[{name}] Holding final/home position for {args.hold:.1f}s...")
    time.sleep(args.hold)

    status(f"[{name}] Landing...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()
    status(f"[{name}] Done.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Two-drone coordinated square flight")
    parser.add_argument("--uri-a", default="radio://0/80/2M/E7E7E7E701")
    parser.add_argument("--uri-b", default="radio://0/80/2M/E7E7E7E702")
    parser.add_argument("--height", type=float, default=0.40)
    parser.add_argument("--side", type=float, default=0.50, help="Square side length in meters")
    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--leg-time", type=float, default=2.5)
    parser.add_argument("--settle", type=float, default=0.5)
    parser.add_argument("--hold", type=float, default=1.0)
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    parser.add_argument(
        "--takeoff-stagger-b",
        type=float,
        default=0.0,
        help="Seconds drone-b waits after sync before takeoff (single Crazyradio).",
    )
    parser.add_argument("--no-blue-led", dest="blue_led", action="store_false")
    parser.set_defaults(blue_led=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    scfs: list[SyncCrazyflie] = []

    try:
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

        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(target=fly_square, args=(scf_a, "drone-a", args, barrier)),
            threading.Thread(target=fly_square, args=(scf_b, "drone-b", args, barrier)),
        ]

        status("Starting synchronized square flight...")
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
