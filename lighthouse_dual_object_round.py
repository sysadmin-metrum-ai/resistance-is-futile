"""Two-Crazyflie Lighthouse path around an obstacle (split X, common Y).

Reads battery from the firmware log (``pm.vbat`` and ``pm.batteryLevel`` when
available), prints it, and shows a prominent terminal warning if charge is
below 25%.

**Why a run can look like “flying away”** (even when +/- axes are correct):

- The high-level commander warns that a new ``go_to`` while the previous
  trajectory is still finishing can produce **wild polynomials** (cflib
  docstring on ``go_to``). This script uses **longer first legs (0.8 m)** than
  ``lighthouse_dual_square.py`` (0.5 m) with similar durations, so timing
  margins matter.
- **Wrong ``--start-a`` / ``--start-b``** uses ``relative=False``; bad numbers
  send both drones on long absolute sprints in world coordinates.
- **Lighthouse / estimator** glitches or weak geometry can make large moves
  unsafe; probe with ``lighthouse_xy_probe.py`` and shorter ``--dy1`` first.

**Placement (default):** Omit ``--start-a`` and ``--start-b``. Each drone does a
vertical takeoff from where it sits, then every leg is **relative** to that
hover pose. Optional ``--start-*`` is only if you want world-frame XY first.

**Two links on one Crazyradio:** Each URI gets its own ``rw_cache`` subfolder
(see ``cache_dir_for_uri`` in ``lighthouse_dual_x_step``). Drone B defaults to a
short ``--takeoff-stagger-b`` after the start barrier.

Flight (relative-only, or after optional absolute start positions):
  1. Both move relative (0, -0.8, 0) by default.
  2. Drone A (E7E7E7E701): (-0.4, 0, 0); Drone B (E7E7E7E702): (-0.8, 0, 0).
  3. Drone A: (+0.4, 0, 0); Drone B: (+0.8, 0, 0).
  4. Both: (0, +0.8, 0).
  5. Land.

Usage:
    uv run python lighthouse_dual_object_round.py
    uv run python lighthouse_dual_object_round.py --start-a 0.5 0.3 --start-b -0.4 -0.35
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from lighthouse_dual_x_step import cache_dir_for_uri
from lighthouse_dual_x_step import configure_drone
from lighthouse_dual_x_step import set_bottom_color_led_blue
from lighthouse_dual_x_step import status
from lighthouse_dual_x_step import stop_all
from lighthouse_dual_x_step import takeoff_stagger_drone_b

VBAT_EMPTY_V = 3.0
VBAT_FULL_V = 4.2
LOW_BATTERY_PCT = 25


def vbat_to_approx_percent(vbat: float) -> int:
    if math.isnan(vbat) or vbat <= 0.0:
        return 0
    pct = (vbat - VBAT_EMPTY_V) / (VBAT_FULL_V - VBAT_EMPTY_V) * 100.0
    return int(max(0.0, min(100.0, pct)))


def read_pm_battery(cf: Crazyflie, label: str, sample_s: float = 0.55) -> tuple[float, int]:
    """Sample ``pm.vbat`` (V) and battery percent (``pm.batteryLevel`` or vbat estimate)."""
    data: dict = {}

    def _cb(_ts: int, d: dict, _lc: LogConfig) -> None:
        data.update(d)

    block_id = int(time.time() * 1000) % 100000
    log = LogConfig(name=f"PMPre{label}{block_id}", period_in_ms=100)
    log.add_variable("pm.vbat", "float")
    log.add_variable("pm.batteryLevel", "uint8_t")
    use_level = True
    try:
        cf.log.add_config(log)
    except KeyError:
        log = LogConfig(name=f"PMVbat{label}{block_id}", period_in_ms=100)
        log.add_variable("pm.vbat", "float")
        cf.log.add_config(log)
        use_level = False

    log.data_received_cb.add_callback(_cb)
    log.start()
    time.sleep(sample_s)
    log.stop()
    try:
        log.delete()
    except Exception:
        pass

    vbat = float(data.get("pm.vbat", float("nan")))
    if use_level and "pm.batteryLevel" in data:
        pct = int(data["pm.batteryLevel"])
    else:
        pct = vbat_to_approx_percent(vbat)

    return vbat, pct


def print_battery_report(uri: str, name: str, vbat: float, pct: int) -> None:
    v_str = f"{vbat:.2f}V" if not math.isnan(vbat) else "N/A"
    status(f"[{name}] Battery  pm.vbat={v_str}  estimated charge≈{pct}%")


def print_low_battery_banner(names: list[str]) -> None:
    red = "\033[1;91m"
    reset = "\033[0m"
    use_color = sys.stdout.isatty()
    r, z = (red, reset) if use_color else ("", "")
    lines = [
        "",
        r + "#" * 72 + z,
        r + "#" + " " * 70 + "#" + z,
        r + "#" + "  WARNING: BATTERY BELOW 25% — PROCEED AT YOUR OWN RISK".ljust(70) + "#" + z,
        r + "#" + f"  Affected: {', '.join(names)}".ljust(70) + "#" + z,
        r + "#" + " " * 70 + "#" + z,
        r + "#" * 72 + z,
        "",
    ]
    for line in lines:
        print(line, flush=True)


def _hl_wait(move_s: float, settle: float, pad: float) -> None:
    """Sleep past the end of an HL trajectory to reduce overlapping ``go_to`` commands."""
    time.sleep(move_s + settle + pad)


def fly_object_round(
    scf: SyncCrazyflie,
    name: str,
    is_drone_a: bool,
    args: argparse.Namespace,
    barrier: threading.Barrier,
) -> None:
    commander = scf.cf.high_level_commander
    pad = args.trajectory_pad

    barrier.wait()
    takeoff_stagger_drone_b(name, args.takeoff_stagger_b)

    status(f"[{name}] Taking off to z={args.height:.2f}m...")
    commander.takeoff(args.height, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.settle)
    time.sleep(args.post_takeoff_hold)

    if args.blue_led and is_drone_a:
        set_bottom_color_led_blue(scf.cf, name)

    if args.start_a is not None and args.start_b is not None:
        sx, sy = args.start_a if is_drone_a else args.start_b
        status(f"[{name}] Moving to world start ({sx:+.2f}, {sy:+.2f}) at z={args.height:.2f}m...")
        commander.go_to(sx, sy, args.height, 0.0, args.position_time, relative=False)
        _hl_wait(args.position_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Leg 1: relative dy={args.dy1:+.2f}m")
    commander.go_to(0.0, args.dy1, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    dx2 = args.dx2_a if is_drone_a else args.dx2_b
    status(f"[{name}] Leg 2: relative dx={dx2:+.2f}m (split around object)")
    commander.go_to(dx2, 0.0, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    dx3 = args.dx3_a if is_drone_a else args.dx3_b
    status(f"[{name}] Leg 3: relative dx={dx3:+.2f}m (return)")
    commander.go_to(dx3, 0.0, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Leg 4: relative dy={args.dy4:+.2f}m")
    commander.go_to(0.0, args.dy4, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Landing...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()
    status(f"[{name}] Done.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Two-drone Lighthouse obstacle detour with pre-flight battery log",
    )
    parser.add_argument("--uri-a", default="radio://0/80/2M/E7E7E7E701", help="Drone A (…01)")
    parser.add_argument("--uri-b", default="radio://0/80/2M/E7E7E7E702", help="Drone B (…02)")
    parser.add_argument(
        "--start-a",
        type=float,
        nargs=2,
        metavar=("X", "Y"),
        default=None,
        help="World-frame XY (m) for A after takeoff; only used when --start-b is also set.",
    )
    parser.add_argument(
        "--start-b",
        type=float,
        nargs=2,
        metavar=("X", "Y"),
        default=None,
        help="World-frame XY (m) for B after takeoff; only used when --start-a is also set.",
    )
    parser.add_argument("--height", type=float, default=0.40)
    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--leg-time", type=float, default=3.0, help="Duration for each relative leg (longer helps 0.8 m legs)")
    parser.add_argument("--position-time", type=float, default=3.0, help="Duration for absolute start goto")
    parser.add_argument("--settle", type=float, default=0.75, help="Pause after each commanded move (before trajectory_pad)")
    parser.add_argument(
        "--trajectory-pad",
        type=float,
        default=0.45,
        help="Extra seconds after each go_to/takeoff-goto to avoid overlapping HL trajectories (cflib warning).",
    )
    parser.add_argument(
        "--post-takeoff-hold",
        type=float,
        default=0.8,
        help="Extra hover time after takeoff before any further high_level commands.",
    )
    parser.add_argument(
        "--takeoff-stagger-b",
        type=float,
        default=1.25,
        help="Seconds drone-b waits after sync before takeoff (E702; eases one-radio contention). Use 0 to match A.",
    )
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    parser.add_argument("--dy1", type=float, default=-0.8, help="First leg: both move this delta-Y (m)")
    parser.add_argument("--dx2-a", type=float, default=-0.4, help="Leg 2 delta-X for drone A")
    parser.add_argument("--dx2-b", type=float, default=-0.8, help="Leg 2 delta-X for drone B")
    parser.add_argument("--dx3-a", type=float, default=0.4, help="Leg 3 delta-X for drone A")
    parser.add_argument("--dx3-b", type=float, default=0.8, help="Leg 3 delta-X for drone B")
    parser.add_argument("--dy4", type=float, default=0.8, help="Leg 4: both move this delta-Y (m)")
    parser.add_argument("--low-battery-pct", type=int, default=LOW_BATTERY_PCT)
    parser.add_argument(
        "--abort-on-low-battery",
        action="store_true",
        help=f"Exit before flight if any drone is below --low-battery-pct (default {LOW_BATTERY_PCT}).",
    )
    parser.add_argument("--no-blue-led", dest="blue_led", action="store_false")
    parser.set_defaults(blue_led=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if (args.start_a is None) ^ (args.start_b is None):
        status("ERROR: provide both --start-a X Y and --start-b X Y, or omit both.")
        return 2

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

        time.sleep(0.3)
        low_names: list[str] = []
        for scf, uri, label in (
            (scf_a, args.uri_a, "drone-a"),
            (scf_b, args.uri_b, "drone-b"),
        ):
            vbat, pct = read_pm_battery(scf.cf, label.replace("-", ""))
            print_battery_report(uri, label, vbat, pct)
            if pct < args.low_battery_pct:
                low_names.append(f"{label} ({pct}%)")

        if low_names:
            print_low_battery_banner(low_names)
            if args.abort_on_low_battery:
                status("Aborting (--abort-on-low-battery).")
                return 1

        configure_drone(scf_a, "drone-a", args.estimator_timeout)
        configure_drone(scf_b, "drone-b", args.estimator_timeout)

        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(
                target=fly_object_round,
                args=(scf_a, "drone-a", True, args, barrier),
            ),
            threading.Thread(
                target=fly_object_round,
                args=(scf_b, "drone-b", False, args, barrier),
            ),
        ]

        status("Starting synchronized object detour...")
        for t in threads:
            t.start()
        for t in threads:
            t.join()

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
