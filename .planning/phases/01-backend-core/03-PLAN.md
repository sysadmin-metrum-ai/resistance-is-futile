---
phase: 01-backend-core
plan: 03
type: execute
wave: 3
depends_on: [02]
files_modified: []
autonomous: true
requirements: [API-01, API-02, API-03, API-04, SAFE-01, SAFE-02, SAFE-03]
user_setup: []

must_haves:
  truths:
    - "Agent can submit mission via POST /missions with waypoints and duration"
    - "Agent can query drone status via GET /drones/{id}"
    - "Agent receives webhook callback when mission completes"
    - "API handles concurrent requests without race conditions (via Redis)"
    - "Kill switch lands all drones immediately via POST /safety/kill-switch"
    - "Pre-flight health check validates battery and connection"
    - "Mission abort stops mission and returns drone to idle via POST /missions/{id}/abort"
  artifacts:
    - "src/api/routes/missions.py - Mission CRUD endpoints"
    - "src/api/routes/drones.py - Drone status endpoints"
    - "src/api/routes/safety.py - Kill switch, health check, abort endpoints"
    - "src/main.py - FastAPI application with all routes"
  key_links:
    - "FastAPI endpoints use DroneManager, MissionQueue, FlightController"
    - "BackgroundTasks for async callback delivery"
    - "API key authentication on all endpoints"
---

<objective>
Implement REST API endpoints for agents and safety systems: mission submission, drone status queries, callbacks, kill switch, health check, and mission abort.

Purpose: Enable AI agents to programmatically dispatch missions and operators to control safety.
Output: FastAPI routes and main application.
</objective>

<execution_context>
@/Users/cgadgil/.claude/get-shit-done/workflows/execute-plan.md
@/Users/cgadgil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-backend-core/02-PLAN.md
@.planning/phases/01-backend-core/01-CONTEXT.md
@.planning/phases/01-backend-core/01-RESEARCH.md
</context>

<interfaces>
<!-- Key services from Plan 2 for reference -->
<!-- DroneManager:
async def discover_drones() -> list[str]
async def register_drone(uri: str, name: str) -> Drone
async def unregister_drone(drone_id: int) -> None
async def get_available_drone() -> Optional[Drone]
async def get_drone(drone_id: int) -> Drone
async def list_drones() -> list[Drone]
async def update_drone_state(drone_id: int, state: str, battery: int = None) -> None

<!-- FlightController:
async def kill_switch() -> None
async def health_check(uri: str) -> dict
async def abort_mission(drone_uri: str) -> None

<!-- MissionQueue:
async def enqueue(mission: dict) -> str
async def get_drone_status(drone_id: str) -> dict

<!-- Mission cancellation:
async def cancel_mission(mission_id: int) -> bool
async def estimate_queue_wait() -> int
 -->

FastAPI Endpoint Patterns (from research):
```python
# Mission submission with auto-assign
POST /missions
Body: {waypoints: list, duration_seconds: int, target_drone_id?: int, callback_url?: string}
Response: {mission_id: int, assigned_drone?: int, status: "pending", estimated_wait?: int}

# Drone status
GET /drones/{drone_id}
Response: {id, uri, name, state, battery, connection_quality, enabled}

# Kill switch
POST /safety/kill-switch
Response: {status: "kill_switch_triggered"}

# Health check
GET /safety/health-check/{drone_id}
Response: {ready: bool, reason?: string}

# Mission abort
POST /missions/{mission_id}/abort
Response: {mission_id, status: "cancelled"}
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create API routes for missions</name>
  <files>src/api/__init__.py, src/api/routes/__init__.py, src/api/routes/missions.py</files>
  <action>
Create src/api/routes/missions.py with FastAPI endpoints:

1. Create MissionRequest Pydantic model:
   - waypoints: list[dict] (required)
   - duration_seconds: int (required, positive)
   - target_drone_id: Optional[int] = None (None = auto-assign)
   - callback_url: Optional[str] = None

2. POST /missions endpoint:
   - If target_drone_id specified: verify drone is available (idle, enabled)
   - If no target: call DroneManager.get_available_drone() for auto-assign
   - If no drones available: call estimate_queue_wait(), return 503 with wait time
   - Create mission record via PostgREST with status="pending"
   - Enqueue mission to Redis via MissionQueue.enqueue()
   - Add background task to process_missions worker
   - Return {mission_id, assigned_drone (if any), status: "pending"}

3. GET /missions/{mission_id}: returns mission details and status

4. DELETE /missions/{mission_id} or POST /missions/{mission_id}/cancel:
   - Calls cancel_mission(mission_id)
   - Returns updated status

Per CONTEXT.md: auto-assign, wait time estimate if all busy.
  </action>
  <verify>python -c "from src.api.routes.missions import router; print('OK')"</verify>
  <done>Mission endpoints implement API-01, API-04, MISS-03</done>
</task>

<task type="auto">
  <name>Task 2: Create API routes for drones</name>
  <files>src/api/routes/drones.py</files>
  <action>
Create src/api/routes/drones.py with FastAPI endpoints:

1. GET /drones: returns list of all drones with status
   - Query PostgREST for all drones
   - Merge with Redis real-time state (battery, state)

2. GET /drones/{drone_id}: returns single drone details
   - Get from PostgREST
   - Include Redis state

3. POST /drones/discover: triggers drone discovery
   - Calls DroneManager.discover_drones()
   - Returns list of found URIs

4. POST /drones: registers new drone
   - Body: {uri: str, name: str}
   - Calls DroneManager.register_drone()
   - Returns created drone

5. DELETE /drones/{drone_id}: unregisters drone
   - Calls DroneManager.unregister_drone()
   - Returns 204

6. PATCH /drones/{drone_id}: updates drone (enabled, etc.)
   - Body: {enabled: bool}
   - Updates via PostgREST

This implements API-02 (query drone status) and FLEET-04 (register/remove at runtime).
  </action>
  <verify>python -c "from src.api.routes.drones import router; print('OK')"</verify>
  <done>Drone endpoints implement API-02, FLEET-01, FLEET-04</done>
</task>

<task type="auto">
  <name>Task 3: Create safety endpoints</name>
  <files>src/api/routes/safety.py</files>
  <action>
Create src/api/routes/safety.py with FastAPI endpoints:

1. POST /safety/kill-switch:
   - Background task triggers FlightController.kill_switch()
   - Updates all drone states to "landed" in Redis
   - Returns {status: "kill_switch_triggered"}
   - Per CONTEXT.md: "triggers immediate land for all drones"

2. GET /safety/health-check/{drone_id}:
   - Validates drone is available
   - Calls FlightController.health_check(drone_uri)
   - Returns {ready: bool, reason?: string}
   - Per research: battery >= 20%, connection >= 70%

3. POST /safety/health-check (bulk):
   - Runs health check on all drones
   - Returns list of results

4. POST /safety/pre-flight/{drone_id}:
   - Runs full pre-flight validation
   - Checks: battery, connection, state, enabled
   - Returns {ready: bool, checks: {...}}

This implements SAFE-01, SAFE-02 requirements.
  </action>
  <verify>python -c "from src.api.routes.safety import router; print('OK')"</verify>
  <done>Safety endpoints implement SAFE-01, SAFE-02</done>
</task>

<task type="auto">
  <name>Task 4: Create FastAPI main application</name>
  <files>src/main.py</files>
  <action>
Create src/main.py - FastAPI application factory:

1. Create FastAPI app with title "Drone Swarm API"
2. Add API key authentication dependency:
   - Check X-API-Key header on all /drones, /missions, /safety endpoints
   - Return 401 if missing/invalid

3. Include routers:
   - from src.api.routes.missions import router as missions_router
   - from src.api.routes.drones import router as drones_router
   - from src.api.routes.safety import router as safety_router
   - app.include_router(missions_router, prefix="/missions", tags=["missions"])
   - app.include_router(drones_router, prefix="/drones", tags=["drones"])
   - app.include_router(safety_router, prefix="/safety", tags=["safety"])

4. Add root endpoint GET / returning {status: "ok"}

5. Add startup event:
   - Initialize Redis connection pool
   - Initialize cflib drivers

6. Add shutdown event:
   - Close Redis connections
   - Disconnect drone swarm

7. Use BackgroundTasks for mission processing and callbacks

Per CONTEXT.md: FastAPI with async, API key in header.
  </action>
  <verify>python -c "from src.main import app; print('OK')"</verify>
  <done>FastAPI app runs, all routes registered</done>
</task>

<task type="auto">
  <name>Task 5: Implement mission completion callback</name>
  <files>src/api/callbacks.py</files>
  <action>
Create src/api/callbacks.py for webhook callbacks:

1. async def send_mission_callback(callback_url: str, mission_result: dict):
   - Uses httpx.AsyncClient to POST result to callback_url
   - Include mission_id, status, result, completed_at
   - Handle errors gracefully (log, don't crash)

2. Integrate into MissionWorker:
   - After mission completes (success/failure), check if callback_url was provided
   - Use BackgroundTasks to send callback without blocking response
   - Add retry logic: 3 attempts with exponential backoff

This implements API-03: "Agent receives mission completion callback with results".
  </action>
  <verify>python -c "from src.api.callbacks import send_mission_callback; print('OK')"</verify>
  <done>Callbacks sent on mission completion</done>
</task>

</tasks>

<verification>
- [ ] All routes import successfully
- [ ] FastAPI app starts without errors
- [ ] API key auth works
- [ ] All API and safety requirements addressed
</verification>

<success_criteria>
Agent API fully functional: missions can be submitted, drone status queried, callbacks sent, concurrent requests handled safely. Safety systems operational: kill switch, health check, abort.
</success_criteria>

<output>
After completion, create `.planning/phases/01-backend-core/03-SUMMARY.md`
</output>
