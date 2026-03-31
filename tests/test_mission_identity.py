import json

import pytest

from src.services.mission_queue import MissionQueue
from src.services.mission_worker import MissionWorker, _mission_patch_path


class _FakeRedisClient:
    def __init__(self):
        self.items = []

    async def rpush(self, key, value):
        self.items.append((key, value))


class _FakePostgrest:
    patched = []

    def __init__(self, settings=None):
        self.settings = settings

    async def patch(self, path, payload):
        self.__class__.patched.append((path, payload))


@pytest.mark.asyncio
async def test_enqueue_preserves_external_mission_id_and_adds_queue_id():
    queue = MissionQueue()
    fake_client = _FakeRedisClient()
    queue._client = fake_client

    queue_id = await queue.enqueue({"mission_id": "mission-123", "waypoints": []})

    assert queue_id
    assert len(fake_client.items) == 1
    _, raw_payload = fake_client.items[0]
    payload = json.loads(raw_payload)
    assert payload["mission_id"] == "mission-123"
    assert payload["queue_id"] == queue_id


@pytest.mark.asyncio
async def test_update_mission_status_uses_external_mission_id(monkeypatch):
    from src.services import mission_worker as mission_worker_module

    _FakePostgrest.patched = []
    monkeypatch.setattr(mission_worker_module, "PostgRESTClient", _FakePostgrest)

    worker = MissionWorker()
    worker._emit_mission_event = _async_noop  # type: ignore[method-assign]

    await worker._update_mission_status("mission-123", MissionWorker.STATUS_RUNNING, "7")

    assert _FakePostgrest.patched == [
        (
            _mission_patch_path("mission-123"),
            {"status": "running", "drone_id": "7"},
        )
    ]


async def _async_noop(*args, **kwargs):
    return None
