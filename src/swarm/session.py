"""Swarm session lifecycle: health, roster, planning, and execution."""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace

from src.swarm.executor import SwarmExecutor
from src.swarm.executor import PhaseCallback
from src.swarm.executor import PreparedExecution
from src.swarm.health import CflibHealthProbe
from src.swarm.health import HealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import HealthThresholds
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.models import MissionState
from src.swarm.models import SwarmSelection
from src.swarm.planner import SwarmPlan
from src.swarm.planner import build_swarm_plan
from src.swarm.planner import load_no_fly_zones
from src.swarm.pose import launch_poses_from_health
from src.swarm.roster import candidates_for_spec
from src.swarm.roster import select_healthiest_swarm

BatteryTelemetryCallback = Callable[[str, dict], None]


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
            result = self.executor.execute(prepared.plan, arm=False)
            return DeployResult(
                prepared.mission_id,
                MissionState.DRY_RUN,
                prepared.selection,
                result.plan,
                result.events,
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

        thresholds = replace(
            self.thresholds,
            health_timeout_s=spec.health_timeout_s,
            max_concurrent_checks=spec.max_concurrent_checks,
        )
        health = await check_candidates_concurrently(
            candidate_list,
            probe=self.probe,
            thresholds=thresholds,
        )
        health = [_reject_missing_pose(item) for item in health]
        # TODO: Re-enable for demos with physical no-fly zones around the server.
        # health = _reject_no_fly_zone_launches(health, spec)
        minimum_size = minimum_viable_swarm_size(spec.swarm_size)
        selection = select_healthiest_swarm(health, spec.swarm_size, minimum_size=minimum_size)
        if not selection.ready:
            return DeployResult(mission_id, MissionState.REFUSED, selection, None, message="insufficient_healthy_drones")

        try:
            planned_spec = replace(spec, swarm_size=len(selection.selected))
            poses = launch_poses_from_health(selection.selected, planned_spec.hover_z)
            plan = build_swarm_plan(poses, planned_spec)
        except ValueError as exc:
            return DeployResult(mission_id, MissionState.REFUSED, selection, None, message=str(exc))
        return DeployResult(mission_id, MissionState.ACCEPTED, selection, plan, message="prepared")

    async def execute_prepared(
        self,
        prepared: DeployResult,
        spec: MissionSpec,
        telemetry_callback: BatteryTelemetryCallback | None = None,
        phase_callback: PhaseCallback | None = None,
    ) -> DeployResult:
        if prepared.plan is None:
            return prepared
        execute = self.executor.execute
        kwargs = {"arm": True}
        if "telemetry_callback" in inspect.signature(execute).parameters:
            kwargs["telemetry_callback"] = telemetry_callback
        if "phase_callback" in inspect.signature(execute).parameters:
            kwargs["phase_callback"] = phase_callback
        result = await asyncio.to_thread(execute, prepared.plan, **kwargs)
        return self.completed_result(prepared, result)

    async def prepare_execution(
        self,
        prepared: DeployResult,
        phase_callback: PhaseCallback | None = None,
        retained_connections: dict | None = None,
    ) -> PreparedExecution:
        if prepared.plan is None:
            raise ValueError("prepared result has no plan")
        prepare = self.executor.prepare
        kwargs = {"phase_callback": phase_callback}
        if "retained_connections" in inspect.signature(prepare).parameters:
            kwargs["retained_connections"] = retained_connections
        return await asyncio.to_thread(prepare, prepared.plan, **kwargs)

    def set_retain_health_connections(self, retain: bool) -> None:
        if hasattr(self.probe, "retain_connections"):
            self.probe.retain_connections = retain  # type: ignore[attr-defined]

    def pop_retained_health_connections(self, uris: set[str]) -> dict:
        if not hasattr(self.probe, "pop_retained_connections"):
            return {}
        return self.probe.pop_retained_connections(uris)  # type: ignore[attr-defined]

    def close_retained_health_connections(self) -> None:
        if hasattr(self.probe, "close_retained_connections"):
            self.probe.close_retained_connections()  # type: ignore[attr-defined]

    async def launch_prepared(
        self,
        prepared: DeployResult,
        execution: PreparedExecution,
        telemetry_callback: BatteryTelemetryCallback | None = None,
        phase_callback: PhaseCallback | None = None,
    ) -> DeployResult:
        result = await asyncio.to_thread(
            self.executor.launch,
            execution,
            telemetry_callback=telemetry_callback,
            phase_callback=phase_callback,
        )
        return self.completed_result(prepared, result)

    def completed_result(self, prepared: DeployResult, result) -> DeployResult:
        selection = _selection_for_plan(prepared.selection, result.plan)
        return DeployResult(
            prepared.mission_id,
            MissionState.COMPLETED,
            selection,
            result.plan,
            result.events,
            message="completed",
        )


def _plan_to_dict(plan: SwarmPlan | None) -> dict | None:
    if plan is None:
        return None
    return {
        "swarm_size": plan.spec.swarm_size,
        "assignment_cost": plan.assignment_cost,
        "formation": plan.spec.formation,
        "pattern": plan.spec.pattern,
        "final_pose": list(plan.spec.final_pose),
        "captured_path": plan.spec.captured_path,
        "yaw_rad": plan.spec.yaw_rad,
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


def minimum_viable_swarm_size(requested_size: int) -> int:
    """Require at least 3 drones and more than half of the requested swarm."""

    return max(MIN_SWARM_SIZE, requested_size // 2 + 1)


def _reject_missing_pose(health: DroneHealth) -> DroneHealth:
    if not health.ready or health.pose is not None:
        return health
    return replace(health, ready=False, reasons=(*health.reasons, "missing_pose"))


def _reject_no_fly_zone_launches(health: list[DroneHealth], spec: MissionSpec) -> list[DroneHealth]:
    try:
        zones = load_no_fly_zones(spec.no_fly_zone_paths)
    except ValueError:
        return health
    if not zones:
        return health

    rejected: list[DroneHealth] = []
    for item in health:
        if not item.ready or item.pose is None:
            rejected.append(item)
            continue
        zone = next((zone for zone in zones if zone.contains(item.pose)), None)
        if zone is None:
            rejected.append(item)
            continue
        rejected.append(
            replace(
                item,
                ready=False,
                score=0.0,
                reasons=(*item.reasons, f"launch_pose_in_no_fly_zone:{zone.name}"),
            )
        )
    return rejected


def _selection_for_plan(selection: SwarmSelection, plan: SwarmPlan) -> SwarmSelection:
    planned_uris = {drone.uri for drone in plan.drones}
    selected = tuple(health for health in selection.selected if health.uri in planned_uris)
    dropped = tuple(health for health in selection.selected if health.uri not in planned_uris)
    return replace(selection, selected=selected, rejected=(*selection.rejected, *dropped))
