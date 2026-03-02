"""Periodic patrol demo script.

Runs scheduled missions at fixed intervals.
Usage:
    python patrol_demo.py --waypoints '[[0,0,1],[2,0,1],[2,2,1],[0,2,1]]' --interval-seconds 30 --count 5
"""

import argparse
import json
import urllib.request
import sys
import os
import time


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
    parser = argparse.ArgumentParser(description="Periodic patrol mission")
    parser.add_argument("--drone-id", type=int, help="Target drone ID")
    parser.add_argument("--waypoints", type=str, required=True, help="JSON array of [x,y,z] waypoints")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Seconds between missions")
    parser.add_argument("--count", type=int, default=3, help="Number of missions to run")
    parser.add_argument("--duration", type=int, default=30, help="Estimated duration per mission")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("API_KEY", ""))
    parser.add_argument("--dry-run", action="store_true", help="Show config without running")
    args = parser.parse_args()

    waypoints = json.loads(args.waypoints)

    print(f"Patrol config: {args.count} missions, {args.interval_seconds}s interval")
    print(f"Waypoints: {waypoints}")

    if args.dry_run:
        return

    for i in range(args.count):
        print(f"\n--- Mission {i+1}/{args.count} ---")
        try:
            result = submit_mission(waypoints, args.duration, args.drone_id, args.api_url, args.api_key)
            print(f"Submitted: {result}")
        except Exception as e:
            print(f"Error: {e}")

        if i < args.count - 1:
            print(f"Waiting {args.interval_seconds}s...")
            time.sleep(args.interval_seconds)

    print("\nPatrol complete.")


if __name__ == "__main__":
    main()
