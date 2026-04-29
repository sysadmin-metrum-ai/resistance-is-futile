"""Pose-based role assignment for interchangeable drones."""

from __future__ import annotations

import itertools
import math

from src.swarm.models import Vec3


def distance3(a: Vec3, b: Vec3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def optimal_assignment(measured: list[Vec3], targets: list[Vec3]) -> tuple[list[int], float]:
    """Return target index per drone with minimum total travel distance."""

    if len(measured) != len(targets):
        raise ValueError("measured and targets must have the same length")
    if not measured:
        return [], 0.0

    best_perm: tuple[int, ...] | None = None
    best_cost = float("inf")
    for perm in itertools.permutations(range(len(targets))):
        cost = sum(distance3(measured[i], targets[perm[i]]) for i in range(len(measured)))
        if cost < best_cost:
            best_cost = cost
            best_perm = perm

    assert best_perm is not None
    return list(best_perm), best_cost
