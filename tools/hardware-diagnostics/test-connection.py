import sys
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

cflib.crtp.init_drivers()

available = cflib.crtp.scan_interfaces()
if not available:
    print("No Crazyflie found.")
    sys.exit(1)
URI = available[0][0]

print("Scanning for Crazyflie drones...")
available = cflib.crtp.scan_interfaces()
if available:
    for i in available:
        print(f"  Found: {i[0]}")
else:
    print("  No Crazyflie found.")
    sys.exit(1)

print(f"\nConnecting to {URI}...")
try:
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
        print("Connected!")
        print("  Link is up. Drone is reachable.")
        print("\nConnection test PASSED.")
except Exception as e:
    print(f"Connection FAILED: {e}")
    sys.exit(1)
