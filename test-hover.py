"""Minimal LPS hover using cflib's PositionHlCommander."""
import argparse
import time
import sys
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.position_hl_commander import PositionHlCommander

from src.services.preflight_logic import (
    PositionSample,
    PositionStabilityThresholds,
    evaluate_position_stability,
    format_position_metrics,
)

cflib.crtp.init_drivers()

TDOA3_STDDEV = "0.15"
ROBUST_TDOA = "1"


def reset_estimator(cf):
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")
    time.sleep(2)


def wait_for_estimator(cf):
    print("Waiting for estimator to converge...")
    log = LogConfig(name="Kalman", period_in_ms=100)
    log.add_variable("kalman.varPX", "float")
    log.add_variable("kalman.varPY", "float")
    log.add_variable("kalman.varPZ", "float")

    var_y_history = []
    var_x_history = []
    var_z_history = []
    threshold = 0.001
    is_stable = False

    def cb(timestamp, data, logconf):
        nonlocal is_stable
        var_x_history.append(data["kalman.varPX"])
        var_y_history.append(data["kalman.varPY"])
        var_z_history.append(data["kalman.varPZ"])
        if len(var_x_history) > 10:
            if (
                max(var_x_history[-10:]) - min(var_x_history[-10:]) < threshold
                and max(var_y_history[-10:]) - min(var_y_history[-10:]) < threshold
                and max(var_z_history[-10:]) - min(var_z_history[-10:]) < threshold
            ):
                is_stable = True

    cf.log.add_config(log)
    log.data_received_cb.add_callback(cb)
    log.start()

    timeout = time.time() + 20
    while not is_stable and time.time() < timeout:
        time.sleep(0.1)
    log.stop()

    if not is_stable:
        print("ERROR: Kalman variance did not converge. Aborting.")
        sys.exit(1)
    print("Estimator converged.")


def parse_args():
    parser = argparse.ArgumentParser(description="Single-drone LPS hover litmus test")
    parser.add_argument("--uri", default="radio://0/80/2M")
    parser.add_argument("--hover-height", type=float, default=0.25)
    parser.add_argument("--hover-seconds", type=float, default=5.0)
    parser.add_argument("--preflight-seconds", type=float, default=3.0)
    parser.add_argument("--xy-spread-max", type=float, default=0.20)
    parser.add_argument("--z-spread-max", type=float, default=0.30)
    parser.add_argument("--z-drift-max", type=float, default=0.30)
    parser.add_argument("--ground-z-max", type=float, default=0.20)
    return parser.parse_args()


args = parse_args()

print("Connecting...")
with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
    cf = scf.cf

    cf.param.set_value("loco.mode", "3")
    cf.param.set_value("tdoa3.stddev", TDOA3_STDDEV)
    cf.param.set_value("kalman.robustTdoa", ROBUST_TDOA)

    reset_estimator(cf)
    wait_for_estimator(cf)

    log_flight = LogConfig(name="Flight", period_in_ms=200)
    log_flight.add_variable("kalman.stateX", "float")
    log_flight.add_variable("kalman.stateY", "float")
    log_flight.add_variable("kalman.stateZ", "float")
    flight_data: list[tuple[float, float, float, float]] = []

    def flight_cb(timestamp, data, logconf):
        x = data["kalman.stateX"]
        y = data["kalman.stateY"]
        z = data["kalman.stateZ"]
        flight_data.append((time.time(), x, y, z))

    cf.log.add_config(log_flight)
    log_flight.data_received_cb.add_callback(flight_cb)
    log_flight.start()

    print(f"Running preflight stability check ({args.preflight_seconds:.0f}s)...")
    time.sleep(args.preflight_seconds)
    stability = evaluate_position_stability(
        [PositionSample(x=x, y=y, z=z) for _, x, y, z in flight_data],
        PositionStabilityThresholds(
            required_samples=8,
            xy_spread_max_m=args.xy_spread_max,
            z_spread_max_m=args.z_spread_max,
            z_drift_max_m=args.z_drift_max,
            ground_z_abs_max_m=args.ground_z_max,
        ),
    )
    print(format_position_metrics(stability.metrics))
    if not stability.ok:
        for reason in stability.reasons:
            print(f"ERROR: {reason}")
        sys.exit(2)

    _, start_x, start_y, start_z = flight_data[-1]
    print(f"Starting position: ({start_x:.3f}, {start_y:.3f}, {start_z:.3f})")
    if abs(start_z) > args.ground_z_max:
        print(f"ERROR: Bad ground pose estimate (z={start_z:.3f}). Aborting.")
        sys.exit(2)

    try:
        cf.platform.send_arming_request(True)
        time.sleep(0.3)
    except Exception:
        pass

    try:
        with PositionHlCommander(
            scf,
            x=start_x,
            y=start_y,
            default_height=args.hover_height,
            default_velocity=0.2,
            controller=PositionHlCommander.CONTROLLER_PID,
        ) as pc:
            print(f"Hovering at {args.hover_height}m for {args.hover_seconds:.0f}s...")
            time.sleep(args.hover_seconds)
            print("Landing...")
        print("Done.")
    except KeyboardInterrupt:
        print("ABORT")
        cf.commander.send_stop_setpoint()
        time.sleep(0.1)

    log_flight.stop()

    if flight_data:
        t0 = flight_data[0][0]
        print(f"\n{'t':>5}  {'X':>7}  {'Y':>7}  {'Z':>7}")
        for t, x, y, z in flight_data:
            print(f"{t-t0:5.1f}  {x:+7.3f}  {y:+7.3f}  {z:+7.3f}")
