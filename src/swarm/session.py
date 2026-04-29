"""Swarm session lifecycle: health, roster, planning, and execution."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

from src.swarm.executor import SwarmExecutor
from src.swarm.health import CflibHealthProbe
from src.swarm.health import HealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.health import normalize_uri
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import HealthThresholds
from src.swarm.models import MissionSpec
from src.swarm.models import MissionState
from src.swarm.models import SwarmSelection
from src.swarm.planner import SwarmPlan
from src.swarm.planner import build_swarm_plan
from src.swarm.pose import launch_poses_from_health
from src.swarm.roster import candidates_for_spec
from src.swarm.roster import select_healthiest_swarm

HEALTH_CACHE_TTL_S = 30.0
_health_cache: dict[str, tuple[float, DroneHealth]] = {}


def cache_health_results(results: list[DroneHealth]) -> None:
    """Store fresh health snapshots so deploy can skip the slow recheck."""
    now = time.monotonic()
    for health in results:
        _health_cache[normalize_uri(health.uri)] = (now, health)


def clear_health_cache() -> None:
    _health_cache.clear()


def _get_cached_health(uris: list[str]) -> list[DroneHealth] | None:
    now = time.monotonic()
    cached: list[DroneHealth] = []
    for uri in uris:
        entry = _health_cache.get(normalize_uri(uri))
        if entry is None:
            return None
        timestamp, health = entry
        if now - timestamp > HEALTH_CACHE_TTL_S:
            return None
        cached.append(health)
    return cached


@dataclass(frozen=True)
class DeployResult:
    mission_id: str
    state: MissionState
    selection: SwarmSelection
    plan: SwarmPlan | None
    events: tuple[str, ...] = ()
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "state": self.state.value,
            "selection": self.selection.to_dict(),
            "plan": _plan_to_dict(self.plan),
            "events": list(self.events),
            "message": self.message,
        }


class SwarmSessionRunner:
    """Build and optionally execute one active swarm session."""

    def __init__(
        self,
        *,
        probe: HealthProbe | None = None,
        executor: SwarmExecutor | None = None,
        thresholds: HealthThresholds | None = None,
    ):
        self.probe = probe or CflibHealthProbe()
        self.executor = executor or SwarmExecutor()
        self.thresholds = thresholds or HealthThresholds()

    async def deploy(self, spec: MissionSpec, candidates: list[DroneCandidate] | None = None) -> DeployResult:
        prepared = await self.prepare(spec, candidates)
        if prepared.plan is None or prepared.state == MissionState.REFUSED:
            return prepared
        if spec.dry_run:
            events = tuple(self.executor.execute(prepared.plan, arm=False))
            return DeployResult(
                prepared.mission_id,
                MissionState.DRY_RUN,
                prepared.selection,
                prepared.plan,
                events,
                message="dry_run",
            )
        if not spec.arm:
            return DeployResult(
                prepared.mission_id,
                MissionState.REFUSED,
                prepared.selection,
                prepared.plan,
                message="arm_required",
            )
        return await self.execute_prepared(prepared, spec)

    async def prepare(self, spec: MissionSpec, candidates: list[DroneCandidate] | None = None) -> DeployResult:
        spec.validate()
        mission_id = str(uuid.uuid4())
        candidate_list = candidates if candidates is not None else candidates_for_spec(spec)
        if not candidate_list:
            selection = SwarmSelection(selected=(), rejected=(), required_size=spec.swarm_size)
            return DeployResult(mission_id, MissionState.REFUSED, selection, None, message="no_candidates")

        cached = _get_cached_health([candidate.uri for candidate in candidate_list])
        if cached is not None:
            health = cached
        else:
            health = await check_candidates_concurrently(
                candidate_list,
                probe=self.probe,
                thresholds=self.thresholds,
            )
            cache_health_results(health)
        selection = select_healthiest_swarm(health, spec.swarm_size)
        if not selection.ready:
            return DeployResult(mission_id, MissionState.REFUSED, selection, None, message="insufficient_healthy_drones")

        try:
            poses = launch_poses_from_health(selection.selected, spec.hover_z)
            plan = build_swarm_plan(poses, spec)
        except ValueError as exc:
            return DeployResult(mission_id, MissionState.REFUSED, selection, None, message=str(exc))
        return DeployResult(mission_id, MissionState.ACCEPTED, selection, plan, message="prepared")

    async def execute_prepared(self, prepared: DeployResult, spec: MissionSpec) -> DeployResult:
        if prepared.plan is None:
            return prepared
        events = await asyncio.to_thread(self.executor.execute, prepared.plan, arm=True)
        return DeployResult(
            prepared.mission_id,
            MissionState.COMPLETED,
            prepared.selection,
            prepared.plan,
            tuple(events),
            message="completed",
        )


def _plan_to_dict(plan: SwarmPlan | None) -> dict | None:
    if plan is None:
        return None
    return {
        "assignment_cost": plan.assignment_cost,
        "formation": plan.spec.formation,
        "pattern": plan.spec.pattern,
        "final_pose": list(plan.spec.final_pose),
        "min_separation_m": plan.spec.min_separation_m,
        "collision_avoidance": plan.spec.enable_collision_avoidance,
        "no_fly_zone_paths": list(plan.spec.no_fly_zone_paths),
        "drones": [
            {
                "uri": drone.uri,
                "launch": list(drone.launch),
                "formation_slot": list(drone.formation_slot),
                "route_to_formation": [list(point) for point in drone.route_to_formation],
                "pattern_points": [list(point) for point in drone.pattern_points],
                "route_to_return": [list(point) for point in drone.route_to_return],
                "return_point": list(drone.return_point),
            }
            for drone in plan.drones
        ],
    }
