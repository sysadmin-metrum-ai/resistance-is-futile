"""Eight Crazyflies — basic row-height X split.

Starting layout is your 3-2-3 floor grid:

    row 1: drones 01, 02, 03   takeoff to z=0.30
    row 2: drones 04, 05       takeoff to z=0.70
    row 3: drones 06, 07, 08   takeoff to z=1.10

After takeoff, the script samples each drone's current Kalman pose and treats that
as "home". Then:

    row 1 goes to absolute x = +1.0
    row 2 holds its sampled home position
    row 3 goes to absolute x = -1.0
    row 1 / row 3 return to their sampled home x
    all land

Blue bottom LED blink starts exactly when the movement phase starts and turns off
right before landing.

Usage:

    uv run python -m tools.lighthouse_demos.lighthouse_oct_row_x_split.py

Optional safer first run:

    uv run python -m tools.lighthouse_demos.lighthouse_oct_row_x_split.py --row1-target-x 0.5 --row3-target-x -0.5 --move-time 8
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from tools.lighthouse_demos.lighthouse_dual_x_step import cache_dir_for_uri
from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_dual_x_step import stop_all
from tools.lighthouse_demos.lighthouse_oct_common import add_oct_uri_args
from tools.lighthouse_demos.lighthouse_oct_common import collect_uris_from_args
from tools.lighthouse_demos.lighthouse_oct_common import configure_all_oct_drones


N = 8
BLUE_WRGB8888 = "255"
LED_OFF = "0"


def bottom_led(cf: Crazyflie, value: str) -> None:
    try:
        cf.param.set_value("colorLedBot.wrgb8888", value)
    except Exception:
        pass


def blink_blue(cf: Crazyflie, stop: threading.Event, half_period_s: float) -> None:
    lit = True
    while not stop.is_set():
        bottom_led(cf, BLUE_WRGB8888 if lit else LED_OFF)
        if stop.wait(max(0.08, half_period_s)):
            break
        lit = not lit
    bottom_led(cf, LED_OFF)


def read_kalman_xyz(cf: Crazyflie, token: str, sample_s: float) -> tuple[float, float, float]:
    data: dict[str, float] = {}

    def on_data(_timestamp: int, d: dict, _logconf: LogConfig) -> None:
        data["x"] = float(d["kalman.stateX"])
        data["y"] = float(d["kalman.stateY"])
        data["z"] = float(d["kalman.stateZ"])

    logconf = LogConfig(name=f"RowSplit{token}{int(time.time() * 1000) % 100000}", period_in_ms=50)
    logconf.add_variable("kalman.stateX", "float")
    logconf.add_variable("kalman.stateY", "float")
    logconf.add_variable("kalman.stateZ", "float")
    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(on_data)
    logconf.start()
    time.sleep(sample_s)
    logconf.stop()
    try:
        logconf.delete()
    except Exception:
        pass

    if not data:
        raise RuntimeError("No Kalman pose sample received")
    return data["x"], data["y"], data["z"]


def row_height(ix: int, args: argparse.Namespace) -> float:
    if ix <= 2:
        return args.row1_z
    if ix <= 4:
        return args.row2_z
    return args.row3_z


def target_x(ix: int, home_x: float, args: argparse.Namespace) -> float:
    if ix <= 2:
        return args.row1_target_x
    if ix <= 4:
        return home_x
    return args.row3_target_x


def fly_worker(
    scf: SyncCrazyflie,
    name: str,
    ix: int,
    args: argparse.Namespace,
    barriers: dict[str, threading.Barrier],
) -> None:
    cf = scf.cf
    hlc = cf.high_level_commander
    z = row_height(ix, args)

    barriers["ready"].wait()

    status(f"[{name}] Takeoff z={z:.2f}m ...")
    hlc.takeoff(z, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.post_takeoff_hold + args.settle)

    status(f"[{name}] Sampling home pose ...")
    home_x, home_y, _home_z = read_kalman_xyz(cf, name[-2:], args.pose_sample_s)
    status(f"[{name}] Home approx ({home_x:+.2f}, {home_y:+.2f}, {z:.2f})")

    barriers["sampled"].wait()

    blink_stop = threading.Event()
    blink_thread = threading.Thread(
        target=blink_blue,
        args=(cf, blink_stop, args.led_blink_half_period),
        name=f"{name}-blink",
        daemon=True,
    )
    blink_thread.start()

    tx = target_x(ix, home_x, args)
    barriers["pre_move"].wait()

    if ix in (3, 4):
        status(f"[{name}] Row 2 hold at home ...")
    else:
        status(f"[{name}] Move to x={tx:+.2f} ...")
    hlc.go_to(tx, home_y, z, 0.0, args.move_time, relative=False)
    time.sleep(args.move_time + args.settle + args.trajectory_pad)

    barriers["at_target"].wait()
    time.sleep(args.hold_at_target)

    barriers["pre_return"].wait()

    status(f"[{name}] Return/hold home ...")
    hlc.go_to(home_x, home_y, z, 0.0, args.return_time, relative=False)
    time.sleep(args.return_time + args.settle + args.trajectory_pad)

    barriers["returned"].wait()

    blink_stop.set()
    blink_thread.join(timeout=3.0)
    bottom_led(cf, LED_OFF)
    time.sleep(0.08)

    status(f"[{name}] Land ...")
    hlc.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time + 0.35)
    hlc.stop()

    barriers["landed"].wait()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Eight-drone basic row-height X split")
    add_oct_uri_args(parser)

    parser.add_argument("--row1-z", type=float, default=0.30, help="Drones 01-03 takeoff/flight height.")
    parser.add_argument("--row2-z", type=float, default=0.70, help="Drones 04-05 hover height.")
    parser.add_argument("--row3-z", type=float, default=1.10, help="Drones 06-08 takeoff/flight height.")
    parser.add_argument("--row1-target-x", type=float, default=1.0, help="Absolute X target for drones 01-03.")
    parser.add_argument("--row3-target-x", type=float, default=-1.0, help="Absolute X target for drones 06-08.")

    parser.add_argument("--takeoff-time", type=float, default=2.8)
    parser.add_argument("--post-takeoff-hold", type=float, default=0.8)
    parser.add_argument("--move-time", type=float, default=7.0)
    parser.add_argument("--return-time", type=float, default=7.0)
    parser.add_argument("--hold-at-target", type=float, default=2.0)
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--settle", type=float, default=0.75)
    parser.add_argument("--trajectory-pad", type=float, default=0.5)
    parser.add_argument("--pose-sample-s", type=float, default=0.4)
    parser.add_argument("--estimator-timeout", type=float, default=25.0)
    parser.add_argument(
        "--configure-batch-size",
        type=int,
        default=1,
        help="Configure N drones at a time; default 1 is safest for one Crazyradio.",
    )
    parser.add_argument("--led-blink-half-period", type=float, default=0.35)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    cflib.crtp.init_drivers()
    uris = collect_uris_from_args(args)
    names = tuple(f"drone-{i:02d}" for i in range(1, 9))
    scfs: list[SyncCrazyflie] = []

    barriers = {
        "ready": threading.Barrier(N),
        "sampled": threading.Barrier(N),
        "pre_move": threading.Barrier(N),
        "at_target": threading.Barrier(N),
        "pre_return": threading.Barrier(N),
        "returned": threading.Barrier(N),
        "landed": threading.Barrier(N),
    }

    try:
        print(__doc__)
        for i, uri in enumerate(uris, start=1):
            status(f"[drone-{i:02d}] Connecting {uri} ...")
            scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
            scf.open_link()
            scfs.append(scf)

        configure_all_oct_drones(
            scfs,
            names,
            args.estimator_timeout,
            batch_size=int(args.configure_batch_size or 1),
        )

        threads = [
            threading.Thread(target=fly_worker, args=(scfs[i], names[i], i, args, barriers), name=names[i])
            for i in range(N)
        ]

        status("Starting row X split sequence.")
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status("All complete.")
    except KeyboardInterrupt:
        status("Interrupted - requesting land/stop.")
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
