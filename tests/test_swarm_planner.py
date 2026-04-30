from src.swarm.assignment import optimal_assignment
from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import PathSafetyError
from src.swarm.planner import SwarmPlan
from src.swarm.planner import build_swarm_plan
from src.swarm.planner import formation_slots
from src.swarm.planner import validate_swarm_plan_clearance


def test_formation_slots_follow_dynamic_swarm_size():
    for size in (3, 4, 5):
        spec = MissionSpec(swarm_size=size, final_pose=(1.0, 2.0, 0.6), formation="line")

        slots = formation_slots(spec)

        assert len(slots) == size
        assert all(slot[0] == 1.0 for slot in slots)
        assert all(slot[2] == 0.6 for slot in slots)


def test_triangle_formation_uses_stacked_3d_geometry():
    spacing = 0.4

    five = formation_slots(MissionSpec(swarm_size=5, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))
    four = formation_slots(MissionSpec(swarm_size=4, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))
    three = formation_slots(MissionSpec(swarm_size=3, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))

    assert five == [
        (0.5, -0.4, 0.55),
        (0.5, 0.0, 0.55),
        (0.5, 0.4, 0.55),
        (0.68, -0.2, 0.8500000000000001),
        (0.68, 0.2, 0.8500000000000001),
    ]
    assert four == [
        (0.5, -0.30000000000000004, 0.55),
        (0.5, 0.1, 0.55),
        (0.68, -0.1, 0.8500000000000001),
        (0.68, 0.30000000000000004, 0.8500000000000001),
    ]
    assert three == [
        (0.5, -0.2, 0.55),
        (0.5, 0.2, 0.55),
        (0.68, 0.0, 0.8500000000000001),
    ]


def test_optimal_assignment_minimizes_total_distance():
    measured = [(0.0, 1.0, 0.5), (0.0, -1.0, 0.5), (0.0, 0.0, 0.5)]
    targets = [(0.0, -1.0, 0.5), (0.0, 0.0, 0.5), (0.0, 1.0, 0.5)]

    assignment, cost = optimal_assignment(measured, targets)

    assert assignment == [2, 0, 1]
    assert cost == 0.0


def test_build_swarm_plan_returns_each_drone_to_own_launch_xy():
    spec = MissionSpec(swarm_size=3, final_pose=(0.5, 0.0, 0.55), pattern="line_shift", no_fly_zone_paths=())
    launch = {
        "a": (0.0, 0.0, 0.55),
        "b": (0.0, 0.5, 0.55),
        "c": (0.0, -0.5, 0.55),
    }

    plan = build_swarm_plan(launch, spec)

    assert len(plan.drones) == 3
    assert {drone.uri for drone in plan.drones} == {"a", "b", "c"}
    for drone in plan.drones:
        assert drone.return_point[:2] == launch[drone.uri][:2]
        assert len(drone.pattern_points) == 3


def test_build_swarm_plan_rejects_launch_poses_inside_min_separation():
    spec = MissionSpec(swarm_size=3, pattern="hold", min_separation_m=0.10, no_fly_zone_paths=())
    launch = {
        "a": (0.0, 0.0, 0.55),
        "b": (0.05, 0.0, 0.55),
        "c": (0.0, 0.5, 0.55),
    }

    try:
        build_swarm_plan(launch, spec)
    except PathSafetyError as exc:
        assert "clearance" in str(exc)
    else:
        raise AssertionError("expected unsafe launch spacing to be rejected")


def test_validate_swarm_plan_rejects_crossing_paths_inside_min_separation():
    spec = MissionSpec(swarm_size=3, pattern="hold", min_separation_m=0.10, no_fly_zone_paths=())
    plan = SwarmPlan(
        spec=spec,
        assignment_cost=0.0,
        drones=(
            DronePlan(
                "a",
                (0.0, -0.2, 0.55),
                (1.0, 0.2, 0.55),
                ((1.0, 0.2, 0.55),),
                ((1.0, 0.2, 0.55),),
                ((0.0, -0.2, 0.55),),
                (0.0, -0.2, 0.55),
            ),
            DronePlan(
                "b",
                (0.0, 0.2, 0.55),
                (1.0, -0.2, 0.55),
                ((1.0, -0.2, 0.55),),
                ((1.0, -0.2, 0.55),),
                ((0.0, 0.2, 0.55),),
                (0.0, 0.2, 0.55),
            ),
            DronePlan(
                "c",
                (0.0, 0.6, 0.55),
                (1.0, 0.6, 0.55),
                ((1.0, 0.6, 0.55),),
                ((1.0, 0.6, 0.55),),
                ((0.0, 0.6, 0.55),),
                (0.0, 0.6, 0.55),
            ),
        ),
    )

    try:
        validate_swarm_plan_clearance(plan)
    except PathSafetyError:
        pass
    else:
        raise AssertionError("expected crossing/close path to be rejected")


def test_build_swarm_plan_reroutes_server_no_fly_zone_path():
    spec = MissionSpec(
        swarm_size=3,
        final_pose=(1.20, 0.0, 0.10),
        formation="line",
        pattern="hold",
        slot_spacing_m=2.0,
        min_separation_m=0.10,
        no_fly_zone_paths=("config/no_fly_zones/server_box.json",),
    )
    launch = {
        "a": (0.0, -2.0, 0.10),
        "b": (0.0, 0.0, 0.10),
        "c": (0.0, 2.0, 0.10),
    }

    plan = build_swarm_plan(launch, spec)

    assert len(plan.drones) == 3
    assert any(len(drone.route_to_formation) > 1 for drone in plan.drones)


def test_build_swarm_plan_accepts_path_above_server_no_fly_zone():
    spec = MissionSpec(
        swarm_size=3,
        final_pose=(0.80, 0.0, 0.55),
        pattern="hold",
        min_separation_m=0.10,
        no_fly_zone_paths=("config/no_fly_zones/server_box.json",),
    )
    launch = {
        "a": (0.0, -0.5, 0.55),
        "b": (0.0, 0.5, 0.55),
        "c": (0.0, 1.0, 0.55),
    }

    plan = build_swarm_plan(launch, spec)

    assert len(plan.drones) == 3


def test_build_swarm_plan_rejects_final_pose_inside_server_box():
    spec = MissionSpec(
        swarm_size=3,
        final_pose=(0.80, 0.0, 0.10),
        formation="diamond",
        pattern="hold",
        min_separation_m=0.10,
        no_fly_zone_paths=("config/no_fly_zones/server_box.json",),
    )
    launch = {
        "a": (0.0, -0.5, 0.55),
        "b": (0.0, 0.5, 0.55),
        "c": (0.0, 1.0, 0.55),
    }

    try:
        build_swarm_plan(launch, spec)
    except PathSafetyError as exc:
        assert "no_fly_zone:server" in str(exc)
    else:
        raise AssertionError("expected unsafe final pose to be rejected")
