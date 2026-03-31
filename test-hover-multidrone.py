"""Two-drone sequential hover test with collision avoidance."""
import argparse
import time
import sys
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig

cflib.crtp.init_drivers()

TDOA3_STDDEV = "0.80"


def parse_args():
    parser = argparse.ArgumentParser(description="Two-drone hover smoke test")
    parser.add_argument("--uri1", default="radio://0/80/2M")
    parser.add_argument("--uri2", default="radio://0/90/2M")
    parser.add_argument("--hover-height", type=float, default=0.4)
    parser.add_argument("--min-separation", type=float, default=0.50)
    return parser.parse_args()


args = parse_args()
DRONES = {
    "drone1": args.uri1,
    "drone2": args.uri2,
}


def reset_and_wait(cf, name):
    cf.param.set_value("loco.mode", "3")
    cf.param.set_value("tdoa3.stddev", TDOA3_STDDEV)
    cf.param.set_value("kalman.robustTdoa", "0")
    cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    cf.param.set_value("kalman.resetEstimation", "0")

    print(f"  [{name}] Waiting for estimator...")
    log = LogConfig(name="K", period_in_ms=100)
    log.add_variable("kalman.varPX", "float")
    log.add_variable("kalman.varPY", "float")
    log.add_variable("kalman.varPZ", "float")

    history = []
    stable = False

    def cb(ts, data, lc):
        nonlocal stable
        v = data["kalman.varPX"] + data["kalman.varPY"] + data["kalman.varPZ"]
        history.append(v)
        if len(history) > 10:
            recent = history[-10:]
            if max(recent) - min(recent) < 0.001:
                stable = True

    cf.log.add_config(log)
    log.data_received_cb.add_callback(cb)
    log.start()

    deadline = time.time() + 30
    while not stable and time.time() < deadline:
        time.sleep(0.1)
    log.stop()

    if not stable:
        print(f"  [{name}] ERROR: Estimator did not converge. Aborting.")
        sys.exit(1)
    print(f"  [{name}] Estimator converged.")


def get_position(cf):
    pos = [None]
    log = LogConfig(name="P", period_in_ms=100)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")

    def cb(ts, data, lc):
        pos[0] = (data["kalman.stateX"], data["kalman.stateY"], data["kalman.stateZ"])

    cf.log.add_config(log)
    log.data_received_cb.add_callback(cb)
    log.start()
    time.sleep(0.5)
    log.stop()
    return pos[0]


def distance(a, b):
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5


print("Connecting to both drones...")
scf1 = SyncCrazyflie(DRONES["drone1"], cf=Crazyflie(rw_cache="./cache"))
scf2 = SyncCrazyflie(DRONES["drone2"], cf=Crazyflie(rw_cache="./cache"))

scf1.open_link()
print(f"  drone1 connected on {DRONES['drone1']}")
scf2.open_link()
print(f"  drone2 connected on {DRONES['drone2']}")

try:
    cf1 = scf1.cf
    cf2 = scf2.cf

    reset_and_wait(cf1, "drone1")
    reset_and_wait(cf2, "drone2")

    pos1 = get_position(cf1)
    pos2 = get_position(cf2)
    sep = distance(pos1, pos2)
    print(f"\n  drone1 at ({pos1[0]:.3f}, {pos1[1]:.3f}, {pos1[2]:.3f})")
    print(f"  drone2 at ({pos2[0]:.3f}, {pos2[1]:.3f}, {pos2[2]:.3f})")
    print(f"  Separation: {sep:.3f}m")

    if sep < args.min_separation:
        print(f"  ERROR: Drones too close ({sep:.3f}m < {args.min_separation}m). Move them apart.")
        sys.exit(1)

    cf1.param.set_value("commander.enHighLevel", "1")
    cf2.param.set_value("commander.enHighLevel", "1")
    hlc1 = cf1.high_level_commander
    hlc2 = cf2.high_level_commander

    print("\n--- Drone 1: takeoff ---")
    hlc1.takeoff(args.hover_height, 2.0)
    time.sleep(3)

    print("--- Drone 1: hovering | Drone 2: takeoff ---")
    hlc2.takeoff(args.hover_height, 2.0)
    time.sleep(3)

    print("--- Both hovering for 3s ---")
    time.sleep(3)

    print("--- Drone 1: landing ---")
    hlc1.land(0.0, 3.0)
    time.sleep(4)
    hlc1.stop()

    print("--- Drone 2: landing ---")
    hlc2.land(0.0, 3.0)
    time.sleep(4)
    hlc2.stop()

    print("\nDone.")

except KeyboardInterrupt:
    print("\nABORT -- killing all motors")
    try:
        scf1.cf.commander.send_stop_setpoint()
    except:
        pass
    try:
        scf2.cf.commander.send_stop_setpoint()
    except:
        pass

finally:
    scf1.close_link()
    scf2.close_link()
