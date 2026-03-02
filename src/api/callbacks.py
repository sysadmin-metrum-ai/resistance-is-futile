"""Mission callback handling for webhook notifications.

Sends HTTP callbacks to agent-provided URLs when missions complete.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


async def send_mission_callback(
    callback_url: str,
    mission_result: dict,
    max_retries: int = 3
) -> bool:
    """
    Send mission completion callback to the specified URL.

    Args:
        callback_url: URL to send the callback to
        mission_result: Dict containing mission_id, status, result, etc.
        max_retries: Maximum number of retry attempts

    Returns:
        True if callback was sent successfully, False otherwise
    """
    if not callback_url:
        logger.debug("No callback URL provided, skipping")
        return False

    # Build callback payload
    payload = {
        "mission_id": mission_result.get("mission_id"),
        "status": mission_result.get("status"),
        "result": mission_result.get("result", {}),
        "completed_at": mission_result.get("completed_at", datetime.utcnow().isoformat()),
    }

    # Retry with exponential backoff
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(callback_url, json=payload)
                response.raise_for_status()
                logger.info(f"Callback sent successfully to {callback_url}")
                return True
        except httpx.TimeoutException:
            logger.warning(
                f"Callback timeout (attempt {attempt + 1}/{max_retries}): {callback_url}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Callback HTTP error (attempt {attempt + 1}/{max_retries}): "
                f"{e.response.status_code} - {callback_url}"
            )
            # Don't retry on client errors (4xx)
            if 400 <= e.response.status_code < 500:
                return False
        except Exception as e:
            logger.error(
                f"Callback failed (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    logger.error(f"Callback failed after {max_retries} attempts: {callback_url}")
    return False


async def send_mission_started_callback(
    callback_url: str,
    mission_data: dict
) -> bool:
    """
    Send mission started callback.

    Args:
        callback_url: URL to send the callback to
        mission_data: Dict containing mission details

    Returns:
        True if callback was sent successfully, False otherwise
    """
    if not callback_url:
        return False

    payload = {
        "mission_id": mission_data.get("mission_id"),
        "event": "mission_started",
        "drone_id": mission_data.get("drone_id"),
        "started_at": datetime.utcnow().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(callback_url, json=payload)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.warning(f"Mission started callback failed: {str(e)}")
        return False


async def send_mission_failed_callback(
    callback_url: str,
    mission_id: str,
    error: str
) -> bool:
    """
    Send mission failed callback.

    Args:
        callback_url: URL to send the callback to
        mission_id: ID of the failed mission
        error: Error message

    Returns:
        True if callback was sent successfully, False otherwise
    """
    if not callback_url:
        return False

    payload = {
        "mission_id": mission_id,
        "event": "mission_failed",
        "error": error,
        "failed_at": datetime.utcnow().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(callback_url, json=payload)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.warning(f"Mission failed callback failed: {str(e)}")
        return False
