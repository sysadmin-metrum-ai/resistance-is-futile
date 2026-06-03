"""Eight Crazyflies — two staggered rows of four (“brick” / herringbone in plan).

**Back row** (four) at more −X, **front row** (four) at more +X with **Y half-offset** so each front
drone sits in the “gap” of the back row — strong anti-wake vs a simple 4×2 grid. Slight **ΔZ**
between rows adds separation without a vertical tower over one spot.

Use the table for **id 01–08** ↔ pad (x, y); do not scatter randomly (see ``lighthouse_oct_common``).
**Bottom LED:** blinks blue after takeoff, off just before land (``--no-led-blink``).

**Ideal floor marks (id 01–08 = uri order)::**

    id   row    rally (x, y) m
    --   ----   ----------------
    01   back   (-0.55, -1.05)
    02   back   (-0.55, -0.35)
    03   back   (-0.55,  0.35)
    04   back   (-0.55,  1.05)
    05   front  ( 0.45, -0.70)
    06   front  ( 0.45,  0.00)
    07   front  ( 0.45,  0.70)
    08   front  ( 0.45,  1.40)

**Show motion:** rally → hold brick in the air → **slide both rows +X** together → slide back →
rally → land.

**Same floor pads as wave 3-2-3:** ``--rally-wave332`` with ``--row*-x`` / ``--y-span-*`` matches
wave tape; first air waypoint holds at pads, then brick + slide (allow long ``--move-time`` for the
first transition).

Usage::

    uv run python -m tools.lighthouse_demos.lighthouse_oct_brick_24.py
    uv run python -m tools.lighthouse_demos.lighthouse_oct_brick_24.py --slide-dx 0.40
    uv run python -m tools.lighthouse_demos.lighthouse_oct_brick_24.py --rally-wave332 --row1-x -0.3 --row2-x 0.3 --row3-x 0.9
"""

from __future__ import annotations

import argparse
import sys

from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_oct_common import Vec3
from tools.lighthouse_demos.lighthouse_oct_common import add_oct_timing_args
from tools.lighthouse_demos.lighthouse_oct_common import add_oct_uri_args
from tools.lighthouse_demos.lighthouse_oct_common import add_wave332_row_args
from tools.lighthouse_demos.lighthouse_oct_common import build_wave332_homes
from tools.lighthouse_demos.lighthouse_oct_common import collect_uris_from_args
from tools.lighthouse_demos.lighthouse_oct_common import run_oct_mission


def homes_brick(hz: float) -> tuple[Vec3, ...]:
    return (
        (-0.55, -1.05, hz),
        (-0.55, -0.35, hz),
        (-0.55, 0.35, hz),
        (-0.55, 1.05, hz),
        (0.45, -0.70, hz),
        (0.45, 0.00, hz),
        (0.45, 0.70, hz),
        (0.45, 1.40, hz),
    )


def air_brick(hz: float, z_back: float, z_front: float, dx: float) -> tuple[Vec3, ...]:
    xb, xf = -0.55 + dx, 0.45 + dx
    return (
        (xb, -1.05, z_back),
        (xb, -0.35, z_back),
        (xb, 0.35, z_back),
        (xb, 1.05, z_back),
        (xf, -0.70, z_front),
        (xf, 0.00, z_front),
        (xf, 0.70, z_front),
        (xf, 1.40, z_front),
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eight-drone staggered brick 4+4 (Lighthouse)")
    add_oct_uri_args(p)
    add_oct_timing_args(p)
    add_wave332_row_args(p)
    p.add_argument("--z-back", type=float, default=0.58)
    p.add_argument("--z-front", type=float, default=0.72)
    p.add_argument("--slide-dx", type=float, default=0.38, help="+X shift for the slide (m).")
    p.add_argument(
        "--rally-wave332",
        action="store_true",
        help="Rally on 3-2-3 wave pads (set --row*-x / --y-span-* to match tape).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    hz = args.hover_z
    zb, zf = args.z_back, args.z_front

    if args.rally_wave332:
        homes = build_wave332_homes(
            hz,
            args.row1_x,
            args.row2_x,
            args.row3_x,
            args.y_span_outer,
            args.y_span_mid,
        )
        f0 = homes
        f1 = air_brick(hz, zb, zf, args.slide_dx)
        f2 = air_brick(hz, zb, zf, 0.0)
        holds = (args.hold_first, args.hold_mid, args.hold_mid)
        waypoints = (f0, f1, f2)
    else:
        homes = homes_brick(hz)
        f0 = air_brick(hz, zb, zf, 0.0)
        f1 = air_brick(hz, zb, zf, args.slide_dx)
        f2 = air_brick(hz, zb, zf, 0.0)
        holds = (args.hold_first, args.hold_mid, args.hold_mid)
        waypoints = (f0, f1, f2)

    def preamble() -> None:
        print(__doc__)

    try:
        run_oct_mission(collect_uris_from_args(args), homes, waypoints, holds, args, preamble=preamble)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
