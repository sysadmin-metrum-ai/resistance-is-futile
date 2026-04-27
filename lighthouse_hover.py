"""Simple Crazyflie Lighthouse hover test.

Usage:
    uv run python lighthouse_hover.py
    uv run python lighthouse_hover.py --uri radio://0/80/2M --hover-height 0.40
"""

import argparse
import sys
import time
from statistics import mean

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.position_hl_commander import PositionHlCommander


DEFAULT_URI = "radio://0/80/2M/E7E7E7E701"
ESTIMATOR_TIMEOUT_S = 15.0
ESTIMATOR_WINDOW = 10
ESTIMATOR_VARIANCE_RANGE_MAX = 0.001
LOG_PERIOD_MS = 200
GROUND_Z_MAX_ABS = 0.20
DEFAULT_HOVER_HEIGHT = 0.40
DEFAULT_TAKEOFF_VELOCITY = 0.35
DEFAULT_TAKEOFF_SETTLE_S = 2.0
DEFAULT_HOVER_XY_ERROR_MAX = 0.15
DEFAULT_HOVER_Z_ERROR_MAX = 0.15
LAND_VELOCITY = 0.2


def status(message: str) -> None:
    print(message, flush=True)


def reset_estimator(cf) -> None:
    status("Resetting Kalman estimator...")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")


def wait_for_estimator(cf, timeout_s: float = ESTIMATOR_TIMEOUT_S) -> None:
    status("Waiting for Kalman estimator convergence...")
    history_x = []
    history_y = []
    history_z = []
    last_report = 0.0

    logconf = LogConfig(name=f"KalmanVar{int(time.time() * 1000)}", period_in_ms=100)
    logconf.add_variable("kalman.varPX", "float")
    logconf.add_variable("kalman.varPY", "float")
    logconf.add_variable("kalman.varPZ", "float")

    def on_data(_timestamp, data, _logconf):
        history_x.append(float(data["kalman.varPX"]))
        history_y.append(float(data["kalman.varPY"]))
        history_z.append(float(data["kalman.varPZ"]))

    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(on_data)
    logconf.start()
    deadline = time.time() + timeout_s

    try:
        while time.time() < deadline:
            if len(history_x) >= ESTIMATOR_WINDOW:
                range_x = max(history_x[-ESTIMATOR_WINDOW:]) - min(history_x[-ESTIMATOR_WINDOW:])
                range_y = max(history_y[-ESTIMATOR_WINDOW:]) - min(history_y[-ESTIMATOR_WINDOW:])
                range_z = max(history_z[-ESTIMATOR_WINDOW:]) - min(history_z[-ESTIMATOR_WINDOW:])
                now = time.time()
                if now - last_report >= 1.0:
                    status(
                        "Estimator variance ranges: "
                        f"x={range_x:.6f} y={range_y:.6f} z={range_z:.6f}"
                    )
                    last_report = now
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

    raise RuntimeError("Kalman estimator did not converge in time.")


def collect_pose_samples(cf, duration_s: float, period_ms: int = LOG_PERIOD_MS) -> list[tuple[float, float, float]]:
    samples = []
    logconf = LogConfig(name=f"Pose{int(time.time() * 1000)}", period_in_ms=period_ms)
    logconf.add_variable("kalman.stateX", "float")
    logconf.add_variable("kalman.stateY", "float")
    logconf.add_variable("kalman.stateZ", "float")

    def on_data(_timestamp, data, _logconf):
        x = float(data["kalman.stateX"])
        y = float(data["kalman.stateY"])
        z = float(data["kalman.stateZ"])
        samples.append((x, y, z))
        status(f"Preflight pose: x={x:.3f} y={y:.3f} z={z:.3f}")

    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(on_data)
    logconf.start()
    try:
        time.sleep(duration_s)
    finally:
        logconf.stop()
    return samples


def ensure_position_stability(
    samples: list[tuple[float, float, float]],
    xy_spread_max: float,
    z_spread_max: float,
    z_drift_max: float,
    ground_z_max_abs: float = GROUND_Z_MAX_ABS,
) -> tuple[float, float, float]:
    if len(samples) < 5:
        raise RuntimeError(f"Too few preflight pose samples: {len(samples)}")

    xs = [sample[0] for sample in samples]
    ys = [sample[1] for sample in samples]
    zs = [sample[2] for sample in samples]

    x_spread = max(xs) - min(xs)
    y_spread = max(ys) - min(ys)
    xy_spread = max(x_spread, y_spread)
    z_spread = max(zs) - min(zs)
    z_drift = abs(zs[-1] - zs[0])
    origin_x = mean(xs)
    origin_y = mean(ys)
    origin_z = mean(zs)

    status(
        "Preflight summary: "
        f"origin=({origin_x:.3f}, {origin_y:.3f}, {origin_z:.3f}) "
        f"xy_spread={xy_spread:.3f} z_spread={z_spread:.3f} z_drift={z_drift:.3f}"
    )

    if abs(origin_z) > ground_z_max_abs:
        raise RuntimeError(
            f"Ground Z estimate looks wrong: {origin_z:.3f} m exceeds {ground_z_max_abs:.3f} m"
        )
    if xy_spread > xy_spread_max:
        raise RuntimeError(f"XY spread too large: {xy_spread:.3f} m exceeds {xy_spread_max:.3f} m")
    if z_spread > z_spread_max:
        raise RuntimeError(f"Z spread too large: {z_spread:.3f} m exceeds {z_spread_max:.3f} m")
    if z_drift > z_drift_max:
        raise RuntimeError(f"Z drift too large: {z_drift:.3f} m exceeds {z_drift_max:.3f} m")

    return origin_x, origin_y, origin_z


def pose_error(
    target_x: float,
    target_y: float,
    target_z: float,
    measured_x: float,
    measured_y: float,
    measured_z: float,
) -> tuple[float, float]:
    xy_error = ((measured_x - target_x) ** 2 + (measured_y - target_y) ** 2) ** 0.5
    z_error = abs(measured_z - target_z)
    return xy_error, z_error


def monitor_hover(
    cf,
    commander: PositionHlCommander,
    target_x: float,
    target_y: float,
    target_z: float,
    duration_s: float,
    xy_error_max: float,
    z_error_max: float,
    z_grace_s: float,
) -> None:
    latest_pose = [None]
    logconf = LogConfig(name=f"HoverPose{int(time.time() * 1000)}", period_in_ms=100)
    logconf.add_variable("kalman.stateX", "float")
    logconf.add_variable("kalman.stateY", "float")
    logconf.add_variable("kalman.stateZ", "float")

    def on_data(_timestamp, data, _logconf):
        latest_pose[0] = (
            float(data["kalman.stateX"]),
            float(data["kalman.stateY"]),
            float(data["kalman.stateZ"]),
        )

    cf.log.add_config(logconf)
    logconf.data_received_cb.add_callback(on_data)
    logconf.start()
    start_time = time.time()
    deadline = time.time() + duration_s

    try:
        while time.time() < deadline:
            if latest_pose[0] is not None:
                measured_x, measured_y, measured_z = latest_pose[0]
                xy_error, z_error = pose_error(
                    target_x,
                    target_y,
                    target_z,
                    measured_x,
                    measured_y,
                    measured_z,
                )
                status(
                    "Hover pose: "
                    f"x={measured_x:.3f} y={measured_y:.3f} z={measured_z:.3f} "
                    f"xy_error={xy_error:.3f} z_error={z_error:.3f}"
                )
                z_grace_elapsed = time.time() - start_time >= z_grace_s
                if xy_error > xy_error_max or (z_grace_elapsed and z_error > z_error_max):
                    status("Hover error exceeded limit, landing now.")
                    commander.land(velocity=LAND_VELOCITY)
                    raise RuntimeError(
                        f"Unsafe hover error: xy={xy_error:.3f} m, z={z_error:.3f} m"
                    )
            time.sleep(0.25)
    finally:
        logconf.stop()


def try_arm(cf) -> None:
    try:
        status("Sending arming request...")
        cf.platform.send_arming_request(True)
        time.sleep(1.0)
    except Exception as exc:
        status(f"Arming request skipped: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Very simple Crazyflie Lighthouse hover test")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Crazyflie radio URI")
    parser.add_argument("--hover-height", type=float, default=DEFAULT_HOVER_HEIGHT, help="Hover height in meters")
    parser.add_argument("--hover-duration", type=float, default=5.0, help="Hover time in seconds")
    parser.add_argument(
        "--takeoff-velocity",
        type=float,
        default=DEFAULT_TAKEOFF_VELOCITY,
        help="Takeoff velocity in meters per second",
    )
    parser.add_argument(
        "--takeoff-settle",
        type=float,
        default=DEFAULT_TAKEOFF_SETTLE_S,
        help="Seconds to allow Z to settle after takeoff before enforcing Z hover error",
    )
    parser.add_argument("--preflight-duration", type=float, default=3.0, help="Pose observation time in seconds")
    parser.add_argument("--xy-spread-max", type=float, default=0.10, help="Maximum allowed XY spread in meters")
    parser.add_argument("--z-spread-max", type=float, default=0.10, help="Maximum allowed Z spread in meters")
    parser.add_argument("--z-drift-max", type=float, default=0.08, help="Maximum allowed Z drift in meters")
    parser.add_argument(
        "--hover-xy-error-max",
        type=float,
        default=DEFAULT_HOVER_XY_ERROR_MAX,
        help="Maximum allowed in-flight XY hover error in meters",
    )
    parser.add_argument(
        "--hover-z-error-max",
        type=float,
        default=DEFAULT_HOVER_Z_ERROR_MAX,
        help="Maximum allowed in-flight Z hover error in meters",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cflib.crtp.init_drivers()
    status(f"Connecting to {args.uri}...")

    cf = None
    try:
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            cf = scf.cf
            status("Connected.")
            status("Configuring estimator and high-level commander...")
            cf.param.set_value("stabilizer.estimator", "2")
            cf.param.set_value("commander.enHighLevel", "1")
            time.sleep(0.2)

            reset_estimator(cf)
            wait_for_estimator(cf)

            status(f"Observing pose stability for {args.preflight_duration:.1f} s...")
            samples = collect_pose_samples(cf, args.preflight_duration)
            hover_x, hover_y, hover_z = ensure_position_stability(
                samples=samples,
                xy_spread_max=args.xy_spread_max,
                z_spread_max=args.z_spread_max,
                z_drift_max=args.z_drift_max,
            )

            try_arm(cf)

            commander = PositionHlCommander(
                scf,
                x=hover_x,
                y=hover_y,
                z=hover_z,
                default_height=args.hover_height,
                default_velocity=args.takeoff_velocity,
                controller=PositionHlCommander.CONTROLLER_PID,
            )

            status(
                "Takeoff approved. "
                f"Holding x={hover_x:.3f}, y={hover_y:.3f} and rising to z={args.hover_height:.3f} "
                f"at {args.takeoff_velocity:.2f} m/s..."
            )
            commander.take_off(height=args.hover_height, velocity=args.takeoff_velocity)
            commander.go_to(hover_x, hover_y, args.hover_height)
            status(f"Hovering for {args.hover_duration:.1f} s...")
            monitor_hover(
                cf=cf,
                commander=commander,
                target_x=hover_x,
                target_y=hover_y,
                target_z=args.hover_height,
                duration_s=args.hover_duration,
                xy_error_max=args.hover_xy_error_max,
                z_error_max=args.hover_z_error_max,
                z_grace_s=args.takeoff_settle,
            )
            status("Landing...")
            commander.land(velocity=LAND_VELOCITY)
            status("Flight complete.")
            return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt received, sending stop setpoint.")
        if cf is not None:
            try:
                cf.commander.send_stop_setpoint()
                time.sleep(0.1)
            except Exception:
                pass
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        if cf is not None:
            try:
                cf.commander.send_stop_setpoint()
                time.sleep(0.1)
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
