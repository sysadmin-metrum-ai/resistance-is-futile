"""Redis-backed mission queue service."""

import json
import uuid
from typing import Optional
import redis.asyncio as redis
from src.core.config import Settings, get_settings


class MissionQueue:
    """Async Redis-backed mission queue with drone state management."""

    PENDING_MISSIONS_KEY = "missions:pending"
    DRONE_STATUS_PREFIX = "drone:"
    DRONE_STATUS_SUFFIX = ":status"

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize with settings or use global settings."""
        self.settings = settings or get_settings()
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client with connection pool."""
        if self._client is None:
            self._pool = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.disconnect()
            self._pool = None

    async def enqueue(self, mission: dict) -> str:
        """
        Add a mission to the pending queue.

        Args:
            mission: Mission data dict

        Returns:
            Queue identifier used for Redis bookkeeping
        """
        client = await self._get_client()
        queue_id = mission.get("queue_id") or str(uuid.uuid4())
        payload = dict(mission)
        payload.setdefault("queue_id", queue_id)
        await client.rpush(self.PENDING_MISSIONS_KEY, json.dumps(payload))
        return queue_id

    async def dequeue(self, timeout: int = 0) -> Optional[dict]:
        """
        Get next mission from queue.

        Args:
            timeout: Blocking timeout in seconds (0 = non-blocking)

        Returns:
            Mission dict or None if empty
        """
        client = await self._get_client()
        if timeout > 0:
            result = await client.blpop(self.PENDING_MISSIONS_KEY, timeout=timeout)
            if result:
                return json.loads(result[1])
        else:
            result = await client.lpop(self.PENDING_MISSIONS_KEY)
            if result:
                return json.loads(result)
        return None

    async def acquire_drone(
        self, drone_id: str, mission_id: str, ttl: int = 300
    ) -> bool:
        """
        Atomically acquire a drone for a mission.

        Uses SETNX for atomic lock acquisition.

        Args:
            drone_id: Drone identifier
            mission_id: Mission identifier
            ttl: Lock TTL in seconds

        Returns:
            True if drone was acquired, False if already locked
        """
        client = await self._get_client()
        lock_key = f"{self.DRONE_STATUS_PREFIX}{drone_id}:lock"
        acquired = await client.setnx(lock_key, mission_id)
        if acquired:
            await client.expire(lock_key, ttl)
        return bool(acquired)

    async def release_drone(self, drone_id: str) -> None:
        """Release a drone from its current mission."""
        client = await self._get_client()
        lock_key = f"{self.DRONE_STATUS_PREFIX}{drone_id}:lock"
        await client.delete(lock_key)

    async def get_drone_status(self, drone_id: str) -> dict:
        """
        Get current drone status from Redis.

        Returns:
            Dict with state and battery, or default values
        """
        client = await self._get_client()
        status_key = f"{self.DRONE_STATUS_PREFIX}{drone_id}{self.DRONE_STATUS_SUFFIX}"
        data = await client.hgetall(status_key)
        return {
            "drone_id": drone_id,
            "state": data.get("state", "offline"),
            "battery": int(data.get("battery", 0)),
        }

    async def update_drone_status(
        self, drone_id: str, state: str, battery: Optional[int] = None
    ) -> None:
        """
        Update drone status in Redis.

        Args:
            drone_id: Drone identifier
            state: New state (idle, busy, offline, error)
            battery: Battery level (0-100)
        """
        client = await self._get_client()
        status_key = f"{self.DRONE_STATUS_PREFIX}{drone_id}{self.DRONE_STATUS_SUFFIX}"
        await client.hset(status_key, "state", state)
        if battery is not None:
            await client.hset(status_key, "battery", str(battery))


async def get_mission_queue() -> MissionQueue:
    """Dependency for FastAPI to get mission queue instance."""
    return MissionQueue()
