from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


Point3 = tuple[float, float, float]


@dataclass(frozen=True)
class GeofenceBox:
    name: str
    minimum: Point3
    maximum: Point3
    margin: float
    raw_points: tuple[Point3, ...] = ()

    @property
    def inflated_minimum(self) -> Point3:
        return tuple(value - self.margin for value in self.minimum)  # type: ignore[return-value]

    @property
    def inflated_maximum(self) -> Point3:
        return tuple(value + self.margin for value in self.maximum)  # type: ignore[return-value]

    @property
    def center(self) -> Point3:
        return tuple((lo + hi) / 2.0 for lo, hi in zip(self.minimum, self.maximum))  # type: ignore[return-value]

    @property
    def inflated_width(self) -> float:
        return self.inflated_maximum[0] - self.inflated_minimum[0]

    @property
    def inflated_depth(self) -> float:
        return self.inflated_maximum[1] - self.inflated_minimum[1]

    def contains(self, point: Point3, inflated: bool = True) -> bool:
        lower = self.inflated_minimum if inflated else self.minimum
        upper = self.inflated_maximum if inflated else self.maximum
        return all(lo <= value <= hi for value, lo, hi in zip(point, lower, upper))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "min": list(self.minimum),
            "max": list(self.maximum),
            "margin": self.margin,
            "inflated_min": list(self.inflated_minimum),
            "inflated_max": list(self.inflated_maximum),
            "raw_points": [list(point) for point in self.raw_points],
        }


def box_from_top_corners(
    points: Iterable[Point3],
    *,
    floor_z: float = 0.0,
    margin: float = 0.35,
    name: str = "server",
) -> GeofenceBox:
    raw_points = tuple(points)
    if len(raw_points) != 4:
        raise ValueError(f"Expected 4 top corner points, got {len(raw_points)}")

    xs = [point[0] for point in raw_points]
    ys = [point[1] for point in raw_points]
    zs = [point[2] for point in raw_points]
    top_z = mean(zs)

    if top_z <= floor_z:
        raise ValueError(f"Measured top z {top_z:.3f} must be above floor z {floor_z:.3f}")

    return GeofenceBox(
        name=name,
        minimum=(min(xs), min(ys), floor_z),
        maximum=(max(xs), max(ys), top_z),
        margin=margin,
        raw_points=raw_points,
    )


def load_box(path: str | Path) -> GeofenceBox:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return GeofenceBox(
        name=str(data.get("name", "server")),
        minimum=tuple(float(value) for value in data["min"]),  # type: ignore[arg-type]
        maximum=tuple(float(value) for value in data["max"]),  # type: ignore[arg-type]
        margin=float(data.get("margin", 0.0)),
        raw_points=tuple(tuple(float(value) for value in point) for point in data.get("raw_points", ())),
    )


def save_box(box: GeofenceBox, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(box.to_dict(), indent=2) + "\n", encoding="utf-8")
