"""Set a Crazyflie radio channel/address in EEPROM.

Usage:
    uv run python scripts/set-radio-config.py --uri radio://0/90/2M --channel 80 --address E7E7E7E702

Power only the Crazyflie you want to reconfigure.
Power cycle it after the write.
"""

import argparse
import sys
import time
from threading import Event

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.mem import MemoryElement
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


def status(message: str) -> None:
    print(message, flush=True)


def wait(event: Event, timeout_s: float, name: str) -> None:
    if not event.wait(timeout_s):
        raise RuntimeError(f"Timed out waiting for {name}")


def parse_radio_address(address: str) -> int:
    cleaned = address.lower().replace("0x", "").replace(":", "").replace("-", "")
    if len(cleaned) != 10:
        raise ValueError("Radio address must be 5 bytes, for example E7E7E7E702")
    return int(cleaned, 16)


def get_i2c_config_memory(cf, timeout_s: float):
    refresh_done = Event()
    refresh_failed = Event()
    cf.mem.refresh(refresh_done.set, refresh_failed.set)
    wait(refresh_done, timeout_s, "memory refresh")
    if refresh_failed.is_set():
        raise RuntimeError("Memory refresh failed")

    i2c_mems = cf.mem.get_mems(MemoryElement.TYPE_I2C)
    if not i2c_mems:
        raise RuntimeError("No I2C config memory found")

    mem = i2c_mems[0]
    read_done = Event()
    mem.update(lambda _mem: read_done.set())
    wait(read_done, timeout_s, "I2C config read")
    if not mem.valid:
        raise RuntimeError("I2C config memory is invalid")
    return mem


def set_radio_config(uri: str, channel: int, address: int, timeout_s: float) -> None:
    cflib.crtp.init_drivers()
    status(f"Connecting to {uri}...")
    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        cf = scf.cf
        time.sleep(1.0)
        mem = get_i2c_config_memory(cf, timeout_s)

        status(f"Current config: {dict(mem.elements)}")
        mem.elements["version"] = 1
        mem.elements["radio_channel"] = channel
        mem.elements["radio_address"] = address

        write_done = Event()
        mem.write_data(lambda *_args: write_done.set())
        wait(write_done, timeout_s, "I2C config write")

        status(f"Wrote channel={channel}, address=0x{address:010X}")
        status(f"Power cycle the Crazyflie, then use: radio://0/{channel}/2M/{address:010X}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set Crazyflie radio channel and address")
    parser.add_argument("--uri", required=True, help="Current URI, for example radio://0/90/2M")
    parser.add_argument("--channel", type=int, required=True, help="New channel, 0-125")
    parser.add_argument("--address", required=True, help="New 5-byte hex address, for example E7E7E7E702")
    parser.add_argument("--timeout", type=float, default=8.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.channel <= 125:
        status(f"ERROR: Channel must be 0-125, got {args.channel}")
        return 1

    try:
        address = parse_radio_address(args.address)
        set_radio_config(args.uri, args.channel, address, args.timeout)
        return 0
    except Exception as exc:
        status(f"ABORT: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
