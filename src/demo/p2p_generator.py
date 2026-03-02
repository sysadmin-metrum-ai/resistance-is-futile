"""Point-to-point mission generator.

Generates A→B→A missions with configurable hover duration.
"""

import math
from typing import List, Dict


def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def generate_p2p_hover(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    altitude: float = 1.0,
    hover_seconds: int = 5,
    speed: float = 1.0
) -> Dict:
    """Generate A→B→A mission with hover at destination.

    Args:
        start_x: Starting X coordinate
        start_y: Starting Y coordinate
        end_x: Destination X coordinate
        end_y: Destination Y coordinate
        altitude: Flight altitude in meters
        hover_seconds: Duration to hover at destination
        speed: Flight speed in m/s (default 1.0)

    Returns:
        Dict with waypoints list and estimated duration
    """
    waypoints = []

    # Takeoff at start position
    waypoints.append({"x": start_x, "y": start_y, "z": 0.0})  # Takeoff point

    # Hover point at destination (slightly above altitude for observation)
    hover_z = altitude + 0.3
    waypoints.append({"x": end_x, "y": end_y, "z": hover_z})

    # Return to start at altitude
    waypoints.append({"x": start_x, "y": start_y, "z": altitude})

    # Land at start
    waypoints.append({"x": start_x, "y": start_y, "z": 0.0})

    # Calculate duration
    distance_out = calculate_distance(start_x, start_y, end_x, end_y)
    distance_total = 2 * distance_out  # Out and back

    # Time = distance/speed + hover time
    duration = int(distance_total / speed) + hover_seconds + 10  # +10s for takeoff/landing

    return {
        "waypoints": waypoints,
        "duration_seconds": duration,
        "start": {"x": start_x, "y": start_y},
        "end": {"x": end_x, "y": end_y},
        "hover_seconds": hover_seconds
    }


if __name__ == "__main__":
    # Test the module
    result = generate_p2p_hover(0, 0, 2, 2, altitude=1.0, hover_seconds=5)
    print(f"Waypoints: {len(result['waypoints'])}")
    print(f"Duration: {result['duration_seconds']}s")
    print(result["waypoints"])
