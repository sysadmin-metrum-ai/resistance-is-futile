#!/usr/bin/env python3
import argparse
import itertools
from pathlib import Path
from typing import Dict, Tuple

import numpy as np


def load_anchor_positions(path: Path) -> Dict[int, Tuple[float, float, float]]:
    ns = {}
    exec(path.read_text(), ns)
    anchors = ns.get("anchor_positions")
    if not isinstance(anchors, dict):
        raise ValueError("anchor file must define anchor_positions dict")
    out = {}
    for k, v in anchors.items():
        out[int(k)] = (float(v[0]), float(v[1]), float(v[2]))
    return out


def pairwise_distances(points: np.ndarray):
    dists = []
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.linalg.norm(points[i] - points[j]))
            dists.append((i, j, d))
    return dists


def tetra_volume(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> float:
    return abs(np.linalg.det(np.stack([b - a, c - a, d - a], axis=1))) / 6.0


def observability_condition(anchors: np.ndarray, p: np.ndarray) -> Tuple[float, float]:
    rows = []
    for a in anchors:
        v = p - a
        r = float(np.linalg.norm(v))
        if r < 1e-6:
            continue
        rows.append(v / r)
    if len(rows) < 4:
        return float("inf"), 0.0
    h = np.array(rows)
    f = h.T @ h
    eig = np.sort(np.real(np.linalg.eigvals(f)))
    min_eig = float(eig[0])
    max_eig = float(eig[-1])
    cond = float(max_eig / min_eig) if min_eig > 1e-9 else float("inf")
    return cond, min_eig


def main() -> int:
    ap = argparse.ArgumentParser(description="Check anchor geometry risk for LPS")
    ap.add_argument("--anchors", default="scripts/anchors.py")
    ap.add_argument("--sample-z", type=float, default=0.5, help="Nominal flight altitude")
    ap.add_argument("--grid-xy", type=float, default=1.0, help="XY sample grid size in meters")
    args = ap.parse_args()

    anchors = load_anchor_positions(Path(args.anchors))
    ids = sorted(anchors.keys())
    pts = np.array([anchors[i] for i in ids], dtype=float)
    n = len(pts)

    print(f"anchors: {ids} (n={n})")
    if n < 4:
        print("FAIL: need at least 4 anchors")
        return 1

    xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]
    x_span = float(xs.max() - xs.min())
    y_span = float(ys.max() - ys.min())
    z_span = float(zs.max() - zs.min())
    print(f"span: x={x_span:.3f}m y={y_span:.3f}m z={z_span:.3f}m")

    # PCA flatness
    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    eig = np.sort(np.real(np.linalg.eigvals(cov)))[::-1]
    flat_ratio = float(eig[-1] / eig[0]) if eig[0] > 1e-12 else 0.0
    print(f"pca eig: [{eig[0]:.6f}, {eig[1]:.6f}, {eig[2]:.6f}] flat_ratio={flat_ratio:.6f}")

    # Pairwise distances
    pd = pairwise_distances(pts)
    dvals = np.array([d for _, _, d in pd], dtype=float)
    print(f"pairwise distance: min={dvals.min():.3f}m max={dvals.max():.3f}m mean={dvals.mean():.3f}m")

    # Tetra volumes
    vols = []
    for i, j, k, m in itertools.combinations(range(n), 4):
        vols.append(tetra_volume(pts[i], pts[j], pts[k], pts[m]))
    vols = np.array(vols, dtype=float)
    print(
        f"tetra volume: min={vols.min():.6f} max={vols.max():.6f} "
        f"median={np.median(vols):.6f} m^3"
    )

    # Observability over a simple XY grid around anchor centroid
    cx, cy = float(xs.mean()), float(ys.mean())
    half = args.grid_xy / 2.0
    samples = [
        np.array([cx - half, cy - half, args.sample_z]),
        np.array([cx + half, cy - half, args.sample_z]),
        np.array([cx + half, cy + half, args.sample_z]),
        np.array([cx - half, cy + half, args.sample_z]),
        np.array([cx, cy, args.sample_z]),
    ]
    conds = []
    mins = []
    for p in samples:
        c, me = observability_condition(pts, p)
        conds.append(c)
        mins.append(me)
    worst_cond = max(conds)
    worst_min_eig = min(mins)
    print(f"observability proxy: worst_cond={worst_cond:.3f} worst_min_eig={worst_min_eig:.6f}")

    # Risk flags
    flags = []
    if z_span < 0.5:
        flags.append("z-span < 0.5m (weak vertical geometry risk)")
    if flat_ratio < 0.02:
        flags.append("anchors nearly coplanar (low PCA flat_ratio)")
    if vols.max() < 0.03:
        flags.append("all anchor quadruples low-volume")
    if worst_cond > 25:
        flags.append("high observability condition number")
    if worst_min_eig < 0.15:
        flags.append("weak directional observability (min eigenvalue low)")

    if flags:
        print("RISK:")
        for f in flags:
            print(f"- {f}")
        return 1

    print("OK: geometry passes heuristic checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
