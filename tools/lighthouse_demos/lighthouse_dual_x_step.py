"""Two-Crazyflie Lighthouse relative X-step test.

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_dual_x_step.py
    uv run python -m tools.lighthouse_demos.lighthouse_dual_x_step.py --uri-a radio://0/80/2M/E7E7E7E701 --uri-b radio://0/80/2M/E7E7E7E702
"""

import argparse
import sys
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


ESTIMATOR_WINDOW = 10
ESTIMATOR_VARIANCE_RANGE_MAX = 0.001


def status(message: str) -> None:
    print(message, flush=True)


def cache_dir_for_uri(uri: str) -> str:
    """Per-radio-address TOC cache. Two open links must not share one ``./cache`` (write races)."""
    suffix = uri.rstrip("/").split("/")[-1]
    return f"./cache/{suffix}"


def takeoff_stagger_drone_b(name: str, seconds: float) -> None:
    """Optional delay for …E702 so …E701 can start takeoff on a busy single-radio link."""
    if name == "drone-b" and seconds > 0:
        status(f"[{name}] Takeoff stagger {seconds:.1f}s…")
        time.sleep(seconds)


def reset_estimator(cf, name: str) -> None:
    status(f"[{name}] Resetting Kalman estimator...")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")


def wait_for_estimator(cf, name: str, timeout_s: float) -> None:
    status(f"[{name}] Waiting for Kalman estimator convergence...")
    xs, ys, zs = [], [], []
    logconf = LogConfig(name=f"EstimatorVar{name}", period_in_ms=100)
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
                    status(f"[{name}] Estimator converged.")
                    return
            time.sleep(0.1)
    finally:
        logconf.stop()

    raise RuntimeError(f"[{name}] Kalman estimator did not converge.")


def arm_if_supported(cf, name: str) -> None:
    status(f"[{name}] Sending arming request...")
    if hasattr(cf, "supervisor"):
        cf.supervisor.send_arming_request(True)
    else:
        cf.platform.send_arming_request(True)
    time.sleep(1.0)


def set_bottom_color_led_blue(cf, name: str) -> None:
    status(f"[{name}] Setting bottom Color LED blue...")
    cf.param.set_value("colorLedBot.wrgb8888", "255")
    time.sleep(0.2)


def configure_drone(scf: SyncCrazyflie, name: str, estimator_timeout: float) -> None:
    cf = scf.cf
    status(f"[{name}] Enabling Kalman estimator and high-level commander...")
    cf.param.set_value("stabilizer.estimator", "2")
    cf.param.set_value("commander.enHighLevel", "1")
    time.sleep(0.5)
    reset_estimator(cf, name)
    wait_for_estimator(cf, name, estimator_timeout)
    arm_if_supported(cf, name)


def fly_relative_x(
    scf: SyncCrazyflie,
    name: str,
    x_distance: float,
    args: argparse.Namespace,
    barrier: threading.Barrier,
) -> None:
    commander = scf.cf.high_level_commander

    status(f"[{name}] Ready for synchronized takeoff.")
    barrier.wait()
    takeoff_stagger_drone_b(name, getattr(args, "takeoff_stagger_b", 0.0))
    status(f"[{name}] Taking off to z={args.height:.2f}m...")
    commander.takeoff(args.height, args.takeoff_time, yaw=None)
    time.sleep(args.takeoff_time + args.settle)

    if args.blue_led and name == "drone-a":
        set_bottom_color_led_blue(scf.cf, name)

    status(f"[{name}] Moving relative X by {x_distance:+.2f}m...")
    commander.go_to(x_distance, 0.0, 0.0, 0.0, args.move_time, relative=True)
    time.sleep(args.move_time + args.hold)

    if args.return_home:
        status(f"[{name}] Returning relative X by {-x_distance:+.2f}m...")
        commander.go_to(-x_distance, 0.0, 0.0, 0.0, args.move_time, relative=True)
        time.sleep(args.move_time + args.settle)

    status(f"[{name}] Landing...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()
    status(f"[{name}] Done.")


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
    parser = argparse.ArgumentParser(description="Two-drone simultaneous Lighthouse X-step test")
    parser.add_argument("--uri-a", default="radio://0/80/2M/E7E7E7E701")
    parser.add_argument("--uri-b", default="radio://0/80/2M/E7E7E7E702")
    parser.add_argument("--height", type=float, default=0.40)
    parser.add_argument("--x-distance", type=float, default=0.50)
    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--move-time", type=float, default=2.5)
    parser.add_argument("--hold", type=float, default=1.0, help="Seconds to hold after the X move")
    parser.add_argument("--settle", type=float, default=1.0, help="Seconds to pause after takeoff/return")
    parser.add_argument("--land-time", type=float, default=3.0)
    parser.add_argument("--estimator-timeout", type=float, default=15.0)
    parser.add_argument(
        "--takeoff-stagger-b",
        type=float,
        default=0.0,
        help="Seconds drone-b waits after sync before takeoff (0 = simultaneous).",
    )
    parser.add_argument("--return-home", action="store_true", help="Return both drones to their own start X before landing")
    parser.add_argument("--no-blue-led", dest="blue_led", action="store_false", help="Do not set drone-a bottom Color LED blue")
    parser.set_defaults(blue_led=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
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

        configure_drone(scf_a, "drone-a", args.estimator_timeout)
        configure_drone(scf_b, "drone-b", args.estimator_timeout)

        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(target=fly_relative_x, args=(scf_a, "drone-a", args.x_distance, args, barrier)),
            threading.Thread(target=fly_relative_x, args=(scf_b, "drone-b", -args.x_distance, args, barrier)),
        ]

        status("Starting synchronized two-drone sequence...")
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

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
