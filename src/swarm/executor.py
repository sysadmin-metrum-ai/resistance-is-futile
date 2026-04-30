"""Synchronized high-level commander execution for a planned swarm mission."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from dataclasses import replace
from typing import Protocol

from src.swarm.health import cache_dir_for_uri
from src.swarm.models import HealthThresholds
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import SwarmPlan
from src.swarm.planner import build_swarm_plan

logger = logging.getLogger(__name__)

# Buffer between schedule build time and first fire, to absorb thread
# startup jitter so every drone has time to reach its sleep_until call.
SCHEDULE_PREP_S = 1.0
LED_BLINK_INTERVAL_S = 0.75
IN_FLIGHT_BATTERY_LOG_MS = 1000
IN_FLIGHT_LOW_VOLTAGE_SAMPLES = 2


@dataclass(frozen=True)
class ExecutionResult:
    events: tuple[str, ...]
    plan: SwarmPlan


@dataclass(frozen=True)
class SwarmSchedule:
    """Absolute monotonic timestamps every drone fires at.

    All worker threads sleep until the same instant before dispatching
    each high-level commander call, so radio queue jitter is the only
    source of inter-drone offset (~10-30ms instead of ~100-300ms).
    """

    takeoff_at: float
    formation_steps: tuple[float, ...]
    led_blue_at: float
    pattern_steps: tuple[float, ...]
    return_steps: tuple[float, ...]
    land_at: float
    cleanup_at: float


def _build_schedule(
    spec: MissionSpec,
    n_formation: int,
    n_pattern: int,
    n_return: int,
) -> SwarmSchedule:
    t = time.monotonic() + SCHEDULE_PREP_S
    takeoff_at = t
    t += spec.takeoff_s + spec.hold_s

    formation_steps: list[float] = []
    for _ in range(n_formation):
        formation_steps.append(t)
        t += spec.move_s + spec.hold_s

    # Brief LED-blue ack right after the formation is locked, before the
    # pattern phase begins. Adds 0.3s of dwell so the visual signal is
    # noticeable.
    led_blue_at = t
    t += 0.3

    pattern_steps: list[float] = []
    for _ in range(n_pattern):
        pattern_steps.append(t)
        t += spec.pattern_s + spec.hold_s

    return_steps: list[float] = []
    for _ in range(n_return):
        return_steps.append(t)
        t += spec.move_s + spec.hold_s

    land_at = t
    cleanup_at = t + spec.land_s + 0.3
    return SwarmSchedule(
        takeoff_at=takeoff_at,
        formation_steps=tuple(formation_steps),
        led_blue_at=led_blue_at,
        pattern_steps=tuple(pattern_steps),
        return_steps=tuple(return_steps),
        land_at=land_at,
        cleanup_at=cleanup_at,
    )


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

    def __init__(self, uri: str, spec: MissionSpec):
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

        self.uri = uri
        self._spec = spec
        self._scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri)))
        self._scf.open_link()
        self.commander = self._scf.cf.high_level_commander
        self._led_mode = self._detect_led_mode()
        self._battery_watch: BatteryWatch | None = None
        if self._led_mode == "colorLedBot" and self._has_param("colorLedBot", "brightCorr"):
            self._scf.cf.param.set_value("colorLedBot.brightCorr", "1")

    def close(self) -> None:
        self._scf.close_link()

    def set_led_blue(self) -> None:
        """Light the bottom LED ring deck full blue (WRGB8888 = 0x000000FF)."""
        try:
            if self._led_mode == "colorLedBot":
                self._scf.cf.param.set_value("colorLedBot.wrgb8888", "255")
            elif self._led_mode == "ring":
                self._scf.cf.param.set_value("ring.effect", "7")
                self._scf.cf.param.set_value("ring.solidRed", "0")
                self._scf.cf.param.set_value("ring.solidGreen", "0")
                self._scf.cf.param.set_value("ring.solidBlue", "100")
        except Exception as exc:
            logger.warning("swarm executor: %s LED set failed: %s", self.uri, exc)

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

    def start_battery_watch(self) -> None:
        from cflib.crazyflie.log import LogConfig

        self._battery_watch = BatteryWatch(self.uri, self.commander, self._scf.cf, LogConfig)
        self._battery_watch.start()

    def stop_battery_watch(self) -> bool:
        if self._battery_watch is None:
            return False
        triggered = self._battery_watch.triggered
        self._battery_watch.stop()
        self._battery_watch = None
        return triggered

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
            radius_xy = max(0.05, spec.min_separation_m / 2.0)
            cf.param.set_value("colAv.ellipsoidX", f"{radius_xy:.3f}")
            cf.param.set_value("colAv.ellipsoidY", f"{radius_xy:.3f}")
            cf.param.set_value("colAv.ellipsoidZ", f"{max(radius_xy * 3.0, 0.15):.3f}")
        time.sleep(0.5)

        logger.info("swarm executor: %s waiting for kalman convergence", self.uri)
        t0 = time.monotonic()
        self._reset_and_wait_estimator(cf, timeout_s=8.0)
        self._assert_power_ready(cf)
        logger.info(
            "swarm executor: %s kalman converged in %.2fs, arming",
            self.uri,
            time.monotonic() - t0,
        )
        self._send_arming_request(cf)
        logger.info("swarm executor: %s armed", self.uri)

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
    def connect(self, uri: str, spec: MissionSpec) -> DroneConnection:
        return CflibDroneConnection(uri, spec)


class BatteryWatch:
    """Low-rate in-flight battery guard that asks only the weak drone to land."""

    def __init__(self, uri: str, commander: Commander, cf, log_cls):
        self.uri = uri
        self.commander = commander
        self.cf = cf
        self.thresholds = HealthThresholds()
        self.low_samples = 0
        self.triggered = False
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
        low_voltage = voltage is None or float(voltage) < self.thresholds.min_voltage
        low_percent = percent is None or int(percent) < self.thresholds.min_battery_percent
        if low_voltage or low_percent:
            self.low_samples += 1
        else:
            self.low_samples = 0
        if self.low_samples < IN_FLIGHT_LOW_VOLTAGE_SAMPLES:
            return

        self.triggered = True
        logger.warning(
            "swarm executor: %s battery watchdog landing: voltage=%s percent=%s",
            self.uri,
            voltage,
            percent,
        )
        try:
            self.commander.land(0.0, 2.0, yaw=None)
        except Exception as exc:
            logger.warning("swarm executor: %s battery watchdog land failed: %s", self.uri, exc)


class SwarmExecutor:
    """Execute a swarm plan with one worker thread per drone."""

    def __init__(self, connector: DroneConnector | None = None):
        self.connector = connector or CflibDroneConnector()

    def execute(self, plan: SwarmPlan, *, arm: bool) -> ExecutionResult:
        if not arm or plan.spec.dry_run:
            return ExecutionResult(tuple(dry_run_events(plan)), plan)

        connections: list[DroneConnection] = []
        try:
            logger.info("swarm executor: opening %d cflib links", len(plan.drones))
            for drone in plan.drones:
                t0 = time.monotonic()
                logger.info("swarm executor: connecting %s", drone.uri)
                try:
                    connections.append(self.connector.connect(drone.uri, plan.spec))
                    logger.info("swarm executor: connected %s in %.2fs", drone.uri, time.monotonic() - t0)
                except BaseException as exc:
                    logger.exception("swarm executor: connect failed for %s: %s", drone.uri, exc)

            plan = _replan_for_remaining(plan, connections, "connect")
            connections = self._configure_in_parallel(connections)
            plan = _replan_for_remaining(plan, connections, "configure")
            logger.info("swarm executor: all drones configured + armed, building schedule")

            n_formation = max(len(d.route_to_formation) for d in plan.drones)
            n_pattern = max(len(d.pattern_points) for d in plan.drones)
            n_return = max(len(d.route_to_return) for d in plan.drones)
            schedule = _build_schedule(plan.spec, n_formation, n_pattern, n_return)
            logger.info(
                "swarm executor: schedule takeoff_at=+%.2fs land_at=+%.2fs",
                schedule.takeoff_at - time.monotonic(),
                schedule.land_at - time.monotonic(),
            )

            events: list[str] = []
            errors: list[BaseException] = []
            lock = threading.Lock()

            def worker(connection: DroneConnection, drone_plan: DronePlan) -> None:
                try:
                    logger.info("swarm executor: %s worker starting", connection.uri)
                    drone_events = self._execute_one(connection, drone_plan, plan, schedule)
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
            return ExecutionResult(tuple(events), plan)
        finally:
            for connection in connections:
                try:
                    connection.close()
                except Exception:
                    pass

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
            try:
                conn.close()
            except Exception:
                pass
        return [conn for conn in connections if conn in configured or conn not in configurable]

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

    def _execute_one(
        self,
        connection: DroneConnection,
        drone_plan: DronePlan,
        swarm_plan: SwarmPlan,
        schedule: SwarmSchedule,
    ) -> list[str]:
        spec = swarm_plan.spec
        uri = drone_plan.uri
        commander = connection.commander
        events: list[str] = []

        # Pad shorter routes by holding at the last waypoint so every drone
        # fires the same number of go_to commands at the same instants.
        formation_points = _pad_route(drone_plan.route_to_formation, len(schedule.formation_steps))
        return_points = _pad_route(drone_plan.route_to_return, len(schedule.return_steps))
        pattern_points = _pad_route(drone_plan.pattern_points, len(schedule.pattern_steps))

        _sleep_until(schedule.takeoff_at)
        logger.info("swarm executor: %s takeoff to %.2fm", uri, spec.hover_z)
        commander.takeoff(spec.hover_z, spec.takeoff_s, yaw=None)
        events.append(f"{uri}:takeoff")
        if hasattr(connection, "start_battery_watch"):
            connection.start_battery_watch()  # type: ignore[attr-defined]
            events.append(f"{uri}:battery_watch_start")
        blink = _start_led_blue_blink(connection, uri)
        if blink is not None:
            events.append(f"{uri}:led_blink_start")

        for fire_at, point in zip(schedule.formation_steps, formation_points):
            _sleep_until(fire_at)
            commander.go_to(*point, 0.0, spec.move_s, relative=False)
            events.append(f"{uri}:formation")

        _sleep_until(schedule.led_blue_at)
        if hasattr(connection, "set_led_blue"):
            connection.set_led_blue()  # type: ignore[attr-defined]
            if blink is None:
                events.append(f"{uri}:led_blue")
            logger.info("swarm executor: %s LED blue", uri)

        for fire_at, point in zip(schedule.pattern_steps, pattern_points):
            _sleep_until(fire_at)
            commander.go_to(*point, 0.0, spec.pattern_s, relative=False)
            events.append(f"{uri}:pattern")

        for fire_at, point in zip(schedule.return_steps, return_points):
            _sleep_until(fire_at)
            commander.go_to(*point, 0.0, spec.move_s, relative=False)
            events.append(f"{uri}:return")

        _sleep_until(schedule.land_at)
        commander.land(0.0, spec.land_s, yaw=None)
        events.append(f"{uri}:land")
        _sleep_until(schedule.cleanup_at)
        if blink is not None:
            stop_blink, blink_thread = blink
            stop_blink.set()
            blink_thread.join(timeout=1.0)
            events.append(f"{uri}:led_blink_stop")
        if hasattr(connection, "set_led_off"):
            connection.set_led_off()  # type: ignore[attr-defined]
            events.append(f"{uri}:led_off")
            logger.info("swarm executor: %s LED off", uri)
        if hasattr(connection, "stop_battery_watch"):
            if connection.stop_battery_watch():  # type: ignore[attr-defined]
                events.append(f"{uri}:battery_watch_landed")
                raise RuntimeError(f"{uri}: battery watchdog triggered landing")
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


def _start_led_blue_blink(connection: DroneConnection, uri: str) -> tuple[threading.Event, threading.Thread] | None:
    if hasattr(connection, "can_blink_led") and not connection.can_blink_led():  # type: ignore[attr-defined]
        return None
    if not hasattr(connection, "set_led_blue") or not hasattr(connection, "set_led_off"):
        return None

    stop = threading.Event()

    def blink() -> None:
        blue = True
        while not stop.is_set():
            if blue:
                connection.set_led_blue()  # type: ignore[attr-defined]
            else:
                connection.set_led_off()  # type: ignore[attr-defined]
            blue = not blue
            stop.wait(LED_BLINK_INTERVAL_S)

    thread = threading.Thread(target=blink, name=f"led-blink-{uri}", daemon=True)
    thread.start()
    logger.info("swarm executor: %s LED blue blink started", uri)
    return stop, thread


def _replan_for_remaining(plan: SwarmPlan, connections: list[DroneConnection], phase: str) -> SwarmPlan:
    minimum_size = _minimum_viable_swarm_size(plan.spec.swarm_size)
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


def _minimum_viable_swarm_size(requested_size: int) -> int:
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
