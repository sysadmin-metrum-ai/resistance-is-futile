---
phase: 01-backend-core
plan: 03
subsystem: API Layer
tags: [fastapi, rest, webhook, safety]
dependency_graph:
  requires:
    - 01-PLAN (database schema)
    - 02-PLAN (fleet, mission, safety services)
  provides:
    - REST API for agent interactions
    - Safety endpoints
  affects:
    - Dashboard (will consume these APIs)
tech_stack:
  - FastAPI (web framework)
  - httpx (async HTTP client for callbacks)
  - pydantic (validation)
  - Redis (connection pool lifecycle)
key_files:
  created:
    - src/api/__init__.py
    - src/api/routes/__init__.py
    - src/api/routes/missions.py
    - src/api/routes/drones.py
    - src/api/routes/safety.py
    - src/api/callbacks.py
    - src/main.py
  modified:
    - pyproject.toml
decisions:
  - "FastAPI chosen for async support and automatic OpenAPI docs"
  - "API key auth via X-API-Key header (simple, effective)"
  - "Callbacks use BackgroundTasks to not block responses"
  - "Health checks return structured response with battery/connection details"
---

# Phase 01 Plan 03: REST API Endpoints Summary

Implemented REST API endpoints for agent mission control and safety systems.

## Completed Tasks

| Task | Name                           | Files                           | Verification |
| ---- | ------------------------------ | ------------------------------- | ------------ |
| 1    | Create API routes for missions | missions.py                    | `from src.api.routes.missions import router` |
| 2    | Create API routes for drones   | drones.py                      | `from src.api.routes.drones import router` |
| 3    | Create safety endpoints        | safety.py                      | `from src.api.routes.safety import router` |
| 4    | Create FastAPI main application| main.py                        | `from src.main import app` |
| 5    | Implement mission callbacks   | callbacks.py                   | `from src.api.callbacks import send_mission_callback` |

## What Was Built

### Mission Endpoints (`/missions`)
- `POST /missions` - Submit mission with waypoints, duration, optional target drone, callback URL
  - Auto-assigns available drone if not specified
  - Returns 503 with wait estimate if no drones available
- `GET /missions/{mission_id}` - Get mission details and status
- `POST /missions/{mission_id}/cancel` - Cancel pending/running mission

### Drone Endpoints (`/drones`)
- `GET /drones` - List all drones with merged PostgREST + Redis state
- `GET /drones/{id}` - Get single drone details
- `POST /drones/discover` - Scan for available Crazyflie drones
- `POST /drones` - Register new drone
- `DELETE /drones/{id}` - Unregister drone
- `PATCH /drones/{id}` - Update drone (enabled flag)

### Safety Endpoints (`/safety`)
- `POST /safety/kill-switch` - Emergency land all drones (background task)
- `GET /safety/health-check/{drone_id}` - Single drone health (battery >= 20%, connection >= 70%)
- `POST /safety/health-check` - Bulk health check all drones
- `GET /safety/pre-flight/{drone_id}` - Full pre-flight validation
- `POST /safety/missions/{mission_id}/abort` - Abort running mission, return drone to idle

### Main Application (`/`)
- FastAPI app with lifespan (Redis pool init/cleanup)
- API key authentication via `X-API-Key` header
- CORS middleware enabled
- Health check endpoint

### Callbacks (`src/api/callbacks.py`)
- Retry logic: 3 attempts with exponential backoff (1s, 2s, 4s)
- Mission started/failed/completed callbacks

## Requirements Coverage

| Requirement | Status | Endpoint |
|-------------|--------|----------|
| API-01 (Agent submits mission via POST /missions) | Implemented | `POST /missions` |
| API-02 (Agent queries drone status via GET /drones/{id}) | Implemented | `GET /drones/{id}` |
| API-03 (Webhook callback on mission completion) | Implemented | `src/api/callbacks.py` |
| API-04 (Concurrent requests via Redis) | Implemented | Uses Redis for queue/state |
| SAFE-01 (Kill switch lands all drones) | Implemented | `POST /safety/kill-switch` |
| SAFE-02 (Pre-flight health check) | Implemented | `GET /safety/health-check/{id}`, `GET /safety/pre-flight/{id}` |
| SAFE-03 (Mission abort returns drone to idle) | Implemented | `POST /safety/missions/{id}/abort` |

## Usage

```bash
# Run the API server
uv run python -m src.main

# Or with uvicorn directly
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

```bash
# Example API calls
curl -X POST http://localhost:8000/missions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"waypoints": [{"x": 1, "y": 2, "z": 1}], "duration_seconds": 60}'

curl http://localhost:8000/drones/1 \
  -H "X-API-Key: your-api-key"

curl -X POST http://localhost:8000/safety/kill-switch \
  -H "X-API-Key: your-api-key"
```

## Self-Check

- All 5 tasks completed
- All modules import successfully
- All required requirements mapped
- 5 commits made for atomic task tracking

## Duration

Tasks completed in single execution session.

---

*Plan 03 complete - Phase 1 backend core fully implemented*
