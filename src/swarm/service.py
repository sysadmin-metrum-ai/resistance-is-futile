"""API-facing deploy service with a single active swarm mission lock."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import replace
from datetime import datetime
from datetime import timezone

import httpx

from src.services.event_broadcaster import get_broadcaster
from src.swarm.models import MissionSpec
from src.swarm.models import MissionState
from src.swarm.executor import PreparedExecution
from src.swarm.session import DeployResult
from src.swarm.session import SwarmSessionRunner

logger = logging.getLogger(__name__)
_PUBLISH_TIMEOUT_S = 1.5
_CALLBACK_TIMEOUT_S = 3.0


class SwarmDeployService:
    """Coordinates deploy requests and prevents overlapping swarm missions."""

    def __init__(self, runner: SwarmSessionRunner | None = None):
        self.runner = runner or SwarmSessionRunner()
        self._lock = asyncio.Lock()
        self._telemetry_lock = threading.Lock()
        self._active_mission_id: str | None = None
        self._active_task: asyncio.Task | None = None
        self._missions: dict[str, DeployResult] = {}
        self._telemetry: dict[str, dict[str, dict]] = {}
        self._phase_lock = threading.Lock()
        self._phases: dict[str, dict] = {}
        self._prepared_executions: dict[str, PreparedExecution] = {}
        self._prepared_specs: dict[str, MissionSpec] = {}
        self._prepared_results: dict[str, DeployResult] = {}

    async def deploy(self, spec: MissionSpec) -> DeployResult:
        if self._active_mission_id is not None:
            raise RuntimeError(f"swarm mission already active: {self._active_mission_id}")

        async with self._lock:
            if self._active_mission_id is not None:
                raise RuntimeError(f"swarm mission already active: {self._active_mission_id}")

            prepared = await self.runner.prepare(spec)
            if prepared.state == MissionState.REFUSED or prepared.plan is None:
                self._missions[prepared.mission_id] = prepared
                await self._publish_and_callback(prepared, spec)
                return prepared

            if spec.dry_run:
                execution = self.runner.executor.execute(prepared.plan, arm=False)
                result = replace(
                    prepared,
                    state=MissionState.DRY_RUN,
                    plan=execution.plan,
                    events=execution.events,
                    message="dry_run",
                )
                self._missions[result.mission_id] = result
                await self._publish_and_callback(result, spec)
                return result

            if not spec.arm:
                result = replace(prepared, state=MissionState.REFUSED, message="arm_required")
                self._missions[result.mission_id] = result
                await self._publish_and_callback(result, spec)
                return result

            self._active_mission_id = prepared.mission_id
            preparing = replace(prepared, state=MissionState.ACCEPTED, message="preparing")
            self._missions[preparing.mission_id] = preparing
            self._set_phase(preparing.mission_id, "preflight", {"source": "deploy"})
            await self._publish(preparing)
            self._active_task = asyncio.create_task(self._run_background(prepared, spec))
            return preparing

    async def prepare_for_launch(self, spec: MissionSpec) -> DeployResult:
        if self._active_mission_id is not None:
            raise RuntimeError(f"swarm mission already active: {self._active_mission_id}")

        async with self._lock:
            if self._active_mission_id is not None:
                raise RuntimeError(f"swarm mission already active: {self._active_mission_id}")

            self.runner.set_retain_health_connections(True)
            try:
                prepared = await self.runner.prepare(spec)
            finally:
                self.runner.set_retain_health_connections(False)
            if prepared.state == MissionState.REFUSED or prepared.plan is None:
                self.runner.close_retained_health_connections()
                self._missions[prepared.mission_id] = prepared
                self._set_phase(
                    prepared.mission_id,
                    "health_failed",
                    {"message": prepared.message, "selection": prepared.selection.to_dict()},
                )
                await self._publish_and_callback(prepared, spec)
                return prepared

            if not spec.arm:
                self.runner.close_retained_health_connections()
                result = replace(prepared, state=MissionState.REFUSED, message="arm_required")
                self._missions[result.mission_id] = result
                self._set_phase(
                    result.mission_id,
                    "health_failed",
                    {"message": result.message, "selection": result.selection.to_dict()},
                )
                await self._publish_and_callback(result, spec)
                return result

            self._active_mission_id = prepared.mission_id
            selected_uris = {health.uri for health in prepared.selection.selected}
            retained_connections = self.runner.pop_retained_health_connections(selected_uris)
            self.runner.close_retained_health_connections()
            preparing = replace(prepared, state=MissionState.ACCEPTED, message="preflight")
            self._missions[preparing.mission_id] = preparing
            self._prepared_specs[preparing.mission_id] = spec
            self._prepared_results[preparing.mission_id] = prepared
            self._set_phase(
                preparing.mission_id,
                "preflight",
                {"source": "health_selection", "selection": prepared.selection.to_dict()},
            )
            await self._publish(preparing)
            self._active_task = asyncio.create_task(self._prepare_background(prepared, spec, retained_connections))
            return preparing

    async def launch_prepared(self, mission_id: str) -> DeployResult:
        prepared_execution = self._prepared_executions.get(mission_id)
        prepared_result = self._prepared_results.get(mission_id)
        spec = self._prepared_specs.get(mission_id)
        if prepared_execution is None or prepared_result is None or spec is None:
            raise RuntimeError("swarm mission is not ready to deploy")

        current_phase = self._phase_snapshot(mission_id).get("phase")
        if current_phase != "ready_to_deploy":
            raise RuntimeError(f"swarm mission is not ready to deploy: {current_phase}")

        running = replace(prepared_result, state=MissionState.RUNNING, message="running")
        self._missions[mission_id] = running
        await self._publish(running)
        self._active_task = asyncio.create_task(self._launch_background(prepared_result, prepared_execution, spec))
        return running

    async def get_status(self, mission_id: str) -> DeployResult | None:
        return self._missions.get(mission_id)

    def result_payload(self, result: DeployResult) -> dict:
        data = result.to_dict()
        data["telemetry"] = self._telemetry_snapshot(result.mission_id)
        data.update(self._phase_snapshot(result.mission_id))
        data.update(self._infra_payload(result))
        return data

    def current_status(self) -> dict:
        """Read-only snapshot of the active mission, if any."""
        mission_id = self._active_mission_id
        if mission_id is None:
            return {"state": "idle", "active_mission_id": None}
        current = self._missions.get(mission_id)
        if current is None:
            return {"state": "unknown", "active_mission_id": mission_id}
        return {
            "state": current.state.value,
            "active_mission_id": mission_id,
            "selected": [health.uri for health in current.selection.selected],
            "message": current.message,
        }

    def battery_telemetry(self, mission_id: str) -> dict[str, dict] | None:
        if mission_id not in self._missions:
            return None
        return self._telemetry_snapshot(mission_id)

    async def abort(self) -> DeployResult | None:
        mission_id = self._active_mission_id
        if mission_id is None:
            return None
        current = self._missions.get(mission_id)
        task = self._active_task
        if task is not None and not task.done():
            # Wait for the cflib worker thread to finish so a new deploy
            # cannot start while drones are still receiving commands.
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
            except (asyncio.TimeoutError, Exception):
                pass
        if current is None:
            self._active_mission_id = None
            self._active_task = None
            return None
        aborted = replace(current, state=MissionState.ABORTED, message="abort_requested")
        self._missions[mission_id] = aborted
        self._active_mission_id = None
        self._active_task = None
        await self._publish(aborted)
        return aborted

    async def _run_background(self, prepared: DeployResult, spec: MissionSpec) -> None:
        try:
            running = replace(prepared, state=MissionState.RUNNING, message="running")
            self._missions[running.mission_id] = running
            await self._publish(running)
            result = await self.runner.execute_prepared(
                prepared,
                spec,
                telemetry_callback=lambda uri, sample: self._record_battery_sample(prepared.mission_id, uri, sample),
                phase_callback=lambda phase, details=None: self._set_phase(prepared.mission_id, phase, details),
            )
        except Exception as exc:
            result = replace(prepared, state=MissionState.FAILED, message=str(exc))
            self._set_phase(prepared.mission_id, "failed", {"message": str(exc)})
        self._missions[result.mission_id] = result
        if self._active_mission_id == result.mission_id:
            self._active_mission_id = None
            self._active_task = None
        await self._publish_and_callback(result, spec)

    async def _prepare_background(
        self,
        prepared: DeployResult,
        spec: MissionSpec,
        retained_connections: dict | None = None,
    ) -> None:
        try:
            execution = await self.runner.prepare_execution(
                prepared,
                phase_callback=lambda phase, details=None: self._set_phase(prepared.mission_id, phase, details),
                retained_connections=retained_connections,
            )
            self._prepared_executions[prepared.mission_id] = execution
            ready = replace(prepared, state=MissionState.ACCEPTED, message="ready_to_deploy")
            self._missions[prepared.mission_id] = ready
            self._set_phase(
                prepared.mission_id,
                "ready_to_deploy",
                {"selected": [drone.uri for drone in execution.plan.drones], "launch_ready": True},
            )
            await self._publish(ready)
        except Exception as exc:
            result = replace(prepared, state=MissionState.FAILED, message=str(exc))
            self._missions[result.mission_id] = result
            self._set_phase(result.mission_id, "failed", {"message": str(exc)})
            if self._active_mission_id == result.mission_id:
                self._active_mission_id = None
                self._active_task = None
            await self._publish_and_callback(result, spec)

    async def _launch_background(
        self,
        prepared: DeployResult,
        execution: PreparedExecution,
        spec: MissionSpec,
    ) -> None:
        try:
            result = await self.runner.launch_prepared(
                prepared,
                execution,
                telemetry_callback=lambda uri, sample: self._record_battery_sample(prepared.mission_id, uri, sample),
                phase_callback=lambda phase, details=None: self._set_phase(prepared.mission_id, phase, details),
            )
        except Exception as exc:
            result = replace(prepared, state=MissionState.FAILED, message=str(exc))
            self._set_phase(prepared.mission_id, "failed", {"message": str(exc)})
        self._missions[result.mission_id] = result
        self._set_phase(result.mission_id, "completed" if result.state == MissionState.COMPLETED else "failed")
        self._prepared_executions.pop(result.mission_id, None)
        self._prepared_specs.pop(result.mission_id, None)
        self._prepared_results.pop(result.mission_id, None)
        if self._active_mission_id == result.mission_id:
            self._active_mission_id = None
            self._active_task = None
        await self._publish_and_callback(result, spec)

    async def _publish_and_callback(self, result: DeployResult, spec: MissionSpec) -> None:
        await self._publish(result)
        await self._post_callback(result, spec)

    async def _publish(self, result: DeployResult) -> None:
        # Redis is best-effort: never let a missing/slow broker stall a deploy.
        async def _do_publish() -> None:
            broadcaster = await get_broadcaster()
            await broadcaster.publish(
                broadcaster.CHANNEL_MISSION_UPDATES,
                {
                    "type": "swarm_deploy",
                    "mission_id": result.mission_id,
                    "state": result.state.value,
                    "selected": [health.uri for health in result.selection.selected],
                },
            )

        try:
            await asyncio.wait_for(_do_publish(), timeout=_PUBLISH_TIMEOUT_S)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.debug("swarm publish skipped: %s", exc)

    async def _post_callback(self, result: DeployResult, spec: MissionSpec) -> None:
        if not spec.callback_url:
            return

        selected = [health.uri for health in result.selection.selected]
        payload = {
            **self._infra_payload(result),
            "mission_id": result.mission_id,
            "state": result.state.value,
            "message": result.message,
            "selected_count": len(selected),
            "selected": selected,
        }
        try:
            async with httpx.AsyncClient(timeout=_CALLBACK_TIMEOUT_S) as client:
                response = await client.post(spec.callback_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.warning("swarm callback skipped: %s", exc)

    def _record_battery_sample(self, mission_id: str, uri: str, sample: dict) -> None:
        with self._telemetry_lock:
            self._telemetry.setdefault(mission_id, {})[uri] = sample

    def _set_phase(self, mission_id: str, phase: str, details: dict | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._phase_lock:
            current = self._phases.get(mission_id, {})
            history = list(current.get("phase_history", []))
            if current.get("phase") != phase:
                history.append({"phase": phase, "started_at": now, "details": details or {}})
                phase_started_at = now
            else:
                phase_started_at = current.get("phase_started_at", now)
            self._phases[mission_id] = {
                "phase": phase,
                "phase_started_at": phase_started_at,
                "phase_updated_at": now,
                "phase_details": details or current.get("phase_details", {}),
                "phase_history": history,
            }
        logger.info("swarm phase: mission=%s phase=%s details=%s", mission_id, phase, details or {})

    def _phase_snapshot(self, mission_id: str) -> dict:
        with self._phase_lock:
            return dict(self._phases.get(mission_id, {}))

    def _telemetry_snapshot(self, mission_id: str) -> dict[str, dict]:
        with self._telemetry_lock:
            return dict(self._telemetry.get(mission_id, {}))

    def _infra_payload(self, result: DeployResult) -> dict:
        """Bridge-facing status flags for DTW's polling demo workflow.

        `infra_continue` means DTW can advance its mock scenario timeline. It
        is intentionally separate from `swarm_success`: unsafe/refused physical
        flight should not block the infrastructure demo.
        """

        selected_count = len(result.selection.selected)
        terminal = result.state in {
            MissionState.COMPLETED,
            MissionState.DRY_RUN,
            MissionState.REFUSED,
            MissionState.FAILED,
            MissionState.ABORTED,
        }
        return {
            "success": True,
            "infra_status": "in_flight" if result.state == MissionState.RUNNING else "success" if terminal else "pending",
            "infra_continue": terminal,
            "swarm_success": result.state in {MissionState.COMPLETED, MissionState.DRY_RUN},
            "swarm_safe_to_fly": result.plan is not None and selected_count >= result.selection.required_size,
        }


_deploy_service: SwarmDeployService | None = None


def get_swarm_deploy_service() -> SwarmDeployService:
    global _deploy_service
    if _deploy_service is None:
        _deploy_service = SwarmDeployService()
    return _deploy_service
