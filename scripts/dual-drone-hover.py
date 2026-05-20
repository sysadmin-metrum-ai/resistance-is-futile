#!/usr/bin/env python3
"""Bare-metal two-drone hover test using cflib directly."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

DEFAULT_URI_A = "radio://0/80/2M/E7E7E7E704"
DEFAULT_URI_B = "radio://1/90/2M/E7E7E7E709"


def _load_single_drone_helpers():
    script_path = Path(__file__).with_name("single-drone-takeoff.py")
    spec = importlib.util.spec_from_file_location("single_drone_takeoff_helpers", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_single = _load_single_drone_helpers()
wait_for_estimator = _single.wait_for_estimator
read_pose = _single.read_pose


def cache_dir_for_uri(uri: str) -> str:
    return f"./cache/{uri.rstrip('/').split('/')[-1]}"


def status(message: str) -> None:
    print(message, flush=True)


def arm_if_supported(cf) -> None:
    if hasattr(cf, "supervisor"):
        cf.supervisor.send_arming_request(True)
    else:
        cf.platform.send_arming_request(True)
    time.sleep(1.0)


def prepare_drone(name: str, scf: SyncCrazyflie, estimator_timeout: float) -> None:
    cf = scf.cf
    status(f"[{name}] enable Kalman estimator + high-level commander")
    cf.param.set_value("stabilizer.estimator", "2")
    cf.param.set_value("commander.enHighLevel", "1")
    time.sleep(0.5)
    status(f"[{name}] reset Kalman estimator")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")
    status(f"[{name}] wait for variance convergence")
    wait_for_estimator(cf, estimator_timeout)
    x, y, z = read_pose(cf)
    status(f"[{name}] pose x={x:.3f} y={y:.3f} z={z:.3f}")
    status(f"[{name}] arm motors")
    arm_if_supported(cf)


def hover_drone(name: str, scf: SyncCrazyflie, args: argparse.Namespace, barrier: threading.Barrier) -> None:
    commander = scf.cf.high_level_commander
    status(f"[{name}] ready for synchronized takeoff")
    barrier.wait()
    status(f"[{name}] takeoff -> {args.height:.2f}m, hover {args.hover:.1f}s")
    commander.takeoff(args.height, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.settle)
    time.sleep(args.hover)
    status(f"[{name}] land")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time + args.settle)
    commander.stop()
    status(f"[{name}] done")


def stop_all(scfs: list[SyncCrazyflie]) -> None:
    for scf in scfs:
        try:
            scf.cf.high_level_commander.land(0.0, 1.0, yaw=None)
        except Exception:
            pass
    time.sleep(1.0)
    for scf in scfs:
        try:
            scf.cf.high_level_commander.stop()
        except Exception:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Two-drone synchronized Lighthouse hover test")
    parser.add_argument("--uri-a", default=DEFAULT_URI_A)
    parser.add_argument("--uri-b", default=DEFAULT_URI_B)
    parser.add_argument("--height", type=float, default=1.0)
    parser.add_argument("--hover", type=float, default=5.0)
    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--land-time", type=float, default=2.5)
    parser.add_argument("--settle", type=float, default=0.3)
    parser.add_argument("--estimator-timeout", type=float, default=8.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    scfs: list[SyncCrazyflie] = []
    try:
        for name, uri in (("drone-a", args.uri_a), ("drone-b", args.uri_b)):
            status(f"[{name}] opening link to {uri}")
            scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
            scf.open_link()
            scfs.append(scf)
            prepare_drone(name, scf, args.estimator_timeout)
        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(target=hover_drone, args=("drone-a", scfs[0], args, barrier)),
            threading.Thread(target=hover_drone, args=("drone-b", scfs[1], args, barrier)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
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
