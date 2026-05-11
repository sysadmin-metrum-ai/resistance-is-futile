from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from camera_socket import AiDeckJpegStream
from camera_socket import status
from led_blink import BlueBlinker
from lighthouse_control import cache_dir_for_uri
from lighthouse_control import configure_drone


def target_for_role(args: argparse.Namespace) -> tuple[float, float, float, float]:
    if args.role == "apex":
        return args.pyramid_tip_x, args.pyramid_tip_y, args.tip_z, args.into_tip_time
    if args.role == "base-py":
        return args.pyramid_tip_x, args.py_half_span, args.base_z, args.into_time
    if args.role == "base-my":
        return args.pyramid_tip_x, -args.py_half_span, args.base_z, args.into_time
    raise ValueError(f"Unknown role: {args.role}")


def save_captures(camera: AiDeckJpegStream, output_dir: Path, count: int, gap_s: float) -> list[Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved: list[Path] = []
    for index in range(count):
        path = output_dir / f"aideck_capture_{stamp}_{index + 1:02d}.jpg"
        saved_path = camera.save_latest(path)
        saved.append(saved_path)
        status(f"[camera] Saved {saved_path}")
        if index + 1 < count:
            time.sleep(gap_s)
    return saved


def fly_and_capture(args: argparse.Namespace) -> list[Path]:
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

    cflib.crtp.init_drivers()
    camera = AiDeckJpegStream(args.aideck_ip, args.aideck_port, args.camera_timeout)
    saved: list[Path] = []
    hlc = None
    landed = False
    blinker = None

    camera.start()
    camera.wait_for_frame(args.camera_timeout)
    status("[camera] First frame received; starting flight.")

    try:
        status(f"[drone] Connecting to {args.uri}...")
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(args.uri))) as scf:
            cf = scf.cf
            hlc = cf.high_level_commander
            configure_drone(cf, args.estimator_timeout)
            blinker = BlueBlinker(cf, args.blue_blink_interval)
            blinker.start()

            home_x, home_y = args.home
            target_x, target_y, target_z, move_s = target_for_role(args)

            status(f"[drone] Takeoff to z={args.hover_z:.2f}m...")
            hlc.takeoff(args.hover_z, args.takeoff_time, yaw=None)
            time.sleep(args.takeoff_time + args.post_takeoff_hold + args.settle)

            status("[drone] Rally go_to...")
            hlc.go_to(home_x, home_y, args.hover_z, 0.0, args.rally_time, relative=False)
            time.sleep(args.rally_time + args.settle + args.trajectory_pad)

            status(f"[drone] Demo target go_to ({args.role})...")
            hlc.go_to(target_x, target_y, target_z, 0.0, move_s, relative=False)
            time.sleep(move_s + args.settle + args.trajectory_pad)

            status("[camera] Saving latest AI deck frames while holding pose...")
            saved = save_captures(camera, Path(args.output_dir), args.captures, args.capture_gap)
            time.sleep(args.after_capture_hold)

            status("[drone] Returning home rally...")
            hlc.go_to(home_x, home_y, args.hover_z, 0.0, args.home_return_time, relative=False)
            time.sleep(args.home_return_time + args.settle + args.trajectory_pad)

            status("[drone] Landing...")
            hlc.land(0.0, args.land_time, yaw=None)
            time.sleep(args.land_time + 0.35)
            hlc.stop()
            landed = True
            blinker.stop()
            return saved
    except Exception:
        if hlc is not None and not landed:
            status("[drone] Error path: landing before abort...")
            try:
                hlc.land(0.0, args.land_time, yaw=None)
                time.sleep(args.land_time + 0.35)
            except Exception:
                pass
        raise
    finally:
        if blinker is not None:
            blinker.stop()
        if hlc is not None:
            try:
                hlc.stop()
            except Exception:
                pass
        camera.stop()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-drone Lighthouse + AI deck camera PoC")
    parser.add_argument("--uri", default="radio://0/80/2M/E7E7E7E701")
    parser.add_argument("--aideck-ip", default="192.168.4.1")
    parser.add_argument("--aideck-port", type=int, default=5000)
    parser.add_argument("--output-dir", default="aideck_camera_poc/captures")
    parser.add_argument("--captures", type=int, default=3)
    parser.add_argument("--capture-gap", type=float, default=0.4)
    parser.add_argument("--camera-timeout", type=float, default=8.0)
    parser.add_argument("--blue-blink-interval", type=float, default=0.35)

    parser.add_argument("--home", nargs=2, type=float, default=[-0.5, 0.0], metavar=("X", "Y"))
    parser.add_argument("--role", choices=("apex", "base-py", "base-my"), default="apex")
    parser.add_argument("--hover-z", type=float, default=0.55)
    parser.add_argument("--tip-z", type=float, default=1.0)
    parser.add_argument("--base-z", type=float, default=0.5)
    parser.add_argument("--pyramid-tip-x", type=float, default=0.5)
    parser.add_argument("--pyramid-tip-y", type=float, default=0.0)
    parser.add_argument("--py-half-span", type=float, default=0.5)

    parser.add_argument("--takeoff-time", type=float, default=2.5)
    parser.add_argument("--post-takeoff-hold", type=float, default=0.7)
    parser.add_argument("--rally-time", type=float, default=5.0)
    parser.add_argument("--into-time", type=float, default=6.5)
    parser.add_argument("--into-tip-time", type=float, default=8.5)
    parser.add_argument("--home-return-time", type=float, default=6.5)
    parser.add_argument("--after-capture-hold", type=float, default=1.0)
    parser.add_argument("--settle", type=float, default=0.75)
    parser.add_argument("--trajectory-pad", type=float, default=0.45)
    parser.add_argument("--estimator-timeout", type=float, default=22.0)
    parser.add_argument("--land-time", type=float, default=3.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        saved = fly_and_capture(args)
        status("[done] Saved captures:")
        for path in saved:
            status(f"  {path}")
        return 0
    except KeyboardInterrupt:
        status("[abort] Keyboard interrupt.")
        return 130
    except Exception as exc:
        status(f"[abort] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
