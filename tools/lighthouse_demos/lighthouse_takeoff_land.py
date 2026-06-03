"""Minimal Lighthouse takeoff/land check.

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_takeoff_land.py --uri radio://0/80/2M
    uv run python -m tools.lighthouse_demos.lighthouse_takeoff_land.py --uri radio://0/80/2M --height 0.35 --hold 2
    uv run python -m tools.lighthouse_demos.lighthouse_takeoff_land.py --uri radio://0/80/2M --height 0.80 --hold 5 --takeoff-time 3.5 --land-time 4.0s
"""

import argparse
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


DEFAULT_URI = "radio://0/80/2M"
DEFAULT_HEIGHT = 0.35
DEFAULT_HOLD_S = 2.0
DEFAULT_TAKEOFF_S = 2.0
DEFAULT_LAND_S = 2.0
ESTIMATOR_TIMEOUT_S = 15.0
ESTIMATOR_WINDOW = 10
ESTIMATOR_VARIANCE_RANGE_MAX = 0.001


def status(message: str) -> None:
    print(message, flush=True)


def reset_estimator(cf) -> None:
    status("Resetting Kalman estimator...")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")


def wait_for_estimator(cf, timeout_s: float = ESTIMATOR_TIMEOUT_S) -> None:
    status("Waiting for Kalman estimator convergence...")
    xs, ys, zs = [], [], []
    logconf = LogConfig(name=f"EstimatorVar{int(time.time() * 1000)}", period_in_ms=100)
    logconf.add_variable("kalman.varPX", "float")
    logconf.add_variable("kalman.varPY", "float")
    logconf.add_variable("kalman.varPZ", "float")

    def on_data(_timestamp, data, _logconf):
        xs.append(float(data["kalman.varPX"]))
        ys.append(float(data["kalman.varPY"]))
        zs.append(float(data["kalman.varPZ"]))

    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(on_data)
    logconf.start()
    deadline = time.time() + timeout_s

    try:
        while time.time() < deadline:
            if len(xs) >= ESTIMATOR_WINDOW:
                range_x = max(xs[-ESTIMATOR_WINDOW:]) - min(xs[-ESTIMATOR_WINDOW:])
                range_y = max(ys[-ESTIMATOR_WINDOW:]) - min(ys[-ESTIMATOR_WINDOW:])
                range_z = max(zs[-ESTIMATOR_WINDOW:]) - min(zs[-ESTIMATOR_WINDOW:])
                if (
                    range_x < ESTIMATOR_VARIANCE_RANGE_MAX
                    and range_y < ESTIMATOR_VARIANCE_RANGE_MAX
                    and range_z < ESTIMATOR_VARIANCE_RANGE_MAX
                ):
                    status(
                        "Estimator converged: "
                        f"var_ranges=({range_x:.6f}, {range_y:.6f}, {range_z:.6f})"
                    )
                    return
            time.sleep(0.1)
    finally:
        logconf.stop()

    raise RuntimeError("Kalman estimator did not converge.")


def arm_if_supported(cf) -> None:
    status("Sending arming request...")
    if hasattr(cf, "supervisor"):
        cf.supervisor.send_arming_request(True)
    else:
        cf.platform.send_arming_request(True)
    time.sleep(1.0)


def stop_commander(commander) -> None:
    if commander is not None:
        commander.stop()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal Crazyflie Lighthouse takeoff/land check")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--height", type=float, default=DEFAULT_HEIGHT, help="Absolute takeoff height in meters")
    parser.add_argument("--hold", type=float, default=DEFAULT_HOLD_S, help="Seconds to wait before landing")
    parser.add_argument("--takeoff-time", type=float, default=DEFAULT_TAKEOFF_S, help="Takeoff duration in seconds")
    parser.add_argument("--land-time", type=float, default=DEFAULT_LAND_S, help="Landing duration in seconds")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    commander = None

    try:
        status(f"Connecting to {args.uri}...")
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            cf = scf.cf
            commander = cf.high_level_commander
            status("Connected.")
            status("Enabling Kalman estimator and high-level commander...")
            cf.param.set_value("stabilizer.estimator", "2")
            cf.param.set_value("commander.enHighLevel", "1")
            time.sleep(0.5)

            reset_estimator(cf)
            wait_for_estimator(cf)
            arm_if_supported(cf)

            status(f"Taking off to absolute z={args.height:.2f}m over {args.takeoff_time:.1f}s...")
            commander.takeoff(args.height, args.takeoff_time, yaw=None)
            time.sleep(args.takeoff_time)

            status(f"Holding for {args.hold:.1f}s...")
            time.sleep(args.hold)

            status(f"Landing over {args.land_time:.1f}s...")
            commander.land(0.0, args.land_time, yaw=None)
            time.sleep(args.land_time)
            commander.stop()
            status("Done.")
            return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt: landing/stopping now.")
        if commander is not None:
            try:
                commander.land(0.0, 1.0, yaw=None)
                time.sleep(1.0)
                commander.stop()
            except Exception:
                stop_commander(commander)
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        stop_commander(commander)
        return 1


if __name__ == "__main__":
    sys.exit(main())
