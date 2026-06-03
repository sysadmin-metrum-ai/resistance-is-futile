"""Eight Crazyflies — single lateral line + synchronized forward/back sweep (anti-wake).

Everyone shares **one altitude** and spacing along **Y** so you avoid vertical stacking; propwash
mostly bothers neighbors along the line — keep **≥0.55 m** edge-to-edge on the ground.

Place **id 01 … 08** on the listed pads (same order as ``--uri-01`` … ``--uri-08``), not arbitrary
positions — see ``lighthouse_oct_common`` module doc for why.

**Bottom LED:** blinks blue after takeoff, off just before land (``--no-led-blink`` to disable).

**Ideal floor marks (same order as ``--uri-01`` … ``--uri-08``):**

Line along Y at fixed x = **-0.40 m** (adjust with ``--line-x`` if needed)::

    id   rally (x, y) m
    --   ----------------
    01   (-0.40, -1.35)
    02   (-0.40, -0.97)
    03   (-0.40, -0.58)
    04   (-0.40, -0.19)
    05   (-0.40,  0.19)
    06   (-0.40,  0.58)
    07   (-0.40,  0.97)
    08   (-0.40,  1.35)

**Show motion:** hold the line → slide entire line **+X** together → slide back → return rally → land.

**Same floor pads as wave 3-2-3:** If drones are already on wave tape (``--row*-x``, ``--y-span-*``),
use ``--rally-wave332`` so rally homes match those pads. The sequence adds a short hold at pads,
then moves into the line, sweeps, and returns (use a generous ``--move-time`` for the first leg).

Usage::

    uv run python -m tools.lighthouse_demos.lighthouse_oct_line_sweep.py
    uv run python -m tools.lighthouse_demos.lighthouse_oct_line_sweep.py --sweep-dx 0.45 --line-x -0.35
    uv run python -m tools.lighthouse_demos.lighthouse_oct_line_sweep.py --rally-wave332 --row1-x -0.3 --row2-x 0.3 --row3-x 0.9
"""

from __future__ import annotations

import argparse
import sys

from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_oct_common import add_oct_timing_args
from tools.lighthouse_demos.lighthouse_oct_common import add_oct_uri_args
from tools.lighthouse_demos.lighthouse_oct_common import add_wave332_row_args
from tools.lighthouse_demos.lighthouse_oct_common import build_wave332_homes
from tools.lighthouse_demos.lighthouse_oct_common import collect_uris_from_args
from tools.lighthouse_demos.lighthouse_oct_common import run_oct_mission

# ~0.38 m center-to-center along Y (fits 8 on ~2.7 m span — scale room as needed)
LINE_YS = (-1.35, -0.97, -0.58, -0.19, 0.19, 0.58, 0.97, 1.35)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eight-drone line + X sweep (Lighthouse)")
    add_oct_uri_args(p)
    add_oct_timing_args(p)
    add_wave332_row_args(p)
    p.add_argument("--line-x", type=float, default=-0.40, help="Shared X for the line (m).")
    p.add_argument("--sweep-dx", type=float, default=0.50, help="+X delta for sweep (m).")
    p.add_argument(
        "--rally-wave332",
        action="store_true",
        help="Rally on 3-2-3 wave pads (set --row*-x / --y-span-* to match tape).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    hz = args.hover_z
    lx = args.line_x

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
        f1 = tuple((lx, y, hz) for y in LINE_YS)
        f2 = tuple((lx + args.sweep_dx, y, hz) for y in LINE_YS)
        f3 = tuple((lx, y, hz) for y in LINE_YS)
        waypoints = (f0, f1, f2, f3)
        holds = (args.hold_first, args.hold_mid, args.hold_mid, args.hold_mid)
    else:
        homes = tuple((lx, y, hz) for y in LINE_YS)
        f0 = tuple((lx, y, hz) for y in LINE_YS)
        f1 = tuple((lx + args.sweep_dx, y, hz) for y in LINE_YS)
        f2 = tuple((lx, y, hz) for y in LINE_YS)
        waypoints = (f0, f1, f2)
        holds = (args.hold_first, args.hold_mid, args.hold_mid)

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
