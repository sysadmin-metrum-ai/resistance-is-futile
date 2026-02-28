"""Event streams API endpoints for Server-Sent Events (SSE).

Provides real-time event streams for drone updates, mission updates,
and LLM token streaming.
"""

import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sse_starlette import EventSourceResponse

from src.services.event_broadcaster import EventBroadcaster, get_broadcaster

router = APIRouter(tags=["events"])


async def event_stream(
    channel: str,
    broadcaster: EventBroadcaster,
) -> AsyncIterator[dict]:
    """
    Generator that streams events from a channel.

    Args:
        channel: Redis channel to subscribe to
        broadcaster: EventBroadcaster instance

    Yields:
        SSE-formatted event dictionaries
    """
    try:
        async for event in broadcaster.subscribe(channel):
            yield {"event": "message", "data": event}
    except asyncio.CancelledError:
        # Client disconnected
        pass
    except Exception as e:
        yield {"event": "error", "data": {"message": str(e)}}


@router.get("/events")
async def events_stream(
    stream: str = Query(
        default="all",
        description="Event stream type: all, drones, missions",
    ),
) -> StreamingResponse:
    """
    SSE endpoint for real-time drone and mission updates.

    Streams events for:
    - Drone registration, state changes, battery updates, position updates
    - Mission created, started, completed, failed, cancelled

    Query Parameters:
        stream: Filter stream type - 'all', 'drones', or 'missions'

    Returns:
        Server-Sent Events response
    """
    broadcaster = await get_broadcaster()

    # Determine channels to subscribe to
    if stream == "drones":
        channels = [EventBroadcaster.CHANNEL_DRONE_UPDATES]
    elif stream == "missions":
        channels = [EventBroadcaster.CHANNEL_MISSION_UPDATES]
    else:  # all
        channels = [
            EventBroadcaster.CHANNEL_DRONE_UPDATES,
            EventBroadcaster.CHANNEL_MISSION_UPDATES,
        ]

    async def multi_channel_stream():
        """Stream events from multiple channels."""
        tasks = []
        queues = []

        for channel in channels:
            queue = asyncio.Queue()
            queues.append(queue)

            async def channel_reader(ch: str, q: asyncio.Queue):
                try:
                    async for event in broadcaster.subscribe(ch):
                        await q.put(event)
                except asyncio.CancelledError:
                    pass

            task = asyncio.create_task(channel_reader(channel, queue))
            tasks.append(task)

        try:
            while True:
                # Wait for any queue to have data
                done, _ = await asyncio.wait(
                    [asyncio.create_task(q.get()) for q in queues],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for future in done:
                    event = future.result()
                    yield {"event": "message", "data": event}

                    # Re-queue the completed wait
                    q = next(q for q in queues if q.empty())
                    # This is simplified - in production we'd track which queue
        finally:
            for task in tasks:
                task.cancel()

    return EventSourceResponse(multi_channel_stream())
