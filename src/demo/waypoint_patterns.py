"""Waypoint pattern generator for demo flights.

Generates waypoint sequences for pattern flights: circle, ellipse, figure-8.
"""

import math
from typing import List, Dict


def generate_circle(
    center_x: float,
    center_y: float,
    radius: float,
    altitude: float,
    num_points: int = 12
) -> List[Dict[str, float]]:
    """Generate waypoints forming a circle.

    Args:
        center_x: X coordinate of circle center
        center_y: Y coordinate of circle center
        radius: Circle radius in meters
        altitude: Flight altitude in meters
        num_points: Number of waypoints to generate

    Returns:
        List of waypoint dicts with x, y, z keys
    """
    waypoints = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        waypoints.append({"x": round(x, 3), "y": round(y, 3), "z": altitude})
    return waypoints


def generate_ellipse(
    center_x: float,
    center_y: float,
    radius_x: float,
    radius_y: float,
    altitude: float,
    num_points: int = 12
) -> List[Dict[str, float]]:
    """Generate waypoints forming an ellipse.

    Args:
        center_x: X coordinate of ellipse center
        center_y: Y coordinate of ellipse center
        radius_x: Semi-major axis (X radius)
        radius_y: Semi-minor axis (Y radius)
        altitude: Flight altitude in meters
        num_points: Number of waypoints to generate

    Returns:
        List of waypoint dicts with x, y, z keys
    """
    waypoints = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = center_x + radius_x * math.cos(angle)
        y = center_y + radius_y * math.sin(angle)
        waypoints.append({"x": round(x, 3), "y": round(y, 3), "z": altitude})
    return waypoints


def generate_figure8(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    altitude: float,
    num_points: int = 16
) -> List[Dict[str, float]]:
    """Generate waypoints forming a figure-8 (lemniscate of Bernoulli).

    Args:
        center_x: X coordinate of figure-8 center
        center_y: Y coordinate of figure-8 center
        width: Total width of figure-8
        height: Total height of figure-8
        altitude: Flight altitude in meters
        num_points: Number of waypoints to generate

    Returns:
        List of waypoint dicts with x, y, z keys
    """
    waypoints = []
    scale = width / 2
    for i in range(num_points):
        t = 2 * math.pi * i / num_points
        # Lemniscate parametric equations
        denom = 1 + math.sin(t) ** 2
        x = center_x + scale * math.cos(t) / denom
        y = center_y + scale * math.sin(t) * math.cos(t) / denom
        waypoints.append({"x": round(x, 3), "y": round(y, 3), "z": altitude})
    return waypoints


if __name__ == "__main__":
    # Test the module
    circle = generate_circle(1.0, 1.5, 2.0, 1.5, 12)
    print(f"Circle: {len(circle)} waypoints")
    print(circle[:2])

    ellipse = generate_ellipse(0, 0, 3.0, 1.5, 1.0, 12)
    print(f"Ellipse: {len(ellipse)} waypoints")

    figure8 = generate_figure8(0, 0, 4.0, 2.0, 1.2, 16)
    print(f"Figure-8: {len(figure8)} waypoints")
