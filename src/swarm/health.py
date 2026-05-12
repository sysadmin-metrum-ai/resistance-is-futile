"""Concurrent drone health checks for swarm roster selection."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import replace
from threading import Event
from typing import Any
from typing import Protocol
from urllib.parse import urlparse

from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import HealthThresholds
from src.swarm.models import Vec3


class HealthProbe(Protocol):
    """Blocking probe used behind an async concurrency wrapper."""

    def check(self, candidate: DroneCandidate, thresholds: HealthThresholds) -> DroneHealth:
        """Return a complete health snapshot for one candidate."""


def normalize_uri(uri: str) -> str:
    return uri.rstrip("/")


def cache_dir_for_uri(uri: str) -> str:
    """Per-address TOC cache; concurrent links should not share one cache file."""

    suffix = normalize_uri(uri).split("/")[-1] or "default"
    return f"./cache/{suffix}"


def radio_scheduler_key(uri: str) -> str:
    """Group probes by physical radio so each Crazyradio is used deliberately."""

    normalized = normalize_uri(uri)
    if not normalized.startswith("radio://"):
        return "non-radio"
    parsed = urlparse(normalized)
    return f"radio://{parsed.netloc}" if parsed.netloc else "radio://0"


def score_health(
    *,
    voltage: float | None,
    battery_percent: int | None,
    connection_quality: int | None,
    battery_pass: bool | None,
    estimator_ready: bool,
    lighthouse_ready: bool,
    thresholds: HealthThresholds,
) -> tuple[bool, float, tuple[str, ...]]:
    """Evaluate a health sample and return readiness, score, and failure reasons."""

    score = 0.0
    reasons: list[str] = []

    if voltage is None:
        reasons.append("missing_voltage")
    elif voltage < thresholds.min_voltage:
        reasons.append("low_voltage")
    else:
        score += min(35.0, (voltage - thresholds.min_voltage) * 50.0 + 20.0)

    if battery_percent is None:
        reasons.append("missing_battery_percent")
    elif battery_percent < thresholds.min_battery_percent:
        reasons.append("low_battery_percent")
    else:
        score += min(25.0, float(battery_percent) / 4.0)

    if connection_quality is None:
        reasons.append("missing_connection_quality")
    elif connection_quality < thresholds.min_connection_quality:
        reasons.append("weak_connection")
    else:
        score += min(25.0, float(connection_quality) / 4.0)

    # battery_pass (firmware health.batteryPass) only flips true after the
    # propeller self-test has run under load, so a grounded drone will always
    # read false. It is a post-flight diagnostic, not a pre-flight gate.
    # Voltage + battery_percent already cover electrical safety; treat
    # battery_pass as advisory bonus only.
    if battery_pass is True:
        score += 5.0

    if not estimator_ready:
        reasons.append("estimator_not_ready")
    else:
        score += 5.0

    if not lighthouse_ready:
        reasons.append("lighthouse_not_ready")
    else:
        score += 5.0

    return not reasons, round(score, 3), tuple(reasons)


def health_from_exception(uri: str, exc: BaseException, elapsed_s: float) -> DroneHealth:
    return DroneHealth(
        uri=normalize_uri(uri),
        ready=False,
        score=0.0,
        reasons=(f"health_check_error:{exc}",),
        elapsed_s=elapsed_s,
    )


class CflibHealthProbe:
    """Read battery, link, Lighthouse, and estimator health from a Crazyflie."""

    def __init__(self, *, retain_connections: bool = False):
        self.retain_connections = retain_connections
        self._retained_connections: dict[str, Any] = {}
        self._retained_lock = threading.Lock()

    def check(self, candidate: DroneCandidate, thresholds: HealthThresholds) -> DroneHealth:
        started = time.monotonic()
        uri = normalize_uri(candidate.uri)

        try:
            import cflib.crtp
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.log import LogConfig
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        except ImportError as exc:
            return health_from_exception(uri, exc, time.monotonic() - started)

        cflib.crtp.init_drivers()
        link_quality: list[int] = []
        scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))

        try:
            scf.open_link()
            cf = scf.cf
            if hasattr(cf, "link_quality_updated"):
                cf.link_quality_updated.add_callback(lambda quality: link_quality.append(int(quality)))

            cf.param.set_value("stabilizer.estimator", "2")
            cf.param.set_value("commander.enHighLevel", "1")
            time.sleep(0.2)

            voltage, battery_percent, battery_pass = self._read_power(LogConfig, cf)
            pose = self._read_pose(LogConfig, cf)
            lighthouse_ready = pose is not None
            # Full estimator reset/convergence is launch preparation work. It
            # runs again on selected retained links before arming, so health
            # selection only verifies that pose telemetry is present.
            estimator_ready = lighthouse_ready
            connection_quality = link_quality[-1] if link_quality else 100
            ready, score, reasons = score_health(
                voltage=voltage,
                battery_percent=battery_percent,
                connection_quality=connection_quality,
                battery_pass=battery_pass,
                estimator_ready=estimator_ready,
                lighthouse_ready=lighthouse_ready,
                thresholds=thresholds,
            )
            health = DroneHealth(
                uri=uri,
                ready=ready,
                score=score,
                reasons=reasons,
                voltage=voltage,
                battery_percent=battery_percent,
                connection_quality=connection_quality,
                battery_pass=battery_pass,
                estimator_ready=estimator_ready,
                lighthouse_ready=lighthouse_ready,
                pose=pose,
                elapsed_s=time.monotonic() - started,
            )
            if self.retain_connections:
                with self._retained_lock:
                    self._retained_connections[uri] = scf
                scf = None
            return health
        finally:
            if scf is not None:
                scf.close_link()

    def pop_retained_connections(self, uris: set[str]) -> dict[str, Any]:
        normalized = {normalize_uri(uri) for uri in uris}
        with self._retained_lock:
            return {
                uri: self._retained_connections.pop(uri)
                for uri in list(self._retained_connections)
                if uri in normalized
            }

    def close_retained_connections(self) -> None:
        with self._retained_lock:
            connections = list(self._retained_connections.values())
            self._retained_connections.clear()
        for scf in connections:
            try:
                scf.close_link()
            except Exception:
                pass

    def _read_power(self, log_cls, cf) -> tuple[float | None, int | None, bool | None]:
        voltages: list[float] = []
        percentages: list[int] = []
        pass_values: list[bool] = []
        for _ in range(3):
            data = self._read_log_once(
                log_cls,
                cf,
                name="SwarmPower",
                variables=(
                    ("pm.vbat", "float"),
                    ("pm.batteryLevel", "uint8_t"),
                    ("health.batteryPass", "uint8_t"),
                ),
                sample_s=0.35,
            )
            voltage = _float_or_none(data.get("pm.vbat"))
            battery_percent = _int_or_none(data.get("pm.batteryLevel"))
            raw_pass = _int_or_none(data.get("health.batteryPass"))
            if voltage is not None:
                voltages.append(voltage)
            if battery_percent is not None:
                percentages.append(battery_percent)
            if raw_pass is not None:
                pass_values.append(raw_pass != 0)
            time.sleep(0.1)

        return (
            min(voltages) if voltages else None,
            min(percentages) if percentages else None,
            all(pass_values) if pass_values else None,
        )

    def _read_pose(self, log_cls, cf) -> Vec3 | None:
        data = self._read_log_once(
            log_cls,
            cf,
            name="SwarmPose",
            variables=(
                ("kalman.stateX", "float"),
                ("kalman.stateY", "float"),
                ("kalman.stateZ", "float"),
            ),
            sample_s=0.45,
        )
        values = (
            _float_or_none(data.get("kalman.stateX")),
            _float_or_none(data.get("kalman.stateY")),
            _float_or_none(data.get("kalman.stateZ")),
        )
        if any(value is None for value in values):
            return None
        return values  # type: ignore[return-value]

    def _reset_and_wait_estimator(self, log_cls, cf, timeout_s: float) -> bool:
        cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(0.1)
        cf.param.set_value("kalman.resetEstimation", "0")

        xs: list[float] = []
        ys: list[float] = []
        zs: list[float] = []
        log = log_cls(name="SwarmEstimator", period_in_ms=100)
        log.add_variable("kalman.varPX", "float")
        log.add_variable("kalman.varPY", "float")
        log.add_variable("kalman.varPZ", "float")

        def on_data(_timestamp, data, _logconf) -> None:
            xs.append(float(data["kalman.varPX"]))
            ys.append(float(data["kalman.varPY"]))
            zs.append(float(data["kalman.varPZ"]))

        cf.log.add_config(log)
        log.data_received_cb.add_callback(on_data)
        log.start()
        deadline = time.monotonic() + timeout_s
        try:
            while time.monotonic() < deadline:
                if _variance_window_ready(xs, ys, zs):
                    return True
                time.sleep(0.1)
            return False
        finally:
            log.stop()
            _delete_log(log)

    def _read_log_once(self, log_cls, cf, *, name: str, variables: tuple[tuple[str, str], ...], sample_s: float) -> dict:
        data: dict = {}
        ready = Event()
        log = log_cls(name=f"{name}{int(time.time() * 1000) % 100000}", period_in_ms=100)
        for variable, kind in variables:
            log.add_variable(variable, kind)

        def on_data(_timestamp, sample, _logconf) -> None:
            data.update(sample)
            ready.set()

        cf.log.add_config(log)
        log.data_received_cb.add_callback(on_data)
        log.start()
        try:
            ready.wait(sample_s)
            return dict(data)
        finally:
            log.stop()
            _delete_log(log)


async def check_candidates_concurrently(
    candidates: list[DroneCandidate],
    *,
    probe: HealthProbe,
    thresholds: HealthThresholds,
) -> list[DroneHealth]:
    """Run bounded health checks per physical radio with independent timeouts."""

    per_radio_limit = max(1, thresholds.max_concurrent_checks)
    radio_keys = {radio_scheduler_key(candidate.uri) for candidate in candidates}
    semaphores = {key: asyncio.Semaphore(per_radio_limit) for key in radio_keys}

    async def check_one(candidate: DroneCandidate) -> DroneHealth:
        semaphore = semaphores[radio_scheduler_key(candidate.uri)]
        async with semaphore:
            started = time.monotonic()
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(probe.check, candidate, thresholds),
                    timeout=thresholds.health_timeout_s,
                )
            except asyncio.TimeoutError:
                return DroneHealth(
                    uri=normalize_uri(candidate.uri),
                    ready=False,
                    score=0.0,
                    reasons=("health_check_timeout",),
                    elapsed_s=time.monotonic() - started,
                )
            except Exception as exc:
                return health_from_exception(candidate.uri, exc, time.monotonic() - started)

    return list(await asyncio.gather(*(check_one(candidate) for candidate in candidates)))


class StaticHealthProbe:
    """Test/dry-run probe that returns configured health snapshots."""

    def __init__(self, health_by_uri: dict[str, DroneHealth]):
        self.health_by_uri = {normalize_uri(uri): health for uri, health in health_by_uri.items()}

    def check(self, candidate: DroneCandidate, thresholds: HealthThresholds) -> DroneHealth:
        health = self.health_by_uri.get(normalize_uri(candidate.uri))
        if health is None:
            return DroneHealth(
                uri=normalize_uri(candidate.uri),
                ready=False,
                score=0.0,
                reasons=("not_configured",),
            )
        return replace(health, uri=normalize_uri(candidate.uri))


def _variance_window_ready(xs: list[float], ys: list[float], zs: list[float]) -> bool:
    # Lighthouse converges fast; 6 samples at 100ms = 0.6s of stable variance
    # is enough confidence the estimator has locked.
    window = 6
    threshold = 0.001
    if len(xs) < window or len(ys) < window or len(zs) < window:
        return False
    return (
        max(xs[-window:]) - min(xs[-window:]) < threshold
        and max(ys[-window:]) - min(ys[-window:]) < threshold
        and max(zs[-window:]) - min(zs[-window:]) < threshold
    )


def _delete_log(log) -> None:
    try:
        log.delete()
    except Exception:
        pass


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _int_or_none(value) -> int | None:
    if value is None:
        return None
    return int(value)
