"""Eight Crazyflies — horizontal ring (octagon) + “breathe” radius change.

All craft share **one Z** (no stacking). Neighbors are angularly separated on a circle — cool
silhouette, modest mutual wake compared to a tight vertical stack.

**Ideal floor marks:** place drones on the **printed** inner-ring (x, y) from the script preamble
(run once with ``--help`` / dry expectations, or run and copy the “Rally / inner ring” table).
Order must match **uri-01 … uri-08** around the circle (not arbitrary assignment).

**Bottom LED:** blinks blue after takeoff, off just before land (``--no-led-blink``).

Conceptually: **circle of radius ~0.78 m** centered at (cx, cy), angles every 45°. Default center
**(0.15, 0.0)** m, radius **0.78 m**::

    id   angle_deg   rally (x, y) approx (cx=0.15, cy=0, R=0.78)
    --   ---------   --------------------------------------------
    01     0         (cx+R, cy)
    02    45         …
    …    …           (use printed table at startup or layout script)

Exact coordinates (match takeoff marks)::

    cx, cy = 0.15, 0.0
    R = 0.78
    import math
    for i in range(8):
        ang = math.radians(i * 45.0 + 22.5)  # +22.5 optional: vertex vs edge alignment
        x = cx + R*math.cos(ang); y = cy + R*math.sin(ang)

Default uses **i * 45°** (no extra 22.5) for simpler tape layout.

**Show motion:** rally on inner ring → expand to **outer radius** → contract to **inner** → return
to rally heights at inner ring xy → land.

**Same floor pads as wave 3-2-3:** ``--rally-wave332`` with matching ``--row*-x`` / ``--y-span-*``.
First air pose holds at pads, then expands/contracts on the ring (first move can be long — increase
``--move-time``).

Usage::

    uv run python lighthouse_oct_ring_breathe.py
    uv run python lighthouse_oct_ring_breathe.py --ring-cx 0.1 --ring-cy 0 --r-inner 0.72 --r-outer 0.95
    uv run python lighthouse_oct_ring_breathe.py --rally-wave332 --row1-x -0.3 --row2-x 0.3 --row3-x 0.9
"""

from __future__ import annotations

import argparse
import math
import sys

from lighthouse_dual_x_step import status
from lighthouse_oct_common import Vec3
from lighthouse_oct_common import add_oct_timing_args
from lighthouse_oct_common import add_oct_uri_args
from lighthouse_oct_common import add_wave332_row_args
from lighthouse_oct_common import build_wave332_homes
from lighthouse_oct_common import collect_uris_from_args
from lighthouse_oct_common import run_oct_mission


def ring_positions(cx: float, cy: float, r: float, z: float) -> tuple[Vec3, ...]:
    out: list[Vec3] = []
    for i in range(8):
        ang = math.radians(i * 45.0)
        out.append((cx + r * math.cos(ang), cy + r * math.sin(ang), z))
    return tuple(out)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eight-drone octagon ring breathe (Lighthouse)")
    add_oct_uri_args(p)
    add_oct_timing_args(p)
    add_wave332_row_args(p)
    p.add_argument("--ring-cx", type=float, default=0.15)
    p.add_argument("--ring-cy", type=float, default=0.0)
    p.add_argument("--r-inner", type=float, default=0.72, help="Inner ring radius (m).")
    p.add_argument("--r-outer", type=float, default=0.92, help="Expanded ring radius (m).")
    p.add_argument(
        "--rally-wave332",
        action="store_true",
        help="Rally on 3-2-3 wave pads (set --row*-x / --y-span-* to match tape).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    hz = args.hover_z
    cx, cy = args.ring_cx, args.ring_cy
    ri, ro = args.r_inner, args.r_outer

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
        f1 = ring_positions(cx, cy, ro, hz)
        f2 = ring_positions(cx, cy, ri, hz)
        holds = (args.hold_first, args.hold_mid, args.hold_mid)
        waypoints = (f0, f1, f2)
    else:
        homes = ring_positions(cx, cy, ri, hz)
        f0 = ring_positions(cx, cy, ri, hz)
        f1 = ring_positions(cx, cy, ro, hz)
        f2 = ring_positions(cx, cy, ri, hz)
        holds = (args.hold_first, args.hold_mid, args.hold_mid)
        waypoints = (f0, f1, f2)

    def preamble() -> None:
        print(__doc__)
        if args.rally_wave332:
            status("Rally on wave 3-2-3 pads (x, y, z) per id:")
        else:
            status("Rally / inner ring (x, y, z) per drone index 0..7:")
        for i, h in enumerate(homes):
            status(f"  id {i + 1:02d}: ({h[0]:+.3f}, {h[1]:+.3f}, {h[2]:.3f})")

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
