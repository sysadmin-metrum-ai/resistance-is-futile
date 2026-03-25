"""
Assign radio channels to Crazyflie drones and store in a local SQLite DB.

Usage:
    python scripts/radio-config.py scan          # Find drones on all channels
    python scripts/radio-config.py assign <ch>   # Assign current drone to channel <ch>
    python scripts/radio-config.py list          # List all known drones
"""
import sys
import time
import sqlite3
import struct
from pathlib import Path
from threading import Event

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.mem import MemoryElement

DB_PATH = Path(__file__).resolve().parent.parent / "drones.db"
SCAN_CHANNEL = 80
DATA_RATE = "2M"


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""
        CREATE TABLE IF NOT EXISTS drones (
            revision0 TEXT PRIMARY KEY,
            name TEXT,
            channel INTEGER NOT NULL,
            last_seen TEXT
        )
    """)
    db.commit()
    return db


def scan():
    cflib.crtp.init_drivers()
    print("Scanning all channels...")
    found = cflib.crtp.scan_interfaces()
    if not found:
        print("  No drones found.")
        return

    db = get_db()
    for uri_info in found:
        uri = uri_info[0]
        print(f"  Found: {uri}")
        try:
            with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
                time.sleep(2)
                rev0 = str(scf.cf.param.get_value("firmware.revision0"))
                ch = int(uri.split("/")[3])
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    "INSERT INTO drones (revision0, channel, last_seen) VALUES (?, ?, ?) "
                    "ON CONFLICT(revision0) DO UPDATE SET channel=?, last_seen=?",
                    (rev0, ch, now, ch, now),
                )
                db.commit()
                print(f"    revision0={rev0} channel={ch}")
        except Exception as e:
            print(f"    Could not connect: {e}")


def assign(new_channel):
    cflib.crtp.init_drivers()
    new_channel = int(new_channel)
    if not 0 <= new_channel <= 125:
        print(f"ERROR: Channel must be 0-125, got {new_channel}")
        sys.exit(1)

    print(f"Scanning for drone to assign to channel {new_channel}...")
    found = cflib.crtp.scan_interfaces()
    if not found:
        print("No drone found.")
        sys.exit(1)

    uri = found[0][0]
    print(f"Connecting to {uri}...")

    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        cf = scf.cf
        time.sleep(2)

        rev0 = str(cf.param.get_value("firmware.revision0"))
        old_channel = int(uri.split("/")[3])
        print(f"  revision0={rev0}  current_channel={old_channel}")

        if old_channel == new_channel:
            print(f"  Already on channel {new_channel}, nothing to do.")
            return

        refresh_done = Event()
        cf.mem.refresh(refresh_done.set, lambda: None)
        refresh_done.wait(8)

        i2c_mems = cf.mem.get_mems(MemoryElement.TYPE_I2C)
        if not i2c_mems:
            print("ERROR: No I2C config memory found.")
            sys.exit(1)

        mem = i2c_mems[0]
        read_done = Event()
        mem.update(lambda _: read_done.set())
        read_done.wait(8)

        print(f"  Current config: {dict(mem.elements)}")

        mem.elements["radio_channel"] = new_channel

        write_done = Event()
        mem.write_data(lambda *a: write_done.set())
        if not write_done.wait(8):
            print("ERROR: Write timed out.")
            sys.exit(1)

        print(f"  Channel set to {new_channel}.")

        db = get_db()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO drones (revision0, channel, last_seen) VALUES (?, ?, ?) "
            "ON CONFLICT(revision0) DO UPDATE SET channel=?, last_seen=?",
            (rev0, new_channel, now, new_channel, now),
        )
        db.commit()
        print(f"  Saved to DB. Power cycle drone — new URI: radio://0/{new_channel}/{DATA_RATE}")


def list_drones():
    db = get_db()
    rows = db.execute("SELECT revision0, name, channel, last_seen FROM drones ORDER BY channel").fetchall()
    if not rows:
        print("No drones registered.")
        return
    print(f"{'revision0':<15} {'name':<15} {'channel':<10} {'URI':<25} {'last_seen'}")
    for rev0, name, ch, seen in rows:
        name = name or "(unnamed)"
        print(f"{rev0:<15} {name:<15} {ch:<10} radio://0/{ch}/{DATA_RATE:<8} {seen}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "scan":
        scan()
    elif cmd == "assign":
        if len(sys.argv) < 3:
            print("Usage: radio-config.py assign <channel>")
            sys.exit(1)
        assign(sys.argv[2])
    elif cmd == "list":
        list_drones()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
