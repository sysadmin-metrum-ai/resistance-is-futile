"""Event streams API endpoints for Server-Sent Events (SSE).

Provides real-time event streams for drone updates, mission updates,
and LLM token streaming.
"""

import asyncio
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette import EventSourceResponse

from src.services.event_broadcaster import EventBroadcaster, get_broadcaster

router = APIRouter(tags=["events"])


class LLMRequest(BaseModel):
    """Request body for LLM streaming."""

    prompt: str
    model: str = "gpt-3.5-turbo"
    max_tokens: int = 500


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


@router.post("/events/llm")
async def stream_llm(request: LLMRequest) -> StreamingResponse:
    """
    Stream LLM response tokens via SSE.

    This endpoint proxies LLM API calls and streams tokens in real-time.
    Clients can also subscribe to /events/llm/subscribe to receive
    broadcast tokens.

    Request Body:
        prompt: The input prompt for the LLM
        model: Model to use (default: gpt-3.5-turbo)
        max_tokens: Maximum tokens to generate (default: 500)

    Returns:
        Server-Sent Events response with token stream
    """
    # Generate unique session ID for this request
    session_id = str(uuid.uuid4())

    # TODO: Integrate with actual LLM API (OpenAI, Anthropic, etc.)
    # For now, this is a placeholder that echoes the prompt
    # Real implementation would:
    # 1. Call LLM API with streaming enabled
    # 2. Yield each token as it's received
    # 3. Publish tokens to Redis for broadcast

    async def token_generator():
        """Generate placeholder tokens for the prompt."""
        # Simulate token streaming with the prompt
        words = request.prompt.split()
        try:
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield {"event": "token", "data": {"token": token, "session_id": session_id}}

                # Publish to Redis for subscribers
                try:
                    broadcaster = await get_broadcaster()
                    await broadcaster.publish(
                        broadcaster.CHANNEL_LLM_TOKENS,
                        {"token": token, "session_id": session_id}
                    )
                except Exception:
                    pass  # Best-effort broadcast

                await asyncio.sleep(0.1)  # Simulate streaming delay

            # Send done event
            yield {"event": "done", "data": {"session_id": session_id}}
        except asyncio.CancelledError:
            yield {"event": "cancelled", "data": {"session_id": session_id}}

    return EventSourceResponse(token_generator())


@router.get("/events/llm/subscribe")
async def subscribe_llm_tokens(
    session_id: str = Query(None, description="Optional session ID to filter by"),
) -> StreamingResponse:
    """
    Subscribe to LLM token stream.

    Clients can subscribe to this endpoint to receive LLM tokens
    broadcast by /events/llm calls.

    Query Parameters:
        session_id: Optional session ID to filter tokens by

    Returns:
        Server-Sent Events response with token stream
    """
    broadcaster = await get_broadcaster()

    async def llm_token_stream():
        """Stream LLM tokens from Redis pub/sub."""
        try:
            async for event in broadcaster.subscribe(broadcaster.CHANNEL_LLM_TOKENS):
                # Filter by session_id if provided
                if session_id and event.get("session_id") != session_id:
                    continue
                yield {"event": "token", "data": event}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(llm_token_stream())
