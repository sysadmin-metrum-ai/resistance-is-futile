# Gap Closure Plan: Self-Contained Testing via Makefile

**Phase:** 01-backend-core
**Mode:** gap_closure
**Gap:** Tests must be self-contained and runnable via simple Makefile targets

---

## Gap Analysis

**Truth being tested:** "Tests are self-contained and runnable via simple make targets"

**Status:** FAILED

**Reason:** User reported "Tests must be self-contained (pytest and others). If servers need to be started, dependencies installed, it should all be a simple 'makefile' based set of targets!"

**UAT Results:**
- 0 passed, 1 issue, 5 skipped
- All skipped because API server couldn't start without manual setup

---

## Solution

Create a Makefile with self-contained test infrastructure that handles:
1. Dependency installation
2. Service startup (Redis)
3. API server startup
4. Test execution

---

## Tasks

### Task 1: Create Makefile with self-contained test infrastructure

**File:** `/home/cgadgil/src/resistance-is-futile/Makefile`

Create a Makefile with the following targets:

- `make install` - Install Python dependencies via uv
- `make services-up` - Start Redis via Docker
- `make services-down` - Stop services
- `make run` - Start API server on port 8000
- `make test` - Run pytest unit tests (if any exist)
- `make test-integration` - Run integration tests against running API server
- `make clean` - Cleanup temporary files and containers

Key considerations:
- Use `uv` for Python package management (already in project)
- Use Docker for Redis service (redis:alpine image)
- Handle port 8000 availability
- Support running integration tests that hit the live API

---

### Task 2: Create docker-compose.yml for Redis service

**File:** `/home/cgadgil/src/resistance-is-futile/docker-compose.yml`

Create docker-compose with:
- Redis service on port 6379
- Named volume for persistence (optional)
- Health check for readiness

---

### Task 3: Create pytest integration tests matching UAT scenarios

**File:** `/home/cgadgil/src/resistance-is-futile/tests/test_integration.py`

Create pytest-based integration tests matching UAT scenarios:

1. **test_api_server_starts** - Server starts without errors on port 8000
2. **test_post_missions_creates_mission** - POST /missions returns 200/201 with mission_id
3. **test_get_missions_returns_mission** - GET /missions/{id} returns mission with status, waypoints
4. **test_get_drones_lists_drones** - GET /drones returns list of drones with state, battery, connection
5. **test_post_safety_kill_switch** - POST /safety/kill-switch returns 200
6. **test_health_check_endpoint** - GET /safety/health-check/{id} returns battery and connection status

Implementation approach:
- Use `pytest` with `pytest-asyncio` for async tests
- Use `httpx.AsyncClient` for API calls
- Use `docker` SDK or subprocess to start services
- Create a pytest fixture to ensure services are running before tests

---

## Dependencies

**New dependencies to add to pyproject.toml:**
- pytest>=7.0.0
- pytest-asyncio>=0.23.0

---

## Verification

After implementation:
1. `make install` - Installs all dependencies
2. `make services-up` - Starts Redis
3. `make test-integration` - Runs integration tests (this is the main verification)
4. `make services-down` - Stops services

Expected: All 6 UAT tests pass via `make test-integration`
