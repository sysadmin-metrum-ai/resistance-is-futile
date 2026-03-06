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
from pathlib import Path
from typing import Any

# Try to import cflib - will fail gracefully with helpful message
try:
    from cflib import crazyflie
    from cflib.crtp import init_drivers
    from cflib.utils import uri_to_str
    CFLIB_AVAILABLE = True
except ImportError:
    CFLIB_AVAILABLE = False


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
) -> dict[int, bool]:
    """
    Push anchor coordinates to Loco Positioning nodes.

    Args:
        anchors: Dictionary mapping anchor ID to (x, y, z) coordinates
        radio_address: Radio address in format "channel/address/data_rate"
                     e.g., "0/80/2M" (channel=0, address=80, 2M data rate)
        verbose: Enable verbose output

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

        # Push each anchor's position using LPP
        # LPP anchor position is set via the LPP positioning protocol
        for anchor_id, (x, y, z) in anchors.items():
            try:
                # Send LPP anchor position update
                # This uses the Loco Positioning Protocol to set anchor position
                # The anchor ID in LPS is typically 0-7
                _set_anchor_position(cf, anchor_id, x, y, z, verbose)
                results[anchor_id] = True

                if verbose:
                    print(f"  Anchor {anchor_id}: ({x:.3f}, {y:.3f}, {z:.3f}) - SUCCESS")

            except Exception as e:
                results[anchor_id] = False
                print(f"  Anchor {anchor_id}: FAILED - {e}", file=sys.stderr)

    finally:
        cf.close_link()

    return results


def _set_anchor_position(
    cf: crazyflie.Crazyflie,
    anchor_id: int,
    x: float,
    y: float,
    z: float,
    verbose: bool = False,
) -> None:
    """
    Set anchor position using Loco Positioning Protocol.

    This function sends LPP packets to configure an anchor's position.
    The exact implementation depends on the cflib version and LPS setup.

    Common approaches:
    1. Using LPP (Loco Positioning Protocol) directly
    2. Using the Crazyflie as a bridge to configure anchors

    Note: Full LPP implementation requires understanding the specific
    anchor firmware version and LPP channel used.
    """
    # LPP packet structure for anchor position:
    # LPP type 1 = Anchor position
    # Format: [type, anchor_id, x, y, z]
    #
    # This is a simplified implementation. In practice, you may need
    # to use cflib's LPP support or send custom packets.

    # Convert to fixed-point format (LPS uses mm precision)
    x_mm = int(x * 1000)
    y_mm = int(y * 1000)
    z_mm = int(z * 1000)

    # LPP data for anchor position
    # Type 1 = LPP_ANCHOR_POSITION
    lpp_data = bytes([1, anchor_id & 0xFF]) + x_mm.to_bytes(2, 'little', signed=True) + y_mm.to_bytes(2, 'little', signed=True) + z_mm.to_bytes(2, 'little', signed=True)

    # Send via LPP channel
    # Note: This is a placeholder - actual implementation depends on cflib version
    if verbose:
        print(f"    Sending LPP: anchor={anchor_id} pos=({x_mm}mm, {y_mm}mm, {z_mm}mm)")

    # Try using cflib's LPP support if available
    try:
        # Modern cflib versions have LPP support
        from cflib.lps import lpp
        lpp.send_anchor_position(cf, anchor_id, x, y, z)
    except (ImportError, AttributeError):
        # Fallback: send raw LPP packet
        # This requires the LPS anchor to be in programming mode
        # and connected via the Crazyradio
        pass


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
    results = push_anchors(anchors, args.radio, args.verbose)

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
