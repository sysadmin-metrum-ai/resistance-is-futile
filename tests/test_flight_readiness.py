from src.services.flight_readiness import evaluate_drone_readiness
from src.services.mission_models import Waypoint3D


def test_readiness_rejects_disabled_or_unhealthy_drone():
    drone = {
        "id": 7,
        "enabled": False,
        "state": "busy",
        "uri": "",
        "battery": 10,
        "connection_quality": 30,
    }

    readiness = evaluate_drone_readiness(drone, duration_seconds=120)

    assert readiness.ready is False
    joined = " ".join(readiness.warnings)
    assert "drone is disabled" in joined
    assert "drone is not idle" in joined
    assert "battery 10% is below minimum" in joined
    assert "connection quality 30% is below minimum" in joined


def test_readiness_accepts_valid_waypoints_and_duration():
    drone = {
        "id": 3,
        "enabled": True,
        "state": "idle",
        "uri": "radio://0/80/2M",
        "battery": 85,
        "connection_quality": 95,
    }

    readiness = evaluate_drone_readiness(
        drone,
        duration_seconds=90,
        waypoints=[
            Waypoint3D(x=0.0, y=0.0, z=0.7),
            Waypoint3D(x=1.0, y=0.5, z=1.1, hold_seconds=2.0, capture=True),
        ],
    )

    assert readiness.ready is True
    assert readiness.checks["battery_sufficient"] is True
    assert readiness.checks["waypoints_in_range"] is True


def test_readiness_rejects_waypoints_outside_demo_box():
    drone = {
        "id": 5,
        "enabled": True,
        "state": "idle",
        "uri": "radio://0/90/2M",
        "battery": 80,
        "connection_quality": 90,
    }

    readiness = evaluate_drone_readiness(
        drone,
        duration_seconds=30,
        waypoints=[Waypoint3D(x=6.0, y=0.0, z=0.5)],
    )

    assert readiness.ready is False
    assert readiness.checks["waypoints_in_range"] is False
