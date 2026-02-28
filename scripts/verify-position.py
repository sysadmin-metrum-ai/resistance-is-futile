#!/usr/bin/env python3
"""
Verify positioning accuracy with a test flight pattern.

This script commands the drone to execute a predefined flight pattern
while recording position estimates from the Loco Positioning system,
then computes the error between expected and actual positions.

Usage:
    python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2
    python scripts/verify-position.py --pattern circle --size 1.5 --threshold 0.2 --drone drone-1

Requirements:
    - Drone API running (see src/main.py)
    - Loco Positioning system configured with anchors

Flight Patterns:
    - square: Square pattern with configurable side length
    - circle: Circular pattern with configurable radius
    - figure8: Figure-8 pattern with configurable scale

Exit Codes:
    0: Test passed (RMS error <= threshold)
    1: Test failed (RMS error > threshold or error during execution)
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from math import pi, sin, cos, sqrt
from typing import Optional

import httpx


@dataclass
class Position:
    """3D position with timestamp."""
    x: float
    y: float
    z: float
    timestamp: float


@dataclass
class TestResult:
    """Result of test."""
    pattern: str
    expected_positions: list[Position]
    actual_positions: list[Position]
    errors: list[float]
    rms_error: float
    max_error: float
    passed: bool


class DroneAPI:
    """Client for the drone mission API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_drone_status(self, drone_id: str) -> dict:
        """Get current drone status."""
        response = await self.client.get(f"{self.base_url}/drones/{drone_id}")
        response.raise_for_status()
        return response.json()

    async def takeoff(self, drone_id: str, height: float) -> dict:
        """Command drone to take off."""
        response = await self.client.post(
            f"{self.base_url}/drones/{drone_id}/takeoff",
            json={"height": height},
        )
        response.raise_for_status()
        return response.json()

    async def land(self, drone_id: str) -> dict:
        """Command drone to land."""
        response = await self.client.post(
            f"{self.base_url}/drones/{drone_id}/land",
        )
        response.raise_for_status()
        return response.json()

    async def go_to(self, drone_id: str, x: float, y: float, z: float) -> dict:
        """Command drone to go to a position."""
        response = await self.client.post(
            f"{self.base_url}/drones/{drone_id}/go_to",
            json={"x": x, "y": y, "z": z},
        )
        response.raise_for_status()
        return response.json()

    async def get_position(self, drone_id: str) -> Position:
        """Get current estimated position from Loco Positioning."""
        # Try state endpoint first
        try:
            response = await self.client.get(f"{self.base_url}/drones/{drone_id}/state")
            if response.status_code == 200:
                state = response.json()
                return Position(
                    x=state.get("state", {}).get("x", 0.0),
                    y=state.get("state", {}).get("y", 0.0),
                    z=state.get("state", {}).get("z", 0.0),
                    timestamp=time.time(),
                )
        except Exception:
            pass

        # Fallback: return last known or zero
        return Position(x=0.0, y=0.0, z=0.0, timestamp=time.time())


def generate_square_points(center_x: float, center_y: float, side: float, z: float) -> list[Position]:
    """Generate waypoints for a square pattern.

    Args:
        center_x: Center X coordinate
        center_y: Center Y coordinate
        side: Length of each side
        z: Flight altitude (Z coordinate)

    Returns:
        List of positions forming a square
    """
    half = side / 2
    # Square: start at corner, go clockwise
    return [
        Position(x=center_x - half, y=center_y - half, z=z, timestamp=0),
        Position(x=center_x + half, y=center_y - half, z=z, timestamp=0),
        Position(x=center_x + half, y=center_y + half, z=z, timestamp=0),
        Position(x=center_x - half, y=center_y + half, z=z, timestamp=0),
        Position(x=center_x - half, y=center_y - half, z=z, timestamp=0),  # Return to start
    ]


def generate_circle_points(center_x: float, center_y: float, radius: float, z: float, num_points: int = 16) -> list[Position]:
    """Generate waypoints for a circular pattern.

    Args:
        center_x: Center X coordinate
        center_y: Center Y coordinate
        radius: Circle radius
        z: Flight altitude (Z coordinate)
        num_points: Number of points to sample

    Returns:
        List of positions forming a circle
    """
    points = []
    for i in range(num_points + 1):  # +1 to close the loop
        angle = 2 * pi * i / num_points
        x = center_x + radius * cos(angle)
        y = center_y + radius * sin(angle)
        points.append(Position(x=x, y=y, z=z, timestamp=0))
    return points


def generate_figure8_points(center_x: float, center_y: float, scale: float, z: float, num_points: int = 32) -> list[Position]:
    """Generate waypoints for a figure-8 pattern (lemniscate).

    Args:
        center_x: Center X coordinate
        center_y: Center Y coordinate
        scale: Scale factor (width of the figure-8)
        z: Flight altitude (Z coordinate)
        num_points: Number of points to sample

    Returns:
        List of positions forming a figure-8
    """
    points = []
    for i in range(num_points + 1):
        t = 2 * pi * i / num_points
        # Lemniscate of Bernoulli (figure-8)
        denom = 1 + sin(t) ** 2
        x = center_x + scale * cos(t) / denom
        y = center_y + scale * sin(t) * cos(t) / denom
        points.append(Position(x=x, y=y, z=z, timestamp=0))
    return points


def compute_error(expected: Position, actual: Position) -> float:
    """Compute Euclidean distance between expected and actual positions."""
    return sqrt(
        (expected.x - actual.x) ** 2 +
        (expected.y - actual.y) ** 2 +
        (expected.z - actual.z) ** 2
    )


async def run_pattern(
    api: DroneAPI,
    drone_id: str,
    pattern: str,
    size: float,
    height: float,
    speed: float,
    verbose: bool = False,
) -> TestResult:
    """Execute a flight pattern and record positions.

    Args:
        api: DroneAPI client
        drone_id: ID of the drone to command
        pattern: Pattern type (square, circle, figure8)
        size: Size parameter (side length for square, radius for circle, scale for figure8)
        height: Flight altitude
        speed: Movement speed in m/s
        verbose: Enable verbose output

    Returns:
        TestResult with expected/actual positions and errors
    """
    # Generate expected waypoints
    center_x, center_y = 0.0, 0.0  # Assume origin is center of flight area

    if pattern == "square":
        waypoints = generate_square_points(center_x, center_y, size, height)
    elif pattern == "circle":
        waypoints = generate_circle_points(center_x, center_y, size, height)
    elif pattern == "figure8":
        waypoints = generate_figure8_points(center_x, center_y, size, height)
    else:
        raise ValueError(f"Unknown pattern: {pattern}")

    if verbose:
        print(f"Generated {len(waypoints)} waypoints for {pattern} pattern")

    # Arm and take off
    if verbose:
        print(f"Taking off to {height}m...")

    await api.takeoff(drone_id, height)
    await asyncio.sleep(2)  # Allow time for takeoff

    # Record positions at each waypoint
    actual_positions: list[Position] = []

    # Calculate dwell time at each waypoint (distance / speed)
    # Assume ~1 second per waypoint for position stabilization
    dwell_time = max(1.0, size / speed)

    for i, wp in enumerate(waypoints):
        if verbose:
            print(f"Moving to waypoint {i+1}/{len(waypoints)}: ({wp.x:.2f}, {wp.y:.2f}, {wp.z:.2f})")

        # Command movement
        await api.go_to(drone_id, wp.x, wp.y, wp.z)

        # Wait for drone to arrive and record position
        await asyncio.sleep(dwell_time)

        # Record actual position from LPS
        actual = await api.get_position(drone_id)
        actual_positions.append(actual)

        if verbose:
            print(f"  Actual position: ({actual.x:.3f}, {actual.y:.3f}, {actual.z:.3f})")

    # Return to origin and land
    if verbose:
        print("Returning to origin and landing...")

    await api.go_to(drone_id, center_x, center_y, height)
    await asyncio.sleep(1)
    await api.land(drone_id)

    # Compute errors
    errors: list[float] = []
    for expected, actual in zip(waypoints, actual_positions):
        err = compute_error(expected, actual)
        errors.append(err)

    rms_error = sqrt(sum(e ** 2 for e in errors) / len(errors)) if errors else 0
    max_error = max(errors) if errors else 0

    passed = rms_error <= threshold  # threshold from outer scope

    return TestResult(
        pattern=pattern,
        expected_positions=waypoints,
        actual_positions=actual_positions,
        errors=errors,
        rms_error=rms_error,
        max_error=max_error,
        passed=passed,
    )


def print_results(result: TestResult, threshold: float, verbose: bool = False):
    """Print test results in a readable format."""
    print("\n" + "=" * 60)
    print("POSITIONING VERIFICATION RESULTS")
    print("=" * 60)
    print(f"Pattern: {result.pattern}")
    print(f"Threshold: {threshold * 100:.1f}cm ({threshold}m)")
    print("-" * 60)
    print(f"RMS Error:  {result.rms_error * 100:.2f}cm ({result.rms_error:.4f}m)")
    print(f"Max Error:   {result.max_error * 100:.2f}cm ({result.max_error:.4f}m)")
    print(f"Mean Error:  {sum(result.errors) / len(result.errors) * 100:.2f}cm")
    print("-" * 60)

    if verbose:
        print("\nWaypoint Details:")
        print(f"{'#':>3} {'Expected':>25} {'Actual':>25} {'Error':>10}")
        print("-" * 70)
        for i, (exp, act, err) in enumerate(zip(
            result.expected_positions,
            result.actual_positions,
            result.errors
        )):
            print(f"{i+1:>3} ({exp.x:>6.2f}, {exp.y:>6.2f}, {exp.z:>5.2f}) "
                  f"({act.x:>6.2f}, {act.y:>6.2f}, {act.z:>5.2f}) "
                  f"{err*100:>7.2f}cm")

    print("=" * 60)
    if result.passed:
        print("RESULT: PASSED - Positioning accuracy within threshold")
    else:
        print("RESULT: FAILED - Positioning accuracy exceeds threshold")
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Verify positioning accuracy with a test flight pattern",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pattern",
        choices=["square", "circle", "figure8"],
        default="square",
        help="Flight pattern type (default: square)",
    )
    parser.add_argument(
        "--size",
        type=float,
        default=1.0,
        help="Pattern size: side length (square), radius (circle), scale (figure8) in meters (default: 1.0)",
    )
    parser.add_argument(
        "--height",
        type=float,
        default=0.5,
        help="Flight altitude in meters (default: 0.5)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=0.3,
        help="Movement speed in m/s (default: 0.3)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.2,
        help="Pass/fail threshold in meters (default: 0.2 = 20cm)",
    )
    parser.add_argument(
        "--drone",
        default="drone-1",
        help="Drone ID to use (default: drone-1)",
    )
    parser.add_argument(
        "--api",
        default="http://localhost:8000",
        help="Base URL for drone API (default: http://localhost:8000)",
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
        help="Generate waypoints but don't execute flight",
    )

    global threshold
    args = parser.parse_args()
    threshold = args.threshold

    # Validate inputs
    if args.size <= 0:
        print("ERROR: --size must be positive", file=sys.stderr)
        sys.exit(1)
    if args.height <= 0:
        print("ERROR: --height must be positive", file=sys.stderr)
        sys.exit(1)
    if args.threshold <= 0:
        print("ERROR: --threshold must be positive", file=sys.stderr)
        sys.exit(1)

    print(f"Verifying positioning with {args.pattern} pattern")
    print(f"  Size: {args.size}m")
    print(f"  Height: {args.height}m")
    print(f"  Threshold: {args.threshold * 100:.1f}cm")
    print(f"  Drone: {args.drone}")

    if args.dry_run:
        # Generate waypoints without flying
        if args.pattern == "square":
            waypoints = generate_square_points(0, 0, args.size, args.height)
        elif args.pattern == "circle":
            waypoints = generate_circle_points(0, 0, args.size, args.height)
        elif args.pattern == "figure8":
            waypoints = generate_figure8_points(0, 0, args.size, args.height)

        print(f"\nGenerated {len(waypoints)} waypoints (dry run - no flight):")
        for i, wp in enumerate(waypoints):
            print(f"  {i+1}: ({wp.x:.3f}, {wp.y:.3f}, {wp.z:.3f})")
        sys.exit(0)

    # Connect to API and run test
    api = DroneAPI(args.api)

    try:
        # Check drone is available
        try:
            status = await api.get_drone_status(args.drone)
            if args.verbose:
                print(f"Drone status: {json.dumps(status, indent=2)}")
        except Exception as e:
            print(f"ERROR: Cannot connect to drone {args.drone}: {e}", file=sys.stderr)
            sys.exit(1)

        # Run the test pattern
        result = await run_pattern(
            api,
            args.drone,
            args.pattern,
            args.size,
            args.height,
            args.speed,
            args.verbose,
        )

        # Print results
        print_results(result, args.threshold, args.verbose)

        # Exit with appropriate code
        sys.exit(0 if result.passed else 1)

    finally:
        await api.close()


if __name__ == "__main__":
    # Global variable for use in nested function
    threshold = 0.2
    asyncio.run(main())
