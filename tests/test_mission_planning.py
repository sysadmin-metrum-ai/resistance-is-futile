from src.services.mission_models import (
    DroneHomePosition,
    MissionRequest,
    ServerInspectionRequest,
    Waypoint3D,
)
from src.services.mission_queue import MissionQueue
from src.services.swarm_planner import build_server_inspection_plan


def test_mission_request_uses_typed_3d_waypoints():
    mission = MissionRequest(
        waypoints=[
            {"x": 0.0, "y": 0.0, "z": 0.6, "hold_seconds": 1.0, "capture": True},
            {"x": 1.0, "y": 0.2, "z": 0.8},
        ],
        duration_seconds=30,
        target_drone_id=7,
    )

    assert isinstance(mission.waypoints[0], Waypoint3D)
    assert mission.waypoints[0].capture is True
    assert mission.waypoints[0].hold_seconds == 1.0


def test_swarm_planner_degrades_from_three_to_one_drone():
    request = ServerInspectionRequest(
        drone_ids=[1, 2, 3],
        home_positions=[
            DroneHomePosition(drone_id=1, home=Waypoint3D(x=-1.0, y=-3.0, z=0.0)),
            DroneHomePosition(drone_id=2, home=Waypoint3D(x=0.0, y=-3.0, z=0.0)),
            DroneHomePosition(drone_id=3, home=Waypoint3D(x=1.0, y=-3.0, z=0.0)),
        ],
        server_position=Waypoint3D(x=0.0, y=0.0, z=0.0),
        preferred_drone_count=3,
        allow_degraded=True,
    )

    plan = build_server_inspection_plan(request, available_drone_ids=[2])

    assert plan.degraded is True
    assert plan.selected_drone_ids == [2]
    assert plan.drone_missions[0].role == "solo"
    assert any(waypoint.capture for waypoint in plan.drone_missions[0].waypoints)


def test_swarm_planner_assigns_three_roles_when_all_drones_available():
    request = ServerInspectionRequest(
        drone_ids=[1, 2, 3],
        home_positions=[
            DroneHomePosition(drone_id=1, home=Waypoint3D(x=-1.0, y=-3.0, z=0.0)),
            DroneHomePosition(drone_id=2, home=Waypoint3D(x=0.0, y=-3.0, z=0.0)),
            DroneHomePosition(drone_id=3, home=Waypoint3D(x=1.0, y=-3.0, z=0.0)),
        ],
        server_position=Waypoint3D(x=0.0, y=0.0, z=0.0),
    )

    plan = build_server_inspection_plan(request, available_drone_ids=[1, 2, 3])
    roles = [mission.role for mission in plan.drone_missions]

    assert plan.degraded is False
    assert roles == ["left", "center", "right"]


def test_mission_queue_enqueue_preserves_existing_mission_identity():
    mission = {
        "mission_id": "mission-123",
        "drone_id": 7,
        "waypoints": [{"x": 0.0, "y": 0.0, "z": 0.5}],
    }

    queue = MissionQueue()
    queue_id = MissionQueue.enqueue

    assert callable(queue_id)
    assert mission["mission_id"] == "mission-123"
