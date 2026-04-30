"""API-facing deploy service with a single active swarm mission lock."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from src.services.event_broadcaster import get_broadcaster
from src.swarm.models import MissionSpec
from src.swarm.models import MissionState
from src.swarm.session import DeployResult
from src.swarm.session import SwarmSessionRunner

logger = logging.getLogger(__name__)
_PUBLISH_TIMEOUT_S = 1.5


class SwarmDeployService:
    """Coordinates deploy requests and prevents overlapping swarm missions."""

    def __init__(self, runner: SwarmSessionRunner | None = None):
        self.runner = runner or SwarmSessionRunner()
        self._lock = asyncio.Lock()
        self._active_mission_id: str | None = None
        self._active_task: asyncio.Task | None = None
        self._missions: dict[str, DeployResult] = {}

    async def deploy(self, spec: MissionSpec) -> DeployResult:
        if self._active_mission_id is not None:
            raise RuntimeError(f"swarm mission already active: {self._active_mission_id}")

        async with self._lock:
            if self._active_mission_id is not None:
                raise RuntimeError(f"swarm mission already active: {self._active_mission_id}")

            prepared = await self.runner.prepare(spec)
            if prepared.state == MissionState.REFUSED or prepared.plan is None:
                self._missions[prepared.mission_id] = prepared
                await self._publish(prepared)
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
                await self._publish(result)
                return result

            if not spec.arm:
                result = replace(prepared, state=MissionState.REFUSED, message="arm_required")
                self._missions[result.mission_id] = result
                await self._publish(result)
                return result

            self._active_mission_id = prepared.mission_id
            running = replace(prepared, state=MissionState.RUNNING, message="running")
            self._missions[running.mission_id] = running
            await self._publish(running)
            self._active_task = asyncio.create_task(self._run_background(prepared, spec))
            return running

    async def get_status(self, mission_id: str) -> DeployResult | None:
        return self._missions.get(mission_id)

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
            result = await self.runner.execute_prepared(prepared, spec)
        except Exception as exc:
            result = replace(prepared, state=MissionState.FAILED, message=str(exc))
        self._missions[result.mission_id] = result
        if self._active_mission_id == result.mission_id:
            self._active_mission_id = None
            self._active_task = None
        await self._publish(result)

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


_deploy_service: SwarmDeployService | None = None


def get_swarm_deploy_service() -> SwarmDeployService:
    global _deploy_service
    if _deploy_service is None:
        _deploy_service = SwarmDeployService()
    return _deploy_service
