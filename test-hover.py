import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander

cflib.crtp.init_drivers()
URI = "radio://0/80/2M"


def wait_for_position_estimator(scf):
    print("Waiting for position estimate to stabilize...")
    log = LogConfig(name="Kalman", period_in_ms=500)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")
    log.add_variable("kalman.varPX", "float")
    log.add_variable("kalman.varPY", "float")
    log.add_variable("kalman.varPZ", "float")

    var_history = []
    stable = False

    def log_callback(timestamp, data, logconf):
        nonlocal stable
        var_x = data["kalman.varPX"]
        var_y = data["kalman.varPY"]
        var_z = data["kalman.varPZ"]
        x = data["kalman.stateX"]
        y = data["kalman.stateY"]
        z = data["kalman.stateZ"]
        var_history.append(var_x + var_y + var_z)
        print(f"  pos=({x:.2f}, {y:.2f}, {z:.2f})  variance={var_x + var_y + var_z:.4f}")
        if len(var_history) > 10:
            recent = var_history[-10:]
            if max(recent) - min(recent) < 0.002 and recent[-1] < 0.05:
                stable = True

    scf.cf.log.add_config(log)
    log.data_received_cb.add_callback(log_callback)
    log.start()

    while not stable:
        time.sleep(0.5)

    log.stop()
    print("Position estimate is stable!")


print("Connecting...")
with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
    wait_for_position_estimator(scf)
    print("Taking off to 0.1m in 3 seconds...")
    print("  Press Ctrl+C at ANY time to kill motors.")
    time.sleep(3)
    try:
        with MotionCommander(scf, default_height=0.2) as mc:
            print("Hovering at 0.1m for 5 seconds...")
            time.sleep(5)
            print("Landing...")
            mc.land()
    except KeyboardInterrupt:
        print("Interrupted -- landing immediately.")
