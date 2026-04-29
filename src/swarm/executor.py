"""Synchronized high-level commander execution for a planned swarm mission."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from src.swarm.health import cache_dir_for_uri
from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import SwarmPlan

logger = logging.getLogger(__name__)

# Buffer between schedule build time and first fire, to absorb thread
# startup jitter so every drone has time to reach its sleep_until call.
SCHEDULE_PREP_S = 1.0


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

    def close(self) -> None:
        self._scf.close_link()

    def set_led_blue(self) -> None:
        """Light the bottom LED ring deck full blue (WRGB8888 = 0x000000FF)."""
        try:
            self._scf.cf.param.set_value("colorLedBot.wrgb8888", "255")
        except Exception as exc:
            logger.warning("swarm executor: %s LED set failed: %s", self.uri, exc)

    def set_led_off(self) -> None:
        """Turn the bottom LED ring deck fully off."""
        try:
            self._scf.cf.param.set_value("colorLedBot.wrgb8888", "0")
        except Exception as exc:
            logger.warning("swarm executor: %s LED off failed: %s", self.uri, exc)

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


class CflibDroneConnector:
    def connect(self, uri: str, spec: MissionSpec) -> DroneConnection:
        return CflibDroneConnection(uri, spec)


class SwarmExecutor:
    """Execute a swarm plan with one worker thread per drone."""

    def __init__(self, connector: DroneConnector | None = None):
        self.connector = connector or CflibDroneConnector()

    def execute(self, plan: SwarmPlan, *, arm: bool) -> list[str]:
        if not arm or plan.spec.dry_run:
            return dry_run_events(plan)

        connections: list[DroneConnection] = []
        try:
            logger.info("swarm executor: opening %d cflib links", len(plan.drones))
            for drone in plan.drones:
                t0 = time.monotonic()
                logger.info("swarm executor: connecting %s", drone.uri)
                connections.append(self.connector.connect(drone.uri, plan.spec))
                logger.info("swarm executor: connected %s in %.2fs", drone.uri, time.monotonic() - t0)

            self._configure_in_parallel(connections)
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
            return events
        finally:
            for connection in connections:
                try:
                    connection.close()
                except Exception:
                    pass

    def _configure_in_parallel(self, connections: list[DroneConnection]) -> None:
        """Run per-drone configure() concurrently; tolerate fakes without one."""
        configurable = [conn for conn in connections if hasattr(conn, "configure")]
        if not configurable:
            return

        logger.info("swarm executor: configuring %d drones in parallel", len(configurable))
        errors: list[BaseException] = []
        lock = threading.Lock()

        def runner(conn: DroneConnection) -> None:
            try:
                conn.configure()  # type: ignore[attr-defined]
            except BaseException as exc:
                logger.exception("swarm executor: %s configure failed: %s", conn.uri, exc)
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=runner, args=(conn,), name=f"cfg-{conn.uri}") for conn in configurable]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors:
            raise RuntimeError("one or more drones failed to configure") from errors[0]

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

        for fire_at, point in zip(schedule.formation_steps, formation_points):
            _sleep_until(fire_at)
            commander.go_to(*point, 0.0, spec.move_s, relative=False)
            events.append(f"{uri}:formation")

        _sleep_until(schedule.led_blue_at)
        if hasattr(connection, "set_led_blue"):
            connection.set_led_blue()  # type: ignore[attr-defined]
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
        if hasattr(connection, "set_led_off"):
            connection.set_led_off()  # type: ignore[attr-defined]
            events.append(f"{uri}:led_off")
            logger.info("swarm executor: %s LED off", uri)
        commander.stop()
        return events


def _pad_route(points: tuple, length: int) -> tuple:
    """Repeat the last waypoint so every drone's timeline has the same length."""
    if not points:
        return tuple()
    if len(points) >= length:
        return points
    return points + (points[-1],) * (length - len(points))


def dry_run_events(plan: SwarmPlan) -> list[str]:
    events: list[str] = []
    for drone in plan.drones:
        events.append(f"{drone.uri}:takeoff")
        events.extend(f"{drone.uri}:formation" for _ in drone.route_to_formation)
        events.extend(f"{drone.uri}:pattern" for _ in drone.pattern_points)
        events.extend(f"{drone.uri}:return" for _ in drone.route_to_return)
        events.append(f"{drone.uri}:land")
    return events
