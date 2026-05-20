from src.swarm.assignment import optimal_assignment
from src.swarm.models import DEFAULT_MIN_SEPARATION_M
from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import PathSafetyError
from src.swarm.planner import SwarmPlan
from src.swarm.planner import build_swarm_plan
from src.swarm.planner import formation_yaw
from src.swarm.planner import formation_slots
from src.swarm.planner import go_to_yaw
from src.swarm.planner import pattern_duration_s
from src.swarm.planner import pattern_final_hold_s
from src.swarm.planner import pattern_hold_s
from src.swarm.planner import pattern_yaws
from src.swarm.planner import validate_swarm_plan_clearance


def test_formation_slots_follow_dynamic_swarm_size():
    for size in (1, 2, 3, 4, 5):
        spec = MissionSpec(swarm_size=size, final_pose=(1.0, 2.0, 0.6), formation="line")

        slots = formation_slots(spec)

        assert len(slots) == size
        assert all(slot[0] == 1.0 for slot in slots)
        assert all(slot[2] == 0.6 for slot in slots)


def test_mission_spec_default_minimum_separation_is_demo_clearance():
    assert MissionSpec().min_separation_m == DEFAULT_MIN_SEPARATION_M == 0.10


def test_triangle_formation_uses_stacked_3d_geometry():
    spacing = 0.4

    two = formation_slots(MissionSpec(swarm_size=2, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))
    five = formation_slots(MissionSpec(swarm_size=5, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))
    four = formation_slots(MissionSpec(swarm_size=4, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))
    three = formation_slots(MissionSpec(swarm_size=3, formation="triangle", slot_spacing_m=spacing, no_fly_zone_paths=()))

    assert two == [
        (0.5, -0.2, 0.55),
        (0.5, 0.2, 0.55),
    ]
    assert five == [
        (0.5, -0.4, 0.55),
        (0.5, 0.0, 0.55),
        (0.5, 0.4, 0.55),
        (0.74, -0.2, 0.8500000000000001),
        (0.74, 0.2, 0.8500000000000001),
    ]
    assert four == [
        (0.5, -0.30000000000000004, 0.55),
        (0.5, 0.1, 0.55),
        (0.74, -0.1, 0.8500000000000001),
        (0.74, 0.30000000000000004, 0.8500000000000001),
    ]
    assert three == [
        (0.5, -0.2, 0.55),
        (0.5, 0.2, 0.55),
        (0.74, 0.0, 0.8500000000000001),
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


def test_default_pattern_moves_forward_and_up_before_returning_to_slot():
    spec = MissionSpec(swarm_size=3, no_fly_zone_paths=())
    launch = {
        "a": (0.0, 0.0, 0.55),
        "b": (0.0, 0.5, 0.55),
        "c": (0.0, -0.5, 0.55),
    }

    plan = build_swarm_plan(launch, spec)

    assert plan.spec.pattern == "up_forward"
    for drone in plan.drones:
        forward_up, slot = drone.pattern_points
        assert forward_up == (drone.formation_slot[0] + 1.0, drone.formation_slot[1], drone.formation_slot[2] + 1.0)
        assert slot == drone.formation_slot


def test_launch_up_pattern_climbs_in_place_and_returns_to_launch_xy():
    spec = MissionSpec(
        swarm_size=2,
        pattern="launch_up",
        final_pose=(0.0, 0.0, 1.0),
        hover_z=0.55,
        no_fly_zone_paths=(),
    )
    launch = {
        "a": (0.0, 0.0, 0.1),
        "b": (0.0, 0.5, 0.1),
    }

    plan = build_swarm_plan(launch, spec)

    assert plan.assignment_cost == 0.0
    for drone in plan.drones:
        assert drone.route_to_formation == ()
        assert drone.pattern_points == (
            (launch[drone.uri][0], launch[drone.uri][1], 1.0),
        )
        assert drone.route_to_return == (
            (launch[drone.uri][0], launch[drone.uri][1], 0.55),
        )
        assert drone.return_point == (launch[drone.uri][0], launch[drone.uri][1], 0.55)


def test_captured_path_uses_recorded_start_and_replays_relative_waypoints(tmp_path):
    capture = tmp_path / "demo_path.json"
    capture.write_text(
        '{"start":[1.0,1.0,0.55],"start_yaw_rad":-1.5707963267948966,"pattern_s":0.4,"pattern_hold_s":0.0,"pattern_final_hold_s":3.0,"yaw_rad":0.0,"yaw_points_rad":[-1.5707963267948966,0.0],"final_center":[0.0,0.0,0.355],"relative_points":[[0.2,0.0,0.0],[0.4,-0.2,0.0]]}'
    )
    spec = MissionSpec(
        swarm_size=3,
        formation="line",
        pattern="captured_path",
        captured_path=str(capture),
        no_fly_zone_paths=(),
    )
    launch = {
        "a": (0.0, 0.0, 0.55),
        "b": (0.0, 0.5, 0.55),
        "c": (0.0, -0.5, 0.55),
    }

    plan = build_swarm_plan(launch, spec)

    slots = formation_slots(spec)
    assert [round(slot[0], 3) for slot in slots] == [0.51, 1.0, 1.49]
    assert [round(slot[1], 3) for slot in slots] == [1.0, 1.0, 1.0]
    assert formation_yaw(spec) == -1.5707963267948966
    assert go_to_yaw(spec) == 0.0
    assert pattern_duration_s(spec) == 0.4
    assert pattern_hold_s(spec) == 0.0
    assert pattern_final_hold_s(spec) == 3.0
    assert pattern_yaws(spec, 3) == (-1.5707963267948966, -1.5707963267948966, 0.0)
    for drone in plan.drones:
        start_center = (1.0, 1.0, 0.55)
        start_offset = (
            drone.formation_slot[0] - start_center[0],
            drone.formation_slot[1] - start_center[1],
            drone.formation_slot[2] - start_center[2],
        )
        assert drone.pattern_points[0] == (
            drone.formation_slot[0] + 0.2,
            drone.formation_slot[1],
            drone.formation_slot[2],
        )
        delta_yaw = 0.0 - formation_yaw(spec)
        c = __import__("math").cos(delta_yaw)
        s = __import__("math").sin(delta_yaw)
        rotated_offset = (
            start_offset[0] * c - start_offset[1] * s,
            start_offset[0] * s + start_offset[1] * c,
            start_offset[2],
        )
        expected_final_pattern = (
            start_center[0] + 0.4 + rotated_offset[0],
            start_center[1] - 0.2 + rotated_offset[1],
            start_center[2] + rotated_offset[2],
        )
        assert tuple(round(value, 6) for value in drone.pattern_points[1]) == (
            round(drone.formation_slot[0] + 0.4, 6),
            round(drone.formation_slot[1] - 0.2, 6),
            round(drone.formation_slot[2], 6),
        )
        assert tuple(round(value, 6) for value in drone.pattern_points[-1]) == tuple(
            round(value, 6) for value in expected_final_pattern
        )
        expected_final_stage = (
            rotated_offset[0],
            rotated_offset[1],
            0.355 + rotated_offset[2],
        )
        assert tuple(round(value, 6) for value in drone.route_to_return[0]) == tuple(
            round(value, 6) for value in expected_final_stage
        )
        assert len(drone.route_to_return) == 2
        assert drone.route_to_return[-1] == drone.return_point


def test_captured_path_uses_spec_final_pose_when_json_has_no_final_center(tmp_path):
    capture = tmp_path / "demo_path.json"
    capture.write_text(
        '{"start":[1.0,1.0,0.55],"start_yaw_rad":0.0,"yaw_rad":0.0,"relative_points":[[0.2,0.0,0.0]]}'
    )
    spec = MissionSpec(
        swarm_size=3,
        formation="line",
        pattern="captured_path",
        captured_path=str(capture),
        final_pose=(0.5, 0.5, 0.8),
        no_fly_zone_paths=(),
    )
    launch = {
        "a": (0.0, 0.0, 0.55),
        "b": (0.0, 0.5, 0.55),
        "c": (0.0, -0.5, 0.55),
    }

    plan = build_swarm_plan(launch, spec)

    for drone in plan.drones:
        slot_offset = (
            drone.formation_slot[0] - 1.0,
            drone.formation_slot[1] - 1.0,
            drone.formation_slot[2] - 0.55,
        )
        assert drone.route_to_return[0] == (
            0.5 + slot_offset[0],
            0.5 + slot_offset[1],
            0.8 + slot_offset[2],
        )


def test_captured_path_unwraps_yaw_points_for_smooth_turns(tmp_path):
    capture = tmp_path / "demo_path.json"
    capture.write_text(
        '{"start":[0.0,0.0,0.55],"start_yaw_rad":2.9,"yaw_rad":-2.9,"relative_points":[[0.1,0.0,0.0],[0.2,0.0,0.0]],"yaw_points_rad":[3.05,-3.05]}'
    )
    spec = MissionSpec(
        swarm_size=3,
        pattern="captured_path",
        captured_path=str(capture),
        no_fly_zone_paths=(),
    )

    yaws = pattern_yaws(spec, 4)

    assert yaws[:2] == (2.9, 3.05)
    assert yaws[2] == 3.05
    assert round(yaws[3], 6) == round(-3.05 + __import__("math").tau, 6)
    assert go_to_yaw(spec) == yaws[-1]


def test_two_drone_captured_path_line_formation_is_side_by_side(tmp_path):
    capture = tmp_path / "demo_path.json"
    capture.write_text('{"start":[1.0,1.0,0.55],"relative_points":[[0.2,0.0,0.0]],"start_yaw_rad":0.0}')
    spec = MissionSpec(
        swarm_size=2,
        formation="line",
        slot_spacing_m=0.15,
        pattern="captured_path",
        captured_path=str(capture),
        no_fly_zone_paths=(),
    )

    slots = formation_slots(spec)

    assert slots == [
        (1.0, 0.925, 0.55),
        (1.0, 1.075, 0.55),
    ]


def test_crazy_pinwheel_uses_three_rings_with_ten_slots():
    spec = MissionSpec(
        swarm_size=10,
        formation="diamond",
        pattern="crazy_pinwheel",
        final_pose=(0.45, 0.0, 0.62),
        slot_spacing_m=0.42,
        no_fly_zone_paths=(),
    )
    slots = formation_slots(spec)
    assert len(slots) == 10
    assert slots[0] == spec.final_pose

    launch = {f"d{i}": (slot[0], slot[1], 0.55) for i, slot in enumerate(slots)}
    plan = build_swarm_plan(launch, spec)

    center_drone = next(drone for drone in plan.drones if drone.formation_slot == spec.final_pose)
    middle_drone = next(
        drone
        for drone in plan.drones
        if abs(drone.formation_slot[0] - spec.final_pose[0] - spec.slot_spacing_m) < 1e-6
    )
    outer_drone = next(
        drone
        for drone in plan.drones
        if abs(
            (drone.formation_slot[0] - spec.final_pose[0]) ** 2
            + (drone.formation_slot[1] - spec.final_pose[1]) ** 2
            - (spec.slot_spacing_m + spec.crazy_pinwheel_outer_delta_m) ** 2
        )
        < 1e-3
    )

    assert center_drone.pattern_points == (
        (0.45, 0.0, 0.84),
        (0.45, 0.0, 0.96),
        (0.45, 0.0, 0.84),
        (0.45, 0.0, 0.62),
    )
    assert len(middle_drone.pattern_points) == 5
    assert len(outer_drone.pattern_points) == 6
    assert tuple(tuple(round(value, 6) for value in point) for point in middle_drone.pattern_points[:4]) == (
        (0.45, 0.42, 0.72),
        (0.03, 0.0, 0.62),
        (0.45, -0.42, 0.72),
        (0.87, -0.0, 0.62),
    )
    assert middle_drone.pattern_points[-1] == middle_drone.formation_slot
    assert outer_drone.pattern_points[-1] == outer_drone.formation_slot


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


def test_validate_swarm_plan_allows_tighter_takeoff_spacing_only():
    spec = MissionSpec(swarm_size=2, pattern="hold", min_separation_m=0.15, no_fly_zone_paths=())
    plan = SwarmPlan(
        spec=spec,
        assignment_cost=0.0,
        drones=(
            DronePlan(
                "a",
                (0.0, 0.0, 0.10),
                (1.0, -1.0, 0.55),
                ((1.0, -1.0, 0.55),),
                ((1.0, -1.0, 0.55),),
                (),
                (0.0, 0.0, 0.55),
            ),
            DronePlan(
                "b",
                (0.0, 0.14, 0.10),
                (1.0, 1.0, 0.55),
                ((1.0, 1.0, 0.55),),
                ((1.0, 1.0, 0.55),),
                (),
                (0.0, 0.14, 0.55),
            ),
        ),
    )

    validate_swarm_plan_clearance(plan)


def test_validate_swarm_plan_rejects_takeoff_spacing_under_013m():
    spec = MissionSpec(swarm_size=2, pattern="hold", min_separation_m=0.15, no_fly_zone_paths=())
    plan = SwarmPlan(
        spec=spec,
        assignment_cost=0.0,
        drones=(
            DronePlan(
                "a",
                (0.0, 0.0, 0.10),
                (1.0, -1.0, 0.55),
                ((1.0, -1.0, 0.55),),
                ((1.0, -1.0, 0.55),),
                ((0.0, 0.0, 0.55),),
                (0.0, 0.0, 0.55),
            ),
            DronePlan(
                "b",
                (0.0, 0.12, 0.10),
                (1.0, 1.0, 0.55),
                ((1.0, 1.0, 0.55),),
                ((1.0, 1.0, 0.55),),
                ((0.0, 0.12, 0.55),),
                (0.0, 0.12, 0.55),
            ),
        ),
    )

    try:
        validate_swarm_plan_clearance(plan)
    except PathSafetyError as exc:
        assert "0.120m < 0.130m" in str(exc)
    else:
        raise AssertionError("expected unsafe takeoff spacing to be rejected")


def test_validate_swarm_plan_rejects_same_xy_even_with_vertical_separation():
    spec = MissionSpec(swarm_size=2, pattern="hold", min_separation_m=0.10, no_fly_zone_paths=())
    plan = SwarmPlan(
        spec=spec,
        assignment_cost=0.0,
        drones=(
            DronePlan(
                "a",
                (0.0, 0.0, 0.55),
                (0.5, 0.5, 0.55),
                ((0.5, 0.5, 0.55),),
                ((0.5, 0.5, 0.55),),
                ((0.0, 0.0, 0.55),),
                (0.0, 0.0, 0.55),
            ),
            DronePlan(
                "b",
                (0.0, 0.2, 0.55),
                (0.5, 0.5, 1.00),
                ((0.5, 0.5, 1.00),),
                ((0.5, 0.5, 1.00),),
                ((0.0, 0.2, 0.55),),
                (0.0, 0.2, 0.55),
            ),
        ),
    )

    try:
        validate_swarm_plan_clearance(plan)
    except PathSafetyError as exc:
        assert "xy clearance" in str(exc)
    else:
        raise AssertionError("expected same XY at different Z to be rejected")


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
        hover_z=0.10,
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
