"""Planning helpers for deterministic single- and multi-drone demo missions."""

from __future__ import annotations

from collections.abc import Iterable

from src.services.mission_models import (
    DroneHomePosition,
    PlannedDroneMission,
    ServerInspectionPlan,
    ServerInspectionRequest,
    Waypoint3D,
)


def build_server_inspection_plan(
    request: ServerInspectionRequest,
    available_drone_ids: Iterable[int],
) -> ServerInspectionPlan:
    """Build a stable inspection plan that degrades from 3 drones to 2 or 1."""
    available = [drone_id for drone_id in request.drone_ids if drone_id in set(available_drone_ids)]
    if not available:
        raise ValueError("no requested drones are currently available")

    selected_count = min(request.preferred_drone_count, len(available))
    if selected_count < request.preferred_drone_count and not request.allow_degraded:
        raise ValueError(
            f"need {request.preferred_drone_count} drones, only {len(available)} available"
        )

    selected = available[:selected_count]
    homes = {item.drone_id: item.home for item in request.home_positions}
    inspection_points = _inspection_points(
        request.server_position,
        request.approach_axis,
        request.inspection_distance,
        request.inspection_height,
        request.lateral_spacing,
    )

    roles_by_count = {
        1: [("solo", [inspection_points["center"]])],
        2: [
            ("left_then_center", [inspection_points["left"], inspection_points["center"]]),
            ("right_then_center", [inspection_points["right"], inspection_points["center"]]),
        ],
        3: [
            ("left", [inspection_points["left"]]),
            ("center", [inspection_points["center"]]),
            ("right", [inspection_points["right"]]),
        ],
    }

    missions: list[PlannedDroneMission] = []
    for drone_id, (role, inspection_sequence) in zip(selected, roles_by_count[selected_count], strict=True):
        home = homes[drone_id]
        waypoints = [
            Waypoint3D(
                x=home.x,
                y=home.y,
                z=request.staging_height,
                yaw_degrees=home.yaw_degrees,
                label="takeoff-stage",
            ),
        ]
        for index, point in enumerate(inspection_sequence, start=1):
            waypoints.append(
                Waypoint3D(
                    x=point.x,
                    y=point.y,
                    z=point.z,
                    yaw_degrees=point.yaw_degrees,
                    hold_seconds=request.hold_seconds,
                    capture=True,
                    label=f"inspect-{index}",
                )
            )
        waypoints.extend(
            [
                Waypoint3D(
                    x=home.x,
                    y=home.y,
                    z=request.staging_height,
                    yaw_degrees=home.yaw_degrees,
                    label="return-stage",
                ),
                Waypoint3D(
                    x=home.x,
                    y=home.y,
                    z=home.z,
                    yaw_degrees=home.yaw_degrees,
                    label="land-home",
                ),
            ]
        )
        missions.append(
            PlannedDroneMission(
                drone_id=drone_id,
                role=role,
                home=home,
                waypoints=waypoints,
            )
        )

    return ServerInspectionPlan(
        selected_drone_ids=selected,
        degraded=selected_count < request.preferred_drone_count,
        approach_axis=request.approach_axis,
        server_position=request.server_position,
        drone_missions=missions,
    )


def _inspection_points(
    server: Waypoint3D,
    approach_axis: str,
    inspection_distance: float,
    inspection_height: float,
    lateral_spacing: float,
) -> dict[str, Waypoint3D]:
    """Generate deterministic front-facing left/center/right inspection points."""
    lateral = lateral_spacing / 2.0
    if approach_axis == "y-":
        center = Waypoint3D(x=server.x, y=server.y - inspection_distance, z=inspection_height, yaw_degrees=0)
        left = Waypoint3D(x=server.x - lateral, y=center.y, z=inspection_height, yaw_degrees=0)
        right = Waypoint3D(x=server.x + lateral, y=center.y, z=inspection_height, yaw_degrees=0)
    elif approach_axis == "y+":
        center = Waypoint3D(x=server.x, y=server.y + inspection_distance, z=inspection_height, yaw_degrees=180)
        left = Waypoint3D(x=server.x + lateral, y=center.y, z=inspection_height, yaw_degrees=180)
        right = Waypoint3D(x=server.x - lateral, y=center.y, z=inspection_height, yaw_degrees=180)
    elif approach_axis == "x-":
        center = Waypoint3D(x=server.x - inspection_distance, y=server.y, z=inspection_height, yaw_degrees=90)
        left = Waypoint3D(x=center.x, y=server.y + lateral, z=inspection_height, yaw_degrees=90)
        right = Waypoint3D(x=center.x, y=server.y - lateral, z=inspection_height, yaw_degrees=90)
    else:
        center = Waypoint3D(x=server.x + inspection_distance, y=server.y, z=inspection_height, yaw_degrees=-90)
        left = Waypoint3D(x=center.x, y=server.y - lateral, z=inspection_height, yaw_degrees=-90)
        right = Waypoint3D(x=center.x, y=server.y + lateral, z=inspection_height, yaw_degrees=-90)
    return {"left": left, "center": center, "right": right}
