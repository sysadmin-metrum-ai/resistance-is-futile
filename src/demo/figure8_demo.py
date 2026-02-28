"""Figure-8 pattern demo script.

Usage:
    python figure8_demo.py --drone-id 1 --altitude 1.2 --width 4.0 --height 2.0
"""

import argparse
import json
import urllib.request
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from waypoint_patterns import generate_figure8


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
    parser = argparse.ArgumentParser(description="Execute figure-8 pattern flight")
    parser.add_argument("--drone-id", type=int, help="Target drone ID")
    parser.add_argument("--altitude", type=float, default=1.2)
    parser.add_argument("--width", type=float, default=4.0, help="Total width")
    parser.add_argument("--height", type=float, default=2.0, help="Total height")
    parser.add_argument("--center-x", type=float, default=0.0)
    parser.add_argument("--center-y", type=float, default=0.0)
    parser.add_argument("--points", type=int, default=16)
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    waypoints = generate_figure8(args.center_x, args.center_y, args.width, args.height, args.altitude, args.points)
    duration = args.points + 12

    print(f"Figure-8 pattern: {args.width}x{args.height}m, {args.altitude}m alt")

    if args.dry_run:
        print("Waypoints:", waypoints)
        return

    result = submit_mission(waypoints, duration, args.drone_id, args.api_url, args.api_key)
    print(f"Mission submitted: {result}")


if __name__ == "__main__":
    main()
