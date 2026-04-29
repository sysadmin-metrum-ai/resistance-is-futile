import time

import pytest

from src.swarm.health import HealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.health import score_health
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import HealthThresholds
from src.swarm.roster import select_healthiest_swarm


class SlowProbe:
    def __init__(self, delay: float, ready: bool = True):
        self.delay = delay
        self.ready = ready

    def check(self, candidate: DroneCandidate, thresholds: HealthThresholds) -> DroneHealth:
        time.sleep(self.delay)
        return DroneHealth(
            uri=candidate.uri,
            ready=self.ready,
            score=90.0,
            voltage=4.0,
            battery_percent=90,
            connection_quality=100,
            battery_pass=True,
            estimator_ready=True,
            lighthouse_ready=True,
            pose=(0.0, 0.0, 0.0),
        )


def test_score_health_rejects_low_voltage_and_weak_connection():
    ready, score, reasons = score_health(
        voltage=3.5,
        battery_percent=80,
        connection_quality=50,
        battery_pass=True,
        estimator_ready=True,
        lighthouse_ready=True,
        thresholds=HealthThresholds(),
    )

    assert ready is False
    assert score > 0
    assert "low_voltage" in reasons
    assert "weak_connection" in reasons


def test_score_health_battery_pass_false_is_advisory_not_blocking():
    """health.batteryPass=false on a grounded drone must not block flight."""
    ready, score, reasons = score_health(
        voltage=4.13,
        battery_percent=90,
        connection_quality=99,
        battery_pass=False,
        estimator_ready=True,
        lighthouse_ready=True,
        thresholds=HealthThresholds(),
    )

    assert ready is True
    assert "battery_health_failed" not in reasons
    assert score > 0


def test_select_healthiest_swarm_uses_top_scores():
    health = [
        DroneHealth("a", True, 70, pose=(0, 0, 0)),
        DroneHealth("b", True, 95, pose=(0, 0, 0)),
        DroneHealth("c", False, 99, reasons=("low_voltage",)),
        DroneHealth("d", True, 80, pose=(0, 0, 0)),
        DroneHealth("e", True, 75, pose=(0, 0, 0)),
    ]

    selection = select_healthiest_swarm(health, 3)

    assert [item.uri for item in selection.selected] == ["b", "d", "e"]
    assert selection.ready is True
    assert "c" in [item.uri for item in selection.rejected]


@pytest.mark.asyncio
async def test_health_checks_run_concurrently():
    candidates = [DroneCandidate(f"radio://0/80/2M/E7E7E7E70{i}") for i in range(5)]
    thresholds = HealthThresholds(health_timeout_s=1.0, max_concurrent_checks=5)

    started = time.monotonic()
    results = await check_candidates_concurrently(
        candidates,
        probe=SlowProbe(0.2),
        thresholds=thresholds,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.45
    assert all(result.ready for result in results)


@pytest.mark.asyncio
async def test_health_check_timeout_is_per_candidate():
    candidates = [DroneCandidate("slow")]
    thresholds = HealthThresholds(health_timeout_s=0.05, max_concurrent_checks=1)

    results = await check_candidates_concurrently(candidates, probe=SlowProbe(0.5), thresholds=thresholds)

    assert results[0].ready is False
    assert results[0].reasons == ("health_check_timeout",)
