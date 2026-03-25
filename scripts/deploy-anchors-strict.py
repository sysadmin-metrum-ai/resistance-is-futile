#!/usr/bin/env python3
import argparse
import subprocess
import sys


def run(cmd):
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, text=True)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Strict deploy: solve gate -> export anchors -> push with verify"
    )
    ap.add_argument("--graph", default="tools/drone-acharya/graph-6a-6l-template.jsonl")
    ap.add_argument("--solver-bin", default="tools/drone-acharya/bin/drone-acharya_linux_amd64")
    ap.add_argument("--anchors-out", default="scripts/anchors.py")
    ap.add_argument("--json-out", default="tools/drone-acharya/solve-output.json")
    ap.add_argument("--radio", default="0/90/2M")
    ap.add_argument("--max-err-m", type=float, default=0.06)
    args = ap.parse_args()

    # Gate solve (no fallback)
    run(
        [
            "uv",
            "run",
            "python",
            "scripts/solve-jsonl-strict.py",
            "--graph",
            args.graph,
            "--solver-bin",
            args.solver_bin,
            "--anchors-out",
            args.anchors_out,
            "--json-out",
            args.json_out,
            "--max-err-m",
            str(args.max_err_m),
        ]
    )

    # Push with strict verification
    run(
        [
            "uv",
            "run",
            "python",
            "scripts/push-anchors.py",
            "--anchors",
            args.anchors_out,
            "--radio",
            args.radio,
            "--verbose",
            "--verify",
            "--verify-retries",
            "5",
            "--verify-timeout",
            "12",
            "--verify-tolerance",
            "0.05",
        ]
    )

    print("PASS: anchors solved and deployed with verification")
    return 0


if __name__ == "__main__":
    sys.exit(main())
