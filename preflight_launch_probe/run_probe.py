#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

from launch import close_all
from launch import launch_and_land
from probe import parse_uri_list
from probe import prepare_drone


DEFAULT_URI = "radio://0/80/2M/E7E7E7E701"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure launch latency after cflib preflight has already prepared drones."
    )
    parser.add_argument(
        "--uris",
        nargs="+",
        default=[DEFAULT_URI],
        help="One or more URIs. Comma-separated values are also accepted.",
    )
    parser.add_argument("--height-m", type=float, default=0.55)
    parser.add_argument("--takeoff-s", type=float, default=2.5)
    parser.add_argument("--hover-s", type=float, default=2.0)
    parser.add_argument("--land-s", type=float, default=2.5)
    parser.add_argument("--schedule-buffer-s", type=float, default=0.25)
    parser.add_argument("--estimator-timeout-s", type=float, default=8.0)
    parser.add_argument("--pose-sample-s", type=float, default=0.5)
    parser.add_argument("--param-settle-s", type=float, default=0.5)
    parser.add_argument("--arm-settle-s", type=float, default=1.0)
    parser.add_argument("--collision-avoidance", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--auto-launch-after-s", type=float)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    uris = parse_uri_list(args.uris)
    if not uris:
        print("No URIs supplied.", file=sys.stderr)
        return 2

    import cflib.crtp

    cflib.crtp.init_drivers()
    prepared = []
    total_started = time.monotonic()
    try:
        print(f"[preflight] preparing {len(uris)} drone(s)")
        for uri in uris:
            started = time.monotonic()
            print(f"[preflight] {uri} connecting/configuring/arming...")
            drone = prepare_drone(uri, args)
            prepared.append(drone)
            pose = drone.pose
            timings = ", ".join(f"{key}={value:.2f}s" for key, value in drone.timings.items())
            print(
                f"[preflight] {uri} ready in {time.monotonic() - started:.2f}s "
                f"pose=({pose[0]:.3f}, {pose[1]:.3f}, {pose[2]:.3f}) {timings}"
            )

        print(f"[preflight] all ready in {time.monotonic() - total_started:.2f}s")
        if args.preflight_only:
            print("[done] preflight-only requested; closing links")
            return 0

        if args.auto_launch_after_s is None:
            input("[launch] press Enter to take off, or Ctrl-C to abort...")
        else:
            print(f"[launch] auto-launching in {args.auto_launch_after_s:.2f}s")
            time.sleep(args.auto_launch_after_s)

        launch_started = time.monotonic()
        launch_called = launch_and_land(prepared, args)
        print(f"[result] flight sequence complete in {time.monotonic() - launch_started:.2f}s")
        for uri, elapsed in sorted(launch_called.items()):
            print(f"[result] {uri} takeoff command dispatched at +{elapsed:.3f}s after launch")
        return 0
    except KeyboardInterrupt:
        print("\n[abort] interrupted")
        return 130
    except Exception as exc:
        print(f"[abort] {exc}", file=sys.stderr)
        return 1
    finally:
        close_all(prepared)


if __name__ == "__main__":
    sys.exit(main())
