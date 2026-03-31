"""Minimal LPS hover using cflib's PositionHlCommander."""
import time
import sys
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.position_hl_commander import PositionHlCommander
from cflib.utils import uri_helper

cflib.crtp.init_drivers()

URI = "radio://0/80/2M"
HOVER_HEIGHT = 0.25
HOVER_SECONDS = 5
TDOA3_STDDEV = "0.15"
ROBUST_TDOA = "1"
PREFLIGHT_SECONDS = 3.0
PREFLIGHT_XY_SPREAD_MAX_M = 0.20
PREFLIGHT_Z_SPREAD_MAX_M = 0.30
PREFLIGHT_Z_DRIFT_MAX_M = 0.30


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
    cf.param.set_value("tdoa3.stddev", TDOA3_STDDEV)
    cf.param.set_value("kalman.robustTdoa", ROBUST_TDOA)

    reset_estimator(cf)
    wait_for_estimator(cf)

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

    _, start_x, start_y, start_z = flight_data[-1]
    print(f"Starting position: ({start_x:.3f}, {start_y:.3f}, {start_z:.3f})")
    if abs(start_z) > 0.20:
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
            default_height=HOVER_HEIGHT,
            default_velocity=0.2,
            controller=PositionHlCommander.CONTROLLER_PID,
        ) as pc:
            print(f"Hovering at {HOVER_HEIGHT}m for {HOVER_SECONDS}s...")
            time.sleep(HOVER_SECONDS)
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
