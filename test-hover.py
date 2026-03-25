"""Minimal LPS hover using the Bitcraze autonomous example pattern."""
import time
import sys
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig

cflib.crtp.init_drivers()
URI = "radio://0/80/2M"
TAKEOFF_HEIGHT_M = 0.25
TAKEOFF_DURATION_S = 3.0
PREFLIGHT_SECONDS = 3.0
PREFLIGHT_XY_SPREAD_MAX_M = 0.20
PREFLIGHT_Z_SPREAD_MAX_M = 0.15
PREFLIGHT_Z_DRIFT_MAX_M = 0.12


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
            min_x = min(var_x_history[-10:])
            max_x = max(var_x_history[-10:])
            min_y = min(var_y_history[-10:])
            max_y = max(var_y_history[-10:])
            min_z = min(var_z_history[-10:])
            max_z = max(var_z_history[-10:])
            if (max_x - min_x) < threshold and (max_y - min_y) < threshold and (max_z - min_z) < threshold:
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
    print("Kalman variance converged (not a position-stability guarantee).")


def ensure_position_stability(flight_data):
    if len(flight_data) < 8:
        print("ERROR: Not enough preflight samples; aborting takeoff.")
        sys.exit(2)

    xs = [x for _, x, _, _ in flight_data]
    ys = [y for _, _, y, _ in flight_data]
    zs = [z for _, _, _, z in flight_data]
    x_spread = max(xs) - min(xs)
    y_spread = max(ys) - min(ys)
    z_spread = max(zs) - min(zs)
    z_drift = abs(zs[-1] - zs[0])

    print(
        f"Preflight spread: x={x_spread:.3f}m y={y_spread:.3f}m "
        f"z={z_spread:.3f}m z_drift={z_drift:.3f}m"
    )

    if (
        max(x_spread, y_spread) > PREFLIGHT_XY_SPREAD_MAX_M
        or z_spread > PREFLIGHT_Z_SPREAD_MAX_M
        or z_drift > PREFLIGHT_Z_DRIFT_MAX_M
    ):
        print("ERROR: Localization unstable; refusing takeoff.")
        sys.exit(2)


print("Connecting...")
with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
    cf = scf.cf

    cf.param.set_value("loco.mode", "3")
    cf.param.set_value("tdoa3.stddev", "0.15")
    cf.param.set_value("kalman.robustTdoa", "0")

    reset_estimator(cf)
    wait_for_estimator(cf)

    cf.param.set_value("commander.enHighLevel", "1")

    log_flight = LogConfig(name="Flight", period_in_ms=200)
    log_flight.add_variable("kalman.stateX", "float")
    log_flight.add_variable("kalman.stateY", "float")
    log_flight.add_variable("kalman.stateZ", "float")

    flight_data = []

    def flight_cb(timestamp, data, logconf):
        x = data["kalman.stateX"]
        y = data["kalman.stateY"]
        z = data["kalman.stateZ"]
        flight_data.append((time.time(), x, y, z))

    cf.log.add_config(log_flight)
    log_flight.data_received_cb.add_callback(flight_cb)
    log_flight.start()

    print(f"Running preflight stability check ({PREFLIGHT_SECONDS:.0f}s)...")
    time.sleep(PREFLIGHT_SECONDS)
    ensure_position_stability(flight_data)

    print("Taking off...")

    commander = cf.high_level_commander

    try:
        commander.takeoff(TAKEOFF_HEIGHT_M, TAKEOFF_DURATION_S)
        time.sleep(3)

        print("Hovering 5s...")
        time.sleep(5)

        print("Landing...")
        commander.land(0.0, 3.0)
        time.sleep(4)

        commander.stop()
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
