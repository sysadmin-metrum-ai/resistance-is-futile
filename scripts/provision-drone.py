#!/usr/bin/env python3
"""Apply the required runtime profile to a Crazyflie after flashing."""

from __future__ import annotations

import argparse
import json
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from src.services.commissioning_profile import (
    CommissioningProfile,
    default_tdoa3_profile,
    default_twr_profile,
)


def build_profile(mode: str) -> CommissioningProfile:
    if mode == "tdoa3":
        return default_tdoa3_profile()
    if mode == "twr":
        return default_twr_profile()
    raise ValueError(f"unsupported mode: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply the required Crazyflie runtime profile after flashing"
    )
    parser.add_argument("--uri", required=True, help="Drone URI, e.g. radio://0/90/2M")
    parser.add_argument(
        "--profile",
        choices=("tdoa3", "twr"),
        default="tdoa3",
        help="Provisioning profile to apply",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=0.3,
        help="Wait after each parameter write",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print final verification as JSON",
    )
    args = parser.parse_args()

    profile = build_profile(args.profile)
    desired = profile.to_param_map()

    cflib.crtp.init_drivers()
    print(f"Connecting to {args.uri} with profile '{args.profile}'...")
    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        cf = scf.cf
        for key, value in desired.items():
            print(f"  set {key}={value}")
            cf.param.set_value(key, value)
            time.sleep(args.settle_seconds)

        verified = {key: str(cf.param.get_value(key)) for key in desired}
        verified["firmware.revision0"] = str(cf.param.get_value("firmware.revision0"))

    if args.json:
        print(json.dumps(verified, indent=2, sort_keys=True))
    else:
        print("Verification:")
        for key, value in verified.items():
            print(f"  {key}={value}")

    mismatches = {
        key: {"expected": desired[key], "actual": verified[key]}
        for key in desired
        if desired[key] != verified[key]
    }
    if mismatches:
        print("ERROR: parameter verification mismatch")
        print(json.dumps(mismatches, indent=2, sort_keys=True))
        return 1

    print("Provisioning complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
