#!/usr/bin/env python3
"""
Push anchor coordinates to Loco Positioning nodes via Crazyradio.

This script programs Loco Positioning (LPS) anchors with their 3D coordinates
using the Loco Positioning Protocol (LPP) over the Crazyradio USB dongle.

Usage:
    python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M
    python scripts/push-anchors.py --anchors anchors.json --radio 0/80/2M --verbose

Requirements:
    pip install cflib

The anchor coordinates should be provided in the format output by:
    drone-acharya solve distances.csv --crazyflie --z-down

For Crazyflie/LPS, generate the anchor file with --z-down (and optionally --rotate-ned,
--offset-*) so coordinates are in NED when pushed to the nodes.

Example anchors.py format:
    anchor_positions = {
        0: (0.00, 0.00, 0.00),
        1: (4.00, 0.00, 0.00),
        2: (4.00, 3.00, 0.00),
        3: (0.00, 3.00, 0.00),
    }

Example anchors.json format:
    {
        "nodes": [
            {"id": 0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"id": 1, "x": 4.0, "y": 0.0, "z": 0.0}
        ]
    }
"""

import argparse
import json
import sys
import time
from threading import Event
from pathlib import Path
from typing import Any

# Try to import cflib - will fail gracefully with helpful message
try:
    from cflib import crazyflie
    from cflib.crazyflie.mem import MemoryElement
    from cflib.crtp import init_drivers
    from lpslib.lopoanchor import LoPoAnchor
    CFLIB_AVAILABLE = True
except ImportError:
    CFLIB_AVAILABLE = False
    LoPoAnchor = None
    MemoryElement = None


def load_anchors_python(filepath: Path) -> dict[int, tuple[float, float, float]]:
    """Load anchor positions from a Python file with anchor_positions dict."""
    namespace: dict[str, Any] = {}
    with open(filepath, "r") as f:
        exec(f.read(), namespace)

    if "anchor_positions" not in namespace:
        raise ValueError("File must define 'anchor_positions' dictionary")

    anchors = namespace["anchor_positions"]

    # Validate format: {id: (x, y, z)}
    result: dict[int, tuple[float, float, float]] = {}
    for anchor_id, coords in anchors.items():
        if not isinstance(anchor_id, int):
            raise ValueError(f"Anchor ID must be integer, got {type(anchor_id)}")
        if len(coords) != 3:
            raise ValueError(f"Anchor {anchor_id} coords must be (x, y, z), got {coords}")
        result[anchor_id] = tuple(float(c) for c in coords)

    return result


def load_anchors_json(filepath: Path) -> dict[int, tuple[float, float, float]]:
    """Load anchor positions from a JSON file."""
    with open(filepath, "r") as f:
        data = json.load(f)

    result: dict[int, tuple[float, float, float]] = {}

    if "nodes" in data:
        # JSON format from drone-acharya --json
        for node in data["nodes"]:
            anchor_id = node["id"]
            result[anchor_id] = (node["x"], node["y"], node["z"])
    elif isinstance(data, dict):
        # Simple dict format {id: [x, y, z]}
        for anchor_id, coords in data.items():
            result[int(anchor_id)] = tuple(float(c) for c in coords)
    else:
        raise ValueError(f"Unexpected JSON format: {data}")

    return result


def load_anchors(filepath: Path) -> dict[int, tuple[float, float, float]]:
    """Load anchor positions from file (auto-detect format)."""
    suffix = filepath.suffix.lower()

    if suffix == ".py":
        return load_anchors_python(filepath)
    elif suffix == ".json":
        return load_anchors_json(filepath)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .py or .json")


def push_anchors(
    anchors: dict[int, tuple[float, float, float]],
    radio_address: str = "0/80/2M",
    verbose: bool = False,
    verify: bool = True,
    verify_tolerance_m: float = 0.05,
    verify_timeout_s: float = 8.0,
    write_retries: int = 3,
    verify_retries: int = 2,
) -> dict[int, bool]:
    """
    Push anchor coordinates to Loco Positioning nodes.

    Args:
        anchors: Dictionary mapping anchor ID to (x, y, z) coordinates
        radio_address: Radio address in format "channel/address/data_rate"
                     e.g., "0/80/2M" (channel=0, address=80, 2M data rate)
        verbose: Enable verbose output
        verify: Read back anchor positions after write
        verify_tolerance_m: Max allowed 3D distance error for readback
        verify_timeout_s: Max seconds to wait per memory read operation
        write_retries: Retries per anchor write after first attempt
        verify_retries: Verification retry loops after first readback

    Returns:
        Dictionary mapping anchor ID to success status
    """
    if not CFLIB_AVAILABLE:
        print("ERROR: cflib is not installed.", file=sys.stderr)
        print("Install it with: pip install cflib", file=sys.stderr)
        sys.exit(1)

    # Initialize Crazyradio drivers
    init_drivers()

    results: dict[int, bool] = {}

    # Convert radio address string to URI
    # Format: "channel/address/data_rate" -> "radio://0/80/2M"
    uri = f"radio://{radio_address.replace('/', '/')}"

    if verbose:
        print(f"Connecting to radio at {uri}")
        print(f"Pushing coordinates for {len(anchors)} anchors...")

    # Create a Crazyflie instance to communicate with anchors
    # Note: We use Crazyflie as a bridge to send LPP packets to anchors
    cf = crazyflie.Crazyflie(uri)

    # Open link
    if verbose:
        print("Opening link...")

    cf.open_link()

    try:
        # Give time for connection to establish
        import time
        time.sleep(0.5)

        if not cf.link_is_up():
            raise RuntimeError("Failed to establish link with radio")

        if verbose:
            print("Link established")

        anchor_bridge = LoPoAnchor(cf)

        # Push each anchor's position
        for anchor_id, (x, y, z) in anchors.items():
            write_ok = False
            last_err: Exception | None = None
            for attempt in range(write_retries + 1):
                try:
                    _set_anchor_position(anchor_bridge, anchor_id, x, y, z, verbose)
                    write_ok = True
                    break
                except Exception as e:
                    last_err = e
                    if verbose:
                        print(
                            f"  Anchor {anchor_id}: write attempt {attempt + 1}/{write_retries + 1} failed: {e}",
                            file=sys.stderr,
                        )
                    time.sleep(0.2)
            results[anchor_id] = write_ok
            if write_ok:
                if verbose:
                    print(f"  Anchor {anchor_id}: ({x:.3f}, {y:.3f}, {z:.3f}) - SUCCESS")
            else:
                print(f"  Anchor {anchor_id}: FAILED - {last_err}", file=sys.stderr)

        if verify and all(results.values()):
            if verbose:
                print("Running readback verification...")
            failed_verify: dict[int, str] = {}
            for verify_attempt in range(verify_retries + 1):
                failed_verify.clear()
                readback_positions, valid_flags = _read_anchor_positions(cf, verify_timeout_s, verbose)
                for anchor_id, (x, y, z) in anchors.items():
                    read_pos = readback_positions.get(anchor_id)
                    is_valid = valid_flags.get(anchor_id, False)
                    if read_pos is None or not is_valid:
                        failed_verify[anchor_id] = "missing/invalid readback"
                        continue
                    err = _distance3(read_pos, (x, y, z))
                    if err > verify_tolerance_m:
                        failed_verify[anchor_id] = (
                            f"error {err:.3f}m exceeds {verify_tolerance_m:.3f}m"
                        )
                    elif verbose:
                        rx, ry, rz = read_pos
                        print(
                            f"  Anchor {anchor_id}: verify ok (readback=({rx:.3f}, {ry:.3f}, {rz:.3f}), err={err:.3f}m)"
                        )
                if not failed_verify:
                    break
                if verify_attempt < verify_retries:
                    if verbose:
                        print(
                            f"Verification pass {verify_attempt + 1}/{verify_retries + 1} failed for "
                            f"{len(failed_verify)} anchors; rewriting failed anchors and retrying..."
                        )
                    for anchor_id in sorted(failed_verify.keys()):
                        x, y, z = anchors[anchor_id]
                        _set_anchor_position(anchor_bridge, anchor_id, x, y, z, verbose)
                    time.sleep(0.5)

            for anchor_id, reason in failed_verify.items():
                results[anchor_id] = False
                print(f"  Anchor {anchor_id}: VERIFY FAILED - {reason}", file=sys.stderr)

    finally:
        cf.close_link()

    return results


def _set_anchor_position(
    anchor_bridge: Any,
    anchor_id: int,
    x: float,
    y: float,
    z: float,
    verbose: bool = False,
) -> None:
    """
    Set anchor position using LoPoAnchor over the Crazyflie link.

    We send each position update multiple times since this path is
    best-effort and does not include explicit per-anchor ACKs.
    """
    if verbose:
        print(f"    Sending LoPoAnchor position: anchor={anchor_id} pos=({x:.3f}, {y:.3f}, {z:.3f})")

    for _ in range(3):
        anchor_bridge.set_position(anchor_id, (x, y, z))
        time.sleep(0.05)


def _distance3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def _wait(event: Event, timeout_s: float, name: str) -> None:
    if not event.wait(timeout_s):
        raise RuntimeError(f"Timed out waiting for {name}")


def _read_anchor_positions(
    cf: Any,
    timeout_s: float,
    verbose: bool = False,
) -> tuple[dict[int, tuple[float, float, float]], dict[int, bool]]:
    """Read anchor positions from Loco memory (v2 preferred, fallback v1)."""
    refresh_done = Event()
    refresh_failed = Event()

    cf.mem.refresh(refresh_done.set, refresh_failed.set)
    _wait(refresh_done, timeout_s, "memory refresh")
    if refresh_failed.is_set():
        raise RuntimeError("Memory refresh failed")

    loco2_mems = cf.mem.get_mems(MemoryElement.TYPE_LOCO2)
    if loco2_mems:
        mem = loco2_mems[0]
        ids_done = Event()
        data_done = Event()
        mem.update_id_list(lambda _: ids_done.set())
        _wait(ids_done, timeout_s, "Loco2 id list")
        mem.update_data(lambda _: data_done.set())
        _wait(data_done, timeout_s, "Loco2 anchor data")
        positions = {aid: tuple(mem.anchor_data[aid].position) for aid in mem.anchor_data}
        valid_flags = {aid: bool(mem.anchor_data[aid].is_valid) for aid in mem.anchor_data}
        if verbose:
            print(f"Read back {len(positions)} anchors from Loco2 memory")
        return positions, valid_flags

    loco_mems = cf.mem.get_mems(MemoryElement.TYPE_LOCO)
    if loco_mems:
        mem = loco_mems[0]
        done = Event()
        mem.update(lambda _: done.set())
        _wait(done, timeout_s, "Loco anchor data")
        positions = {}
        valid_flags = {}
        for idx, anchor in enumerate(mem.anchor_data):
            positions[idx] = tuple(anchor.position)
            valid_flags[idx] = bool(anchor.is_valid)
        if verbose:
            print(f"Read back {len(positions)} anchors from Loco memory")
        return positions, valid_flags

    raise RuntimeError("No Loco memory found (TYPE_LOCO/TYPE_LOCO2)")


def main():
    parser = argparse.ArgumentParser(
        description="Push anchor coordinates to Loco Positioning nodes via Crazyradio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--anchors",
        type=Path,
        required=True,
        help="Path to anchor coordinates file (.py or .json format)",
    )
    parser.add_argument(
        "--radio",
        default="0/80/2M",
        help="Radio address (default: 0/80/2M)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse anchors but don't push to hardware",
    )
    parser.add_argument(
        "--verify",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Read back anchor positions after write (default: enabled)",
    )
    parser.add_argument(
        "--verify-tolerance",
        type=float,
        default=0.05,
        help="Allowed 3D readback error in meters (default: 0.05)",
    )
    parser.add_argument(
        "--verify-timeout",
        type=float,
        default=8.0,
        help="Timeout (seconds) for each memory-read stage (default: 8.0)",
    )
    parser.add_argument(
        "--write-retries",
        type=int,
        default=3,
        help="Retries per anchor write after first attempt (default: 3)",
    )
    parser.add_argument(
        "--verify-retries",
        type=int,
        default=2,
        help="Verification retries after first readback (default: 2)",
    )

    args = parser.parse_args()

    # Load anchor positions
    print(f"Loading anchors from {args.anchors}...")
    try:
        anchors = load_anchors(args.anchors)
    except Exception as e:
        print(f"ERROR: Failed to load anchors: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(anchors)} anchors:")
    for anchor_id, (x, y, z) in sorted(anchors.items()):
        print(f"  Anchor {anchor_id}: ({x:.3f}, {y:.3f}, {z:.3f})")

    if args.dry_run:
        print("\nDry run - not pushing to hardware")
        sys.exit(0)

    # Push anchors
    print(f"\nPushing anchors via radio {args.radio}...")
    if args.write_retries < 0 or args.verify_retries < 0:
        print("ERROR: --write-retries and --verify-retries must be >= 0", file=sys.stderr)
        sys.exit(2)
    results = push_anchors(
        anchors,
        args.radio,
        args.verbose,
        verify=args.verify,
        verify_tolerance_m=args.verify_tolerance,
        verify_timeout_s=args.verify_timeout,
        write_retries=args.write_retries,
        verify_retries=args.verify_retries,
    )

    # Summary
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    print(f"\nResults: {success_count}/{total_count} anchors configured successfully")

    if success_count < total_count:
        print("\nFailed anchors:")
        for anchor_id, success in results.items():
            if not success:
                print(f"  Anchor {anchor_id}")
        sys.exit(1)

    print("\nAll anchors configured successfully!")


if __name__ == "__main__":
    main()
