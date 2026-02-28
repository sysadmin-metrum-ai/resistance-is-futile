"""Point-to-point demo script.

Usage:
    python p2p_demo.py --start-x 0 --start-y 0 --end-x 2 --end-y 2 --hover-seconds 5 --altitude 1.0
"""

import argparse
import json
import urllib.request
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from p2p_generator import generate_p2p_hover


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
    parser = argparse.ArgumentParser(description="Execute point-to-point mission")
    parser.add_argument("--drone-id", type=int, help="Target drone ID")
    parser.add_argument("--start-x", type=float, default=0.0)
    parser.add_argument("--start-y", type=float, default=0.0)
    parser.add_argument("--end-x", type=float, required=True)
    parser.add_argument("--end-y", type=float, required=True)
    parser.add_argument("--hover-seconds", type=int, default=5)
    parser.add_argument("--altitude", type=float, default=1.0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = generate_p2p_hover(args.start_x, args.start_y, args.end_x, args.end_y, args.altitude, args.hover_seconds, args.speed)
    waypoints = result["waypoints"]
    duration = result["duration_seconds"]

    print(f"P2P mission: ({args.start_x},{args.start_y}) -> ({args.end_x},{args.end_y}), hover {args.hover_seconds}s")

    if args.dry_run:
        print("Waypoints:", waypoints)
        return

    result = submit_mission(waypoints, duration, args.drone_id, args.api_url, args.api_key)
    print(f"Mission submitted: {result}")


if __name__ == "__main__":
    main()
