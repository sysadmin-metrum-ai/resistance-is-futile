"""Flight controller service for Crazyflie drone control."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from typing import Any, Optional

from src.core.config import Settings, get_settings
from src.services.mission_models import Waypoint3D


@dataclass
class HealthStatus:
    """Drone health status from pre-flight checks."""

    battery: int
    connection_quality: int
    is_healthy: bool
    message: str


@dataclass
class MissionResult:
    """Result of a mission execution."""

    success: bool
    message: str
    waypoints_completed: int
    duration_seconds: int


def _coerce_waypoint(waypoint: Any) -> Waypoint3D:
    """Normalize dicts or tuple-like values into a typed waypoint."""

    if isinstance(waypoint, Waypoint3D):
        return waypoint
    if isinstance(waypoint, dict):
        return Waypoint3D(**waypoint)
    if isinstance(waypoint, (list, tuple)) and len(waypoint) >= 3:
        return Waypoint3D(x=waypoint[0], y=waypoint[1], z=waypoint[2])
    raise TypeError(f"unsupported waypoint type: {type(waypoint)!r}")


class FlightController:
    """Controls Crazyflie drones via cflib."""

    MIN_BATTERY_THRESHOLD = 20
    MIN_CONNECTION_QUALITY = 70
    DEFAULT_TRAVEL_SPEED_MPS = 0.5
    DEFAULT_VERTICAL_SPEED_MPS = 0.35

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._swarm = None
        self._drones: dict[str, dict[str, Any]] = {}

    async def connect_swarm(self, uris: list[str]) -> None:
        """Connect to multiple drones as a swarm."""

        try:
            from cflib.crtp import CachedCfFactory
            from cflib.swarm import Swarm
            import cflib.crtp

            cflib.crtp.init_drivers()
            self._swarm = Swarm(uris, factory=CachedCfFactory())
            await asyncio.to_thread(self._swarm.open_links)
            self._drones = {uri: {"connected": True} for uri in uris}
        except ImportError as exc:
            raise RuntimeError("cflib not installed - cannot connect to drones") from exc

    async def disconnect(self) -> None:
        """Disconnect all drones in the swarm."""

        if self._swarm:
            await asyncio.to_thread(self._swarm.close_links)
            self._swarm = None
        self._drones = {}

    async def kill_switch(self) -> None:
        """Emergency stop all currently connected swarm members."""

        if not self._swarm:
            return

        def _emergency_land(scf):
            cf = scf.cf
            cf.commander.send_setpoint(0, 0, 0, 0)
            try:
                cf.high_level_commander.stop()
            except Exception:
                pass

        await asyncio.to_thread(self._swarm.parallel_safe, _emergency_land)

    async def health_check(self, uri: str) -> HealthStatus:
        """Run a short live radio probe and approximate battery from `pm.vbat`."""

        try:
            return await asyncio.to_thread(self._probe_health_sync, uri)
        except Exception as exc:
            return HealthStatus(
                battery=0,
                connection_quality=0,
                is_healthy=False,
                message=f"Health check error: {exc}",
            )

    async def execute_mission(
        self,
        drone_uri: str,
        waypoints: list,
        duration_seconds: int,
    ) -> MissionResult:
        """Execute a waypoint mission on a single drone using high-level commands."""

        try:
            typed_waypoints = [_coerce_waypoint(waypoint) for waypoint in waypoints]
            if not typed_waypoints:
                return MissionResult(
                    success=False,
                    message="Mission has no waypoints",
                    waypoints_completed=0,
                    duration_seconds=duration_seconds,
                )

            return await asyncio.to_thread(
                self._execute_mission_sync,
                drone_uri,
                typed_waypoints,
                duration_seconds,
            )
        except Exception as exc:
            return MissionResult(
                success=False,
                message=f"Mission error: {exc}",
                waypoints_completed=0,
                duration_seconds=duration_seconds,
            )

    async def abort_mission(self, drone_uri: str) -> None:
        """Best-effort land-and-stop for a single drone."""

        await asyncio.to_thread(self._abort_mission_sync, drone_uri)

    def _probe_health_sync(self, uri: str) -> HealthStatus:
        """Probe the link and approximate battery percentage from logged voltage."""

        try:
            import cflib.crtp
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.log import LogConfig
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
            from cflib.crazyflie.syncLogger import SyncLogger
        except ImportError as exc:
            raise RuntimeError("cflib not installed - cannot probe drone health") from exc

        cflib.crtp.init_drivers()
        cf = Crazyflie(rw_cache="./cache")
        with SyncCrazyflie(uri, cf=cf) as scf:
            log_config = LogConfig(name="health_probe", period_in_ms=100)
            log_config.add_variable("pm.vbat", "float")
            with SyncLogger(scf, log_config) as logger:
                entry = next(iter(logger))
                vbat = float(entry[1]["pm.vbat"])

        battery = self._voltage_to_percent(vbat)
        connection_quality = 100
        is_healthy = (
            battery >= self.MIN_BATTERY_THRESHOLD
            and connection_quality >= self.MIN_CONNECTION_QUALITY
        )
        message = (
            f"live link probe passed; pm.vbat={vbat:.2f}V "
            f"(approx battery {battery}%)"
        )
        if not is_healthy:
            message = (
                f"live link probe failed thresholds; pm.vbat={vbat:.2f}V "
                f"(approx battery {battery}%)"
            )

        return HealthStatus(
            battery=battery,
            connection_quality=connection_quality,
            is_healthy=is_healthy,
            message=message,
        )

    def _execute_mission_sync(
        self,
        drone_uri: str,
        waypoints: list[Waypoint3D],
        duration_seconds: int,
    ) -> MissionResult:
        """Run a mission using the Crazyflie high-level commander."""

        try:
            import cflib.crtp
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        except ImportError as exc:
            raise RuntimeError("cflib not installed - cannot execute missions") from exc

        cflib.crtp.init_drivers()
        cf = Crazyflie(rw_cache="./cache")
        with SyncCrazyflie(drone_uri, cf=cf) as scf:
            self._prepare_estimator(scf.cf)
            scf.cf.param.set_value("commander.enHighLevel", "1")
            hlc = scf.cf.high_level_commander

            current_x, current_y, current_z = 0.0, 0.0, 0.0
            completed = 0

            for index, waypoint in enumerate(waypoints):
                target_z = max(0.0, waypoint.z)
                if index == 0 and target_z > 0.0:
                    takeoff_duration = max(2.0, target_z / self.DEFAULT_VERTICAL_SPEED_MPS)
                    hlc.takeoff(target_z, takeoff_duration)
                    time.sleep(takeoff_duration + 0.5)
                    current_z = target_z

                distance = math.dist(
                    (current_x, current_y, current_z),
                    (waypoint.x, waypoint.y, target_z),
                )
                travel_time = max(1.0, distance / self.DEFAULT_TRAVEL_SPEED_MPS)
                hlc.go_to(
                    waypoint.x,
                    waypoint.y,
                    target_z,
                    math.radians(waypoint.yaw_degrees),
                    travel_time,
                    relative=False,
                )
                time.sleep(travel_time + 0.25)
                if waypoint.hold_seconds > 0:
                    time.sleep(waypoint.hold_seconds)
                current_x, current_y, current_z = waypoint.x, waypoint.y, target_z
                completed += 1

            land_duration = max(2.0, current_z / self.DEFAULT_VERTICAL_SPEED_MPS) if current_z > 0 else 2.0
            hlc.land(0.0, land_duration)
            time.sleep(land_duration + 0.5)
            hlc.stop()

        return MissionResult(
            success=True,
            message="Mission completed via high-level commander",
            waypoints_completed=completed,
            duration_seconds=duration_seconds,
        )

    def _abort_mission_sync(self, drone_uri: str) -> None:
        """Best-effort abort using high-level commander stop semantics."""

        try:
            import cflib.crtp
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        except ImportError as exc:
            raise RuntimeError("cflib not installed - cannot abort mission") from exc

        cflib.crtp.init_drivers()
        cf = Crazyflie(rw_cache="./cache")
        with SyncCrazyflie(drone_uri, cf=cf) as scf:
            scf.cf.param.set_value("commander.enHighLevel", "1")
            hlc = scf.cf.high_level_commander
            hlc.land(0.0, 2.0)
            time.sleep(2.5)
            hlc.stop()

    def _prepare_estimator(self, cf) -> None:
        """Reset and settle the estimator before autonomous motion."""

        cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(0.1)
        cf.param.set_value("kalman.resetEstimation", "0")
        time.sleep(2.0)

    @staticmethod
    def _voltage_to_percent(voltage: float) -> int:
        """Approximate a 1S pack percentage from voltage for operator gating."""

        normalized = (voltage - 3.2) / (4.2 - 3.2)
        return max(0, min(100, round(normalized * 100)))
