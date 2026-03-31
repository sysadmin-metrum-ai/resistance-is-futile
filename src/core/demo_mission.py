"""Demo mission planning utilities for DTW-style inspection runs.

The planner in this module formalizes the fixed demo contract:

- drones launch from home pads on one side of the field
- they transit through staging points
- they inspect the server from left / center / right front poses
- they return to their home pads

The same mission should degrade gracefully from 3 drones to 2 to 1 based on
the set of healthy, available drones.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


SLOTS = ("left", "center", "right")


@dataclass(frozen=True)
class Waypoint3D:
    """A 3D waypoint with optional mission semantics."""

    label: str
    x: float
    y: float
    z: float
    yaw_deg: float = 0.0
    hold_s: float = 0.0
    capture: bool = False

    def to_dict(self) -> dict:
        """Return a JSON-friendly waypoint representation."""
        return asdict(self)


@dataclass(frozen=True)
class DroneAssignment:
    """Mission slice for one drone."""

    drone_id: str
    slot: str
    waypoints: list[Waypoint3D]

    def to_dict(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "slot": self.slot,
            "waypoints": [wp.to_dict() for wp in self.waypoints],
        }


@dataclass(frozen=True)
class DemoMissionPlan:
    """Full mission plan for an inspection run."""

    mission_type: str
    available_drones: list[str]
    assignments: list[DroneAssignment]

    def to_dict(self) -> dict:
        return {
            "mission_type": self.mission_type,
            "available_drones": list(self.available_drones),
            "assignments": [assignment.to_dict() for assignment in self.assignments],
        }


def build_default_demo_layout() -> dict[str, dict[str, Waypoint3D]]:
    """Return the default fixed-pose layout for the acrylic-box demo."""
    home = {
        "left": Waypoint3D("home-left", -3.0, -4.0, 0.0),
        "center": Waypoint3D("home-center", 0.0, -4.0, 0.0),
        "right": Waypoint3D("home-right", 3.0, -4.0, 0.0),
    }
    staging = {
        "left": Waypoint3D("staging-left", -2.0, -1.5, 0.8, hold_s=1.0),
        "center": Waypoint3D("staging-center", 0.0, -1.5, 0.8, hold_s=1.0),
        "right": Waypoint3D("staging-right", 2.0, -1.5, 0.8, hold_s=1.0),
    }
    inspect = {
        "left": Waypoint3D("inspect-left", -1.5, 1.0, 0.9, yaw_deg=0.0, hold_s=2.0, capture=True),
        "center": Waypoint3D("inspect-center", 0.0, 1.2, 1.0, yaw_deg=0.0, hold_s=2.5, capture=True),
        "right": Waypoint3D("inspect-right", 1.5, 1.0, 0.9, yaw_deg=0.0, hold_s=2.0, capture=True),
    }
    return {
        "home": home,
        "staging": staging,
        "inspect": inspect,
    }


def build_server_inspection_plan(
    available_drones: list[str] | tuple[str, ...],
    layout: dict[str, dict[str, Waypoint3D]] | None = None,
) -> DemoMissionPlan:
    """Build a deterministic server-inspection mission plan.

    Planning rules:
    - 3 drones: left / center / right simultaneously
    - 2 drones: left and right first, then center reassigned to the left drone
    - 1 drone: left, center, right sequentially
    """
    if not available_drones:
        raise ValueError("at least one available drone is required")

    if len(available_drones) > 3:
        raise ValueError("demo planner supports at most 3 drones")

    layout = layout or build_default_demo_layout()
    homes = layout["home"]
    staging = layout["staging"]
    inspect = layout["inspect"]

    drones = [str(drone_id) for drone_id in available_drones]

    if len(drones) == 3:
        assignments = [
            _assignment_for_slot(drones[0], "left", homes, staging, inspect, ["left"]),
            _assignment_for_slot(drones[1], "center", homes, staging, inspect, ["center"]),
            _assignment_for_slot(drones[2], "right", homes, staging, inspect, ["right"]),
        ]
    elif len(drones) == 2:
        assignments = [
            _assignment_for_slot(drones[0], "left", homes, staging, inspect, ["left", "center"]),
            _assignment_for_slot(drones[1], "right", homes, staging, inspect, ["right"]),
        ]
    else:
        assignments = [
            _assignment_for_slot(drones[0], "center", homes, staging, inspect, ["left", "center", "right"]),
        ]

    return DemoMissionPlan(
        mission_type="swarm_inspect_server",
        available_drones=drones,
        assignments=assignments,
    )


def _assignment_for_slot(
    drone_id: str,
    slot: str,
    homes: dict[str, Waypoint3D],
    staging: dict[str, Waypoint3D],
    inspect: dict[str, Waypoint3D],
    inspection_order: list[str],
) -> DroneAssignment:
    waypoints = [
        homes[slot],
        staging[slot],
    ]

    for inspect_slot in inspection_order:
        # Route the drone through the staging pose nearest its assigned home slot
        # for predictable, human-readable motion during testing.
        waypoints.append(inspect[inspect_slot])

    waypoints.extend(
        [
            staging[slot],
            homes[slot],
        ]
    )

    return DroneAssignment(
        drone_id=drone_id,
        slot=slot,
        waypoints=waypoints,
    )
