"""Ellipse pattern demo script.

Usage:
    python ellipse_demo.py --drone-id 1 --altitude 1.5 --radius-x 3.0 --radius-y 1.5
"""

import argparse
import json
import urllib.request
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from waypoint_patterns import generate_ellipse


def submit_mission(waypoints, duration, drone_id=None, api_url="http://localhost:8000", api_key=""):
    """Submit mission via API."""
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
    parser = argparse.ArgumentParser(description="Execute ellipse pattern flight")
    parser.add_argument("--drone-id", type=int, help="Target drone ID")
    parser.add_argument("--altitude", type=float, default=1.5)
    parser.add_argument("--radius-x", type=float, default=3.0, help="Semi-major axis")
    parser.add_argument("--radius-y", type=float, default=1.5, help="Semi-minor axis")
    parser.add_argument("--center-x", type=float, default=0.0)
    parser.add_argument("--center-y", type=float, default=0.0)
    parser.add_argument("--points", type=int, default=12)
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    waypoints = generate_ellipse(args.center_x, args.center_y, args.radius_x, args.radius_y, args.altitude, args.points)
    duration = args.points + 10

    print(f"Ellipse pattern: {args.radius_x}x{args.radius_y}m, {args.altitude}m alt")

    if args.dry_run:
        print("Waypoints:", waypoints)
        return

    result = submit_mission(waypoints, duration, args.drone_id, args.api_url, args.api_key)
    print(f"Mission submitted: {result}")


if __name__ == "__main__":
    main()
