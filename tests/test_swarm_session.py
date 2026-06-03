import asyncio
from dataclasses import replace

import pytest

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
        poses: dict[str, tuple[float, float, float]] | None = None,
    ):
        self.calls: list[str] = []
        self.unhealthy = unhealthy or set()
        self.missing_pose = missing_pose or set()
        self.low_voltage = low_voltage or set()
        self.low_battery_percent = low_battery_percent or set()
        self.poses = poses or {}
        self.thresholds_seen: list[HealthThresholds] = []

    def check(self, candidate: DroneCandidate, thresholds: HealthThresholds) -> DroneHealth:
        self.calls.append(candidate.uri)
        self.thresholds_seen.append(thresholds)
        y = float(candidate.uri[-1]) * 0.45
        reasons = []
        if candidate.uri in self.unhealthy:
            reasons.append("failed_health")
        if candidate.uri in self.low_voltage:
            reasons.append("low_voltage")
        if candidate.uri in self.low_battery_percent:
            reasons.append("low_battery_percent")
        ready = not reasons
        pose = self.poses.get(candidate.uri, (0.0, y, 0.0))
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
            pose=None if candidate.uri in self.missing_pose else pose,
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


def test_prepare_fixed_pair_degrades_to_one_healthy_drone():
    probe = CountingProbe(unhealthy={"drone-9"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate("drone-4"), DroneCandidate("drone-9")]
    spec = MissionSpec(swarm_size=2, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.plan.spec.swarm_size == 1
    assert [item.uri for item in result.selection.selected] == ["drone-4"]
    assert [item.uri for item in result.selection.rejected] == ["drone-9"]


def test_prepare_fixed_pair_refuses_when_both_drones_fail():
    probe = CountingProbe(unhealthy={"drone-4", "drone-9"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate("drone-4"), DroneCandidate("drone-9")]
    spec = MissionSpec(swarm_size=2, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is None
    assert result.message == "insufficient_healthy_drones"
    assert result.selection.selected == ()


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


def test_prepare_refuses_degraded_result_when_full_swarm_required():
    probe = CountingProbe(unhealthy={"drone-4"})
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(swarm_size=5, require_full_swarm=True, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is None
    assert result.message == "insufficient_healthy_drones"
    assert result.selection.required_size == 5


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


@pytest.mark.skip(reason="No-fly-zone launch rejection is disabled until the server geofence is used in demos.")
def test_prepare_rejects_launch_pose_inside_no_fly_zone_and_uses_remaining_drones(tmp_path):
    no_fly_zone = tmp_path / "server_box.json"
    no_fly_zone.write_text(
        """
{
  "name": "server",
  "min": [-0.1, -0.1, -0.1],
  "max": [0.1, 0.1, 0.1],
  "margin": 0.05
}
""".strip()
    )
    probe = CountingProbe(
        poses={
            "drone-0": (0.0, 0.0, 0.0),
            "drone-1": (0.0, 1.0, 0.0),
            "drone-2": (0.0, 2.0, 0.0),
            "drone-3": (0.0, 3.0, 0.0),
            "drone-4": (0.0, 4.0, 0.0),
        }
    )
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(5)]
    spec = MissionSpec(
        swarm_size=4,
        formation="line",
        final_pose=(1.0, 2.5, 0.55),
        no_fly_zone_paths=(str(no_fly_zone),),
    )

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert [item.uri for item in result.selection.selected] == ["drone-1", "drone-2", "drone-3", "drone-4"]
    rejected = result.selection.rejected[0]
    assert rejected.uri == "drone-0"
    assert "launch_pose_in_no_fly_zone:server" in rejected.reasons


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
    assert sorted(probe.calls) == [f"drone-{index}" for index in range(10)]


def test_prepare_uses_alternate_healthy_subset_when_top_five_are_unsafe():
    probe = CountingProbe(
        poses={
            "drone-0": (0.0, 0.0, 0.0),
            "drone-1": (0.0, 0.20, 0.0),
            "drone-2": (0.0, 0.40, 0.0),
            "drone-3": (0.0, 0.60, 0.0),
            "drone-4": (0.0, 0.13, 0.0),
            "drone-5": (0.0, 0.80, 0.0),
        }
    )
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(6)]
    spec = MissionSpec(swarm_size=5, pattern="hold", min_separation_m=0.15, no_fly_zone_paths=())

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert result.message == "prepared"
    assert len(result.selection.selected) == 5
    assert "drone-4" not in [item.uri for item in result.selection.selected]
    assert "drone-5" in [item.uri for item in result.selection.selected]


def test_prepare_uses_spec_health_check_concurrency():
    probe = CountingProbe()
    runner = SwarmSessionRunner(probe=probe)
    candidates = [DroneCandidate(f"drone-{index}") for index in range(3)]
    spec = MissionSpec(
        swarm_size=3,
        no_fly_zone_paths=(),
        health_timeout_s=8.0,
        max_concurrent_checks=2,
    )

    result = asyncio.run(runner.prepare(spec, candidates))

    assert result.plan is not None
    assert {threshold.health_timeout_s for threshold in probe.thresholds_seen} == {8.0}
    assert {threshold.max_concurrent_checks for threshold in probe.thresholds_seen} == {2}


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
