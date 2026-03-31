from src.services.preflight_logic import (
    PositionStabilityThresholds,
    compute_position_metrics,
    evaluate_position_stability,
)


def test_compute_position_metrics_tracks_spread_and_latest_point():
    metrics = compute_position_metrics(
        [
            (0.0, 0.0, 0.00),
            (0.1, -0.1, 0.02),
            (0.2, 0.1, 0.03),
        ]
    )

    assert metrics.samples == 3
    assert metrics.x_spread == 0.2
    assert metrics.y_spread == 0.2
    assert metrics.z_spread == 0.03
    assert metrics.latest_x == 0.2
    assert metrics.latest_y == 0.1
    assert metrics.latest_z == 0.03


def test_evaluate_position_stability_passes_for_tight_cluster():
    thresholds = PositionStabilityThresholds(
        required_samples=4,
        xy_spread_max_m=0.2,
        z_spread_max_m=0.2,
        z_drift_max_m=0.2,
        ground_z_abs_max_m=0.2,
    )

    result = evaluate_position_stability(
        [
            (0.00, 0.00, 0.01),
            (0.02, 0.01, 0.02),
            (0.01, -0.01, 0.00),
            (0.03, 0.00, 0.01),
        ],
        thresholds,
    )

    assert result.ok is True
    assert result.reasons == ()


def test_evaluate_position_stability_rejects_large_spread_drift_and_ground_pose():
    thresholds = PositionStabilityThresholds(
        required_samples=4,
        xy_spread_max_m=0.2,
        z_spread_max_m=0.2,
        z_drift_max_m=0.1,
        ground_z_abs_max_m=0.1,
    )

    result = evaluate_position_stability(
        [
            (0.0, 0.0, 0.00),
            (0.3, 0.0, 0.05),
            (0.3, 0.3, 0.15),
            (0.3, 0.3, 0.20),
        ],
        thresholds,
    )

    assert result.ok is False
    joined = " ".join(result.reasons)
    assert "xy spread too high" in joined
    assert "z drift too high" in joined
    assert "ground pose estimate out of range" in joined
