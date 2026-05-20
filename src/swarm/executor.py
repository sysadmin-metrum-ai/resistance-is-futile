"""Synchronized high-level commander execution for a planned swarm mission."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from typing import Any
from typing import Protocol

from src.swarm.health import cache_dir_for_uri
from src.swarm.models import HealthThresholds
from src.swarm.models import MIN_EXECUTION_SWARM_SIZE
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import SwarmPlan
from src.swarm.planner import build_swarm_plan
from src.swarm.planner import formation_yaw
from src.swarm.planner import go_to_yaw
from src.swarm.planner import pattern_duration_s
from src.swarm.planner import pattern_final_hold_s
from src.swarm.planner import pattern_hold_s
from src.swarm.planner import pattern_yaws

logger = logging.getLogger(__name__)

# Buffer between schedule build time and first fire, to absorb thread
# startup jitter so every drone has time to reach its sleep_until call.
SCHEDULE_PREP_S = 1.0
LED_BLINK_INTERVAL_S = 0.75
LED_POST_LAND_S = 3.0
RTL_LAND_SEQUENCE_DELAY_S = 2.0
FINAL_LAND_SETTLE_S = 0.5
IN_FLIGHT_BATTERY_LOG_MS = 1000
IN_FLIGHT_LAND_BATTERY_PERCENT = 5
IN_FLIGHT_LOW_BATTERY_SAMPLES = 5
IN_FLIGHT_WATCHDOG_LAND_S = 3.0
BatteryTelemetryCallback = Callable[[str, dict], None]
PhaseCallback = Callable[[str, dict | None], None]


@dataclass(frozen=True)
class ExecutionResult:
    events: tuple[str, ...]
    plan: SwarmPlan


@dataclass(frozen=True)
class PreparedExecution:
    plan: SwarmPlan
    connections: tuple[DroneConnection, ...]
    red_blinks: tuple[tuple[threading.Event, threading.Thread], ...] = ()


@dataclass(frozen=True)
class SwarmSchedule:
    """Absolute monotonic timestamps every drone fires at.

    All worker threads sleep until the same instant before dispatching
    each high-level commander call, so radio queue jitter is the only
    source of inter-drone offset (~10-30ms instead of ~100-300ms).
    """

    takeoff_ats: tuple[float, ...]
    formation_fire_ats: tuple[tuple[float, ...], ...]
    led_blue_at: float
    pattern_fire_ats: tuple[tuple[float, ...], ...]
    return_fire_ats: tuple[tuple[float, ...], ...]
    land_ats: tuple[float, ...]
    cleanup_at: float

    @property
    def takeoff_at(self) -> float:
        return min(self.takeoff_ats) if self.takeoff_ats else 0.0

    @property
    def land_at(self) -> float:
        return max(self.land_ats) if self.land_ats else 0.0


def _build_schedule(
    plan: SwarmPlan | MissionSpec,
    n_formation: int,
    n_pattern: int,
    n_return: int,
) -> SwarmSchedule:
    spec = plan.spec if isinstance(plan, SwarmPlan) else plan
    n_drones = len(plan.drones) if isinstance(plan, SwarmPlan) else spec.swarm_size
    t = time.monotonic() + SCHEDULE_PREP_S
    pattern_s = pattern_duration_s(spec)
    pattern_hold = pattern_hold_s(spec)
    pattern_final_hold = pattern_final_hold_s(spec)
    takeoff_at = t
    t += spec.takeoff_s + spec.hold_s

    if isinstance(plan, SwarmPlan):
        formation_ranks = _formation_stagger_ranks(plan)
    else:
        formation_ranks = tuple(range(n_drones))
    formation_fire_ats = _formation_times(
        start_at=t,
        spec=spec,
        n_formation=n_formation,
        formation_ranks=formation_ranks,
    )
    if n_formation > 0:
        t += n_drones * n_formation * (spec.move_s + spec.hold_s)

    # Brief LED-blue ack right after the formation is locked, before the
    # pattern phase begins. Adds 0.3s of dwell so the visual signal is
    # noticeable.
    led_blue_at = t
    t += 0.3

    pattern_steps: list[float] = []
    for _ in range(n_pattern):
        pattern_steps.append(t)
        t += pattern_s + pattern_hold
    t += pattern_final_hold

    if isinstance(plan, SwarmPlan):
        return_ranks = _return_stagger_ranks(plan, n_return=n_return)
    else:
        return_ranks = tuple(range(n_drones))
    return_fire_ats, land_ats = _return_and_land_times(
        start_at=t,
        spec=spec,
        n_return=n_return,
        return_ranks=return_ranks,
    )
    cleanup_at = max(land_ats) + spec.land_s + LED_POST_LAND_S
    return SwarmSchedule(
        takeoff_ats=tuple(takeoff_at for _ in range(n_drones)),
        formation_fire_ats=formation_fire_ats,
        led_blue_at=led_blue_at,
        pattern_fire_ats=tuple(tuple(pattern_steps) for _ in range(n_drones)),
        return_fire_ats=return_fire_ats,
        land_ats=land_ats,
        cleanup_at=cleanup_at,
    )


def _formation_times(
    *,
    start_at: float,
    spec: MissionSpec,
    n_formation: int,
    formation_ranks: tuple[int, ...],
) -> tuple[tuple[float, ...], ...]:
    if n_formation <= 0:
        return tuple(tuple() for _ in formation_ranks)
    route_span_s = n_formation * (spec.move_s + spec.hold_s)
    rank_fire_ats: dict[int, tuple[float, ...]] = {}
    for rank in range(len(formation_ranks)):
        route_start = start_at + rank * route_span_s
        rank_fire_ats[rank] = tuple(route_start + step * (spec.move_s + spec.hold_s) for step in range(n_formation))
    return tuple(rank_fire_ats[rank] for rank in formation_ranks)


def _return_and_land_times(
    *,
    start_at: float,
    spec: MissionSpec,
    n_return: int,
    return_ranks: tuple[int, ...],
) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]:
    shared_steps = 1 if n_return > 1 else 0
    shared_fire_ats: list[float] = []
    cursor = start_at
    for _ in range(shared_steps):
        shared_fire_ats.append(cursor)
        cursor += spec.move_s + spec.hold_s

    rank_fire_ats: dict[int, tuple[float, ...]] = {}
    rank_land_ats: dict[int, float] = {}
    for rank in range(len(return_ranks)):
        fire_ats = list(shared_fire_ats)
        step_cursor = cursor
        for _ in range(shared_steps, n_return):
            fire_ats.append(step_cursor)
            step_cursor += spec.move_s + FINAL_LAND_SETTLE_S
        rank_fire_ats[rank] = tuple(fire_ats)
        rank_land_ats[rank] = step_cursor
        cursor = step_cursor + spec.land_s + RTL_LAND_SEQUENCE_DELAY_S
    return (
        tuple(rank_fire_ats[rank] for rank in return_ranks),
        tuple(rank_land_ats[rank] for rank in return_ranks),
    )


def _formation_stagger_ranks(plan: SwarmPlan) -> tuple[int, ...]:
    ordered = sorted(
        enumerate(plan.drones),
        key=lambda item: (_route_distance_m(item[1].return_point, item[1].route_to_formation), item[0]),
    )
    ranks = [0] * len(plan.drones)
    for rank, (drone_ix, _drone) in enumerate(ordered):
        ranks[drone_ix] = rank
    return tuple(ranks)


def _return_stagger_ranks(plan: SwarmPlan, *, n_return: int) -> tuple[int, ...]:
    shared_steps = 1 if n_return > 1 else 0
    ordered = sorted(
        enumerate(plan.drones),
        key=lambda item: (_return_home_distance_m(item[1], shared_steps=shared_steps), item[0]),
    )
    ranks = [0] * len(plan.drones)
    for rank, (drone_ix, _drone) in enumerate(ordered):
        ranks[drone_ix] = rank
    return tuple(ranks)


def _return_home_distance_m(drone: DronePlan, *, shared_steps: int) -> float:
    start = drone.pattern_points[-1] if drone.pattern_points else drone.formation_slot
    shared = drone.route_to_return[:shared_steps]
    home_route = drone.route_to_return[shared_steps:]
    if shared:
        start = shared[-1]
    return _route_distance_m(start, home_route)


def _route_distance_m(start: tuple[float, float, float], route: tuple[tuple[float, float, float], ...]) -> float:
    points = (start, *route)
    return sum(_distance_m(a, b) for a, b in zip(points, points[1:]))


def _distance_m(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _sleep_until(deadline: float) -> None:
    delay = deadline - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def _read_log_once(log_cls, cf, *, name: str, variables: tuple[tuple[str, str], ...], sample_s: float) -> dict:
    from threading import Event

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
        try:
            log.delete()
        except Exception:
            pass


def _read_power_for_executor(log_cls, cf) -> tuple[float | None, int | None]:
    voltages: list[float] = []
    percentages: list[int] = []
    for _ in range(2):
        data = _read_log_once(
            log_cls,
            cf,
            name="ExecPower",
            variables=(("pm.vbat", "float"), ("pm.batteryLevel", "uint8_t")),
            sample_s=0.35,
        )
        if data.get("pm.vbat") is not None:
            voltages.append(float(data["pm.vbat"]))
        if data.get("pm.batteryLevel") is not None:
            percentages.append(int(data["pm.batteryLevel"]))
        time.sleep(0.1)
    return min(voltages) if voltages else None, min(percentages) if percentages else None


class Commander(Protocol):
    def takeoff(self, absolute_height_m: float, duration_s: float, **kwargs) -> None: ...

    def go_to(self, x: float, y: float, z: float, yaw: float, duration_s: float, **kwargs) -> None: ...

    def land(self, absolute_height_m: float, duration_s: float, **kwargs) -> None: ...

    def stop(self) -> None: ...


class DroneConnection(Protocol):
    uri: str
    commander: Commander

    def close(self) -> None: ...


class DroneConnector(Protocol):
    def connect(self, uri: str, spec: MissionSpec) -> DroneConnection: ...


class CflibDroneConnection:
    """Two-phase setup: connect() opens the radio link (sequential), then
    configure() runs Kalman reset/wait + arming and is safe to call in
    parallel across drones."""

    def __init__(self, uri: str, spec: MissionSpec, scf: Any | None = None):
        self.uri = uri
        self._spec = spec
        if scf is None:
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

            scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
            scf.open_link()
        self._scf = scf
        self.commander = self._scf.cf.high_level_commander
        self._led_mode = self._detect_led_mode()
        self._battery_watch: BatteryWatch | None = None
        if self._led_mode == "colorLedBot" and self._has_param("colorLedBot", "brightCorr"):
            self._scf.cf.param.set_value("colorLedBot.brightCorr", "1")

    def close(self) -> None:
        self._scf.close_link()

    def set_led_red(self) -> None:
        self._set_led_color("red", 100, 0, 0)

    def set_led_blue(self) -> None:
        self._set_led_color("blue", 0, 0, 100)

    def set_led_orange(self) -> None:
        self._set_led_color("orange", 100, 35, 0)

    def set_led_green(self) -> None:
        self._set_led_color("green", 0, 100, 0)

    def set_led_yellow(self) -> None:
        self._set_led_color("yellow", 100, 100, 0)

    def set_led_cyan(self) -> None:
        self._set_led_color("cyan", 0, 100, 100)

    def set_led_purple(self) -> None:
        self._set_led_color("purple", 80, 0, 100)

    def _set_led_color(self, label: str, red: int, green: int, blue: int) -> None:
        try:
            if self._led_mode == "colorLedBot":
                wrgb8888 = (red << 16) | (green << 8) | blue
                self._scf.cf.param.set_value("colorLedBot.wrgb8888", str(wrgb8888))
            elif self._led_mode == "ring":
                self._scf.cf.param.set_value("ring.effect", "7")
                self._scf.cf.param.set_value("ring.solidRed", str(red))
                self._scf.cf.param.set_value("ring.solidGreen", str(green))
                self._scf.cf.param.set_value("ring.solidBlue", str(blue))
        except Exception as exc:
            logger.warning("swarm executor: %s LED %s set failed: %s", self.uri, label, exc)

    def set_led_off(self) -> None:
        """Turn the bottom LED ring deck fully off."""
        try:
            if self._led_mode == "colorLedBot":
                self._scf.cf.param.set_value("colorLedBot.wrgb8888", "0")
            elif self._led_mode == "ring":
                self._scf.cf.param.set_value("ring.effect", "0")
        except Exception as exc:
            logger.warning("swarm executor: %s LED off failed: %s", self.uri, exc)

    def can_blink_led(self) -> bool:
        return self._led_mode in {"colorLedBot", "ring"}

    def start_battery_watch(self, telemetry_callback: BatteryTelemetryCallback | None = None) -> None:
        from cflib.crazyflie.log import LogConfig

        self._battery_watch = BatteryWatch(self.uri, self.commander, self._scf.cf, LogConfig, telemetry_callback)
        self._battery_watch.start()

    def stop_battery_watch(self) -> bool:
        if self._battery_watch is None:
            return False
        triggered = self._battery_watch.triggered
        self._battery_watch.stop()
        self._battery_watch = None
        return triggered

    def is_battery_watch_triggered(self) -> bool:
        return self._battery_watch is not None and self._battery_watch.triggered

    def _detect_led_mode(self) -> str:
        if self._has_param("colorLedBot", "wrgb8888"):
            return "colorLedBot"
        if self._has_param("ring", "effect"):
            return "ring"
        logger.info("swarm executor: %s no supported bottom LED params found", self.uri)
        return "none"

    def _has_param(self, group: str, name: str) -> bool:
        try:
            toc = self._scf.cf.param.toc.toc
            group_toc = toc.get(group)
            return group_toc is not None and name in group_toc
        except Exception:
            return False

    def configure(self) -> None:
        cf = self._scf.cf
        spec = self._spec
        cf.param.set_value("stabilizer.estimator", "2")
        cf.param.set_value("commander.enHighLevel", "1")
        if spec.enable_collision_avoidance:
            # BVCA requires peer localization and is confirmed with PID, not Mellinger.
            cf.param.set_value("stabilizer.controller", "1")
            cf.param.set_value("colAv.enable", "1")
            radius_xy = max(0.10, spec.min_separation_m)
            cf.param.set_value("colAv.ellipsoidX", f"{radius_xy:.3f}")
            cf.param.set_value("colAv.ellipsoidY", f"{radius_xy:.3f}")
            cf.param.set_value("colAv.ellipsoidZ", f"{max(radius_xy * 3.0, 0.45):.3f}")
        time.sleep(0.5)

        logger.info("swarm executor: %s waiting for kalman convergence", self.uri)
        t0 = time.monotonic()
        self._reset_and_wait_estimator(cf, timeout_s=8.0)
        logger.info(
            "swarm executor: %s kalman converged in %.2fs, arming",
            self.uri,
            time.monotonic() - t0,
        )
        self._send_arming_request(cf)
        logger.info("swarm executor: %s armed", self.uri)

    def refresh_launch_authorization(self) -> None:
        cf = self._scf.cf
        cf.param.set_value("commander.enHighLevel", "1")
        self._send_arming_request(cf)
        logger.info("swarm executor: %s launch authorization refreshed", self.uri)

    def _reset_and_wait_estimator(self, cf, *, timeout_s: float) -> None:
        from cflib.crazyflie.log import LogConfig

        cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(0.1)
        cf.param.set_value("kalman.resetEstimation", "0")

        xs: list[float] = []
        ys: list[float] = []
        zs: list[float] = []
        log = LogConfig(name=f"ExecVar{int(time.time() * 1000) % 100000}", period_in_ms=100)
        log.add_variable("kalman.varPX", "float")
        log.add_variable("kalman.varPY", "float")
        log.add_variable("kalman.varPZ", "float")

        def on_data(_ts, data, _conf) -> None:
            xs.append(float(data["kalman.varPX"]))
            ys.append(float(data["kalman.varPY"]))
            zs.append(float(data["kalman.varPZ"]))

        cf.log.add_config(log)
        log.data_received_cb.add_callback(on_data)
        log.start()
        try:
            deadline = time.monotonic() + timeout_s
            # Window matches Bitcraze official examples: 10 samples at 100ms
            # = 1.0s of stable variance before we trust the estimate.
            window = 10
            threshold = 0.001
            while time.monotonic() < deadline:
                if (
                    len(xs) >= window
                    and max(xs[-window:]) - min(xs[-window:]) < threshold
                    and max(ys[-window:]) - min(ys[-window:]) < threshold
                    and max(zs[-window:]) - min(zs[-window:]) < threshold
                ):
                    # Extra settle so the position state itself (not just the
                    # variance) tracks truth before we arm + takeoff.
                    time.sleep(0.5)
                    return
                time.sleep(0.1)
            raise RuntimeError(f"{self.uri}: kalman did not converge in {timeout_s}s")
        finally:
            log.stop()
            try:
                log.delete()
            except Exception:
                pass

    def _send_arming_request(self, cf) -> None:
        # Firmware >=2023.11 requires arming. 2024+ moved the API from
        # cf.platform to cf.supervisor; try supervisor first.
        if hasattr(cf, "supervisor"):
            cf.supervisor.send_arming_request(True)
        else:
            cf.platform.send_arming_request(True)
        time.sleep(1.0)

    def _assert_power_ready(self, cf) -> None:
        from cflib.crazyflie.log import LogConfig

        thresholds = HealthThresholds()
        voltage, battery_percent = _read_power_for_executor(LogConfig, cf)
        if voltage is None or voltage < thresholds.min_voltage:
            raise RuntimeError(f"{self.uri}: voltage {voltage} below {thresholds.min_voltage:.2f}V")
        if battery_percent is None or battery_percent < thresholds.min_battery_percent:
            raise RuntimeError(
                f"{self.uri}: battery_percent {battery_percent} below {thresholds.min_battery_percent}%"
            )


class CflibDroneConnector:
    def __init__(self, retained_connections: dict[str, Any] | None = None):
        self._retained_connections = retained_connections or {}

    def connect(self, uri: str, spec: MissionSpec) -> DroneConnection:
        scf = self._retained_connections.pop(uri, None)
        return CflibDroneConnection(uri, spec, scf=scf)


class BatteryWatch:
    """Low-rate in-flight battery guard that asks only the weak drone to land."""

    def __init__(
        self,
        uri: str,
        commander: Commander,
        cf,
        log_cls,
        telemetry_callback: BatteryTelemetryCallback | None = None,
    ):
        self.uri = uri
        self.commander = commander
        self.cf = cf
        self.thresholds = HealthThresholds()
        self.low_samples = 0
        self.critical_samples = 0
        self.triggered = False
        self.trigger_reason: str | None = None
        self._telemetry_callback = telemetry_callback
        self._log = log_cls(name=f"BattWatch{int(time.time() * 1000) % 100000}", period_in_ms=IN_FLIGHT_BATTERY_LOG_MS)
        self._log.add_variable("pm.vbat", "float")
        self._log.add_variable("pm.batteryLevel", "uint8_t")

    def start(self) -> None:
        self.cf.log.add_config(self._log)
        self._log.data_received_cb.add_callback(self._on_data)
        self._log.start()
        logger.info("swarm executor: %s battery watchdog started", self.uri)

    def stop(self) -> None:
        try:
            self._log.stop()
        except Exception:
            pass
        try:
            self._log.delete()
        except Exception:
            pass

    def _on_data(self, _timestamp, data, _logconf) -> None:
        if self.triggered:
            return
        voltage = data.get("pm.vbat")
        percent = data.get("pm.batteryLevel")
        voltage_value = float(voltage) if voltage is not None else None
        percent_value = int(percent) if percent is not None else None
        reason = self._update_battery_counters(voltage_value, percent_value)
        if reason is None:
            self._publish_sample(voltage_value, percent_value)
            return

        self.triggered = True
        self.trigger_reason = reason
        logger.warning(
            "swarm executor: %s battery watchdog landing: voltage=%s percent=%s reason=%s",
            self.uri,
            voltage,
            percent,
            reason,
        )
        try:
            self.commander.land(0.0, IN_FLIGHT_WATCHDOG_LAND_S, yaw=None)
        except Exception as exc:
            logger.warning("swarm executor: %s battery watchdog land failed: %s", self.uri, exc)
        self._publish_sample(voltage_value, percent_value)

    def _update_battery_counters(self, voltage: float | None, battery_percent: int | None) -> str | None:
        low_percent = battery_percent is not None and battery_percent <= IN_FLIGHT_LAND_BATTERY_PERCENT
        if low_percent:
            self.low_samples += 1
        else:
            self.low_samples = 0
        if self.low_samples >= IN_FLIGHT_LOW_BATTERY_SAMPLES:
            return "critical_battery_percent"
        return None

    def _publish_sample(self, voltage: float | None, battery_percent: int | None) -> None:
        if self._telemetry_callback is None:
            return
        try:
            self._telemetry_callback(
                self.uri,
                {
                    "voltage": voltage,
                    "battery_percent": battery_percent,
                    "low_samples": self.low_samples,
                    "critical_samples": self.critical_samples,
                    "watchdog_landed": self.triggered,
                    "trigger_reason": self.trigger_reason,
                    "sampled_at": time.time(),
                },
            )
        except Exception:
            logger.debug("swarm executor: %s battery telemetry callback failed", self.uri, exc_info=True)


class SwarmExecutor:
    """Execute a swarm plan with one worker thread per drone."""

    def __init__(self, connector: DroneConnector | None = None):
        self.connector = connector or CflibDroneConnector()
        self._active_lock = threading.RLock()
        self._active_connections: list[DroneConnection] = []
        self._emergency_stop = threading.Event()

    def execute(
        self,
        plan: SwarmPlan,
        *,
        arm: bool,
        telemetry_callback: BatteryTelemetryCallback | None = None,
        phase_callback: PhaseCallback | None = None,
    ) -> ExecutionResult:
        if not arm or plan.spec.dry_run:
            return ExecutionResult(tuple(dry_run_events(plan)), plan)

        prepared = self.prepare(plan, phase_callback=phase_callback)
        return self.launch(prepared, telemetry_callback=telemetry_callback, phase_callback=phase_callback)

    def prepare(
        self,
        plan: SwarmPlan,
        *,
        phase_callback: PhaseCallback | None = None,
        retained_connections: dict[str, Any] | None = None,
    ) -> PreparedExecution:
        self._emergency_stop.clear()
        connections: list[DroneConnection] = []
        green_blinks: list[tuple[threading.Event, threading.Thread]] = []
        try:
            logger.info("swarm executor: opening %d cflib links", len(plan.drones))
            connector = CflibDroneConnector(retained_connections) if retained_connections else self.connector
            connections, green_blinks = self._connect_in_parallel(plan, connector=connector)
            self._set_active_connections(connections)

            plan = _replan_for_remaining(plan, connections, "connect")
            connections = self._configure_in_parallel(connections)
            self._set_active_connections(connections)
            if self._emergency_stop.is_set():
                raise RuntimeError("emergency_stop_requested")
            plan = _replan_for_remaining(plan, connections, "configure")
            green_blinks = _start_ready_led_blinks(connections)
            logger.info("swarm executor: all drones configured + armed, ready to deploy")
            _notify_phase(
                phase_callback,
                "ready_to_deploy",
                {"selected": [connection.uri for connection in connections], "launch_ready": True},
            )
            return PreparedExecution(plan=plan, connections=tuple(connections), red_blinks=tuple(green_blinks))
        except BaseException:
            _stop_led_blinks(green_blinks)
            for connection in connections:
                try:
                    connection.close()
                except Exception:
                    pass
            raise

    def launch(
        self,
        prepared: PreparedExecution,
        *,
        telemetry_callback: BatteryTelemetryCallback | None = None,
        phase_callback: PhaseCallback | None = None,
    ) -> ExecutionResult:
        plan = prepared.plan
        connections = list(prepared.connections)
        green_blinks = list(prepared.red_blinks)
        try:
            logger.info("swarm executor: launching prepared swarm")
            self._set_active_connections(connections)
            _stop_led_blinks(green_blinks)
            green_blinks = []
            connections = self._refresh_launch_authorization(connections)
            self._set_active_connections(connections)
            plan = _replan_for_remaining(plan, connections, "launch_authorization")
            for connection in connections:
                if hasattr(connection, "set_led_blue"):
                    connection.set_led_blue()  # type: ignore[attr-defined]
                    logger.info("swarm executor: %s LED blue launch", connection.uri)

            n_formation = max(len(d.route_to_formation) for d in plan.drones)
            n_pattern = max(len(d.pattern_points) for d in plan.drones)
            n_return = max(len(d.route_to_return) for d in plan.drones)
            schedule = _build_schedule(plan, n_formation, n_pattern, n_return)
            logger.info(
                "swarm executor: schedule takeoff_at=+%.2fs land_at=+%.2fs",
                schedule.takeoff_at - time.monotonic(),
                schedule.land_at - time.monotonic(),
            )
            _notify_phase(phase_callback, "taking_off", {"takeoff_in_seconds": max(0.0, schedule.takeoff_at - time.monotonic())})

            events: list[str] = []
            errors: list[BaseException] = []
            lock = threading.Lock()
            phase_once = {
                "taking_off": threading.Event(),
                "returning": threading.Event(),
            }

            def worker(connection: DroneConnection, drone_plan: DronePlan) -> None:
                try:
                    logger.info("swarm executor: %s worker starting", connection.uri)
                    drone_events = self._execute_one(
                        connection,
                        drone_plan,
                        plan,
                        schedule,
                        telemetry_callback,
                        phase_callback,
                        phase_once,
                    )
                    with lock:
                        events.extend(drone_events)
                    logger.info("swarm executor: %s worker finished cleanly", connection.uri)
                except BaseException as exc:
                    logger.exception("swarm executor: %s worker failed: %s", connection.uri, exc)
                    with lock:
                        errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=(connection, drone_plan), name=f"swarm-{drone_plan.uri}")
                for connection, drone_plan in zip(connections, plan.drones)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            if errors:
                self.stop_all(connections)
                raise RuntimeError("swarm execution failed") from errors[0]
            _notify_phase(phase_callback, "completed", {"events": len(events)})
            return ExecutionResult(tuple(events), plan)
        finally:
            _stop_led_blinks(green_blinks)
            for connection in connections:
                try:
                    connection.close()
                except Exception:
                    pass
            self._set_active_connections([])

    def _connect_in_parallel(
        self,
        plan: SwarmPlan,
        *,
        connector: DroneConnector | None = None,
    ) -> tuple[list[DroneConnection], list[tuple[threading.Event, threading.Thread]]]:
        """Open selected links concurrently, then preserve plan order."""

        connector = connector or self.connector
        by_uri: dict[str, DroneConnection] = {}
        lock = threading.Lock()

        def runner(drone: DronePlan) -> None:
            t0 = time.monotonic()
            logger.info("swarm executor: connecting %s", drone.uri)
            try:
                connection = connector.connect(drone.uri, plan.spec)
                with lock:
                    by_uri[drone.uri] = connection
                    self._set_active_connections([by_uri[item.uri] for item in plan.drones if item.uri in by_uri])
                logger.info("swarm executor: connected %s in %.2fs", drone.uri, time.monotonic() - t0)
            except BaseException as exc:
                logger.exception("swarm executor: connect failed for %s: %s", drone.uri, exc)

        threads = [threading.Thread(target=runner, args=(drone,), name=f"conn-{drone.uri}") for drone in plan.drones]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return [by_uri[drone.uri] for drone in plan.drones if drone.uri in by_uri], []

    def _configure_in_parallel(self, connections: list[DroneConnection]) -> list[DroneConnection]:
        """Run per-drone configure() concurrently; tolerate fakes without one."""
        configurable = [conn for conn in connections if hasattr(conn, "configure")]
        if not configurable:
            return connections

        logger.info("swarm executor: configuring %d drones in parallel", len(configurable))
        configured: list[DroneConnection] = []
        lock = threading.Lock()

        def runner(conn: DroneConnection) -> None:
            try:
                conn.configure()  # type: ignore[attr-defined]
                with lock:
                    configured.append(conn)
            except BaseException as exc:
                logger.exception("swarm executor: %s configure failed: %s", conn.uri, exc)

        threads = [threading.Thread(target=runner, args=(conn,), name=f"cfg-{conn.uri}") for conn in configurable]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        failed = [conn for conn in configurable if conn not in configured]
        for conn in failed:
            _land_stop_and_close(conn)
        return [conn for conn in connections if conn in configured or conn not in configurable]

    def _refresh_launch_authorization(self, connections: list[DroneConnection]) -> list[DroneConnection]:
        refreshable = [conn for conn in connections if hasattr(conn, "refresh_launch_authorization")]
        if not refreshable:
            return connections

        logger.info("swarm executor: refreshing launch authorization on %d drones", len(refreshable))
        authorized: list[DroneConnection] = []
        failed: list[DroneConnection] = []
        lock = threading.Lock()

        def runner(conn: DroneConnection) -> None:
            try:
                conn.refresh_launch_authorization()  # type: ignore[attr-defined]
                with lock:
                    authorized.append(conn)
            except BaseException as exc:
                logger.exception("swarm executor: %s launch authorization refresh failed: %s", conn.uri, exc)
                with lock:
                    failed.append(conn)

        threads = [threading.Thread(target=runner, args=(conn,), name=f"arm-{conn.uri}") for conn in refreshable]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for conn in failed:
            _land_stop_and_close(conn)
        return [conn for conn in connections if conn in authorized or conn not in refreshable]

    def stop_all(self, connections: list[DroneConnection]) -> None:
        for connection in connections:
            try:
                connection.commander.land(0.0, 1.0, yaw=None)
            except Exception:
                pass
        time.sleep(1.0)
        for connection in connections:
            try:
                connection.commander.stop()
            except Exception:
                pass
            if hasattr(connection, "set_led_off"):
                try:
                    connection.set_led_off()  # type: ignore[attr-defined]
                except Exception:
                    pass

    def emergency_stop_active(self) -> list[str]:
        self._emergency_stop.set()
        with self._active_lock:
            connections = list(self._active_connections)
        self.stop_all(connections)
        return [connection.uri for connection in connections]

    def _set_active_connections(self, connections: list[DroneConnection]) -> None:
        with self._active_lock:
            self._active_connections = list(connections)

    def _execute_one(
        self,
        connection: DroneConnection,
        drone_plan: DronePlan,
        swarm_plan: SwarmPlan,
        schedule: SwarmSchedule,
        telemetry_callback: BatteryTelemetryCallback | None = None,
        phase_callback: PhaseCallback | None = None,
        phase_once: dict[str, threading.Event] | None = None,
    ) -> list[str]:
        spec = swarm_plan.spec
        uri = drone_plan.uri
        commander = connection.commander
        crazy_mode = spec.pattern == "crazy_pinwheel"
        yaw = go_to_yaw(spec)
        start_yaw = formation_yaw(spec)
        pattern_s = pattern_duration_s(spec)
        drone_index = swarm_plan.drones.index(drone_plan)
        events: list[str] = []

        # Pad shorter routes by holding at the last waypoint so every drone
        # fires the same number of go_to commands at the same instants.
        formation_fires = schedule.formation_fire_ats[drone_index]
        formation_points = _pad_route(drone_plan.route_to_formation, len(formation_fires))
        return_fires = schedule.return_fire_ats[drone_index]
        return_points = _pad_route(drone_plan.route_to_return, len(return_fires))
        pattern_fires = schedule.pattern_fire_ats[drone_index]
        pattern_points = _pad_route(drone_plan.pattern_points, len(pattern_fires))
        pattern_point_yaws = pattern_yaws(spec, len(pattern_points))

        _sleep_until(schedule.takeoff_ats[drone_index])
        if self._emergency_stop.is_set():
            events.append(f"{uri}:emergency_stop")
            return events
        logger.info("swarm executor: %s takeoff to %.2fm", uri, spec.hover_z)
        if phase_once is not None and not phase_once["taking_off"].is_set():
            phase_once["taking_off"].set()
            _notify_phase(phase_callback, "taking_off", {"first_takeoff_uri": uri})
        commander.takeoff(spec.hover_z, spec.takeoff_s, yaw=None)
        events.append(f"{uri}:takeoff")
        if hasattr(connection, "start_battery_watch"):
            _start_battery_watch(connection, telemetry_callback)
            events.append(f"{uri}:battery_watch_start")
        blink_color, blink_phase_s = _in_flight_blink_style(spec, drone_index)
        blink = _start_led_blink(connection, uri, blink_color, phase_s=blink_phase_s)
        if blink is not None:
            events.append(f"{uri}:led_{blink_color}_blink_start")

        battery_watch_landed = False

        def note_battery_watch_landed() -> bool:
            nonlocal battery_watch_landed
            if battery_watch_landed or not _battery_watch_triggered(connection):
                return battery_watch_landed
            battery_watch_landed = True
            events.append(f"{uri}:battery_watch_landed")
            return True

        for fire_at, point in zip(formation_fires, formation_points):
            _sleep_until(fire_at)
            if self._emergency_stop.is_set():
                events.append(f"{uri}:emergency_stop")
                return events
            if note_battery_watch_landed():
                break
            commander.go_to(*point, start_yaw, spec.move_s, relative=False)
            events.append(f"{uri}:formation")

        if not battery_watch_landed:
            _sleep_until(schedule.led_blue_at)
            if note_battery_watch_landed():
                pass

        if not battery_watch_landed:
            last_pattern_completion_at: float | None = None
            for index, (fire_at, point, point_yaw) in enumerate(zip(pattern_fires, pattern_points, pattern_point_yaws)):
                _sleep_until(fire_at)
                if self._emergency_stop.is_set():
                    events.append(f"{uri}:emergency_stop")
                    return events
                if note_battery_watch_landed():
                    break
                commander.go_to(*point, point_yaw, pattern_s, relative=False)
                events.append(f"{uri}:pattern")
                last_pattern_completion_at = fire_at + pattern_s

            if not battery_watch_landed and last_pattern_completion_at is not None:
                _sleep_until(last_pattern_completion_at)
                if blink is not None and not crazy_mode:
                    _stop_led_blink(blink)
                    blink = None
                if not crazy_mode and hasattr(connection, "set_led_orange"):
                    connection.set_led_orange()  # type: ignore[attr-defined]
                    events.append(f"{uri}:led_orange")
                    logger.info("swarm executor: %s LED orange", uri)

        if not battery_watch_landed:
            for fire_at, point in zip(return_fires, return_points):
                _sleep_until(fire_at)
                if self._emergency_stop.is_set():
                    events.append(f"{uri}:emergency_stop")
                    return events
                if note_battery_watch_landed():
                    break
                if phase_once is not None and not phase_once["returning"].is_set():
                    phase_once["returning"].set()
                    _notify_phase(phase_callback, "returning", {"first_return_uri": uri})
                commander.go_to(*point, yaw, spec.move_s, relative=False)
                events.append(f"{uri}:return")

        if not battery_watch_landed:
            _sleep_until(schedule.land_ats[drone_index])
            if self._emergency_stop.is_set():
                events.append(f"{uri}:emergency_stop")
                return events
            if not note_battery_watch_landed():
                if spec.pattern == "launch_up" and hasattr(connection, "set_led_blue"):
                    connection.set_led_blue()  # type: ignore[attr-defined]
                    events.append(f"{uri}:led_blue")
                    logger.info("swarm executor: %s LED blue before land", uri)
                commander.land(0.0, spec.land_s, yaw=None)
                events.append(f"{uri}:land")
                _sleep_until(schedule.land_ats[drone_index] + spec.land_s)
                if not crazy_mode:
                    blink = _replace_led_blink(blink, connection, uri, "green")
                if blink is not None and not crazy_mode:
                    events.append(f"{uri}:led_green_blink_start")
        _sleep_until(schedule.cleanup_at)
        if self._emergency_stop.is_set():
            events.append(f"{uri}:emergency_stop")
            return events
        if blink is not None:
            _stop_led_blink(blink)
            events.append(f"{uri}:led_blink_stop")
        if hasattr(connection, "set_led_off"):
            connection.set_led_off()  # type: ignore[attr-defined]
            events.append(f"{uri}:led_off")
            logger.info("swarm executor: %s LED off", uri)
        if hasattr(connection, "stop_battery_watch"):
            if connection.stop_battery_watch():  # type: ignore[attr-defined]
                if not battery_watch_landed:
                    events.append(f"{uri}:battery_watch_landed")
            else:
                events.append(f"{uri}:battery_watch_stop")
        commander.stop()
        return events


def _pad_route(points: tuple, length: int) -> tuple:
    """Repeat the last waypoint so every drone's timeline has the same length."""
    if not points:
        return tuple()
    if len(points) >= length:
        return points
    return points + (points[-1],) * (length - len(points))


def _notify_phase(callback: PhaseCallback | None, phase: str, details: dict | None = None) -> None:
    if callback is None:
        return
    try:
        callback(phase, details)
    except Exception:
        logger.debug("swarm executor: phase callback failed", exc_info=True)


def _in_flight_blink_style(spec: MissionSpec, drone_index: int) -> tuple[str, float]:
    if spec.pattern != "crazy_pinwheel":
        return "blue", 0.0
    colors = ("cyan", "purple", "yellow", "blue", "green", "red", "orange", "cyan", "purple", "yellow")
    return colors[drone_index % len(colors)], drone_index * 0.17


def _start_led_blink(
    connection: DroneConnection,
    uri: str,
    color: str,
    phase_s: float = 0.0,
) -> tuple[threading.Event, threading.Thread] | None:
    if hasattr(connection, "can_blink_led") and not connection.can_blink_led():  # type: ignore[attr-defined]
        return None
    setter = getattr(connection, f"set_led_{color}", None)
    if setter is None or not hasattr(connection, "set_led_off"):
        return None

    stop = threading.Event()
    if phase_s <= 0:
        setter()
    else:
        connection.set_led_off()  # type: ignore[attr-defined]

    def blink() -> None:
        if phase_s > 0 and stop.wait(phase_s):
            return
        lit = True
        while not stop.is_set():
            if lit:
                setter()
            else:
                connection.set_led_off()  # type: ignore[attr-defined]
            lit = not lit
            stop.wait(LED_BLINK_INTERVAL_S)

    thread = threading.Thread(target=blink, name=f"led-{color}-blink-{uri}", daemon=True)
    thread.start()
    logger.info("swarm executor: %s LED %s blink started", uri, color)
    return stop, thread


def _start_ready_led_blinks(connections: list[DroneConnection]) -> list[tuple[threading.Event, threading.Thread]]:
    blinks: list[tuple[threading.Event, threading.Thread]] = []
    for connection in connections:
        blink = _start_led_blink(connection, connection.uri, "green")
        if blink is not None:
            blinks.append(blink)
    return blinks


def _replace_led_blink(
    current: tuple[threading.Event, threading.Thread] | None,
    connection: DroneConnection,
    uri: str,
    color: str,
) -> tuple[threading.Event, threading.Thread] | None:
    if current is not None:
        _stop_led_blink(current)
    return _start_led_blink(connection, uri, color)


def _stop_led_blinks(blinks: list[tuple[threading.Event, threading.Thread]]) -> None:
    for blink in blinks:
        _stop_led_blink(blink)


def _stop_led_blink(blink: tuple[threading.Event, threading.Thread]) -> None:
    stop_blink, blink_thread = blink
    stop_blink.set()
    blink_thread.join(timeout=1.0)


def _battery_watch_triggered(connection: DroneConnection) -> bool:
    checker = getattr(connection, "is_battery_watch_triggered", None)
    return checker is not None and bool(checker())


def _start_battery_watch(
    connection: DroneConnection,
    telemetry_callback: BatteryTelemetryCallback | None,
) -> None:
    try:
        connection.start_battery_watch(telemetry_callback)  # type: ignore[attr-defined]
    except TypeError:
        connection.start_battery_watch()  # type: ignore[attr-defined]


def _land_stop_and_close(connection: DroneConnection) -> None:
    try:
        connection.commander.land(0.0, 1.0, yaw=None)
    except Exception:
        pass
    time.sleep(1.0)
    try:
        connection.commander.stop()
    except Exception:
        pass
    try:
        connection.close()
    except Exception:
        pass


def _replan_for_remaining(plan: SwarmPlan, connections: list[DroneConnection], phase: str) -> SwarmPlan:
    minimum_size = _minimum_viable_swarm_size(plan.spec.swarm_size, plan.spec.pattern)
    if len(connections) < minimum_size:
        raise RuntimeError(
            f"{phase}_quorum_lost: {len(connections)} of {plan.spec.swarm_size} drones remain; "
            f"need at least {minimum_size}"
        )
    if len(connections) == len(plan.drones):
        return plan

    launch_by_uri = {drone.uri: drone.launch for drone in plan.drones}
    remaining_launches = {connection.uri: launch_by_uri[connection.uri] for connection in connections}
    reduced_spec = replace(plan.spec, swarm_size=len(remaining_launches))
    logger.info(
        "swarm executor: replanning %d-drone mission after %s failures",
        len(remaining_launches),
        phase,
    )
    return build_swarm_plan(remaining_launches, reduced_spec)


def _minimum_viable_swarm_size(requested_size: int, pattern: str = "") -> int:
    if pattern == "crazy_pinwheel":
        return requested_size
    if requested_size <= 2:
        return MIN_EXECUTION_SWARM_SIZE
    return max(MIN_SWARM_SIZE, requested_size // 2 + 1)


def dry_run_events(plan: SwarmPlan) -> list[str]:
    events: list[str] = []
    for drone in plan.drones:
        events.append(f"{drone.uri}:takeoff")
        events.extend(f"{drone.uri}:formation" for _ in drone.route_to_formation)
        events.extend(f"{drone.uri}:pattern" for _ in drone.pattern_points)
        events.extend(f"{drone.uri}:return" for _ in drone.route_to_return)
        events.append(f"{drone.uri}:land")
    return events
