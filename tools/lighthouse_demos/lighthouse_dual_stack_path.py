"""Two Crazyflies: split heights, stack B over A, shared relative path, B returns home.

1. Drone A (…01) takeoff to ``--height-a`` (default 0.2 m).
2. Drone B (…02) takeoff to ``--height-b`` (default 0.4 m).
3. Sample Kalman XY(Z); B flies in world frame to A's (x, y) at B's hover height (stacked).
4. Both run the same relative legs (default −Y, −X, +X, +Y using 0.8 / 0.6 / 0.6 / 0.8 m).
5. B flies back to its sampled pre-stack pose; A idles for the same duration.
6. Both land.

Distances default to 0.8 m then 0.6 m then 0.6 m then 0.8 m (``-8 / -6 / +6 / +8`` in decimetres).

Usage:
    uv run python -m tools.lighthouse_demos.lighthouse_dual_stack_path.py
    uv run python -m tools.lighthouse_demos.lighthouse_dual_stack_path.py --height-a 0.22 --height-b 0.45
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from typing import MutableMapping

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from tools.lighthouse_demos.lighthouse_dual_x_step import cache_dir_for_uri
from tools.lighthouse_demos.lighthouse_dual_x_step import configure_drone
from tools.lighthouse_demos.lighthouse_dual_x_step import set_bottom_color_led_blue
from tools.lighthouse_demos.lighthouse_dual_x_step import status
from tools.lighthouse_demos.lighthouse_dual_x_step import stop_all
from tools.lighthouse_demos.lighthouse_dual_x_step import takeoff_stagger_drone_b


def _hl_wait(move_s: float, settle: float, pad: float) -> None:
    time.sleep(move_s + settle + pad)


def read_kalman_xyz(cf: Crazyflie, token: str, sample_s: float = 0.4) -> tuple[float, float, float]:
    """One-shot Kalman position (m), same convention as ``lighthouse_hover``."""
    data: dict = {}

    def _cb(_ts: int, d: dict, _lc: LogConfig) -> None:
        data.update(d)

    log = LogConfig(name=f"KPose{token}{int(time.time() * 1000) % 100000}", period_in_ms=50)
    log.add_variable("kalman.stateX", "float")
    log.add_variable("kalman.stateY", "float")
    log.add_variable("kalman.stateZ", "float")
    cf.log.add_config(log)
    log.data_received_cb.add_callback(_cb)
    log.start()
    time.sleep(sample_s)
    log.stop()
    try:
        log.delete()
    except Exception:
        pass

    return (
        float(data.get("kalman.stateX", 0.0)),
        float(data.get("kalman.stateY", 0.0)),
        float(data.get("kalman.stateZ", 0.0)),
    )


def fly_stack_path(
    scf: SyncCrazyflie,
    name: str,
    is_drone_a: bool,
    args: argparse.Namespace,
    pose: MutableMapping[str, float],
    pose_lock: threading.Lock,
    barrier: threading.Barrier,
) -> None:
    commander = scf.cf.high_level_commander
    pad = args.trajectory_pad
    h_a = args.height_a
    h_b = args.height_b

    barrier.wait()
    takeoff_stagger_drone_b(name, args.takeoff_stagger_b)

    if is_drone_a:
        status(f"[{name}] Takeoff to z={h_a:.2f}m...")
        commander.takeoff(h_a, args.takeoff_time, yaw=None)
        time.sleep(args.takeoff_time + args.settle + args.post_takeoff_hold)
    else:
        status(f"[{name}] Takeoff to z={h_b:.2f}m...")
        commander.takeoff(h_b, args.takeoff_time, yaw=None)
        time.sleep(args.takeoff_time + args.settle + args.post_takeoff_hold)

    if args.blue_led and is_drone_a:
        set_bottom_color_led_blue(scf.cf, name)

    barrier.wait()

    x, y, z = read_kalman_xyz(scf.cf, name.replace("-", ""))
    status(f"[{name}] Sampled pose x={x:+.3f} y={y:+.3f} z={z:+.3f}m")
    with pose_lock:
        if is_drone_a:
            pose["ax"] = x
            pose["ay"] = y
            pose["az"] = z
        else:
            pose["bx0"] = x
            pose["by0"] = y
            pose["bz0"] = z

    barrier.wait()

    if is_drone_a:
        status(f"[{name}] Holding while drone-b stacks above (same x,y)...")
        time.sleep(args.stack_time + args.settle + pad)
    else:
        ax, ay = pose["ax"], pose["ay"]
        status(f"[{name}] World go_to A's column ({ax:+.3f}, {ay:+.3f}) at z={h_b:.2f}m...")
        commander.go_to(ax, ay, h_b, 0.0, args.stack_time, relative=False)
        _hl_wait(args.stack_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Leg 1: relative dy={args.dy1:+.2f}m (same both)")
    commander.go_to(0.0, args.dy1, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Leg 2: relative dx={args.dx2:+.2f}m")
    commander.go_to(args.dx2, 0.0, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Leg 3: relative dx={args.dx3:+.2f}m")
    commander.go_to(args.dx3, 0.0, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Leg 4: relative dy={args.dy4:+.2f}m")
    commander.go_to(0.0, args.dy4, 0.0, 0.0, args.leg_time, relative=True)
    _hl_wait(args.leg_time, args.settle, pad)

    barrier.wait()

    if is_drone_a:
        status(f"[{name}] Holding while drone-b returns to start pose...")
        time.sleep(args.return_home_time + args.settle + pad)
    else:
        bx0, by0, bz0 = pose["bx0"], pose["by0"], pose["bz0"]
        status(f"[{name}] Return to pre-stack pose ({bx0:+.3f}, {by0:+.3f}, {bz0:+.3f})m...")
        commander.go_to(bx0, by0, bz0, 0.0, args.return_home_time, relative=False)
        _hl_wait(args.return_home_time, args.settle, pad)

    barrier.wait()

    status(f"[{name}] Landing...")
    commander.land(0.0, args.land_time, yaw=None)
    time.sleep(args.land_time)
    commander.stop()
    status(f"[{name}] Done.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stack B over A, shared relative box, B returns then land")
    p.add_argument("--uri-a", default="radio://0/80/2M/E7E7E7E701")
    p.add_argument("--uri-b", default="radio://0/80/2M/E7E7E7E702")
    p.add_argument("--height-a", type=float, default=0.20, help="Drone A hover height (m)")
    p.add_argument("--height-b", type=float, default=0.40, help="Drone B hover height (m), stacked above A")
    p.add_argument("--takeoff-time", type=float, default=2.5)
    p.add_argument("--leg-time", type=float, default=3.0)
    p.add_argument("--stack-time", type=float, default=4.0, help="Duration for B world move to A's x,y")
    p.add_argument("--return-home-time", type=float, default=4.0, help="Duration for B world move back to pre-stack pose")
    p.add_argument("--settle", type=float, default=0.75)
    p.add_argument("--post-takeoff-hold", type=float, default=0.6)
    p.add_argument("--trajectory-pad", type=float, default=0.45)
    p.add_argument("--takeoff-stagger-b", type=float, default=1.25)
    p.add_argument("--land-time", type=float, default=3.0)
    p.add_argument("--estimator-timeout", type=float, default=15.0)
    p.add_argument("--dy1", type=float, default=-0.8, help="Leg 1: both relative delta-Y (m)")
    p.add_argument("--dx2", type=float, default=-0.6, help="Leg 2: both relative delta-X (m)")
    p.add_argument("--dx3", type=float, default=0.6, help="Leg 3: both relative delta-X (m)")
    p.add_argument("--dy4", type=float, default=0.8, help="Leg 4: both relative delta-Y (m)")
    p.add_argument("--no-blue-led", dest="blue_led", action="store_false")
    p.set_defaults(blue_led=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.height_b <= args.height_a:
        status("ERROR: --height-b should be above --height-a for a vertical stack.")
        return 2

    cflib.crtp.init_drivers()
    scfs: list[SyncCrazyflie] = []
    pose: dict[str, float] = {}
    pose_lock = threading.Lock()

    try:
        status(f"[drone-a] Connecting to {args.uri_a}...")
        scf_a = SyncCrazyflie(args.uri_a, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri_a)))
        scf_a.open_link()
        scfs.append(scf_a)
        status("[drone-a] Connected.")

        status(f"[drone-b] Connecting to {args.uri_b}...")
        scf_b = SyncCrazyflie(args.uri_b, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri_b)))
        scf_b.open_link()
        scfs.append(scf_b)
        status("[drone-b] Connected.")

        time.sleep(0.25)
        configure_drone(scf_a, "drone-a", args.estimator_timeout)
        configure_drone(scf_b, "drone-b", args.estimator_timeout)

        barrier = threading.Barrier(2)
        threads = [
            threading.Thread(
                target=fly_stack_path,
                args=(scf_a, "drone-a", True, args, pose, pose_lock, barrier),
            ),
            threading.Thread(
                target=fly_stack_path,
                args=(scf_b, "drone-b", False, args, pose, pose_lock, barrier),
            ),
        ]

        status("Starting stack + shared path sequence...")
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status("Both drones complete.")
        return 0
    except KeyboardInterrupt:
        status("Keyboard interrupt: landing/stopping both drones now.")
        stop_all(scfs)
        return 130
    except Exception as exc:
        status(f"ABORT: {exc}")
        stop_all(scfs)
        return 1
    finally:
        for scf in scfs:
            try:
                scf.close_link()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
