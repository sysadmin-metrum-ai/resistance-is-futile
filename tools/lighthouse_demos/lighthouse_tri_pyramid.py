"""Three Crazyflies: Lighthouse pyramid — synchronized parallel flight phases.

Starts from quadrant rally positions; all phases use ``threading.Barrier(3)`` so takeoff,
rally pose, pyramid move, LEDs, return-to-home go_to, and land start together (subject to
same-radio jitter — use thin ``--takeoff-delay-*`` only if the link flakes).

Assignments (apex vs bases) minimize total Euclidean move from measured Kalman poses to
triangle targets:

  Apex: (tip_x, tip_y, tip_z) — default z = 1.0 m
  Base +Y / −Y: (tip_x, ±half_span, base_z)

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_tri_pyramid.py
    uv run python -m tools.lighthouse_demos.lighthouse_tri_pyramid.py --skip-lights

Lights: only ``colorLedBot.wrgb8888`` is used (bottom Color deck LED). Older scripts
referenced ``led_ring.*`` params; stock firmware often has **no** LED-ring deck TOC
entries — cflib would log “Unable to find variable …” even before our code caught
failures — so ring params are not set here anymore.
"""

from __future__ import annotations

import argparse
import itertools
import math
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from tools.lighthouse_demos.lighthouse_dual_x_step import cache_dir_for_uri
from tools.lighthouse_demos.lighthouse_dual_x_step import configure_drone
from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_dual_x_step import stop_all

Vec3 = tuple[float, float, float]

ROLE_IDX_TIP = 0
ROLE_IDX_BASE_PY = 1
ROLE_IDX_BASE_MY = 2


def _dist3(a: Vec3, b: Vec3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def read_kalman_xyz(cf: Crazyflie, token: str, sample_s: float = 0.45) -> Vec3:
    data: dict = {}

    def _cb(_ts: int, d: dict, _lc: LogConfig) -> None:
        data.update(d)

    log = LogConfig(name=f"KTri{token}{int(time.time() * 1000) % 100000}", period_in_ms=50)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")
    cf.log.add_config(log)
    log.data_received_cb.add_callback(_cb)
    log.start()
    time.sleep(sample_s)
    log.stop()
    try:
        log.delete()
    except Exception:
        pass

    return (
        float(data.get("kalman.stateX", 0.0)),
        float(data.get("kalman.stateY", 0.0)),
        float(data.get("kalman.stateZ", 0.0)),
    )


def optimal_assignment(measured: list[Vec3], targets: list[Vec3]) -> tuple[list[int], float]:
    n = len(measured)
    best_cost = float("inf")
    best_perm: list[int] | None = None
    for tup in itertools.permutations(range(n)):
        sigma = list(tup)
        cost = sum(_dist3(measured[i], targets[sigma[i]]) for i in range(n))
        if cost < best_cost:
            best_cost = cost
            best_perm = sigma
    assert best_perm is not None
    return best_perm, best_cost


def _hl_pause(move_s: float, settle: float, pad: float) -> None:
    time.sleep(move_s + settle + pad)


def role_label(role_ix: int) -> str:
    return ("apex", "base +y", "base −y")[role_ix]


# Packed WRGB (~RGB yellow 0xFFFF00); Crazyflie bottom Color deck accepts uint32 decimal str.
YELLOW_WRGB_DEC = "16776960"


def set_bottom_led_yellow(cf: Crazyflie, name: str) -> None:
    status(f"[{name}] Bottom Color LED yellow …")
    try:
        cf.param.set_value("colorLedBot.wrgb8888", YELLOW_WRGB_DEC)
        time.sleep(0.12)
    except Exception as exc:
        status(f"[{name}] colorLedBot skipped: {exc}")


def turn_off_bottom_led(cf: Crazyflie, name: str) -> None:
    status(f"[{name}] Bottom Color LED off …")
    try:
        cf.param.set_value("colorLedBot.wrgb8888", "0")
        time.sleep(0.06)
    except Exception:
        pass


def fly_worker(
    scf: SyncCrazyflie,
    name: str,
    drone_ix: int,
    args: argparse.Namespace,
    nominal: tuple[Vec3, Vec3, Vec3],
    pyramid_targets: tuple[Vec3, Vec3, Vec3],
    measured_xyz: list[Vec3 | None],
    perm_holder: dict[str, object],
    barriers: dict[str, threading.Barrier],
) -> None:
    """One thread per drone; barriers keep phases aligned."""
    hlc = scf.cf.high_level_commander
    hz = args.hover_z
    settle, pad = args.settle, args.trajectory_pad

    barriers["ready"].wait()
    if args.takeoff_stagger[drone_ix] > 0:
        time.sleep(args.takeoff_stagger[drone_ix])

    status(f"[{name}] Takeoff z={hz:.2f}m …")
    hlc.takeoff(hz, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.post_takeoff_hold + settle)

    barriers["post_takeoff"].wait()

    tg = nominal[drone_ix]
    status(f"[{name}] Rally go_to …")
    hlc.go_to(tg[0], tg[1], tg[2], 0.0, args.rally_time, relative=False)
    _hl_pause(args.rally_time, settle, pad)

    measured_xyz[drone_ix] = read_kalman_xyz(scf.cf, name[:4])

    barriers["sampled"].wait()

    perm: list[int] = perm_holder["perm"]  # filled by barrier action
    role_ix = perm[drone_ix]
    target = pyramid_targets[role_ix]
    move_s = args.into_tip_time if role_ix == ROLE_IDX_TIP else args.into_time

    barriers["assigned"].wait()

    status(f"[{name}] Pyramid go_to ({role_label(role_ix)}) …")
    hlc.go_to(target[0], target[1], target[2], 0.0, move_s, relative=False)
    _hl_pause(move_s, settle, pad)

    barriers["pyramid_met"].wait()

    time.sleep(args.pyramid_hold_s)

    barriers["pre_light"].wait()

    if args.lights:
        set_bottom_led_yellow(scf.cf, name)

    barriers["lit"].wait()

    barriers["dwell"].wait()
    time.sleep(args.after_lights_hold_s)

    barriers["pre_turn_off"].wait()
    if args.lights:
        turn_off_bottom_led(scf.cf, name)
    barriers["lights_dark"].wait()

    barriers["pre_return"].wait()

    hom = nominal[drone_ix]
    status(f"[{name}] Returning home rally …")
    hlc.go_to(hom[0], hom[1], hom[2], 0.0, args.home_return_time, relative=False)
    _hl_pause(args.home_return_time, settle, pad)

    barriers["home_met"].wait()

    if args.land_stagger[drone_ix] > 0:
        time.sleep(args.land_stagger[drone_ix])

    status(f"[{name}] Land …")
    hlc.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time + 0.35)
    hlc.stop()

    barriers["landed"].wait()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lighthouse three-drone pyramid (synced parallel)")
    parser.add_argument("--uri-a", dest="uri_a", default="radio://0/80/2M/E7E7E7E701")
    parser.add_argument("--uri-b", dest="uri_b", default="radio://0/80/2M/E7E7E7E702")
    parser.add_argument("--uri-c", dest="uri_c", default="radio://0/80/2M/E7E7E7E703")

    parser.add_argument("--home-a", nargs=2, type=float, default=[-0.5, 0.5], metavar=("X", "Y"))
    parser.add_argument("--home-b", nargs=2, type=float, default=[-0.5, 0.0], metavar=("X", "Y"))
    parser.add_argument("--home-c", nargs=2, type=float, default=[-0.5, -0.5], metavar=("X", "Y"))

    parser.add_argument("--hover-z", type=float, default=0.55, help="Rally / takeoff height (m).")

    parser.add_argument("--tip-z", dest="tip_z", type=float, default=1.0)
    parser.add_argument("--base-z", dest="base_z", type=float, default=0.5)

    parser.add_argument("--pyramid-tip-x", type=float, default=0.5)
    parser.add_argument("--pyramid-tip-y", type=float, default=0.0)
    parser.add_argument("--py-half-span", type=float, default=0.5)

    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--post-takeoff-hold", type=float, default=0.7)
    parser.add_argument("--rally-time", type=float, default=5.0)

    parser.add_argument("--into-time", type=float, default=6.5, help="Base roles go_to duration (s).")
    parser.add_argument("--into-tip-time", type=float, default=8.5, help="Apex go_to duration (s).")

    parser.add_argument("--settle", type=float, default=0.75)
    parser.add_argument("--trajectory-pad", type=float, default=0.45)

    parser.add_argument(
        "--takeoff-delay-b",
        type=float,
        default=0.0,
        help="Optional delay (s) before B takeoff after barrier (if radio needs it).",
    )
    parser.add_argument(
        "--takeoff-delay-c",
        type=float,
        default=0.0,
        help="Optional delay (s) before C takeoff after barrier.",
    )
    parser.add_argument(
        "--land-delay-b",
        type=float,
        default=0.0,
        help="Optional delay (s) before B land command.",
    )
    parser.add_argument(
        "--land-delay-c",
        type=float,
        default=0.0,
        help="Optional delay (s) before C land command.",
    )

    parser.add_argument("--home-return-time", type=float, default=6.5)
    parser.add_argument("--pyramid-hold", type=float, dest="pyramid_hold_s", default=3.0)
    parser.add_argument("--after-lights-hold", type=float, dest="after_lights_hold_s", default=2.0)

    parser.add_argument("--estimator-timeout", type=float, default=22.0)
    parser.add_argument("--land-time", type=float, default=3.0)

    parser.add_argument("--skip-lights", dest="lights", action="store_false", default=True)

    args = parser.parse_args(argv)

    setattr(
        args,
        "takeoff_stagger",
        (0.0, float(args.takeoff_delay_b), float(args.takeoff_delay_c)),
    )
    setattr(args, "land_stagger", (0.0, float(args.land_delay_b), float(args.land_delay_c)))
    return args


def run(args: argparse.Namespace) -> None:
    cflib.crtp.init_drivers()

    uri_list = (args.uri_a, args.uri_b, args.uri_c)
    hz = args.hover_z
    names = ("drone-a", "drone-b", "drone-c")

    scfs: list[SyncCrazyflie] = []

    nominal = (
        (args.home_a[0], args.home_a[1], hz),
        (args.home_b[0], args.home_b[1], hz),
        (args.home_c[0], args.home_c[1], hz),
    )

    pyramid_targets = (
        (args.pyramid_tip_x, args.pyramid_tip_y, args.tip_z),
        (args.pyramid_tip_x, args.py_half_span, args.base_z),
        (args.pyramid_tip_x, -args.py_half_span, args.base_z),
    )

    measured_xyz: list[Vec3 | None] = [None, None, None]
    perm_holder: dict[str, object] = {"perm": None}

    def _assign_action() -> None:
        m = [measured_xyz[0], measured_xyz[1], measured_xyz[2]]
        assert all(x is not None for x in m)
        perm, cost = optimal_assignment([m[0], m[1], m[2]], list(pyramid_targets))
        perm_holder["perm"] = perm
        lines = [f"{names[k]} → {role_label(perm[k])}" for k in range(3)]
        status(f"Assignments (min Σ distance ≈ {cost:.3f} m)")
        status(" · " + "; ".join(lines))

    barriers = {
        "ready": threading.Barrier(3),
        "post_takeoff": threading.Barrier(3),
        "sampled": threading.Barrier(3, action=_assign_action),
        "assigned": threading.Barrier(3),
        "pyramid_met": threading.Barrier(3),
        "pre_light": threading.Barrier(3),
        "lit": threading.Barrier(3),
        "dwell": threading.Barrier(3),
        "pre_turn_off": threading.Barrier(3),
        "lights_dark": threading.Barrier(3),
        "pre_return": threading.Barrier(3),
        "home_met": threading.Barrier(3),
        "landed": threading.Barrier(3),
    }

    try:
        for label, uri in zip(("a", "b", "c"), uri_list):
            status(f"[drone-{label}] Connecting {uri}…")
            scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
            scf.open_link()
            scfs.append(scf)

        for scf, name in zip(scfs, names):
            configure_drone(scf, name, args.estimator_timeout)

        threads = [
            threading.Thread(
                target=fly_worker,
                args=(scfs[i], names[i], i, args, nominal, pyramid_targets, measured_xyz, perm_holder, barriers),
                name=names[i],
            )
            for i in range(3)
        ]

        status("Parallel pyramid run (barrier-synced phases).")
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status("All complete.")
    except KeyboardInterrupt:
        status("Interrupted — requesting land/stop on known links.")
        stop_all(scfs)
        raise
    except Exception:
        stop_all(scfs)
        raise
    finally:
        for scf in scfs:
            try:
                scf.close_link()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run(args)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
