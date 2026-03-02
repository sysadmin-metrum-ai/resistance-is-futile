"""API routes package."""

from src.api.routes.missions import router as missions_router
from src.api.routes.drones import router as drones_router
from src.api.routes.safety import router as safety_router

__all__ = ["missions_router", "drones_router", "safety_router"]
