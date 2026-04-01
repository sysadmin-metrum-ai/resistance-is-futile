"""Minimal LED ring test: red, green, blue for one second each."""

import argparse
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie


SOLID_EFFECT = "7"
OFF_EFFECT = "0"
DEFAULT_HOLD_SECONDS = 1.0
DEFAULT_BRIGHTNESS = 255


def parse_args():
    parser = argparse.ArgumentParser(description="Simple Crazyflie LED ring RGB test")
    parser.add_argument(
        "--uri",
        default=None,
        help="Crazyflie URI, e.g. radio://0/90/2M. Defaults to the first detected drone.",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=DEFAULT_HOLD_SECONDS,
        help="How long to hold each color",
    )
    parser.add_argument(
        "--brightness",
        type=int,
        default=DEFAULT_BRIGHTNESS,
        help="Channel intensity from 0-255",
    )
    return parser.parse_args()


def resolve_uri(cli_uri: str | None) -> str:
    if cli_uri:
        return cli_uri

    available = cflib.crtp.scan_interfaces()
    if not available:
        print("No Crazyflie found. Pass --uri if the radio scan is missing your drone.")
        sys.exit(1)

    uri = available[0][0]
    print(f"Using first detected drone: {uri}")
    return uri


def set_solid_color(cf: Crazyflie, red: int, green: int, blue: int) -> None:
    cf.param.set_value("ring.effect", SOLID_EFFECT)
    cf.param.set_value("ring.solidRed", str(red))
    cf.param.set_value("ring.solidGreen", str(green))
    cf.param.set_value("ring.solidBlue", str(blue))


def turn_off(cf: Crazyflie) -> None:
    cf.param.set_value("ring.solidRed", "0")
    cf.param.set_value("ring.solidGreen", "0")
    cf.param.set_value("ring.solidBlue", "0")
    cf.param.set_value("ring.effect", OFF_EFFECT)


def main() -> int:
    args = parse_args()
    seconds = max(0.1, args.seconds)
    brightness = max(0, min(255, args.brightness))

    cflib.crtp.init_drivers()
    uri = resolve_uri(args.uri)

    print(f"Connecting to {uri}...")
    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        cf = scf.cf
        time.sleep(0.3)

        try:
            for name, rgb in (
                ("red", (brightness, 0, 0)),
                ("green", (0, brightness, 0)),
                ("blue", (0, 0, brightness)),
            ):
                print(f"Showing {name} for {seconds:.1f}s")
                set_solid_color(cf, *rgb)
                time.sleep(seconds)
        finally:
            turn_off(cf)
            print("LED ring off")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
