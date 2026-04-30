import asyncio
from dataclasses import replace

from src.swarm.executor import ExecutionResult
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import HealthThresholds
from src.swarm.models import MissionSpec
from src.swarm.session import SwarmSessionRunner


class CountingProbe:
    def __init__(
        self,
        *,
        unhealthy: set[str] | None = None,
        missing_pose: set[str] | None = None,
        low_voltage: set[str] | None = None,
        low_battery_percent: set[str] | None = None,
    ):
        self.calls: list[str] = []
        self.unhealthy = unhealthy or set()
        self.missing_pose = missing_pose or set()
        self.low_voltage = low_voltage or set()
        self.low_battery_percent = low_battery_percent or set()

    def check(self, candidate: DroneCandidate, thresholds: HealthThresholds) -> DroneHealth:
        self.calls.append(candidate.uri)
        y = float(candidate.uri[-1]) * 0.45
        reasons = []
        if candidate.uri in self.unhealthy:
            reasons.append("failed_health")
        if candidate.uri in self.low_voltage:
            reasons.append("low_voltage")
        if candidate.uri in self.low_battery_percent:
            reasons.append("low_battery_percent")
        ready = not reasons
        return DroneHealth(
            uri=candidate.uri,
            ready=ready,
            score=90.0 if ready else 0.0,
            reasons=tuple(reasons),
            voltage=3.6 if candidate.uri in self.low_voltage else 4.0,
            battery_percent=20 if candidate.uri in self.low_battery_percent else 90,
            connection_quality=100,
            battery_pass=True,
            estimator_ready=ready,
            lighthouse_ready=ready,
            pose=None if candidate.uri in self.missing_pose else (0.0, y, 0.0),
        )


class ReplanningExecutor:
    def execute(self, plan, *, arm):
        return ExecutionResult(
            events=tuple(f"{drone.uri}:takeoff" for drone in plan.drones if drone.uri != "drone-4"),
            plan=type(plan)(
                spec=replace(plan.spec, swarm_size=4),
                drones=plan.drones[:-1],
                assignment_cost=plan.assignment_cost,
            ),
        )


def test_prepare_runs_health_probe_every_time():
    probe = CountingProbe()
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(3)]
    spec = MissionSpec(swarm_size=3, no_fly_zone_paths=())

    first = asyncio.run(runner.prepare(spec, candidates))
    second = asyncio.run(runner.prepare(spec, candidates))

    assert first.plan is not None
    assert second.plan is not None
    assert probe.calls == ["drone-0", "drone-1", "drone-2"] * 2


def test_prepare_degrades_to_four_when_one_drone_is_unhealthy():
    probe = CountingProbe(unhealthy={"drone-4"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.plan.spec.swarm_size == 4
    assert len(result.selection.selected) == 4
    assert [item.uri for item in result.selection.rejected] == ["drone-4"]


def test_prepare_rejects_missing_pose_and_uses_remaining_drones():
    probe = CountingProbe(missing_pose={"drone-4"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.plan.spec.swarm_size == 4
    rejected = result.selection.rejected[0]
    assert rejected.uri == "drone-4"
    assert "missing_pose" in rejected.reasons


def test_prepare_refuses_when_majority_of_five_drones_fail():
    probe = CountingProbe(unhealthy={"drone-2", "drone-3", "drone-4"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is None
    assert result.message == "insufficient_healthy_drones"
    assert len(result.selection.selected) == 2


def test_prepare_checks_all_candidates_and_chooses_healthiest_five():
    probe = CountingProbe(unhealthy={"drone-0", "drone-1", "drone-2"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(10)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.plan.spec.swarm_size == 5
    assert result.message == "prepared"
    assert [item.uri for item in result.selection.selected] == [f"drone-{index}" for index in range(3, 8)]
    assert probe.calls == [f"drone-{index}" for index in range(10)]


def test_prepare_degrades_global_candidate_pool_to_four():
    probe = CountingProbe(unhealthy={"drone-0", "drone-1", "drone-2", "drone-9", "drone-8", "drone-7"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(10)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.plan.spec.swarm_size == 4
    assert result.message == "prepared"
    assert [item.uri for item in result.selection.selected] == ["drone-3", "drone-4", "drone-5", "drone-6"]


def test_prepare_excludes_low_battery_drones_before_planning():
    probe = CountingProbe(low_voltage={"drone-0"}, low_battery_percent={"drone-1"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(7)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.plan.spec.swarm_size == 5
    assert "drone-0" not in [item.uri for item in result.selection.selected]
    assert "drone-1" not in [item.uri for item in result.selection.selected]
    rejected = {item.uri: item.reasons for item in result.selection.rejected}
    assert "low_voltage" in rejected["drone-0"]
    assert "low_battery_percent" in rejected["drone-1"]


def test_prepare_refuses_when_battery_gate_leaves_fewer_than_three_drones():
    probe = CountingProbe(
        low_voltage={"drone-0", "drone-1"},
        low_battery_percent={"drone-2"},
    )
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is None
    assert result.message == "insufficient_healthy_drones"
    assert len(result.selection.selected) == 2


def test_execute_prepared_reports_replanned_selected_count():
    probe = CountingProbe()
    runner = SwarmSessionRunner(probe=probe, executor=ReplanningExecutor())
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(swarm_size=5, no_fly_zone_paths=(), dry_run=False, arm=True)

    prepared = asyncio.run(runner.prepare(spec, candidates))
    result = asyncio.run(runner.execute_prepared(prepared, spec))

    assert result.plan is not None
    assert len(result.selection.selected) == 4
    assert "drone-4" in [item.uri for item in result.selection.rejected]
