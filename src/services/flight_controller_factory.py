"""Factory helpers for selecting the active flight controller implementation."""

from __future__ import annotations

from typing import Any

from src.core.config import Settings, get_settings


def build_flight_controller(settings: Settings | None = None) -> Any:
    """Build either the mock or real controller based on current settings."""

    resolved = settings or get_settings()
    if resolved.mock_mode:
        from src.services.mock_flight_controller import MockFlightController

        return MockFlightController(resolved)

    from src.services.flight_controller import FlightController

    return FlightController(resolved)


async def get_flight_controller() -> Any:
    """FastAPI dependency wrapper for the active flight controller."""

    return build_flight_controller()
