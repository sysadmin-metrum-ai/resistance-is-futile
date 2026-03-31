"""Tests for the fixed-pose DTW demo mission planner."""

import pytest

from src.core.demo_mission import build_default_demo_layout, build_server_inspection_plan


def test_default_layout_has_expected_slots():
    layout = build_default_demo_layout()

    assert set(layout["home"]) == {"left", "center", "right"}
    assert set(layout["staging"]) == {"left", "center", "right"}
    assert set(layout["inspect"]) == {"left", "center", "right"}


def test_three_drone_plan_assigns_all_front_poses():
    plan = build_server_inspection_plan(["drone-a", "drone-b", "drone-c"])

    assert plan.mission_type == "swarm_inspect_server"
    assert [assignment.slot for assignment in plan.assignments] == ["left", "center", "right"]
    assert [assignment.drone_id for assignment in plan.assignments] == ["drone-a", "drone-b", "drone-c"]

    labels = [[wp.label for wp in assignment.waypoints] for assignment in plan.assignments]
    assert labels[0] == ["home-left", "staging-left", "inspect-left", "staging-left", "home-left"]
    assert labels[1] == ["home-center", "staging-center", "inspect-center", "staging-center", "home-center"]
    assert labels[2] == ["home-right", "staging-right", "inspect-right", "staging-right", "home-right"]


def test_two_drone_plan_reassigns_center_pose():
    plan = build_server_inspection_plan(["drone-a", "drone-b"])

    assert [assignment.slot for assignment in plan.assignments] == ["left", "right"]

    left_labels = [wp.label for wp in plan.assignments[0].waypoints]
    right_labels = [wp.label for wp in plan.assignments[1].waypoints]

    assert left_labels == [
        "home-left",
        "staging-left",
        "inspect-left",
        "inspect-center",
        "staging-left",
        "home-left",
    ]
    assert right_labels == [
        "home-right",
        "staging-right",
        "inspect-right",
        "staging-right",
        "home-right",
    ]


def test_single_drone_plan_runs_sequential_inspection():
    plan = build_server_inspection_plan(["solo"])

    assert len(plan.assignments) == 1
    assignment = plan.assignments[0]
    assert assignment.slot == "center"
    assert [wp.label for wp in assignment.waypoints] == [
        "home-center",
        "staging-center",
        "inspect-left",
        "inspect-center",
        "inspect-right",
        "staging-center",
        "home-center",
    ]


def test_planner_requires_between_one_and_three_drones():
    with pytest.raises(ValueError):
        build_server_inspection_plan([])

    with pytest.raises(ValueError):
        build_server_inspection_plan(["a", "b", "c", "d"])
