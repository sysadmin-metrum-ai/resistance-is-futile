"""Schedule construction for synchronized swarm execution."""

from __future__ import annotations

import time
from dataclasses import dataclass

from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import SwarmPlan
from src.swarm.planner import pattern_duration_s
from src.swarm.planner import pattern_final_hold_s
from src.swarm.planner import pattern_hold_s

SCHEDULE_PREP_S = 1.0
LED_POST_LAND_S = 3.0
RTL_LAND_SEQUENCE_DELAY_S = 2.0
FINAL_LAND_SETTLE_S = 0.5


@dataclass(frozen=True)
class SwarmSchedule:
    """Absolute monotonic timestamps every drone fires at."""

    takeoff_ats: tuple[float, ...]
    formation_fire_ats: tuple[tuple[float, ...], ...]
    led_blue_at: float
    pattern_fire_ats: tuple[tuple[float, ...], ...]
    return_fire_ats: tuple[tuple[float, ...], ...]
    land_ats: tuple[float, ...]
    cleanup_at: float

    @property
    def takeoff_at(self) -> float:
        return min(self.takeoff_ats) if self.takeoff_ats else 0.0

    @property
    def land_at(self) -> float:
        return max(self.land_ats) if self.land_ats else 0.0


def build_schedule(
    plan: SwarmPlan | MissionSpec,
    n_formation: int,
    n_pattern: int,
    n_return: int,
) -> SwarmSchedule:
    spec = plan.spec if isinstance(plan, SwarmPlan) else plan
    n_drones = len(plan.drones) if isinstance(plan, SwarmPlan) else spec.swarm_size
    t = time.monotonic() + SCHEDULE_PREP_S
    pattern_s = pattern_duration_s(spec)
    pattern_hold = pattern_hold_s(spec)
    pattern_final_hold = pattern_final_hold_s(spec)
    takeoff_at = t
    t += spec.takeoff_s + spec.hold_s

    formation_ranks = _formation_stagger_ranks(plan) if isinstance(plan, SwarmPlan) else tuple(range(n_drones))
    formation_fire_ats = _formation_times(
        start_at=t,
        spec=spec,
        n_formation=n_formation,
        formation_ranks=formation_ranks,
    )
    if n_formation > 0:
        t += n_drones * n_formation * (spec.move_s + spec.hold_s)

    led_blue_at = t
    t += 0.3

    pattern_steps: list[float] = []
    for _ in range(n_pattern):
        pattern_steps.append(t)
        t += pattern_s + pattern_hold
    t += pattern_final_hold

    return_ranks = _return_stagger_ranks(plan, n_return=n_return) if isinstance(plan, SwarmPlan) else tuple(range(n_drones))
    return_fire_ats, land_ats = _return_and_land_times(
        start_at=t,
        spec=spec,
        n_return=n_return,
        return_ranks=return_ranks,
    )
    cleanup_at = max(land_ats) + spec.land_s + LED_POST_LAND_S
    return SwarmSchedule(
        takeoff_ats=tuple(takeoff_at for _ in range(n_drones)),
        formation_fire_ats=formation_fire_ats,
        led_blue_at=led_blue_at,
        pattern_fire_ats=tuple(tuple(pattern_steps) for _ in range(n_drones)),
        return_fire_ats=return_fire_ats,
        land_ats=land_ats,
        cleanup_at=cleanup_at,
    )


def sleep_until(deadline: float) -> None:
    delay = deadline - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def _formation_times(
    *,
    start_at: float,
    spec: MissionSpec,
    n_formation: int,
    formation_ranks: tuple[int, ...],
) -> tuple[tuple[float, ...], ...]:
    if n_formation <= 0:
        return tuple(tuple() for _ in formation_ranks)
    route_span_s = n_formation * (spec.move_s + spec.hold_s)
    rank_fire_ats: dict[int, tuple[float, ...]] = {}
    for rank in range(len(formation_ranks)):
        route_start = start_at + rank * route_span_s
        rank_fire_ats[rank] = tuple(route_start + step * (spec.move_s + spec.hold_s) for step in range(n_formation))
    return tuple(rank_fire_ats[rank] for rank in formation_ranks)


def _return_and_land_times(
    *,
    start_at: float,
    spec: MissionSpec,
    n_return: int,
    return_ranks: tuple[int, ...],
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]:
    shared_steps = 1 if n_return > 1 else 0
    shared_fire_ats: list[float] = []
    cursor = start_at
    for _ in range(shared_steps):
        shared_fire_ats.append(cursor)
        cursor += spec.move_s + spec.hold_s

    rank_fire_ats: dict[int, tuple[float, ...]] = {}
    rank_land_ats: dict[int, float] = {}
    for rank in range(len(return_ranks)):
        fire_ats = list(shared_fire_ats)
        step_cursor = cursor
        for _ in range(shared_steps, n_return):
            fire_ats.append(step_cursor)
            step_cursor += spec.move_s + FINAL_LAND_SETTLE_S
        rank_fire_ats[rank] = tuple(fire_ats)
        rank_land_ats[rank] = step_cursor
        cursor = step_cursor + spec.land_s + RTL_LAND_SEQUENCE_DELAY_S
    return (
        tuple(rank_fire_ats[rank] for rank in return_ranks),
        tuple(rank_land_ats[rank] for rank in return_ranks),
    )


def _formation_stagger_ranks(plan: SwarmPlan) -> tuple[int, ...]:
    ordered = sorted(
        enumerate(plan.drones),
        key=lambda item: (_route_distance_m(item[1].return_point, item[1].route_to_formation), item[0]),
    )
    ranks = [0] * len(plan.drones)
    for rank, (drone_ix, _drone) in enumerate(ordered):
        ranks[drone_ix] = rank
    return tuple(ranks)


def _return_stagger_ranks(plan: SwarmPlan, *, n_return: int) -> tuple[int, ...]:
    shared_steps = 1 if n_return > 1 else 0
    ordered = sorted(
        enumerate(plan.drones),
        key=lambda item: (_return_home_distance_m(item[1], shared_steps=shared_steps), item[0]),
    )
    ranks = [0] * len(plan.drones)
    for rank, (drone_ix, _drone) in enumerate(ordered):
        ranks[drone_ix] = rank
    return tuple(ranks)


def _return_home_distance_m(drone: DronePlan, *, shared_steps: int) -> float:
    start = drone.pattern_points[-1] if drone.pattern_points else drone.formation_slot
    shared = drone.route_to_return[:shared_steps]
    home_route = drone.route_to_return[shared_steps:]
    if shared:
        start = shared[-1]
    return _route_distance_m(start, home_route)


def _route_distance_m(start: tuple[float, float, float], route: tuple[tuple[float, float, float], ...]) -> float:
    points = (start, *route)
    return sum(_distance_m(a, b) for a, b in zip(points, points[1:]))


def _distance_m(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
