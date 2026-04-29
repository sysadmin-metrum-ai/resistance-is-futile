from pathlib import Path

from src.safety.geofence import box_from_top_corners
from src.safety.geofence import load_box
from src.safety.geofence import save_box


def test_box_from_top_corners_uses_xy_bounds_and_average_top_z():
    box = box_from_top_corners(
        [
            (1.0, 2.0, 0.82),
            (2.0, 2.0, 0.78),
            (2.0, 4.0, 0.80),
            (1.0, 4.0, 0.80),
        ],
        floor_z=0.0,
        margin=0.25,
    )

    assert box.minimum == (1.0, 2.0, 0.0)
    assert box.maximum == (2.0, 4.0, 0.8)
    assert box.inflated_minimum == (0.75, 1.75, -0.25)
    assert box.inflated_maximum == (2.25, 4.25, 1.05)


def test_box_contains_uses_inflated_bounds_by_default():
    box = box_from_top_corners(
        [(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0)],
        margin=0.2,
    )

    assert box.contains((-0.1, 0.5, 0.5))
    assert not box.contains((-0.1, 0.5, 0.5), inflated=False)
    assert not box.contains((-0.3, 0.5, 0.5))


def test_save_and_load_box_round_trip(tmp_path: Path):
    path = tmp_path / "server_box.json"
    box = box_from_top_corners(
        [(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0)],
        name="server",
        margin=0.35,
    )

    save_box(box, path)
    loaded = load_box(path)

    assert loaded == box
