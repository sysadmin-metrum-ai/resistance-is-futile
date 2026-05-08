"""FastAPI application for Drone Swarm Agent Integration.

Main entry point that sets up the API server with all routes.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logging.getLogger("src.swarm").setLevel(logging.INFO)

from src.core.config import get_settings
from src.api.routes.missions import router as missions_router
from src.api.routes.drones import router as drones_router
from src.api.routes.safety import router as safety_router
from src.api.routes.events import router as events_router
from src.api.routes.led import router as led_router
from src.api.routes.images import router as images_router
from src.api.routes.fleets import router as fleets_router
from src.api.routes.anchors import router as anchors_router
from src.api.routes.swarm import dtw_router
from src.api.routes.swarm import router as swarm_router


# Global Redis connection
_redis_pool: redis.ConnectionPool = None


async def init_redis() -> None:
    """Initialize Redis connection pool on startup."""
    global _redis_pool
    settings = get_settings()
    try:
        _redis_pool = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        # Test connection
        await _redis_pool.ping()
    except Exception as e:
        print(f"Warning: Could not connect to Redis: {e}")
        _redis_pool = None


async def close_redis() -> None:
    """Close Redis connections on shutdown."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown."""
    # Startup
    await init_redis()
    print("Drone Swarm API started")

    yield

    # Shutdown
    await close_redis()
    print("Drone Swarm API stopped")


# Create FastAPI app
app = FastAPI(
    title="Drone Swarm API",
    description="REST API for AI drone mission control",
    version="0 agent-driven.1.0",
    lifespan=lifespan,
)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(missions_router, prefix="/api/missions", tags=["missions"])
app.include_router(drones_router, prefix="/api/drones", tags=["drones"])
app.include_router(safety_router, prefix="/api/safety", tags=["safety"])
app.include_router(events_router, prefix="/api", tags=["events"])
app.include_router(led_router, prefix="/api/led", tags=["led"])
app.include_router(images_router, prefix="/api/images", tags=["images"])
app.include_router(fleets_router, prefix="/api/fleets", tags=["fleets"])
app.include_router(anchors_router, prefix="/api/anchors", tags=["anchors"])
app.include_router(swarm_router, prefix="/api/swarm", tags=["swarm"])
app.include_router(swarm_router, prefix="/swarm", tags=["swarm"])
app.include_router(dtw_router, tags=["dtw"])


@app.get("/")
async def root():
    """Root endpoint returning API status."""
    return {"status": "ok", "service": "Drone Swarm API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "redis": _redis_pool is not None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
