"""Repeatedly call the swarm deploy API until fewer than 3 drones are viable.

Defaults to dry-run. Use ``--fly --yes`` to send armed hardware missions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx


TERMINAL_STATES = {"completed", "dry_run", "refused", "failed", "aborted"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loop swarm deploy API calls for demo endurance testing")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value")
    parser.add_argument("--swarm-size", type=int, default=5, choices=[3, 4, 5])
    parser.add_argument("--formation", choices=["line", "triangle", "diamond", "v"], default="triangle")
    parser.add_argument("--pattern", choices=["line_shift", "square", "hold", "up_forward"], default="hold")
    parser.add_argument("--allow-uri", action="append", default=[], help="Candidate URI; repeatable")
    parser.add_argument("--deny-uri", action="append", default=[], help="Excluded URI; repeatable")
    parser.add_argument("--sleep-s", type=float, default=5.0, help="Pause between completed missions")
    parser.add_argument("--poll-s", type=float, default=2.0, help="Status polling interval while a mission is running")
    parser.add_argument("--critical-count", type=int, default=3, help="Stop when selected drones fall below this count")
    parser.add_argument("--max-runs", type=int, default=0, help="0 means run until critical/refused/failure")
    parser.add_argument("--fly", action="store_true", help="Send non-dry-run armed deploy requests")
    parser.add_argument("--yes", action="store_true", help="Required with --fly")
    return parser.parse_args(argv)


def headers(args: argparse.Namespace) -> dict[str, str]:
    result = {"Content-Type": "application/json"}
    if args.api_key:
        result["X-API-Key"] = args.api_key
    return result


def deploy_payload(args: argparse.Namespace) -> dict[str, Any]:
    fly = bool(args.fly and args.yes)
    payload = {
        "swarm_size": args.swarm_size,
        "formation": args.formation,
        "pattern": args.pattern,
        "dry_run": not fly,
        "arm": fly,
    }
    if args.allow_uri:
        payload["allowed_uris"] = args.allow_uri
    if args.deny_uri:
        payload["denied_uris"] = args.deny_uri
    return payload


def wait_for_terminal(client: httpx.Client, args: argparse.Namespace, mission_id: str) -> dict[str, Any]:
    url = f"{args.base_url.rstrip('/')}/api/swarm/deploy/{mission_id}"
    while True:
        response = client.get(url, headers=headers(args))
        response.raise_for_status()
        data = response.json()
        state = data.get("state")
        selected_count = len(data.get("selected", []))
        print(f"mission {mission_id}: state={state} selected={selected_count}", flush=True)
        if state in TERMINAL_STATES:
            return data
        time.sleep(args.poll_s)


def should_stop(data: dict[str, Any], critical_count: int) -> bool:
    selected_count = len(data.get("selected", []))
    state = data.get("state")
    return selected_count < critical_count or state in {"failed", "aborted"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.fly and not args.yes:
        print("ABORT: --fly requires --yes", flush=True)
        return 2

    payload = deploy_payload(args)
    print(f"Using payload: {json.dumps(payload, sort_keys=True)}", flush=True)
    if args.allow_uri:
        print(f"Using {len(args.allow_uri)} explicit candidate URIs.", flush=True)
    else:
        print("Leaving allowed_uris empty so the API scans available drones each mission.", flush=True)

    deploy_url = f"{args.base_url.rstrip('/')}/api/swarm/deploy"
    run = 0
    timeout = httpx.Timeout(180.0, connect=10.0)
    with httpx.Client(timeout=timeout) as client:
        while args.max_runs <= 0 or run < args.max_runs:
            run += 1
            print(f"\n=== mission cycle {run} ===", flush=True)
            response = client.post(deploy_url, headers=headers(args), json=payload)
            response.raise_for_status()
            data = response.json()
            mission_id = data["mission_id"]
            print(
                f"deploy accepted: mission={mission_id} state={data['state']} "
                f"selected={len(data.get('selected', []))}",
                flush=True,
            )

            if data.get("state") == "running":
                data = wait_for_terminal(client, args, mission_id)

            selected_count = len(data.get("selected", []))
            print(
                f"mission done: mission={mission_id} state={data.get('state')} "
                f"selected={selected_count} message={data.get('message')}",
                flush=True,
            )

            if should_stop(data, args.critical_count):
                print(f"Stopping: selected_count={selected_count} < critical_count={args.critical_count}", flush=True)
                return 0

            print(f"Sleeping {args.sleep_s:.1f}s before next deploy...", flush=True)
            time.sleep(args.sleep_s)

    return 0


if __name__ == "__main__":
    sys.exit(main())
