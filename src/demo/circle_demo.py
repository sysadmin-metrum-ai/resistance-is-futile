"""Circle pattern demo script.

Usage:
    python circle_demo.py --drone-id 1 --altitude 1.5 --radius 2.0 --center-x 0 --center-y 0
"""

import argparse
import json
import urllib.request
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from waypoint_patterns import generate_circle


def submit_mission(waypoints, duration, drone_id=None, api_url="http://localhost:8000", api_key=""):
    """Submit mission via API."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    payload = {
        "waypoints": waypoints,
        "duration_seconds": duration
    }
    if drone_id is not None:
        payload["target_drone_id"] = drone_id

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{api_url}/missions", data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Execute circle pattern flight")
    parser.add_argument("--drone-id", type=int, help="Target drone ID")
    parser.add_argument("--altitude", type=float, default=1.5, help="Flight altitude (m)")
    parser.add_argument("--radius", type=float, default=2.0, help="Circle radius (m)")
    parser.add_argument("--center-x", type=float, default=0.0, help="Center X coordinate")
    parser.add_argument("--center-y", type=float, default=0.0, help="Center Y coordinate")
    parser.add_argument("--points", type=int, default=12, help="Number of waypoints")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true", help="Print waypoints without submitting")
    args = parser.parse_args()

    waypoints = generate_circle(args.center_x, args.center_y, args.radius, args.altitude, args.points)
    # Estimate: each segment ~1 second + 10s for takeoff/land
    duration = args.points + 10

    print(f"Circle pattern: {args.radius}m radius, {args.altitude}m altitude, {args.points} points")

    if args.dry_run:
        print("Waypoints:", waypoints)
        return

    result = submit_mission(waypoints, duration, args.drone_id, args.api_url, args.api_key)
    print(f"Mission submitted: {result}")


if __name__ == "__main__":
    main()
