"""Shared preflight logic for operator scripts and API gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import pstdev
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PositionSample:
    """One position sample from the estimator."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class PositionStabilityThresholds:
    """Thresholds for deciding if localization is stable enough to fly."""

    required_samples: int = 10
    xy_spread_max_m: float = 0.20
    z_spread_max_m: float = 0.25
    z_drift_max_m: float = 0.20
    ground_z_abs_max_m: float | None = None


@dataclass(frozen=True)
class PositionStabilityMetrics:
    """Computed spread and drift metrics for a sample window."""

    samples: int
    x_spread: float
    y_spread: float
    z_spread: float
    z_drift: float
    z_stdev: float
    latest_x: float
    latest_y: float
    latest_z: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PositionStabilityResult:
    """Full result of evaluating a sample window against thresholds."""

    ok: bool
    metrics: PositionStabilityMetrics
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "metrics": self.metrics.to_dict(),
            "reasons": list(self.reasons),
        }


def _normalize_samples(samples: Iterable[PositionSample | Sequence[float]]) -> list[PositionSample]:
    normalized: list[PositionSample] = []
    for sample in samples:
        if isinstance(sample, PositionSample):
            normalized.append(sample)
            continue
        if len(sample) != 3:
            raise ValueError(f"expected (x, y, z) sample, got {sample!r}")
        normalized.append(PositionSample(float(sample[0]), float(sample[1]), float(sample[2])))
    return normalized


def compute_position_metrics(
    samples: Iterable[PositionSample | Sequence[float]],
) -> PositionStabilityMetrics:
    """Compute spread, drift, and variance metrics for estimator samples."""

    normalized = _normalize_samples(samples)
    if not normalized:
        return PositionStabilityMetrics(
            samples=0,
            x_spread=0.0,
            y_spread=0.0,
            z_spread=0.0,
            z_drift=0.0,
            z_stdev=0.0,
            latest_x=0.0,
            latest_y=0.0,
            latest_z=0.0,
        )

    xs = [sample.x for sample in normalized]
    ys = [sample.y for sample in normalized]
    zs = [sample.z for sample in normalized]
    latest = normalized[-1]

    return PositionStabilityMetrics(
        samples=len(normalized),
        x_spread=max(xs) - min(xs),
        y_spread=max(ys) - min(ys),
        z_spread=max(zs) - min(zs),
        z_drift=abs(zs[-1] - zs[0]),
        z_stdev=pstdev(zs) if len(zs) > 1 else 0.0,
        latest_x=latest.x,
        latest_y=latest.y,
        latest_z=latest.z,
    )


def evaluate_position_stability(
    samples: Iterable[PositionSample | Sequence[float]],
    thresholds: PositionStabilityThresholds,
) -> PositionStabilityResult:
    """Assess whether a sample window is stable enough for takeoff."""

    metrics = compute_position_metrics(samples)
    reasons: list[str] = []

    if metrics.samples < thresholds.required_samples:
        reasons.append(
            f"too few samples ({metrics.samples} < {thresholds.required_samples})"
        )
    if max(metrics.x_spread, metrics.y_spread) > thresholds.xy_spread_max_m:
        reasons.append(
            "xy spread too high "
            f"({max(metrics.x_spread, metrics.y_spread):.3f}m > {thresholds.xy_spread_max_m:.3f}m)"
        )
    if metrics.z_spread > thresholds.z_spread_max_m:
        reasons.append(
            f"z spread too high ({metrics.z_spread:.3f}m > {thresholds.z_spread_max_m:.3f}m)"
        )
    if metrics.z_drift > thresholds.z_drift_max_m:
        reasons.append(
            f"z drift too high ({metrics.z_drift:.3f}m > {thresholds.z_drift_max_m:.3f}m)"
        )
    if thresholds.ground_z_abs_max_m is not None and abs(metrics.latest_z) > thresholds.ground_z_abs_max_m:
        reasons.append(
            "ground pose estimate out of range "
            f"(|{metrics.latest_z:.3f}|m > {thresholds.ground_z_abs_max_m:.3f}m)"
        )

    return PositionStabilityResult(
        ok=not reasons,
        metrics=metrics,
        reasons=tuple(reasons),
    )


def format_position_metrics(metrics: PositionStabilityMetrics) -> str:
    """Human-readable one-line summary for operator scripts."""

    return (
        f"samples={metrics.samples} "
        f"x_spread={metrics.x_spread:.3f}m "
        f"y_spread={metrics.y_spread:.3f}m "
        f"z_spread={metrics.z_spread:.3f}m "
        f"z_drift={metrics.z_drift:.3f}m "
        f"z_stdev={metrics.z_stdev:.3f}m "
        f"latest=({metrics.latest_x:.3f}, {metrics.latest_y:.3f}, {metrics.latest_z:.3f})"
    )
