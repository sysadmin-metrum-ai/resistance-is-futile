"""Eight Crazyflies — 3-2-3 “wave” formation with horizontal row stagger (anti-wake).

Uses ``lighthouse_oct_common`` (barrier-synced HL moves). Default URIs: ``radio://0/80/2M/E7E7E7E701`` … ``…708``.

**Why rows are staggered in +X:** If three drones share the same (x, y) and only differ in Z, the
upper propwash hits the lower craft. Here the back row is more −X, the middle row mid-X, the front
row more +X, with modest Z steps — columns do not line up vertically.

**Starting positions — use the table (not “anywhere”).**

The script assumes **drone id 01** is on **pad 01**’s (x, y), … **08** on **pad 08**. The Kalman /
Lighthouse origin is fixed in the room: if you place a craft far from its programmed home, the
first ``go_to`` is a long horizontal move (unsafe with neighbors, hard on one radio). You do **not**
need millimetre tape accuracy—stay within roughly **0.15–0.2 m** of the mark—but random spots are a
bad idea for this formation.

**Ideal floor starting positions (tape marks, ~0.55–0.65 m between nearest neighbors):**

Place each airframe on its mark **before** connecting so takeoff is mostly vertical, then the rally
``go_to`` only trims position to ``(x, y, --hover-z)``.

**Id → seat (same for rally on the floor and formation in the air):**

- Row of three at ``row1_x``: **01** −Y wing, **02** center, **03** +Y wing.
- Row of two at ``row2_x``: **04** −Y, **05** +Y.
- Row of three at ``row3_x``: **06** −Y, **07** center, **08** +Y.

(“Right / left” in your description: **01 / 04 / 06** on the **−Y** side, **03 / 05 / 08** on the **+Y** side.)

The script **does not** read where the drones actually are — it commands the programmed ``(x, y)``.
Put each craft on the pad that matches **its** row/uri so takeoff + rally are short.

**Default row X / |Y| (override to match your room):**

    --row1-x -0.70  --row2-x -0.05  --row3-x 0.60
    --y-span-outer 0.65  --y-span-mid 0.40

**Example matching pads at x ≈ −0.3, +0.3, +0.9** (keep ``y-span-*`` in line with real spacing)::

    uv run python lighthouse_oct_wave_332.py \\
        --row1-x -0.3 --row2-x 0.3 --row3-x 0.9 \\
        --y-span-outer 0.65 --y-span-mid 0.40

Keep the whole grid inside your Lighthouse-solved volume and clear of people.

**Flight idea:** Rally at the table heights → hold a 3-2-3 formation → step everyone +X together
(wave through the volume) → step back → return to rally → land (optional per-drone land stagger).

**LEDs:** All oct scripts use ``lighthouse_oct_common``: bottom Color LED **blinks blue** after
takeoff and turns **off** just before ``land()`` (disable with ``--no-led-blink``).

**Configure:** Default is **one drone at a time** (``--configure-batch-size 1``) so one Crazyradio
does not starve 07–08 on Kalman logs. Use ``--configure-batch-size 4`` or ``8`` only if you have
proven headroom.

Usage::

    uv run python lighthouse_oct_wave_332.py
    uv run python lighthouse_oct_wave_332.py --takeoff-stagger-step 0.12
"""

from __future__ import annotations

import argparse
import sys

from lighthouse_dual_x_step import status
from lighthouse_oct_common import add_oct_timing_args
from lighthouse_oct_common import add_oct_uri_args
from lighthouse_oct_common import add_wave332_row_args
from lighthouse_oct_common import build_wave332_homes
from lighthouse_oct_common import collect_uris_from_args
from lighthouse_oct_common import formation_wave332
from lighthouse_oct_common import run_oct_mission


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eight-drone 3-2-3 wave formation (Lighthouse)")
    add_oct_uri_args(p)
    add_oct_timing_args(p)
    add_wave332_row_args(p)
    p.add_argument("--z-back", type=float, default=0.56, help="Back row altitude (m).")
    p.add_argument("--z-mid", type=float, default=0.70, help="Middle row altitude (m).")
    p.add_argument("--z-front", type=float, default=0.84, help="Front row altitude (m).")
    p.add_argument("--wave-dx", type=float, default=0.32, help="+X shift for wave step (m).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    hz = args.hover_z
    r1, r2, r3 = args.row1_x, args.row2_x, args.row3_x
    yo, ym = args.y_span_outer, args.y_span_mid
    homes = build_wave332_homes(hz, r1, r2, r3, yo, ym)

    zb, zm, zf = args.z_back, args.z_mid, args.z_front
    f0 = formation_wave332(zb, zm, zf, r1, r2, r3, yo, ym, 0.0)
    f1 = formation_wave332(zb, zm, zf, r1, r2, r3, yo, ym, args.wave_dx)
    f2 = formation_wave332(zb, zm, zf, r1, r2, r3, yo, ym, 0.0)

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
