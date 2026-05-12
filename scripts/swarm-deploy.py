"""Deploy a 3-5 Crazyflie swarm mission from the CLI.

Defaults to dry-run. Use both ``--arm`` and ``--yes`` to fly hardware.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.swarm.models import MissionSpec
from src.swarm.session import SwarmSessionRunner


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deploy one dynamic Crazyflie swarm mission")
    parser.add_argument("--swarm-size", type=int, default=3, choices=[3, 4, 5])
    parser.add_argument("--formation", choices=["line", "triangle", "diamond", "v"], default="triangle")
    parser.add_argument("--pattern", choices=["line_shift", "square", "hold", "up_forward", "captured_path"], default="up_forward")
    parser.add_argument("--final-pose", nargs=3, type=float, default=(0.50, 0.0, 0.55), metavar=("X", "Y", "Z"))
    parser.add_argument("--slot-spacing", type=float, default=0.49)
    parser.add_argument("--min-separation", type=float, default=0.10)
    parser.add_argument("--captured-path", default=None, help="Path JSON from scripts/capture-demo-path.py")
    parser.add_argument("--yaw-rad", type=float, default=0.0, help="Yaw passed to high-level go_to commands")
    parser.add_argument(
        "--no-fly-zone",
        action="append",
        default=[],
        help="Geofence JSON path; repeatable. Defaults to no geofence.",
    )
    parser.add_argument("--no-collision-avoidance", dest="collision_avoidance", action="store_false")
    parser.add_argument("--hover-z", type=float, default=0.55)
    parser.add_argument("--allow-uri", action="append", default=[], help="Candidate URI; repeatable")
    parser.add_argument("--deny-uri", action="append", default=[], help="Excluded URI; repeatable")
    parser.add_argument("--arm", action="store_true", help="Allow hardware flight when paired with --yes")
    parser.add_argument("--yes", action="store_true", help="Confirm non-dry-run hardware flight")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    arm = bool(args.arm and args.yes and not args.dry_run)
    spec = MissionSpec(
        swarm_size=args.swarm_size,
        formation=args.formation,
        pattern=args.pattern,
        final_pose=tuple(args.final_pose),
        slot_spacing_m=args.slot_spacing,
        min_separation_m=args.min_separation,
        enable_collision_avoidance=args.collision_avoidance,
        no_fly_zone_paths=tuple(args.no_fly_zone),
        captured_path=args.captured_path,
        yaw_rad=args.yaw_rad,
        hover_z=args.hover_z,
        dry_run=not arm,
        arm=arm,
        allowed_uris=tuple(args.allow_uri),
        denied_uris=tuple(args.deny_uri),
    )
    result = await SwarmSessionRunner().deploy(spec)
    print(json.dumps(result.to_dict(), indent=2), flush=True)
    return 0 if result.state.value in {"dry_run", "completed"} else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
