import time

import pytest

from src.swarm.health import HealthProbe
from src.swarm.health import check_candidates_concurrently
from src.swarm.health import radio_scheduler_key
from src.swarm.health import score_health
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import HealthThresholds
from src.swarm.roster import select_healthiest_swarm
from src.swarm.roster import discover_candidates
from src.swarm.roster import default_radio_candidates


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


def test_score_health_allows_twelve_point_five_percent_preflight():
    ready, score, reasons = score_health(
        voltage=3.75,
        battery_percent=13,
        connection_quality=99,
        battery_pass=False,
        estimator_ready=True,
        lighthouse_ready=True,
        thresholds=HealthThresholds(),
    )

    assert ready is True
    assert reasons == ()
    assert score > 0


def test_score_health_rejects_below_twelve_point_five_percent_preflight():
    ready, score, reasons = score_health(
        voltage=3.75,
        battery_percent=12,
        connection_quality=99,
        battery_pass=False,
        estimator_ready=True,
        lighthouse_ready=True,
        thresholds=HealthThresholds(),
    )

    assert ready is False
    assert score > 0
    assert "low_battery_percent" in reasons


def test_default_radio_candidates_generate_known_fleet_range(monkeypatch):
    monkeypatch.delenv("CRAZYFLIE_URI_COUNT", raising=False)
    monkeypatch.delenv("CRAZYFLIE_URI_PREFIX", raising=False)
    monkeypatch.delenv("CRAZYFLIE_URI_LIST", raising=False)

    candidates = default_radio_candidates()

    assert [candidate.uri for candidate in candidates] == [
        "radio://0/80/2M/E7E7E7E701",
        "radio://0/80/2M/E7E7E7E700",
        "radio://1/90/2M/E7E7E7E709",
    ]


def test_default_radio_candidates_allow_exact_uri_list(monkeypatch):
    monkeypatch.setenv(
        "CRAZYFLIE_URI_LIST",
        "radio://1/90/2M/E7E7E7E705, radio://0/80/2M/E7E7E7E700",
    )

    candidates = default_radio_candidates()

    assert [candidate.uri for candidate in candidates] == [
        "radio://1/90/2M/E7E7E7E705",
        "radio://0/80/2M/E7E7E7E700",
    ]


def test_discover_candidates_defaults_to_configured_fleet(monkeypatch):
    monkeypatch.delenv("CRAZYFLIE_DISCOVERY_MODE", raising=False)
    monkeypatch.delenv("CRAZYFLIE_URI_COUNT", raising=False)
    monkeypatch.delenv("CRAZYFLIE_URI_PREFIX", raising=False)
    monkeypatch.delenv("CRAZYFLIE_URI_LIST", raising=False)

    candidates = discover_candidates()

    assert [candidate.uri for candidate in candidates] == [candidate.uri for candidate in default_radio_candidates()]


def test_radio_scheduler_key_groups_by_dongle():
    assert radio_scheduler_key("radio://0/80/2M/E7E7E7E700") == "radio://0"
    assert radio_scheduler_key("radio://1/90/2M/E7E7E7E705") == "radio://1"
    assert radio_scheduler_key("drone-0") == "non-radio"


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


def test_select_healthiest_swarm_allows_fixed_pair_fallback_to_one():
    health = [
        DroneHealth("radio://0/80/2M/E7E7E7E704", True, 90, pose=(0, 0, 0)),
        DroneHealth("radio://1/90/2M/E7E7E7E709", False, 0, reasons=("low_voltage",)),
    ]

    selection = select_healthiest_swarm(health, 2, minimum_size=1)

    assert [item.uri for item in selection.selected] == ["radio://0/80/2M/E7E7E7E704"]
    assert selection.ready is True
    assert selection.required_size == 1


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
async def test_default_health_checks_run_one_at_a_time():
    candidates = [DroneCandidate(f"radio://0/80/2M/E7E7E7E70{i}") for i in range(4)]
    thresholds = HealthThresholds(health_timeout_s=1.0)

    started = time.monotonic()
    results = await check_candidates_concurrently(
        candidates,
        probe=SlowProbe(0.2),
        thresholds=thresholds,
    )
    elapsed = time.monotonic() - started

    assert 0.75 <= elapsed < 1.0
    assert all(result.ready for result in results)


@pytest.mark.asyncio
async def test_default_health_checks_run_once_per_radio():
    candidates = [
        DroneCandidate("radio://0/80/2M/E7E7E7E700"),
        DroneCandidate("radio://1/90/2M/E7E7E7E705"),
        DroneCandidate("radio://0/80/2M/E7E7E7E701"),
        DroneCandidate("radio://1/90/2M/E7E7E7E706"),
    ]
    thresholds = HealthThresholds(health_timeout_s=1.0)

    started = time.monotonic()
    results = await check_candidates_concurrently(
        candidates,
        probe=SlowProbe(0.2),
        thresholds=thresholds,
    )
    elapsed = time.monotonic() - started

    assert 0.35 <= elapsed < 0.65
    assert all(result.ready for result in results)


@pytest.mark.asyncio
async def test_health_check_timeout_is_per_candidate():
    candidates = [DroneCandidate("slow")]
    thresholds = HealthThresholds(health_timeout_s=0.05, max_concurrent_checks=1)

    results = await check_candidates_concurrently(candidates, probe=SlowProbe(0.5), thresholds=thresholds)

    assert results[0].ready is False
    assert results[0].reasons == ("health_check_timeout",)


@pytest.mark.asyncio
async def test_health_timeout_does_not_include_queue_wait():
    candidates = [DroneCandidate(f"drone-{index}") for index in range(4)]
    thresholds = HealthThresholds(health_timeout_s=0.15, max_concurrent_checks=1)

    results = await check_candidates_concurrently(candidates, probe=SlowProbe(0.1), thresholds=thresholds)

    assert all(result.ready for result in results)
    assert all(result.elapsed_s < 0.15 for result in results)
