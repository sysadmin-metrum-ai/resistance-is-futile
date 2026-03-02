"""Agent-triggered demo script.

Accepts natural language mission description and dispatches drone.
Usage:
    python trigger_demo.py "Inspect the north corner" --drone-id 1
    python trigger_demo.py "Circle the center twice" --pattern circle
"""

import argparse
import json
import urllib.request
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from waypoint_patterns import generate_circle, generate_figure8, generate_ellipse


# Simple keyword-based parsing for demo purposes
LOCATION_KEYWORDS = {
    "north": (0, 3, 1.5),
    "south": (0, -3, 1.5),
    "east": (3, 0, 1.5),
    "west": (-3, 0, 1.5),
    "center": (0, 0, 1.5),
    "northeast": (2, 2, 1.5),
    "northwest": (-2, 2, 1.5),
    "southeast": (2, -2, 1.5),
    "southwest": (-2, -2, 1.5),
}


def parse_mission(description: str, pattern: str = None) -> dict:
    """Parse natural language to mission parameters."""
    desc_lower = description.lower()

    # Check for location keywords
    for keyword, coords in LOCATION_KEYWORDS.items():
        if keyword in desc_lower:
            x, y, z = coords
            return {"type": "point", "x": x, "y": y, "z": z, "description": description}

    # Check for pattern keywords
    if "circle" in desc_lower or "round" in desc_lower:
        pattern = "circle"
    elif "figure" in desc_lower or "8" in desc_lower:
        pattern = "figure8"
    elif "ellipse" in desc_lower or "oval" in desc_lower:
        pattern = "ellipse"

    if pattern:
        return {"type": "pattern", "pattern": pattern, "description": description}

    # Default to center point
    return {"type": "point", "x": 0, "y": 0, "z": 1.5, "description": description}


def submit_mission(waypoints, duration, drone_id=None, api_url="http://localhost:8000", api_key=""):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    payload = {"waypoints": waypoints, "duration_seconds": duration}
    if drone_id is not None:
        payload["target_drone_id"] = drone_id

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{api_url}/missions", data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Agent-triggered drone mission")
    parser.add_argument("mission", help="Mission description (e.g., 'Inspect the north corner')")
    parser.add_argument("--drone-id", type=int, help="Target drone ID")
    parser.add_argument("--pattern", choices=["circle", "ellipse", "figure8", "auto"], default="auto")
    parser.add_argument("--altitude", type=float, default=1.5)
    parser.add_argument("--radius", type=float, default=2.0)
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Agent dispatching: '{args.mission}'")

    # Parse mission
    mission = parse_mission(args.mission, args.pattern if args.pattern != "auto" else None)

    # Generate waypoints
    if mission["type"] == "point":
        waypoints = [
            {"x": 0, "y": 0, "z": 0},
            {"x": mission["x"], "y": mission["y"], "z": mission["z"]},
            {"x": 0, "y": 0, "z": 0},
        ]
        duration = 20
        print(f" -> Point mission: ({mission['x']}, {mission['y']}, {mission['z']})")
    else:
        pattern = mission.get("pattern", "circle")
        if pattern == "circle":
            waypoints = generate_circle(0, 0, args.radius, args.altitude, 12)
        elif pattern == "figure8":
            waypoints = generate_figure8(0, 0, args.radius * 2, args.radius, args.altitude, 16)
        else:
            waypoints = generate_ellipse(0, 0, args.radius, args.radius * 0.6, args.altitude, 12)
        duration = len(waypoints) + 10
        print(f" -> Pattern mission: {pattern}")

    if args.dry_run:
        print("Waypoints:", waypoints)
        return

    result = submit_mission(waypoints, duration, args.drone_id, args.api_url, args.api_key)
    print(f"Mission submitted: {result}")


if __name__ == "__main__":
    main()
