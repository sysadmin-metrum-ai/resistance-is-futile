"""Take off, move +X, move back, and land using Lighthouse positioning.

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_x_step.py --uri radio://0/80/2M
    uv run python -m tools.lighthouse_demos.lighthouse_x_step.py --uri radio://0/80/2M --height 0.40 --x-distance 0.50
"""

import argparse
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


ESTIMATOR_WINDOW = 10
ESTIMATOR_VARIANCE_RANGE_MAX = 0.001


def status(message: str) -> None:
    print(message, flush=True)


def reset_estimator(cf) -> None:
    status("Resetting Kalman estimator...")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")


def wait_for_estimator(cf, timeout_s: float) -> None:
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
                    status("Estimator converged.")
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crazyflie Lighthouse X-axis step test")
    parser.add_argument("--uri", default="radio://0/80/2M")
    parser.add_argument("--height", type=float, default=0.40, help="Absolute takeoff height in meters")
    parser.add_argument("--x-distance", type=float, default=0.50, help="Relative X movement in meters")
    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--move-time", type=float, default=2.0)
    parser.add_argument("--settle", type=float, default=1.0, help="Seconds to pause after each move")
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    return parser.parse_args(argv)


def run_sequence(cf, args: argparse.Namespace) -> None:
    commander = cf.high_level_commander
    arm_if_supported(cf)

    status(f"Taking off to absolute z={args.height:.2f}m over {args.takeoff_time:.1f}s...")
    commander.takeoff(args.height, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.settle)

    status(f"Moving +X by {args.x_distance:.2f}m over {args.move_time:.1f}s...")
    commander.go_to(args.x_distance, 0.0, 0.0, 0.0, args.move_time, relative=True)
    time.sleep(args.move_time + args.settle)

    status(f"Moving back -X by {args.x_distance:.2f}m over {args.move_time:.1f}s...")
    commander.go_to(-args.x_distance, 0.0, 0.0, 0.0, args.move_time, relative=True)
    time.sleep(args.move_time + args.settle)

    status(f"Landing over {args.land_time:.1f}s...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()


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
            cf.param.set_value("stabilizer.estimator", "2")
            cf.param.set_value("commander.enHighLevel", "1")
            time.sleep(0.5)
            reset_estimator(cf)
            wait_for_estimator(cf, args.estimator_timeout)
            run_sequence(cf, args)
            status("Done.")
            return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt: landing/stopping now.")
        if commander is not None:
            commander.land(0.0, 1.0, yaw=None)
            time.sleep(1.0)
            commander.stop()
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        if commander is not None:
            commander.stop()
        return 1


if __name__ == "__main__":
    sys.exit(main())
