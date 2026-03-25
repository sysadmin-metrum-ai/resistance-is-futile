#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def run_solver(bin_path: Path, graph_path: Path):
    p = subprocess.run(
        [str(bin_path), "solve", str(graph_path), "--validate"],
        text=True,
        capture_output=True,
    )
    return p.returncode, (p.stdout or "") + "\n" + (p.stderr or "")


def load_records(path: Path):
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def write_records(path: Path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose failing JSONL solve combinations")
    ap.add_argument("--graph", default="tools/drone-acharya/graph-6a-6l-template.jsonl")
    ap.add_argument("--solver-bin", default="tools/drone-acharya/bin/drone-acharya_linux_amd64")
    args = ap.parse_args()

    graph = Path(args.graph)
    solver_bin = Path(args.solver_bin)
    records = load_records(graph)
    nodes = [r for r in records if r.get("type") == "node"]
    edges = [r for r in records if r.get("type") == "edge"]

    rc, out = run_solver(solver_bin, graph)
    print(f"baseline_rc={rc}")
    if rc == 0:
        print("baseline solve passes; no diagnosis needed")
        return 0
    print("baseline_error:")
    print(out.strip().splitlines()[0])

    latent_ids = [n["id"] for n in nodes if n.get("kind") == "latent"]
    anchor_ids = [n["id"] for n in nodes if n.get("kind") == "anchor"]
    print(f"anchors={anchor_ids}")
    print(f"latents={latent_ids}")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Try dropping one latent at a time
        print("\nSingle-latent drop tests:")
        for lid in latent_ids:
            rec2 = []
            for r in records:
                if r.get("type") == "node" and r.get("id") == lid:
                    continue
                if r.get("type") == "edge" and lid in (r.get("a"), r.get("b")):
                    continue
                rec2.append(r)
            tmp = td / f"drop-{lid}.jsonl"
            write_records(tmp, rec2)
            rc2, out2 = run_solver(solver_bin, tmp)
            status = "PASS" if rc2 == 0 else "FAIL"
            first = out2.strip().splitlines()[0] if out2.strip() else ""
            print(f"- drop {lid}: {status} {first}")

        # Try dropping one edge at a time (only for positive distances)
        print("\nSingle-edge drop tests (first 20 passes shown):")
        pass_count = 0
        for i, e in enumerate(edges):
            if float(e.get("distance", -1.0)) <= 0:
                continue
            rec2 = records[:]
            rec2.remove(e)
            tmp = td / f"drop-edge-{i}.jsonl"
            write_records(tmp, rec2)
            rc2, out2 = run_solver(solver_bin, tmp)
            if rc2 == 0:
                pass_count += 1
                print(f"- drop edge {e['a']}-{e['b']}: PASS")
                if pass_count >= 20:
                    break
        if pass_count == 0:
            print("- no single-edge removal produced PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
