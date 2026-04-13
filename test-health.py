"""Fleet health check: self-test, battery, and motor spin-up for all registered drones.

Reads the drone roster from drones.db, scans the radio for each one,
and runs diagnostics sequentially. With a single Crazyradio PA only one
connection at a time is possible; multiple radios would enable parallel checks.

Usage:
    python test-health.py                  # check all drones in DB
    python test-health.py --motors         # include motor spin test
    python test-health.py --uri radio://0/80/2M  # single drone override

Importable:
    from test_health import preflight_check
    results = preflight_check(motor_test=False)
"""
import sys
import time
import sqlite3
import argparse
from pathlib import Path
from dataclasses import dataclass, field

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig

DB_PATH = Path(__file__).resolve().parent / "drones.db"
DATA_RATE = "2M"
MOTOR_TEST_PWM = 12000
MOTOR_SPIN_SEC = 0.8
MIN_BATTERY_V = 3.3
CRIT_BATTERY_V = 3.0


@dataclass
class DroneResult:
    name: str
    uri: str
    revision0: str = ""
    selftest: bool = False
    battery_v: float = 0.0
    motors_ok: bool = False
    error: str = ""

    @property
    def passed(self):
        return self.selftest and self.battery_v >= CRIT_BATTERY_V and not self.error


def _update_last_seen(revision0, uri):
    """Stamp last_seen so the DB reflects the most recent preflight."""
    db = sqlite3.connect(str(DB_PATH))
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    ch = int(uri.split("/")[3])
    db.execute(
        "UPDATE drones SET channel=?, last_seen=? WHERE revision0=?",
        (ch, now, revision0),
    )
    db.commit()
    db.close()


def load_fleet():
    """Return list of (name, channel, revision0) from the DB."""
    if not DB_PATH.exists():
        return []
    db = sqlite3.connect(str(DB_PATH))
    rows = db.execute(
        "SELECT name, channel, revision0 FROM drones ORDER BY channel"
    ).fetchall()
    db.close()
    return [(r[0] or f"unnamed_{r[2]}", r[1], r[2]) for r in rows]


def check_one(uri, name, motor_test=False):
    """Run health checks on a single drone. Returns DroneResult."""
    result = DroneResult(name=name, uri=uri)
    try:
        with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            cf = scf.cf
            time.sleep(1)

            result.revision0 = str(cf.param.get_value("firmware.revision0"))
            selftest = cf.param.get_value("system.selftestPassed")
            result.selftest = str(selftest) == "1"

            bat_data = {}
            bat_log = LogConfig(name="Battery", period_in_ms=100)
            bat_log.add_variable("pm.vbat", "float")

            def _cb(ts, data, logconf):
                bat_data.update(data)

            cf.log.add_config(bat_log)
            bat_log.data_received_cb.add_callback(_cb)
            bat_log.start()
            time.sleep(0.5)
            bat_log.stop()
            result.battery_v = bat_data.get("pm.vbat", 0.0)

            if motor_test:
                cf.param.set_value("motorPowerSet.enable", "1")
                try:
                    for i in range(1, 5):
                        key = f"motorPowerSet.m{i}"
                        cf.param.set_value(key, str(MOTOR_TEST_PWM))
                        time.sleep(MOTOR_SPIN_SEC)
                        cf.param.set_value(key, "0")
                        time.sleep(0.2)
                    result.motors_ok = True
                finally:
                    for i in range(1, 5):
                        cf.param.set_value(f"motorPowerSet.m{i}", "0")
                    cf.param.set_value("motorPowerSet.enable", "0")
            else:
                result.motors_ok = True

    except Exception as e:
        result.error = str(e)

    return result


def preflight_check(motor_test=False, single_uri=None):
    """Run health checks on the full fleet (or a single URI).

    Returns a list of DroneResult. Suitable as a gate before any mission.
    """
    cflib.crtp.init_drivers()

    print("Scanning radio...")
    on_air = {f[0] for f in cflib.crtp.scan_interfaces()}
    print(f"  Drones on air: {on_air or 'none'}")

    if single_uri:
        targets = [("manual", single_uri)]
    else:
        fleet = load_fleet()
        if not fleet:
            print("No drones in DB. Run: scripts/radio-config.py scan")
            return []
        targets = [(name, f"radio://0/{ch}/{DATA_RATE}") for name, ch, _ in fleet]

    channels = [t[1].split("/")[3] for t in targets]
    dupes = [c for c in channels if channels.count(c) > 1]
    if dupes:
        print(f"  WARNING: channel conflict on {set(dupes)}")

    results = []
    for name, uri in targets:
        tag = f"[{name}]"
        if uri not in on_air:
            r = DroneResult(name=name, uri=uri, error="not found on air")
            print(f"\n{tag} {uri} -- SKIP (not powered on)")
            results.append(r)
            continue

        print(f"\n{tag} {uri}")
        r = check_one(uri, name, motor_test=motor_test)

        st = "PASS" if r.selftest else "FAIL"
        bv = f"{r.battery_v:.2f}V" if r.battery_v else "N/A"
        bl = ""
        if r.battery_v < CRIT_BATTERY_V:
            bl = " CRITICAL"
        elif r.battery_v < MIN_BATTERY_V:
            bl = " LOW"

        print(f"  selftest: {st}  battery: {bv}{bl}  motors: {'ok' if r.motors_ok else 'skip'}")
        if r.error:
            print(f"  ERROR: {r.error}")
        print(f"  --> {'GO' if r.passed else 'NO-GO'}")

        if r.passed and DB_PATH.exists():
            _update_last_seen(r.revision0, uri)

        results.append(r)

    return results


def print_summary(results):
    print("\n" + "=" * 50)
    print("FLEET PREFLIGHT SUMMARY")
    print("=" * 50)
    offline = [r for r in results if r.error == "not found on air"]
    checked = [r for r in results if r.error != "not found on air"]
    go = [r for r in checked if r.passed]
    nogo = [r for r in checked if not r.passed]

    for r in results:
        if r.error == "not found on air":
            status = "OFF   "
        elif r.passed:
            status = "GO    "
        else:
            status = "NO-GO "
        print(f"  {status} {r.name:<15} {r.uri:<25} {r.battery_v:.2f}V")

    print(f"\n  {len(go)} GO / {len(nogo)} NO-GO / {len(offline)} offline")
    if nogo:
        print(f"  NO-GO: {', '.join(r.name for r in nogo)}")
    if not checked:
        print("  No drones online to check.")
        return False
    return len(nogo) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fleet preflight health check")
    parser.add_argument("--motors", action="store_true", help="Include motor spin-up test")
    parser.add_argument("--uri", type=str, default=None, help="Check a single URI instead of full fleet")
    args = parser.parse_args()

    results = preflight_check(motor_test=args.motors, single_uri=args.uri)
    if not results:
        sys.exit(1)
    all_go = print_summary(results)
    sys.exit(0 if all_go else 1)
