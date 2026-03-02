---
phase: 01-backend-core
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
autonomous: true
requirements: []
user_setup:
  - service: postgrest
    why: "Required by architectural decision - all DB access via PostgREST"
    env_vars:
      - name: POSTGREST_URL
        source: "PostgREST server URL (e.g., http://localhost:3000)"
      - name: POSTGREST_API_KEY
        source: "PostgREST API key for authentication"
  - service: redis
    why: "Mission queue and real-time state cache"
    env_vars:
      - name: REDIS_URL
        source: "Redis connection URL (e.g., redis://localhost:6379)"
  - service: postgres
    why: "Persistent storage for drone state, missions, fleet config"
    env_vars:
      - name: DATABASE_URL
        source: "PostgreSQL connection string"

must_haves:
  truths:
    - "PostgREST client can make async GET/POST/PATCH/DELETE requests"
    - "Redis connection pool available for mission queue"
    - "Database schema created with drones and missions tables"
    - "Configuration loaded from environment variables"
  artifacts:
    - "src/core/config.py - Settings class with env var support"
    - "src/core/postgrest.py - Async PostgREST client"
    - "src/services/mission_queue.py - Redis-backed mission queue"
    - "scripts/init-db.sql - Database schema for PostgREST"
  key_links:
    - "PostgREST client used by all API routes"
    - "Mission queue used by background workers"
---

<objective>
Create infrastructure foundation: configuration, PostgREST client, Redis mission queue, and database schema. This establishes the shared foundation all subsequent plans depend on.

Purpose: Enable the API to interact with PostgreSQL (via PostgREST) and Redis for mission queuing.
Output: Core service modules, database schema, environment configuration.
</objective>

<execution_context>
@/Users/cgadgil/.claude/get-shit-done/workflows/execute-plan.md
@/Users/cgadgil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-backend-core/01-CONTEXT.md
@.planning/phases/01-backend-core/01-RESEARCH.md
</context>

<interfaces>
<!-- From 01-RESEARCH.md - Key patterns to implement -->

PostgREST Client Interface (from research Pattern 1):
```python
class PostgRESTClient:
    async def get(self, path: str) -> dict
    async def post(self, path: str, data: dict) -> dict
    async def patch(self, path: str, data: dict) -> dict
    async def delete(self, path: str) -> dict
```

Mission Queue Interface (from research Pattern 2):
```python
class MissionQueue:
    async def enqueue(self, mission: dict) -> str  # Returns mission_id
    async def dequeue(self, timeout: int = 0) -> Optional[dict]
    async def acquire_drone(self, drone_id: str, mission_id: str, ttl: int = 300) -> bool
    async def release_drone(self, drone_id: str) -> None
    async def get_drone_status(self, drone_id: str) -> dict
    async def update_drone_status(self, drone_id: str, state: str, battery: int = None) -> None
```

Settings Interface:
```python
class Settings(BaseSettings):
    postgrest_url: str = "http://localhost:3000"
    postgrest_api_key: str = ""
    redis_url: str = "redis://localhost:6379"
    api_key: str = ""  # For API authentication
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create project structure and configuration</name>
  <files>src/__init__.py, src/core/__init__.py, src/core/config.py, .env.example</files>
  <action>
Create the project directory structure and configuration module:

1. Create src/core/config.py with a Settings class using pydantic_settings.BaseSettings
2. Include these settings with defaults:
   - postgrest_url: str = "http://localhost:3000"
   - postgrest_api_key: str = ""
   - redis_url: str = "redis://localhost:6379"
   - api_key: str = "" (for agent authentication)
3. Create .env.example with all required environment variables
4. Ensure proper async support (class must be importable)

This is foundational - all other modules import from config.
  </action>
  <verify>
python -c "from src.core.config import Settings; s = Settings(); print('OK')"</verify>
  <done>Settings class loads from environment, .env.example lists all required vars</done>
</task>

<task type="auto">
  <name>Task 2: Create PostgREST async client</name>
  <files>src/core/postgrest.py</files>
  <action>
Create src/core/postgrest.py implementing the PostgRESTClient:

1. Create PostgRESTClient class that accepts Settings in constructor
2. Use httpx.AsyncClient for HTTP requests (NOT requests library - must be async)
3. Implement async methods: get, post, patch, delete
4. Include proper headers: {"apikey": api_key, "Content-Type": "application/json"}
5. Raise exceptions on HTTP errors (response.raise_for_status())
6. Add a get_drones() method for querying all drones
7. Add a get_missions() method for querying missions
8. Add dependency injection function for FastAPI Depends()

This is the required pattern per CONTEXT.md: all DB access via PostgREST, not direct PostgreSQL.
  </action>
  <verify>
python -c "from src.core.postgrest import PostgRESTClient; print('OK')"</verify>
  <done>PostgRESTClient has all CRUD methods, proper async implementation</done>
</task>

<task type="auto">
  <name>Task 3: Create Redis mission queue service</name>
  <files>src/services/__init__.py, src/services/mission_queue.py</files>
  <action>
Create src/services/mission_queue.py implementing MissionQueue:

1. Use redis.asyncio (NOT sync redis) for async support
2. Implement:
   - enqueue(mission: dict) -> str - adds to Redis list "missions:pending"
   - dequeue(timeout: int = 0) -> Optional[dict] - blocking pop using BRPOP
   - acquire_drone(drone_id: str, mission_id: str, ttl: int = 300) -> bool - uses SETNX for atomic lock
   - release_drone(drone_id: str) - removes lock
   - get_drone_status(drone_id: str) -> dict - from Redis hash "drone:{id}:status"
   - update_drone_status(drone_id: str, state: str, battery: int = None) - updates hash
3. Use JSON serialization for mission data in Redis
4. Connection pool should be shared (use from_url with connection pool)

This handles concurrent mission requests (API-04) using Redis atomic operations.
  </action>
  <verify>
python -c "from src.services.mission_queue import MissionQueue; print('OK')"</verify>
  <done>MissionQueue uses redis.asyncio, implements all required methods</done>
</task>

<task type="auto">
  <name>Task 4: Create database schema for PostgREST</name>
  <files>scripts/init-db.sql</files>
  <action>
Create scripts/init-db.sql with PostgreSQL schema:

1. Create drones table:
   - id: SERIAL PRIMARY KEY
   - uri: VARCHAR NOT NULL UNIQUE (radio URI like "radio-0-80-1M-0")
   - name: VARCHAR NOT NULL (like "drone-1")
   - state: VARCHAR DEFAULT 'offline' (idle, busy, offline, error)
   - battery: INTEGER DEFAULT 0
   - connection_quality: INTEGER DEFAULT 0
   - enabled: BOOLEAN DEFAULT true
   - created_at: TIMESTAMP DEFAULT now()
   - updated_at: TIMESTAMP DEFAULT now()

2. Create missions table:
   - id: SERIAL PRIMARY KEY
   - drone_id: INTEGER REFERENCES drones(id)
   - waypoints: JSONB NOT NULL
   - duration_seconds: INTEGER NOT NULL
   - status: VARCHAR DEFAULT 'pending' (pending, running, completed, failed, cancelled)
   - callback_url: VARCHAR
   - result: JSONB
   - created_at: TIMESTAMP DEFAULT now()
   - updated_at: TIMESTAMP DEFAULT now()

3. Create indexes:
   - missions.drone_id
   - missions.status
   - drones.state

4. Grant permissions to anon role (required for PostgREST)

This schema supports all fleet and mission requirements (FLEET-01, FLEET-03, MISS-02).
  </action>
  <verify>psql -f scripts/init-db.sql (syntax check only - no actual DB connection required for plan verification)</verify>
  <done>SQL schema created with proper tables, columns, indexes, and permissions</done>
</task>

</tasks>

<verification>
- [ ] All imports work without errors
- [ ] Configuration loads from environment
- [ ] PostgREST client has async methods
- [ ] Mission queue uses redis.asyncio
- [ ] Database schema covers drones and missions tables
</verification>

<success_criteria>
Configuration module, PostgREST client, and Redis mission queue are importable and functional. Database schema created.
</success_criteria>

<output>
After completion, create `.planning/phases/01-backend-core/01-SUMMARY.md`
</output>
