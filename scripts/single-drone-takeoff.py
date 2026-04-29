#!/usr/bin/env python3
"""Bare-metal single-drone takeoff test using cflib directly.

Mirrors the proven configure_drone sequence from
lighthouse_dual_x_step.py: estimator + HL commander -> reset Kalman ->
WAIT for variance convergence (proves Lighthouse is feeding pose) ->
arm via supervisor -> takeoff. Will refuse to fly if the estimator does
not converge within the timeout.

Usage:
    uv run python scripts/single-drone-takeoff.py radio://0/80/2M/E7E7E7E701
"""

from __future__ import annotations

import argparse
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


VARIANCE_WINDOW = 10
VARIANCE_THRESHOLD = 0.001
POST_CONVERGE_SETTLE_S = 0.5


def wait_for_estimator(cf, timeout_s: float) -> tuple[float, float, float]:
    """Block until kalman.varP[XYZ] are stable, return last (vx, vy, vz)."""
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    log = LogConfig(name="EstimatorVar", period_in_ms=100)
    log.add_variable("kalman.varPX", "float")
    log.add_variable("kalman.varPY", "float")
    log.add_variable("kalman.varPZ", "float")

    def on_data(_ts, data, _conf) -> None:
        xs.append(float(data["kalman.varPX"]))
        ys.append(float(data["kalman.varPY"]))
        zs.append(float(data["kalman.varPZ"]))

    cf.log.add_config(log)
    log.data_received_cb.add_callback(on_data)
    log.start()
    try:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if (
                len(xs) >= VARIANCE_WINDOW
                and max(xs[-VARIANCE_WINDOW:]) - min(xs[-VARIANCE_WINDOW:]) < VARIANCE_THRESHOLD
                and max(ys[-VARIANCE_WINDOW:]) - min(ys[-VARIANCE_WINDOW:]) < VARIANCE_THRESHOLD
                and max(zs[-VARIANCE_WINDOW:]) - min(zs[-VARIANCE_WINDOW:]) < VARIANCE_THRESHOLD
            ):
                time.sleep(POST_CONVERGE_SETTLE_S)
                return xs[-1], ys[-1], zs[-1]
            time.sleep(0.1)
        raise RuntimeError(f"kalman variance did not converge in {timeout_s}s")
    finally:
        log.stop()
        try:
            log.delete()
        except Exception:
            pass


def read_pose(cf, sample_s: float = 0.5) -> tuple[float, float, float]:
    """Read current Lighthouse-fused pose. Raises if no sample arrives."""
    sample: dict = {}
    log = LogConfig(name="PoseSample", period_in_ms=100)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")

    def on_data(_ts, data, _conf) -> None:
        sample.update(data)

    cf.log.add_config(log)
    log.data_received_cb.add_callback(on_data)
    log.start()
    try:
        time.sleep(sample_s)
        if not sample:
            raise RuntimeError("no pose samples received - is the Lighthouse deck attached?")
        return (
            float(sample["kalman.stateX"]),
            float(sample["kalman.stateY"]),
            float(sample["kalman.stateZ"]),
        )
    finally:
        log.stop()
        try:
            log.delete()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uri", help="Crazyflie URI, e.g. radio://0/80/2M/E7E7E7E701")
    parser.add_argument("--height", type=float, default=0.5, help="Absolute takeoff height in meters")
    parser.add_argument("--hover", type=float, default=2.0, help="Hover seconds")
    parser.add_argument("--estimator-timeout", type=float, default=8.0)
    args = parser.parse_args()

    print("[1/8] init drivers")
    cflib.crtp.init_drivers()

    print(f"[2/8] opening link to {args.uri}")
    t0 = time.monotonic()
    cf = Crazyflie(rw_cache="./cache/single")
    with SyncCrazyflie(args.uri, cf=cf) as scf:
        print(f"      link up in {time.monotonic() - t0:.2f}s")
        cf = scf.cf

        print("[3/8] enable Kalman estimator + high-level commander")
        cf.param.set_value("stabilizer.estimator", "2")
        cf.param.set_value("commander.enHighLevel", "1")
        time.sleep(0.5)

        print("[4/8] reset Kalman estimator")
        cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(0.1)
        cf.param.set_value("kalman.resetEstimation", "0")

        print(f"[5/8] wait for variance convergence (max {args.estimator_timeout}s)")
        t1 = time.monotonic()
        wait_for_estimator(cf, args.estimator_timeout)
        print(f"      converged in {time.monotonic() - t1:.2f}s")

        print("[6/8] read Lighthouse pose")
        x, y, z = read_pose(cf)
        print(f"      pose x={x:.3f} y={y:.3f} z={z:.3f}")
        if z > 0.30:
            print(f"      WARNING: z={z:.3f}m looks too high for a grounded drone; check Lighthouse calibration")

        print("[7/8] arm motors")
        if hasattr(cf, "supervisor"):
            cf.supervisor.send_arming_request(True)
        else:
            cf.platform.send_arming_request(True)
        time.sleep(1.0)

        print(f"[8/8] takeoff -> {args.height}m, hover {args.hover}s, land")
        commander = cf.high_level_commander
        commander.takeoff(args.height, 2.5)
        time.sleep(2.5 + 0.3)
        time.sleep(args.hover)
        commander.land(0.0, 2.5)
        time.sleep(2.5 + 0.3)
        commander.stop()
        print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
