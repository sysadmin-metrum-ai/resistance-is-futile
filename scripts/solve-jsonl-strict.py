#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_edges(path: Path):
    edges = []
    for line_no, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("type") == "edge":
            edges.append((line_no, rec["a"], rec["b"], float(rec["distance"])))
    return edges


def fail(msg: str, code: int = 1):
    print(f"ERROR: {msg}")
    raise SystemExit(code)


def run_cmd(cmd):
    print("+", " ".join(cmd))
    return subprocess.run(cmd, text=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Strict JSONL solve gate: zip solver only, no fallback"
    )
    ap.add_argument("--graph", default="tools/drone-acharya/graph-6a-6l-template.jsonl")
    ap.add_argument(
        "--solver-bin",
        default="tools/drone-acharya/bin/drone-acharya_linux_amd64",
    )
    ap.add_argument("--anchors-out", default="scripts/anchors.py")
    ap.add_argument("--json-out", default="tools/drone-acharya/solve-output.json")
    ap.add_argument("--max-err-m", type=float, default=0.06)
    args = ap.parse_args()

    graph = Path(args.graph)
    solver_bin = Path(args.solver_bin)
    if not graph.exists():
        fail(f"graph file not found: {graph}")
    if not solver_bin.exists():
        fail(f"solver binary not found: {solver_bin}")

    edges = parse_edges(graph)
    if not edges:
        fail("no edges in graph")

    placeholders = [(ln, a, b) for ln, a, b, d in edges if d <= 0]
    if placeholders:
        print("Found nonpositive/placeholder distances:")
        for ln, a, b in placeholders[:20]:
            print(f"- line {ln}: {a}-{b}")
        fail("fill all distances (> 0) before solve", code=2)

    # Run validation solve first (must pass)
    res = run_cmd(
        [
            str(solver_bin),
            "solve",
            str(graph),
            "--validate",
        ]
    )
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        fail("zip solver failed on graph (no fallback allowed)", code=3)

    # Parse validation table and enforce max error gate
    text = (res.stdout or "") + "\n" + (res.stderr or "")
    worst = 0.0
    for line in text.splitlines():
        parts = line.split("\t")
        # Residual rows look like "A0-L0\tmeasured\tcomputed\terror\tresidual"
        if len(parts) >= 4 and "-" in parts[0]:
            try:
                err = float(parts[3])
            except ValueError:
                continue
            worst = max(worst, err)
    print(f"validation_worst_error_m={worst:.3f}")
    if worst > args.max_err_m:
        fail(
            f"worst validation error {worst:.3f}m exceeds gate {args.max_err_m:.3f}m",
            code=4,
        )

    # Export anchors strictly from solver output
    export = run_cmd(
        [
            str(solver_bin),
            "solve",
            str(graph),
            "--crazyflie",
            "--z-down",
            "-o",
            args.anchors_out,
        ]
    )
    if export.returncode != 0:
        print(export.stdout)
        print(export.stderr)
        fail("failed to export anchors from solver output", code=5)

    # Also save json solve output for audit trail
    json_out = run_cmd(
        [
            str(solver_bin),
            "solve",
            str(graph),
            "--json",
            "--validate",
            "-o",
            args.json_out,
        ]
    )
    if json_out.returncode != 0:
        print(json_out.stdout)
        print(json_out.stderr)
        fail("failed to export json solve artifact", code=6)

    print(f"PASS: solver gate passed. anchors written to {args.anchors_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
