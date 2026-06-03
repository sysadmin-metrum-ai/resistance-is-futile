"""Single Crazyflie: relative moves forward, left, and right from origin.

Sequence (all relative, same height): +X -> home, +Y -> home, -Y -> home, land.

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_xy_probe.py
    uv run python -m tools.lighthouse_demos.lighthouse_xy_probe.py --uri radio://0/80/2M/E7E7E7E702 --step 0.15
"""

import argparse
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from tools.lighthouse_demos.lighthouse_x_step import arm_if_supported
from tools.lighthouse_demos.lighthouse_x_step import reset_estimator
from tools.lighthouse_demos.lighthouse_x_step import status
from tools.lighthouse_demos.lighthouse_x_step import wait_for_estimator


def leg(commander, msg: str, dx: float, dy: float, move_s: float, settle: float) -> None:
    status(msg)
    commander.go_to(dx, dy, 0.0, 0.0, move_s, relative=True)
    time.sleep(move_s + settle)


def run_probe(
    cf,
    step: float,
    takeoff_s: float,
    move_s: float,
    settle: float,
    height: float,
    land_s: float,
) -> None:
    hlc = cf.high_level_commander
    arm_if_supported(cf)

    status(f"Takeoff to z={height:.2f}m...")
    hlc.takeoff(height, takeoff_s, yaw=None)
    time.sleep(takeoff_s + settle)

    leg(hlc, f"1/6  relative +X  +{step:.2f} m", step, 0.0, move_s, settle)
    leg(hlc, "2/6  return  -X (back to start)", -step, 0.0, move_s, settle)
    leg(hlc, f"3/6  relative +Y  +{step:.2f} m", 0.0, step, move_s, settle)
    leg(hlc, "4/6  return  -Y (back to start)", 0.0, -step, move_s, settle)
    leg(hlc, f"5/6  relative -Y  -{step:.2f} m", 0.0, -step, move_s, settle)
    leg(hlc, "6/6  return  +Y (back to start)", 0.0, step, move_s, settle)

    status("Landing...")
    hlc.land(0.0, land_s, yaw=None)
    time.sleep(land_s)
    hlc.stop()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe high-level +X / +Y directions (tiny box)")
    p.add_argument("--uri", default="radio://0/80/2M/E7E7E7E701", help="Target drone (default …01)")
    p.add_argument("--step", type=float, default=0.1, help="Each leg size in meters")
    p.add_argument("--height", type=float, default=0.40)
    p.add_argument("--takeoff-time", type=float, default=2.5)
    p.add_argument("--move-time", type=float, default=2.0)
    p.add_argument("--settle", type=float, default=0.8)
    p.add_argument("--land-time", type=float, default=3.0)
    p.add_argument("--estimator-timeout", type=float, default=15.0)
    p.add_argument("--post-estimator-hold", type=float, default=2.0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cflib.crtp.init_drivers()
    hlc = None

    try:
        status(f"Connecting to {args.uri}...")
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            cf = scf.cf
            hlc = cf.high_level_commander
            status("Connected. Lighthouse / Kalman estimator 2 + high-level commander.")
            cf.param.set_value("stabilizer.estimator", "2")
            cf.param.set_value("commander.enHighLevel", "1")
            time.sleep(0.5)
            reset_estimator(cf)
            wait_for_estimator(cf, args.estimator_timeout)
            status(f"Kalman estimator extra hold {args.post_estimator_hold:.1f}s...")
            time.sleep(args.post_estimator_hold)
            run_probe(
                cf,
                step=args.step,
                takeoff_s=args.takeoff_time,
                move_s=args.move_time,
                settle=args.settle,
                height=args.height,
                land_s=args.land_time,
            )
            status("Done.")
            return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt: landing/stopping now.")
        if hlc is not None:
            hlc.land(0.0, 1.0, yaw=None)
            time.sleep(1.0)
            hlc.stop()
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        if hlc is not None:
            try:
                hlc.stop()
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
