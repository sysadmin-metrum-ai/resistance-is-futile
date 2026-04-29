"""Pose helpers for launch sampling and validation."""

from __future__ import annotations

from src.swarm.models import DroneHealth
from src.swarm.models import Vec3


def launch_poses_from_health(selected: list[DroneHealth] | tuple[DroneHealth, ...], hover_z: float) -> dict[str, Vec3]:
    """Use health-check pose samples as the controller's launch references."""

    poses: dict[str, Vec3] = {}
    for health in selected:
        if health.pose is None:
            raise ValueError(f"{health.uri} has no launch pose")
        poses[health.uri] = health.pose
    return poses


def minimum_xy_spacing(poses: list[Vec3]) -> float:
    if len(poses) < 2:
        return float("inf")
    best = float("inf")
    for i, first in enumerate(poses):
        for second in poses[i + 1 :]:
            dist = ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5
            best = min(best, dist)
    return best
