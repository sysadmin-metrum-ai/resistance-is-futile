"""Dynamic swarm flight-path planning from a final pose and pattern spec."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

from src.safety.geofence import GeofenceBox
from src.safety.geofence import load_box
from src.swarm.assignment import distance3
from src.swarm.models import MissionSpec
from src.swarm.models import Vec3


@dataclass(frozen=True)
class DronePlan:
    uri: str
    launch: Vec3
    formation_slot: Vec3
    route_to_formation: tuple[Vec3, ...]
    pattern_points: tuple[Vec3, ...]
    route_to_return: tuple[Vec3, ...]
    return_point: Vec3


@dataclass(frozen=True)
class SwarmPlan:
    spec: MissionSpec
    drones: tuple[DronePlan, ...]
    assignment_cost: float


class PathSafetyError(ValueError):
    """Raised when planned simultaneous paths violate inter-drone clearance."""


def formation_slots(spec: MissionSpec) -> list[Vec3]:
    """Build formation slots around `spec.final_pose` for the requested swarm size."""

    spec.validate()
    x, y, z = spec.final_pose
    spacing = spec.slot_spacing_m
    n = spec.swarm_size

    if spec.formation == "line":
        offsets = [(0.0, (i - (n - 1) / 2.0) * spacing, 0.0) for i in range(n)]
    elif spec.formation == "triangle":
        offsets = _triangle_offsets(n, spacing)
    elif spec.formation == "diamond":
        offsets = _diamond_offsets(n, spacing)
    elif spec.formation == "v":
        offsets = _v_offsets(n, spacing)
    else:
        raise ValueError(f"unsupported formation: {spec.formation}")

    return [(x + dx, y + dy, z + dz) for dx, dy, dz in offsets]


def build_swarm_plan(uri_to_launch: dict[str, Vec3], spec: MissionSpec) -> SwarmPlan:
    """Assign drones to slots and create per-drone pattern/return points."""

    spec.validate()
    if len(uri_to_launch) != spec.swarm_size:
        raise ValueError("launch pose count must match swarm_size")

    uris = list(uri_to_launch.keys())
    launches = [uri_to_launch[uri] for uri in uris]
    slots = formation_slots(spec)
    no_fly_zones = load_no_fly_zones(spec.no_fly_zone_paths)
    unsafe_reason: PathSafetyError | None = None
    no_fly_reason: PathSafetyError | None = None
    for assignment, cost in _ranked_assignments(launches, slots):
        try:
            plan = SwarmPlan(
                spec=spec,
                drones=tuple(
                    _drone_plan(uri, launches[i], slots[assignment[i]], spec, no_fly_zones)
                    for i, uri in enumerate(uris)
                ),
                assignment_cost=cost,
            )
            validate_swarm_plan_clearance(plan, no_fly_zones=no_fly_zones)
            return plan
        except PathSafetyError as exc:
            if "no_fly_zone:" in str(exc) and no_fly_reason is None:
                no_fly_reason = exc
            unsafe_reason = exc

    raise no_fly_reason or unsafe_reason or PathSafetyError("no safe assignment found")


def load_no_fly_zones(paths: tuple[str, ...]) -> tuple[GeofenceBox, ...]:
    boxes: list[GeofenceBox] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise PathSafetyError(f"no_fly_zone_missing:{raw_path}")
        boxes.append(load_box(path))
    return tuple(boxes)


def _ranked_assignments(measured: list[Vec3], targets: list[Vec3]) -> list[tuple[tuple[int, ...], float]]:
    ranked: list[tuple[tuple[int, ...], float]] = []
    for perm in itertools.permutations(range(len(targets))):
        cost = sum(distance3(measured[i], targets[perm[i]]) for i in range(len(measured)))
        ranked.append((perm, cost))
    return sorted(ranked, key=lambda item: item[1])


def _drone_plan(uri: str, launch: Vec3, slot: Vec3, spec: MissionSpec, zones: tuple[GeofenceBox, ...]) -> DronePlan:
    return_point = (launch[0], launch[1], spec.hover_z)
    return DronePlan(
        uri=uri,
        launch=launch,
        formation_slot=slot,
        route_to_formation=_route_between(launch, slot, spec, zones),
        pattern_points=_pattern_points(slot, spec),
        route_to_return=_route_between(slot, return_point, spec, zones),
        return_point=return_point,
    )


def validate_swarm_plan_clearance(
    plan: SwarmPlan,
    samples_per_segment: int = 25,
    no_fly_zones: tuple[GeofenceBox, ...] = (),
) -> None:
    """Verify all simultaneous path samples keep the requested clearance.

    The controller has global visibility from sampled launch poses and rejects
    paths that would place two drone centers closer than `min_separation_m`.
    Hardware execution also enables firmware BVCA as a reactive safety layer.
    """

    if len(plan.drones) < 2:
        return

    timelines = _padded_timelines([_timeline(drone) for drone in plan.drones])
    segment_count = len(timelines[0]) - 1

    for segment_ix in range(segment_count):
        for sample_ix in range(samples_per_segment + 1):
            t = sample_ix / samples_per_segment
            points = [
                _lerp(timeline[segment_ix], timeline[segment_ix + 1], t)
                for timeline in timelines
            ]
            _assert_min_distance(points, plan.spec.min_separation_m, f"segment_{segment_ix}")
            _assert_clear_of_no_fly_zones(points, no_fly_zones, f"segment_{segment_ix}")


def _timeline(drone: DronePlan) -> list[Vec3]:
    return [
        drone.launch,
        *drone.route_to_formation,
        *drone.pattern_points,
        *drone.route_to_return,
    ]


def _padded_timelines(timelines: list[list[Vec3]]) -> list[list[Vec3]]:
    max_len = max(len(timeline) for timeline in timelines)
    return [timeline + [timeline[-1]] * (max_len - len(timeline)) for timeline in timelines]


def _lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def _route_between(start: Vec3, goal: Vec3, spec: MissionSpec, zones: tuple[GeofenceBox, ...]) -> tuple[Vec3, ...]:
    _raise_if_point_in_zone(start, zones, "route_start")
    _raise_if_point_in_zone(goal, zones, "route_goal")

    direct = (goal,)
    if _polyline_clear((start, *direct), zones):
        return direct

    candidates: list[tuple[Vec3, ...]] = []
    for zone in zones:
        candidates.extend(_detour_candidates(start, goal, zone, spec))

    ranked = sorted(candidates, key=lambda route: _route_distance(start, route))
    for route in ranked:
        if _polyline_clear((start, *route), zones):
            return route

    raise PathSafetyError("no safe geofence detour found")


def _raise_if_point_in_zone(point: Vec3, zones: tuple[GeofenceBox, ...], label: str) -> None:
    for zone in zones:
        if zone.contains(point):
            raise PathSafetyError(f"{label} enters no_fly_zone:{zone.name}")


def _polyline_clear(points: tuple[Vec3, ...], zones: tuple[GeofenceBox, ...], samples_per_segment: int = 25) -> bool:
    for start, goal in zip(points, points[1:]):
        for sample_ix in range(samples_per_segment + 1):
            point = _lerp(start, goal, sample_ix / samples_per_segment)
            if any(zone.contains(point) for zone in zones):
                return False
    return True


def _detour_candidates(start: Vec3, goal: Vec3, zone: GeofenceBox, spec: MissionSpec) -> list[tuple[Vec3, ...]]:
    clearance = max(spec.min_separation_m, zone.margin, 0.10)
    z = max(start[2], goal[2], spec.hover_z)
    min_x, min_y, _min_z = zone.inflated_minimum
    max_x, max_y, max_z = zone.inflated_maximum
    sx, sy, _sz = start
    gx, gy, _gz = goal

    side_routes = [
        ((min_x - clearance, sy, z), (min_x - clearance, gy, z), goal),
        ((max_x + clearance, sy, z), (max_x + clearance, gy, z), goal),
        ((sx, min_y - clearance, z), (gx, min_y - clearance, z), goal),
        ((sx, max_y + clearance, z), (gx, max_y + clearance, z), goal),
    ]
    over_z = max(max_z + clearance, z)
    over_route = ((sx, sy, over_z), (gx, gy, over_z), goal)
    return [*side_routes, over_route]


def _route_distance(start: Vec3, route: tuple[Vec3, ...]) -> float:
    total = 0.0
    current = start
    for point in route:
        total += distance3(current, point)
        current = point
    return total


def _assert_min_distance(points: list[Vec3], min_distance: float, phase: str) -> None:
    for i, first in enumerate(points):
        for j, second in enumerate(points[i + 1 :], start=i + 1):
            dist = distance3(first, second)
            if dist < min_distance:
                raise PathSafetyError(
                    f"{phase}: drones {i} and {j} clearance {dist:.3f}m < {min_distance:.3f}m"
                )


def _assert_clear_of_no_fly_zones(points: list[Vec3], zones: tuple[GeofenceBox, ...], phase: str) -> None:
    for drone_ix, point in enumerate(points):
        for zone in zones:
            if zone.contains(point):
                raise PathSafetyError(f"{phase}: drone {drone_ix} enters no_fly_zone:{zone.name}")


def _pattern_points(slot: Vec3, spec: MissionSpec) -> tuple[Vec3, ...]:
    x, y, z = slot
    d = spec.slot_spacing_m * 0.5
    if spec.pattern == "hold":
        return (slot,)
    if spec.pattern == "line_shift":
        return ((x + d, y, z), (x - d, y, z), slot)
    if spec.pattern == "square":
        return ((x + d, y, z), (x + d, y + d, z), (x, y + d, z), slot)
    if spec.pattern == "up_forward":
        # Each drone steps +1m forward (X) and +1m up (Z) from its slot,
        # holds, then comes back to the slot before returning to launch.
        return ((x + 1.0, y, z + 1.0), slot)
    raise ValueError(f"unsupported pattern: {spec.pattern}")


def _triangle_offsets(n: int, spacing: float) -> list[Vec3]:
    top_z = spacing * 0.75
    top_x = spacing * 0.45
    if n == 5:
        return [
            (0.0, -spacing, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, spacing, 0.0),
            (top_x, -spacing * 0.5, top_z),
            (top_x, spacing * 0.5, top_z),
        ]
    if n == 4:
        return [
            (0.0, -spacing * 0.75, 0.0),
            (0.0, spacing * 0.25, 0.0),
            (top_x, -spacing * 0.25, top_z),
            (top_x, spacing * 0.75, top_z),
        ]
    return [
        (0.0, -spacing * 0.5, 0.0),
        (0.0, spacing * 0.5, 0.0),
        (top_x, 0.0, top_z),
    ]


def _diamond_offsets(n: int, spacing: float) -> list[Vec3]:
    base = [
        (0.0, 0.0, 0.0),
        (spacing, 0.0, 0.0),
        (0.0, spacing, 0.0),
        (-spacing, 0.0, 0.0),
        (0.0, -spacing, 0.0),
    ]
    return base[:n]


def _v_offsets(n: int, spacing: float) -> list[Vec3]:
    offsets: list[Vec3] = [(0.0, 0.0, 0.0)]
    wing = 1
    while len(offsets) < n:
        offsets.append((-wing * spacing, -wing * spacing, 0.0))
        if len(offsets) < n:
            offsets.append((-wing * spacing, wing * spacing, 0.0))
        wing += 1
    return offsets
