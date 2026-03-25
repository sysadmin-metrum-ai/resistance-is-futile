import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig

cflib.crtp.init_drivers()
URI = "radio://0/90/2M"

print("Connecting...")
with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
    cf = scf.cf

    # Check LPS mode
    try:
        mode = cf.param.get_value("loco.mode")
        print(f"LPS mode: {mode} (0=auto, 1=TWR, 2=TDoA2, 3=TDoA3)")
    except Exception as e:
        print(f"Could not read loco.mode: {e}")

    # Check estimator
    try:
        estimator = cf.param.get_value("stabilizer.estimator")
        print(f"Estimator: {estimator} (1=complementary, 2=kalman)")
    except Exception as e:
        print(f"Could not read estimator: {e}")

    # Position + ranging log
    log_pos = LogConfig(name="Position", period_in_ms=200)
    log_pos.add_variable("kalman.stateX", "float")
    log_pos.add_variable("kalman.stateY", "float")
    log_pos.add_variable("kalman.stateZ", "float")
    log_pos.add_variable("kalman.varPX", "float")
    log_pos.add_variable("kalman.varPY", "float")
    log_pos.add_variable("kalman.varPZ", "float")

    # Ranging distances to each anchor
    log_range = LogConfig(name="Ranging", period_in_ms=500)
    for i in range(7):
        log_range.add_variable(f"ranging.distance{i}", "float")

    positions = []
    ranges_data = []

    def pos_cb(timestamp, data, logconf):
        x = data["kalman.stateX"]
        y = data["kalman.stateY"]
        z = data["kalman.stateZ"]
        vx = data["kalman.varPX"]
        vy = data["kalman.varPY"]
        vz = data["kalman.varPZ"]
        positions.append((x, y, z))
        print(f"  pos=({x:+.3f}, {y:+.3f}, {z:+.3f})  var=({vx:.4f}, {vy:.4f}, {vz:.4f})  total_var={vx+vy+vz:.4f}")

    def range_cb(timestamp, data, logconf):
        parts = []
        for i in range(7):
            d = data[f"ranging.distance{i}"]
            if d > 0:
                parts.append(f"A{i}={d:.3f}")
            else:
                parts.append(f"A{i}=---")
        ranges_data.append(data)
        print(f"  ranges: {' | '.join(parts)}")

    cf.log.add_config(log_pos)
    log_pos.data_received_cb.add_callback(pos_cb)
    log_pos.start()

    cf.log.add_config(log_range)
    log_range.data_received_cb.add_callback(range_cb)
    log_range.start()

    print("\nMonitoring for 10 seconds (drone on ground, no takeoff)...\n")
    time.sleep(10)

    log_pos.stop()
    log_range.stop()

    # Summary
    if positions:
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        zs = [p[2] for p in positions]
        print(f"\n=== Position Summary (n={len(positions)}) ===")
        print(f"  X: mean={sum(xs)/len(xs):+.3f}  min={min(xs):+.3f}  max={max(xs):+.3f}  spread={max(xs)-min(xs):.3f}")
        print(f"  Y: mean={sum(ys)/len(ys):+.3f}  min={min(ys):+.3f}  max={max(ys):+.3f}  spread={max(ys)-min(ys):.3f}")
        print(f"  Z: mean={sum(zs)/len(zs):+.3f}  min={min(zs):+.3f}  max={max(zs):+.3f}  spread={max(zs)-min(zs):.3f}")

    if ranges_data:
        print(f"\n=== Ranging Summary ===")
        for i in range(7):
            vals = [d[f"ranging.distance{i}"] for d in ranges_data if d[f"ranging.distance{i}"] > 0]
            if vals:
                avg = sum(vals) / len(vals)
                spread = max(vals) - min(vals)
                print(f"  Anchor {i}: avg={avg:.3f}m  spread={spread:.3f}m  samples={len(vals)}/{len(ranges_data)}")
            else:
                print(f"  Anchor {i}: NO RANGING DATA")
