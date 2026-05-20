"""Dynamic swarm flight-path planning from a final pose and pattern spec."""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from typing import Literal
from functools import lru_cache
from pathlib import Path

from src.safety.geofence import GeofenceBox
from src.safety.geofence import load_box
from src.swarm.assignment import distance3
from src.swarm.assignment import optimal_assignment
from src.swarm.models import CRAZY_PINWHEEL_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.models import Vec3

CRAZY_PINWHEEL_RADIUS_EPS_M = 0.05

CAPTURED_RTL_XY_LANE_M = 0.15
TAKEOFF_MIN_XY_SEPARATION_M = 0.13
CAPTURED_MIN_PATTERN_S = 0.4


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
    x, y, z = _formation_center(spec)
    spacing = spec.slot_spacing_m
    n = spec.swarm_size

    if spec.pattern == "crazy_pinwheel":
        if n != CRAZY_PINWHEEL_SWARM_SIZE:
            raise ValueError(f"crazy_pinwheel requires swarm_size={CRAZY_PINWHEEL_SWARM_SIZE}")
        offsets = _crazy_pinwheel_offsets(spacing, spec.crazy_pinwheel_outer_delta_m)
    elif spec.formation == "line":
        offsets = [(0.0, (i - (n - 1) / 2.0) * spacing, 0.0) for i in range(n)]
    elif spec.formation == "triangle":
        offsets = _triangle_offsets(n, spacing)
    elif spec.formation == "diamond":
        offsets = _diamond_offsets(n, spacing)
    elif spec.formation == "v":
        offsets = _v_offsets(n, spacing)
    else:
        raise ValueError(f"unsupported formation: {spec.formation}")

    if spec.pattern == "captured_path":
        offsets = [_rotate_offset(offset, formation_yaw(spec)) for offset in offsets]

    return [(x + dx, y + dy, z + dz) for dx, dy, dz in offsets]


def build_swarm_plan(uri_to_launch: dict[str, Vec3], spec: MissionSpec) -> SwarmPlan:
    """Assign drones to slots and create per-drone pattern/return points."""

    spec.validate()
    if len(uri_to_launch) != spec.swarm_size:
        raise ValueError("launch pose count must match swarm_size")
    if spec.pattern == "launch_up":
        plan = SwarmPlan(
            spec=spec,
            drones=tuple(_launch_up_drone_plan(uri, launch, spec) for uri, launch in uri_to_launch.items()),
            assignment_cost=0.0,
        )
        validate_swarm_plan_clearance(plan, no_fly_zones=load_no_fly_zones(spec.no_fly_zone_paths))
        return plan

    uris = list(uri_to_launch.keys())
    launches = [uri_to_launch[uri] for uri in uris]
    slots = formation_slots(spec)
    no_fly_zones = load_no_fly_zones(spec.no_fly_zone_paths)
    unsafe_reason: PathSafetyError | None = None
    no_fly_reason: PathSafetyError | None = None
    for assignment, cost in _ranked_assignments(launches, slots, spec):
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


def _ranked_assignments(
    measured: list[Vec3],
    targets: list[Vec3],
    spec: MissionSpec,
) -> list[tuple[tuple[int, ...], float]]:
    if spec.pattern == "crazy_pinwheel":
        assignment, cost = _crazy_pinwheel_assignment(measured, targets, spec)
        return [(tuple(assignment), cost)]

    ranked: list[tuple[tuple[int, ...], float]] = []
    for perm in itertools.permutations(range(len(targets))):
        cost = sum(distance3(measured[i], targets[perm[i]]) for i in range(len(measured)))
        ranked.append((perm, cost))
    return sorted(ranked, key=lambda item: item[1])


def _drone_plan(uri: str, launch: Vec3, slot: Vec3, spec: MissionSpec, zones: tuple[GeofenceBox, ...]) -> DronePlan:
    return_point = (launch[0], launch[1], spec.hover_z)
    pattern_points = _pattern_points(slot, spec)
    return DronePlan(
        uri=uri,
        launch=launch,
        formation_slot=slot,
        route_to_formation=_route_between(return_point, slot, spec, zones),
        pattern_points=pattern_points,
        route_to_return=_route_to_return(slot, pattern_points, return_point, spec, zones),
        return_point=return_point,
    )


def _launch_up_drone_plan(uri: str, launch: Vec3, spec: MissionSpec) -> DronePlan:
    return_point = (launch[0], launch[1], spec.hover_z)
    high_point = (launch[0], launch[1], spec.final_pose[2])
    return DronePlan(
        uri=uri,
        launch=launch,
        formation_slot=return_point,
        route_to_formation=(),
        pattern_points=(high_point,),
        route_to_return=(return_point,),
        return_point=return_point,
    )


def _route_to_return(
    slot: Vec3,
    pattern_points: tuple[Vec3, ...],
    return_point: Vec3,
    spec: MissionSpec,
    zones: tuple[GeofenceBox, ...],
) -> tuple[Vec3, ...]:
    if spec.pattern == "captured_path" and pattern_points:
        final_slot = _captured_final_slot(slot, spec)
        return (final_slot, return_point)
    return _route_between(slot, return_point, spec, zones)


def validate_swarm_plan_clearance(
    plan: SwarmPlan,
    samples_per_segment: int = 100,
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
        min_separation_m = _segment_min_separation(plan.spec, segment_ix)
        first_sample_ix = 0 if segment_ix == 0 else 1
        for sample_ix in range(first_sample_ix, samples_per_segment + 1):
            t = sample_ix / samples_per_segment
            points = [
                _lerp(timeline[segment_ix], timeline[segment_ix + 1], t)
                for timeline in timelines
            ]
            _assert_min_distance(points, min_separation_m, f"segment_{segment_ix}")
            _assert_clear_of_no_fly_zones(points, no_fly_zones, f"segment_{segment_ix}")


def _timeline(drone: DronePlan) -> list[Vec3]:
    return [
        drone.launch,
        drone.return_point,
        *drone.route_to_formation,
        *drone.pattern_points,
        *drone.route_to_return,
    ]


def _segment_min_separation(spec: MissionSpec, segment_ix: int) -> float:
    if segment_ix == 0:
        return min(spec.min_separation_m, TAKEOFF_MIN_XY_SEPARATION_M)
    return spec.min_separation_m


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
            dist = _distance_xy(first, second)
            if dist < min_distance:
                raise PathSafetyError(
                    f"{phase}: drones {i} and {j} xy clearance {dist:.3f}m < {min_distance:.3f}m"
                )


def _distance_xy(a: Vec3, b: Vec3) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


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
    if spec.pattern == "launch_up":
        return ((x, y, spec.final_pose[2]), slot)
    if spec.pattern == "crazy_pinwheel":
        return _crazy_pinwheel_points(slot, spec)
    if spec.pattern == "captured_path":
        center = _formation_center(spec)
        slot_offset = (x - center[0], y - center[1], z - center[2])
        start_yaw = formation_yaw(spec)
        points: list[Vec3] = []
        relative_points = _captured_relative_points(spec)
        previous_yaw = start_yaw
        for (dx, dy, dz), yaw in zip(relative_points, _captured_yaws_for_relative_points(spec)):
            path_center = (center[0] + dx, center[1] + dy, center[2] + dz)
            points.append(_captured_offset_point(path_center, slot_offset, previous_yaw, start_yaw))
            if abs(yaw - previous_yaw) > 1e-6:
                points.append(_captured_offset_point(path_center, slot_offset, yaw, start_yaw))
            previous_yaw = yaw
        return tuple(points)
    raise ValueError(f"unsupported pattern: {spec.pattern}")


def _crazy_pinwheel_points(slot: Vec3, spec: MissionSpec) -> tuple[Vec3, ...]:
    tier = _crazy_pinwheel_tier(slot, spec)
    if tier == "center":
        return (
            (slot[0], slot[1], slot[2] + 0.22),
            (slot[0], slot[1], slot[2] + 0.34),
            (slot[0], slot[1], slot[2] + 0.22),
            slot,
        )
    if tier == "middle":
        return _crazy_pinwheel_orbit(slot, spec, steps=4, z_lift_angles={math.pi / 2.0, math.pi * 1.5})
    if tier == "outer":
        return _crazy_pinwheel_orbit(slot, spec, steps=5, z_lift_angles=set())
    raise ValueError(f"crazy_pinwheel slot not on a known ring: {slot}")


def _crazy_pinwheel_orbit(
    slot: Vec3,
    spec: MissionSpec,
    *,
    steps: int,
    z_lift_angles: set[float],
) -> tuple[Vec3, ...]:
    cx, cy, _ = spec.final_pose
    dx, dy, dz = slot[0] - cx, slot[1] - cy, slot[2] - spec.final_pose[2]
    points: list[Vec3] = []
    for step in range(1, steps + 1):
        angle = step * (2.0 * math.pi / steps)
        rdx, rdy, _ = _rotate_offset((dx, dy, dz), angle)
        z_lift = 0.10 if angle in z_lift_angles else 0.0
        points.append((cx + rdx, cy + rdy, slot[2] + z_lift))
    points.append(slot)
    return tuple(points)


def _crazy_pinwheel_offsets(spacing: float, outer_delta: float) -> list[Vec3]:
    outer_radius = spacing + outer_delta
    middle = [
        (spacing, 0.0, 0.0),
        (0.0, spacing, 0.0),
        (-spacing, 0.0, 0.0),
        (0.0, -spacing, 0.0),
    ]
    outer: list[Vec3] = []
    for index in range(5):
        angle = math.pi / 5.0 + index * (2.0 * math.pi / 5.0)
        outer.append((outer_radius * math.cos(angle), outer_radius * math.sin(angle), 0.0))
    return [(0.0, 0.0, 0.0), *middle, *outer]


def _crazy_pinwheel_tier(slot: Vec3, spec: MissionSpec) -> Literal["center", "middle", "outer"]:
    radius = _crazy_pinwheel_xy_radius(slot, spec)
    spacing = spec.slot_spacing_m
    outer_radius = spacing + spec.crazy_pinwheel_outer_delta_m
    if radius < CRAZY_PINWHEEL_RADIUS_EPS_M:
        return "center"
    if abs(radius - spacing) < CRAZY_PINWHEEL_RADIUS_EPS_M:
        return "middle"
    if abs(radius - outer_radius) < CRAZY_PINWHEEL_RADIUS_EPS_M:
        return "outer"
    raise ValueError(f"crazy_pinwheel slot radius {radius:.3f}m is not on a known ring")


def _crazy_pinwheel_xy_radius(slot: Vec3, spec: MissionSpec) -> float:
    cx, cy, _ = spec.final_pose
    return math.hypot(slot[0] - cx, slot[1] - cy)


def _crazy_pinwheel_assignment(
    measured: list[Vec3],
    targets: list[Vec3],
    spec: MissionSpec,
) -> tuple[list[int], float]:
    del spec
    return optimal_assignment(measured, targets)


def _formation_center(spec: MissionSpec) -> Vec3:
    if spec.pattern != "captured_path":
        return spec.final_pose
    return _load_captured_path(spec.captured_path)["start"]


def _captured_relative_points(spec: MissionSpec) -> tuple[Vec3, ...]:
    points = _load_captured_path(spec.captured_path)["relative_points"]
    if not points:
        raise ValueError("captured_path must contain at least one relative point")
    return points


def _captured_final_center(spec: MissionSpec) -> Vec3:
    data = _load_captured_path(spec.captured_path)
    configured = data.get("final_center")
    if isinstance(configured, list | tuple) and len(configured) == 3:
        return _vec3(configured, "final_center")
    return spec.final_pose


def _captured_final_slot(slot: Vec3, spec: MissionSpec) -> Vec3:
    center = _formation_center(spec)
    slot_offset = (slot[0] - center[0], slot[1] - center[1], slot[2] - center[2])
    rotated_offset = _rotate_offset(slot_offset, go_to_yaw(spec) - formation_yaw(spec))
    final_center = _captured_final_center(spec)
    return (
        final_center[0] + rotated_offset[0],
        final_center[1] + rotated_offset[1],
        final_center[2] + rotated_offset[2],
    )


def _captured_return_lane_point(final_slot: Vec3, return_point: Vec3) -> Vec3:
    dy = return_point[1]
    if dy > 0:
        lane_y = dy + CAPTURED_RTL_XY_LANE_M
    elif dy < 0:
        lane_y = dy - CAPTURED_RTL_XY_LANE_M
    else:
        lane_y = CAPTURED_RTL_XY_LANE_M
    return (return_point[0], lane_y, final_slot[2])


def go_to_yaw(spec: MissionSpec) -> float:
    if spec.pattern == "captured_path" and spec.captured_path:
        yaws = _captured_yaws(spec)
        if yaws:
            return yaws[-1]
    return spec.yaw_rad


def formation_yaw(spec: MissionSpec) -> float:
    if spec.pattern == "captured_path" and spec.captured_path:
        data = _load_captured_path(spec.captured_path)
        start_yaw = data.get("start_yaw_rad")
        if isinstance(start_yaw, int | float):
            return float(start_yaw)
        yaws = _captured_yaws(spec)
        if yaws:
            return yaws[0]
    return go_to_yaw(spec)


def pattern_yaws(spec: MissionSpec, count: int) -> tuple[float, ...]:
    if count <= 0:
        return tuple()
    if spec.pattern == "captured_path" and spec.captured_path:
        yaws = _captured_expanded_yaws(spec)
        if yaws:
            if len(yaws) >= count:
                return yaws[:count]
            return yaws + (yaws[-1],) * (count - len(yaws))
    return (go_to_yaw(spec),) * count


def _captured_yaws_for_relative_points(spec: MissionSpec) -> tuple[float, ...]:
    relative_points = _captured_relative_points(spec)
    yaws = _captured_yaws(spec)
    if not yaws:
        return (go_to_yaw(spec),) * len(relative_points)
    if len(yaws) >= len(relative_points):
        return yaws[: len(relative_points)]
    return yaws + (yaws[-1],) * (len(relative_points) - len(yaws))


def _captured_expanded_yaws(spec: MissionSpec) -> tuple[float, ...]:
    start_yaw = formation_yaw(spec)
    expanded: list[float] = []
    previous_yaw = start_yaw
    for yaw in _captured_yaws_for_relative_points(spec):
        expanded.append(previous_yaw)
        if abs(yaw - previous_yaw) > 1e-6:
            expanded.append(yaw)
        previous_yaw = yaw
    return tuple(expanded)


def _captured_yaws(spec: MissionSpec) -> tuple[float, ...]:
    data = _load_captured_path(spec.captured_path)
    raw_yaws = data.get("yaw_points_rad")
    if not isinstance(raw_yaws, list | tuple) or not raw_yaws:
        yaw = data.get("yaw_rad")
        return (float(yaw),) if isinstance(yaw, int | float) else tuple()
    raw_start_yaw = data.get("start_yaw_rad")
    start_yaw = float(raw_start_yaw) if isinstance(raw_start_yaw, int | float) else float(raw_yaws[0])
    return _unwrap_yaws(tuple(float(yaw) for yaw in raw_yaws), start_yaw)


def _unwrap_yaws(yaws: tuple[float, ...], start_yaw: float) -> tuple[float, ...]:
    unwrapped: list[float] = []
    previous = start_yaw
    for yaw in yaws:
        while yaw - previous > math.pi:
            yaw -= math.tau
        while yaw - previous < -math.pi:
            yaw += math.tau
        unwrapped.append(yaw)
        previous = yaw
    return tuple(unwrapped)


def pattern_duration_s(spec: MissionSpec) -> float:
    if spec.pattern == "captured_path" and spec.captured_path:
        duration = _load_captured_path(spec.captured_path).get("pattern_s")
        if isinstance(duration, int | float) and float(duration) > 0:
            return max(float(duration), CAPTURED_MIN_PATTERN_S)
    return spec.pattern_s


def pattern_hold_s(spec: MissionSpec) -> float:
    if spec.pattern == "captured_path" and spec.captured_path:
        hold_s = _load_captured_path(spec.captured_path).get("pattern_hold_s")
        if isinstance(hold_s, int | float) and float(hold_s) >= 0:
            return float(hold_s)
        return 0.0
    return spec.hold_s


def pattern_final_hold_s(spec: MissionSpec) -> float:
    if spec.pattern == "captured_path" and spec.captured_path:
        final_hold_s = _load_captured_path(spec.captured_path).get("pattern_final_hold_s")
        if isinstance(final_hold_s, int | float) and float(final_hold_s) >= 0:
            return float(final_hold_s)
    return 0.0


@lru_cache(maxsize=8)
def _load_captured_path(raw_path: str | None) -> dict[str, object]:
    if raw_path is None:
        raise ValueError("captured_path is required")
    path = Path(raw_path)
    if not path.exists():
        raise ValueError(f"captured_path_missing:{raw_path}")
    data = json.loads(path.read_text())
    start = _vec3(data.get("start"), "start")
    relative_points = tuple(_vec3(point, "relative_points") for point in data.get("relative_points", ()))
    return {
        "start": start,
        "relative_points": relative_points,
        "final_center": data.get("final_center"),
        "pattern_s": data.get("pattern_s"),
        "pattern_hold_s": data.get("pattern_hold_s"),
        "pattern_final_hold_s": data.get("pattern_final_hold_s"),
        "start_yaw_rad": data.get("start_yaw_rad"),
        "yaw_rad": data.get("yaw_rad"),
        "yaw_points_rad": data.get("yaw_points_rad"),
    }


def _vec3(raw: object, label: str) -> Vec3:
    if not isinstance(raw, list | tuple) or len(raw) != 3:
        raise ValueError(f"captured_path_invalid:{label}")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def _rotate_offset(offset: Vec3, yaw_rad: float) -> Vec3:
    x, y, z = offset
    c = math.cos(yaw_rad)
    s = math.sin(yaw_rad)
    return (x * c - y * s, x * s + y * c, z)


def _captured_offset_point(path_center: Vec3, slot_offset: Vec3, yaw: float, start_yaw: float) -> Vec3:
    rotated_offset = _rotate_offset(slot_offset, yaw - start_yaw)
    return (
        path_center[0] + rotated_offset[0],
        path_center[1] + rotated_offset[1],
        path_center[2] + rotated_offset[2],
    )


def _triangle_offsets(n: int, spacing: float) -> list[Vec3]:
    top_z = spacing * 0.75
    top_x = spacing * 0.60
    if n == 1:
        return [(0.0, 0.0, 0.0)]
    if n == 2:
        return [
            (0.0, -spacing * 0.5, 0.0),
            (0.0, spacing * 0.5, 0.0),
        ]
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
