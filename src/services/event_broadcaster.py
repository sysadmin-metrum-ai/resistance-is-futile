"""Event broadcaster service for real-time SSE updates.

Provides pub/sub functionality using Redis to broadcast drone and mission
events to connected clients via Server-Sent Events (SSE).
"""

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

import redis.asyncio as redis

from src.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """
    Pub/sub service for broadcasting real-time events via SSE.

    Uses Redis pub/sub channels to distribute events to multiple
    subscribers. Each event type has its own channel.
    """

    # Event channels
    CHANNEL_DRONE_UPDATES = "events:drone_updates"
    CHANNEL_MISSION_UPDATES = "events:mission_updates"
    CHANNEL_LLM_TOKENS = "events:llm_tokens"

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize with settings."""
        self.settings = settings or get_settings()
        self._pubsub: Optional[redis.client.PubSub] = None
        self._redis: Optional[redis.Redis] = None
        self._subscriptions: dict[str, asyncio.Queue] = {}

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def _get_pubsub(self) -> redis.client.PubSub:
        """Get or create pub/sub connection."""
        if self._pubsub is None:
            self._pubsub = (await self._get_redis()).pubsub()
        return self._pubsub

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """
        Subscribe to a channel and yield messages.

        Args:
            channel: Redis channel to subscribe to

        Yields:
            Parsed event dictionaries
        """
        pubsub = await self._get_pubsub()
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in {channel}: {message['data']}")
        finally:
            await pubsub.unsubscribe(channel)

    async def publish(self, channel: str, message: dict) -> None:
        """
        Publish a message to a channel.

        Args:
            channel: Redis channel to publish to
            message: Dictionary to serialize and publish
        """
        r = await self._get_redis()
        await r.publish(channel, json.dumps(message))

    async def unsubscribe(self, channel: str) -> None:
        """
        Unsubscribe from a channel.

        Args:
            channel: Redis channel to unsubscribe from
        """
        if self._pubsub:
            await self._pubsub.unsubscribe(channel)

    async def close(self) -> None:
        """Close Redis connections."""
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global singleton instance
_broadcaster: Optional[EventBroadcaster] = None


async def get_broadcaster() -> EventBroadcaster:
    """Get or create the global EventBroadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster
