import json

import pytest

from src.services.mission_cancellation import _remove_from_queue, get_mission_status
from src.services.mission_queue import MissionQueue


class _FakeRedisClient:
    def __init__(self, items):
        self._items = list(items)
        self.removed = []

    async def lrange(self, key, start, end):
        return list(self._items)

    async def lrem(self, key, count, item):
        self.removed.append((key, count, item))


class _FakePostgrest:
    def __init__(self, settings=None):
        self.settings = settings
        self.path = None

    async def get(self, path):
        self.path = path
        return [{"mission_id": "mission-123", "status": "pending"}]


@pytest.mark.asyncio
async def test_remove_from_queue_matches_external_mission_id():
    payload = json.dumps({"mission_id": "mission-123", "queue_id": "queue-1"})
    queue = MissionQueue()
    queue._client = _FakeRedisClient([payload])

    await _remove_from_queue("mission-123", queue)

    assert queue._client.removed == [(queue.PENDING_MISSIONS_KEY, 1, payload)]


@pytest.mark.asyncio
async def test_get_mission_status_uses_external_mission_id(monkeypatch):
    from src.services import mission_cancellation as mission_cancellation_module

    fake = _FakePostgrest()
    monkeypatch.setattr(
        mission_cancellation_module,
        "PostgRESTClient",
        lambda settings=None: fake,
    )

    result = await get_mission_status("mission-123")

    assert result == {"mission_id": "mission-123", "status": "pending"}
    assert fake.path == "/missions?mission_id=eq.mission-123&select=*"
