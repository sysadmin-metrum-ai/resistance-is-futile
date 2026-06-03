"""Shared helpers for eight-Crazyflie Lighthouse shows (channel 80, …E701–…E708).

Barriers keep phases aligned across eight threads. Each pattern script defines
rally homes and waypoint sets; this module runs the mission.

Anti-wake: patterns should avoid stacking multiple props over the same (x, y);
prefer row offsets in +X and modest altitude separation.

Each pattern defines eight **rally (x, y)** homes: place that physical drone on that pad so
takeoff is mostly vertical and the first ``go_to`` does not cross through another craft. Random
placement works poorly for tight shows (long cross-field moves, estimator/Lighthouse confusion,
collision risk).

**One Crazyradio, eight links:** Kalman convergence uses logging on every link at once. Running all
eight ``configure_drone`` calls in parallel often **starves** later addresses so 07–08 finish late
while 01–06 are already idle — then anything that assumed “everyone ready” together misbehaves.
Default is **serial** configure (``--configure-batch-size 1``); try **2–4** for a compromise, or **8**
only if you have proven airtime headroom.
"""

from __future__ import annotations

import argparse
import threading
import time
from typing import Callable, Sequence

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from tools.lighthouse_demos.lighthouse_dual_x_step import cache_dir_for_uri
from tools.lighthouse_demos.lighthouse_dual_x_step import configure_drone
from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_dual_x_step import stop_all

OCT_N = 8

Vec3 = tuple[float, float, float]

# Bottom Color deck — same convention as ``lighthouse_dual_x_step.set_bottom_color_led_blue``.
_BOTTOM_LED_PARAM = "colorLedBot.wrgb8888"
_BLUE_WRGB8888 = "255"
_LED_OFF = "0"


def _bottom_led(cf: Crazyflie, value: str) -> None:
    try:
        cf.param.set_value(_BOTTOM_LED_PARAM, value)
    except Exception:
        pass


def _blue_blink_worker(cf: Crazyflie, stop: threading.Event, half_period_s: float) -> None:
    lit = True
    while not stop.is_set():
        _bottom_led(cf, _BLUE_WRGB8888 if lit else _LED_OFF)
        if stop.wait(max(0.08, half_period_s)):
            break
        lit = not lit
    _bottom_led(cf, _LED_OFF)


def default_uri_80(drone_suffix: int) -> str:
    """Crazyradio 0, datarate 2M, channel 80, address E7E7E7E7XX."""
    if not 1 <= drone_suffix <= 8:
        raise ValueError("drone id must be 1..8")
    return f"radio://0/80/2M/E7E7E7E7{drone_suffix:02d}"


def default_uris_01_08() -> tuple[str, ...]:
    return tuple(default_uri_80(i) for i in range(1, 9))


def hl_pause(move_s: float, settle: float, pad: float) -> None:
    time.sleep(move_s + settle + pad)


def add_oct_uri_args(p: argparse.ArgumentParser) -> None:
    for i in range(1, 9):
        p.add_argument(
            f"--uri-{i:02d}",
            dest=f"uri_{i:02d}",
            default=default_uri_80(i),
            help=f"Drone {i:02d} (default channel 80)",
        )


def collect_uris_from_args(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(getattr(args, f"uri_{i:02d}") for i in range(1, 9))


def add_oct_timing_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--hover-z", type=float, default=0.55, help="Rally / cruise height (m).")
    p.add_argument("--takeoff-time", type=float, default=2.8)
    p.add_argument("--post-takeoff-hold", type=float, default=0.85)
    p.add_argument("--move-time", type=float, default=7.0, help="HL go_to duration between poses.")
    p.add_argument("--settle", type=float, default=0.75)
    p.add_argument("--trajectory-pad", type=float, default=0.5)
    p.add_argument("--hold-first", type=float, default=4.0, help="Hold at first formation (s).")
    p.add_argument("--hold-mid", type=float, default=2.5, help="Hold at intermediate formations (s).")
    p.add_argument("--home-return-time", type=float, default=7.0)
    p.add_argument("--land-time", type=float, default=3.0)
    p.add_argument("--estimator-timeout", type=float, default=25.0)
    p.add_argument(
        "--takeoff-stagger-step",
        type=float,
        default=0.0,
        help="Drone k waits k*step seconds after sync before takeoff (single-radio relief).",
    )
    p.add_argument(
        "--land-stagger-step",
        type=float,
        default=0.0,
        help="Drone k waits k*step seconds before land() after sync.",
    )
    p.add_argument(
        "--led-blink-half-period",
        type=float,
        default=0.35,
        help="Bottom LED blue blink half-period (s) after takeoff until just before land.",
    )
    p.add_argument(
        "--no-led-blink",
        dest="led_blink",
        action="store_false",
        help="Disable bottom Color LED blue blink.",
    )
    p.set_defaults(led_blink=True)
    p.add_argument(
        "--configure-batch-size",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Run estimator+arm configure for N drones at a time (1=one-by-one, default, safest on "
            "one Crazyradio; 2–4=batched parallel; 8=all parallel, can starve late addresses)."
        ),
    )


def add_wave332_row_args(p: argparse.ArgumentParser) -> None:
    """3-2-3 wave pad geometry (shared by ``lighthouse_oct_wave_332`` and ``--rally-wave332``)."""
    p.add_argument("--row1-x", type=float, default=-0.70, help="Wave row of three (01–03) X (m).")
    p.add_argument("--row2-x", type=float, default=-0.05, help="Wave row of two (04–05) X (m).")
    p.add_argument("--row3-x", type=float, default=0.60, help="Wave row of three (06–08) X (m).")
    p.add_argument(
        "--y-span-outer",
        type=float,
        default=0.65,
        help="Wave |y| for wing drones on 3-drone rows (01/03, 06/08).",
    )
    p.add_argument(
        "--y-span-mid",
        type=float,
        default=0.40,
        help="Wave |y| for middle-row drones (04/05).",
    )


def build_wave332_homes(
    hz: float,
    row1_x: float,
    row2_x: float,
    row3_x: float,
    y_span_outer: float,
    y_span_mid: float,
) -> tuple[Vec3, ...]:
    yo, ym = y_span_outer, y_span_mid
    return (
        (row1_x, -yo, hz),
        (row1_x, 0.0, hz),
        (row1_x, yo, hz),
        (row2_x, -ym, hz),
        (row2_x, ym, hz),
        (row3_x, -yo, hz),
        (row3_x, 0.0, hz),
        (row3_x, yo, hz),
    )


def formation_wave332(
    z_back: float,
    z_mid: float,
    z_front: float,
    row1_x: float,
    row2_x: float,
    row3_x: float,
    y_span_outer: float,
    y_span_mid: float,
    dx: float,
) -> tuple[Vec3, ...]:
    yo, ym = y_span_outer, y_span_mid
    xb, xm, xf = row1_x + dx, row2_x + dx, row3_x + dx
    return (
        (xb, -yo, z_back),
        (xb, 0.0, z_back),
        (xb, yo, z_back),
        (xm, -ym, z_mid),
        (xm, ym, z_mid),
        (xf, -yo, z_front),
        (xf, 0.0, z_front),
        (xf, yo, z_front),
    )


def configure_all_oct_drones(
    scfs: Sequence[SyncCrazyflie],
    names: Sequence[str],
    estimator_timeout: float,
    batch_size: int,
) -> None:
    if len(scfs) != OCT_N or len(names) != OCT_N:
        raise ValueError("need 8 links and 8 names")

    batch = max(1, min(OCT_N, int(batch_size)))

    if batch == 1:
        status("Configuring drones one at a time (batch size 1)…")
        for scf, name in zip(scfs, names):
            configure_drone(scf, name, estimator_timeout)
        status("All drones configured.")
        return

    if batch >= OCT_N:
        status("Configuring all 8 drones in parallel (estimator + arm)…")
    else:
        status(f"Configuring drones in parallel batches of {batch}…")

    errors: list[BaseException] = []
    lock = threading.Lock()

    def _one(scf: SyncCrazyflie, name: str) -> None:
        try:
            configure_drone(scf, name, estimator_timeout)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    for start in range(0, OCT_N, batch):
        end = min(start + batch, OCT_N)
        workers = [
            threading.Thread(target=_one, args=(scfs[i], names[i]), name=f"cfg-{names[i]}")
            for i in range(start, end)
        ]
        for t in workers:
            t.start()
        for t in workers:
            t.join()
        if errors:
            raise errors[0]

    status("All drones configured.")


def fly_worker_oct(
    scf: SyncCrazyflie,
    name: str,
    drone_ix: int,
    home: Vec3,
    waypoints: Sequence[Sequence[Vec3]],
    hold_after_wp: Sequence[float],
    args: argparse.Namespace,
    barriers: dict[str, threading.Barrier],
) -> None:
    hlc = scf.cf.high_level_commander
    hz = args.hover_z
    settle, pad = args.settle, args.trajectory_pad
    move_s = args.move_time

    takeoff_stagger = drone_ix * float(args.takeoff_stagger_step)
    land_stagger = drone_ix * float(args.land_stagger_step)
    blink_stop: threading.Event | None = None
    blink_thread: threading.Thread | None = None

    barriers["ready"].wait()
    if takeoff_stagger > 0:
        time.sleep(takeoff_stagger)

    status(f"[{name}] Takeoff z={hz:.2f}m …")
    hlc.takeoff(hz, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.post_takeoff_hold + settle)

    if getattr(args, "led_blink", True):
        blink_stop = threading.Event()
        blink_thread = threading.Thread(
            target=_blue_blink_worker,
            args=(scf.cf, blink_stop, float(args.led_blink_half_period)),
            name=f"{name}-led-blink",
            daemon=True,
        )
        blink_thread.start()

    barriers["post_takeoff"].wait()

    status(f"[{name}] Rally go_to …")
    hlc.go_to(home[0], home[1], home[2], 0.0, move_s, relative=False)
    hl_pause(move_s, settle, pad)

    barriers["at_rally"].wait()

    for wi in range(len(waypoints)):
        tgt = waypoints[wi][drone_ix]
        status(f"[{name}] Formation {wi + 1}/{len(waypoints)} go_to …")
        hlc.go_to(tgt[0], tgt[1], tgt[2], 0.0, move_s, relative=False)
        hl_pause(move_s, settle, pad)
        barriers[f"wp_{wi}"].wait()
        hold = hold_after_wp[wi] if wi < len(hold_after_wp) else args.hold_mid
        time.sleep(hold)
        barriers[f"post_hold_{wi}"].wait()

    barriers["pre_home"].wait()

    status(f"[{name}] Return rally …")
    hlc.go_to(home[0], home[1], home[2], 0.0, args.home_return_time, relative=False)
    hl_pause(args.home_return_time, settle, pad)

    barriers["home_met"].wait()

    if land_stagger > 0:
        time.sleep(land_stagger)

    if blink_stop is not None:
        blink_stop.set()
    if blink_thread is not None:
        blink_thread.join(timeout=3.0)
    _bottom_led(scf.cf, _LED_OFF)
    time.sleep(0.08)

    status(f"[{name}] Land …")
    hlc.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time + 0.4)
    hlc.stop()

    barriers["landed"].wait()


def build_barriers_for_waypoints(n_waypoints: int) -> dict[str, threading.Barrier]:
    parts: dict[str, threading.Barrier] = {
        "ready": threading.Barrier(OCT_N),
        "post_takeoff": threading.Barrier(OCT_N),
        "at_rally": threading.Barrier(OCT_N),
        "pre_home": threading.Barrier(OCT_N),
        "home_met": threading.Barrier(OCT_N),
        "landed": threading.Barrier(OCT_N),
    }
    for i in range(n_waypoints):
        parts[f"wp_{i}"] = threading.Barrier(OCT_N)
        parts[f"post_hold_{i}"] = threading.Barrier(OCT_N)
    return parts


def run_oct_mission(
    uris: tuple[str, ...],
    homes: Sequence[Vec3],
    waypoints: Sequence[Sequence[Vec3]],
    hold_after_wp: Sequence[float],
    args: argparse.Namespace,
    preamble: Callable[[], None] | None = None,
) -> None:
    if len(uris) != OCT_N or len(homes) != OCT_N:
        raise ValueError("need exactly 8 URIs and 8 home positions")
    for w in waypoints:
        if len(w) != OCT_N:
            raise ValueError("each waypoint set must have 8 positions")

    cflib.crtp.init_drivers()
    scfs: list[SyncCrazyflie] = []
    names = tuple(f"drone-{i:02d}" for i in range(1, 9))

    barriers = build_barriers_for_waypoints(len(waypoints))

    try:
        if preamble:
            preamble()

        for ix, (label, uri) in enumerate(zip(range(1, 9), uris)):
            status(f"[drone-{label:02d}] Connecting {uri}…")
            scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
            scf.open_link()
            scfs.append(scf)

        configure_all_oct_drones(
            scfs,
            names,
            args.estimator_timeout,
            batch_size=int(getattr(args, "configure_batch_size", 1) or 1),
        )

        threads = [
            threading.Thread(
                target=fly_worker_oct,
                args=(
                    scfs[i],
                    names[i],
                    i,
                    homes[i],
                    waypoints,
                    hold_after_wp,
                    args,
                    barriers,
                ),
                name=names[i],
            )
            for i in range(OCT_N)
        ]

        status("Eight-drone show: threads start.")
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status("All complete.")
    except KeyboardInterrupt:
        status("Interrupted — land/stop.")
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