# Phase 1: Backend Core - Research

**Researched:** 2026-02-27
**Domain:** Drone Swarm Control API & Mission Management
**Confidence:** HIGH

## Summary

Phase 1 implements the backend core enabling AI agents to programmatically dispatch Crazyflie drone missions with safety guarantees. The architecture uses FastAPI for the REST API, PostgREST for database access (not direct PostgreSQL), Redis for mission queue/state, and cflib for drone control. This research confirms the stack is viable and identifies key patterns for mission queuing, drone allocation, and safety systems.

**Primary recommendation:** Use FastAPI with httpx for PostgREST communication, Redis lists for mission queue with BRPOP blocking pops, and cflib's Swarm class with CachedCfFactory for drone connections. Implement kill switch as an async background task that iterates all connected drones and commands immediate land.

---

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Drone Discovery:** Manual scan trigger — admin clicks button to scan for available Crazyflie drones; sequential IDs mapped to radio URI (drone-1 = radio-0-80-1M-0, etc.)
- **Mission Allocation:** Auto-assign — submit mission without specifying drone; system picks available drone; returns wait time estimate if all drones busy
- **Fleet Management:** Dynamic drone registration at runtime; drone state tracked (idle, busy, offline, error); manual availability override
- **API Design:** FastAPI with async support; API key/token in header; all database interaction via PostgREST (not directly to PostgreSQL)
- **Data Storage:** PostgreSQL with PostgREST for all DB API access; mission logs, drone state, fleet configuration persisted
- **Safety:** Kill switch API endpoint triggers immediate land for all drones; pre-flight health check validates battery % and connection quality; mission abort returns drone to home position then lands

### Claude's Discretion

- Redis vs in-memory for mission queue — both viable; Redis provides persistence across restarts
- Database schema design — flexible; research standard patterns
- cflib integration specifics — need to validate with hardware

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope

</user_constraints>

---

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| API-01 | Agent can submit mission request via REST API (target drone, waypoints, duration) | FastAPI async endpoints with Pydantic validation; POST /missions with JSON body |
| API-02 | Agent can query drone status (battery, position, connection quality) | GET /drones/{id} endpoint; Redis for real-time state caching |
| API-03 | Agent receives mission completion callback with results | Webhook/callback URL in mission request; BackgroundTasks for async notification |
| API-04 | API handles concurrent mission requests without race conditions | Redis atomic operations; drone ownership/lease model |
| FLEET-01 | System tracks available drones by URI | PostgreSQL via PostgREST; drone registry table |
| FLEET-02 | System allocates drones to mission (one drone per mission) | Auto-assignment logic in FastAPI; availability check against Redis state |
| FLEET-03 | Drone state persisted (idle, busy, offline, error) | State column in drones table; updated via PostgREST |
| FLEET-04 | Drones can be registered/removed from fleet at runtime | POST/DELETE /drones endpoints; dynamic Swarm update |
| MISS-01 | Mission queue accepts and orders mission requests | Redis list with LPUSH/BRPOP; FIFO ordering |
| MISS-02 | Mission lifecycle tracked (pending, running, completed, failed, cancelled) | Status column in missions table; state machine logic |
| MISS-03 | Missions can be cancelled while in queue | DELETE or PATCH /missions/{id}; remove from Redis queue |
| MISS-04 | Missions execute in sequence (one at a time per drone) | Per-drone queue in Redis; worker processes one at a time |
| SAFE-01 | Kill switch command lands all drones immediately | POST /safety/kill-switch; iterates Swarm, calls land() |
| SAFE-02 | Pre-flight health check validates battery and connection before takeoff | Health check function queries drone state via cflib |
| SAFE-03 | Mission abort command stops current mission and returns drone to idle | POST /missions/{id}/abort; returns home position, then land |

</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115+ | REST API server with async support | Native WebSocket, background tasks, dependency injection for auth |
| httpx | 0.27+ | Async HTTP client | Makes requests from FastAPI to PostgREST |
| Redis | 7.x | Mission queue, real-time state cache | BRPOP for blocking queue pop; pub/sub for state changes |
| cflib | latest | Crazyflie drone control | Official Bitcraze library; Swarm class for multi-drone |
| Pydantic | 2.x | Request/response validation | Built-in to FastAPI ecosystem |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PostgreSQL | 16+ | Persistent storage | All data persistence via PostgREST |
| PostgREST | 13+ | REST API from PostgreSQL | Required by architectural decision |
| python-dotenv | latest | Environment configuration | Local dev, API keys |
| uvicorn | latest | ASGI server | Running FastAPI in production |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI | Flask + threading | FastAPI async is cleaner for concurrent mission handling |
| Redis queue | In-memory asyncio.Queue | Redis persists across restarts; needed for production |
| httpx | requests (sync) | Must use async httpx since FastAPI is async |
| PostgREST | Direct SQLAlchemy | Locked decision - must use PostgREST |

**Installation:**
```bash
pip install fastapi httpx redis cflib pydantic pydantic-settings uvicorn
# Also requires: PostgreSQL + PostgREST (infrastructure, not Python)
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── api/                    # FastAPI route handlers
│   ├── routes/
│   │   ├── missions.py     # Mission CRUD endpoints
│   │   ├── drones.py       # Drone management endpoints
│   │   └── safety.py       # Kill switch, health check
│   └── dependencies.py     # Auth, PostgREST client
├── core/
│   ├── config.py           # Settings from environment
│   └── postgrest.py        # httpx client for PostgREST
├── services/
│   ├── mission_queue.py    # Redis-backed mission queue
│   ├── drone_manager.py    # Fleet state management
│   └── flight_controller.py # cflib integration
├── models/
│   └── schemas.py          # Pydantic models
└── main.py                 # FastAPI app factory
```

### Pattern 1: FastAPI + PostgREST Integration

**What:** FastAPI endpoints call PostgREST via httpx instead of direct database access

**When to use:** Every database operation in this phase

**Example:**
```python
# src/core/postgrest.py
import httpx
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    postgrest_url: str = "http://localhost:3000"
    postgrest_api_key: str = ""

class PostgRESTClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.postgrest_url
        self.headers = {
            "apikey": settings.postgrest_api_key,
            "Content-Type": "application/json"
        }

    async def get(self, path: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}{path}", headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, data: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}{path}", json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def patch(self, path: str, data: dict):
        async with httpx.AsyncClient() as client:
            response = await client.patch(f"{self.base_url}{path}", json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def delete(self, path: str):
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}{path}", headers=self.headers)
            response.raise_for_status()
            return response.json()
```

```python
# src/api/routes/drones.py
from fastapi import APIRouter, Depends
from src.core.postgrest import PostgRESTClient

router = APIRouter()

@router.get("/drones")
async def list_drones(client: PostgRESTClient = Depends()):
    return await client.get("/drones?select=*")

@router.get("/drones/{drone_id}")
async def get_drone(drone_id: int, client: PostgRESTClient = Depends()):
    return await client.get(f"/drones?id=eq.{drone_id}")
```

### Pattern 2: Redis Mission Queue with Drone Ownership

**What:** Redis lists with atomic operations for mission queue and drone lease model

**When to use:** Handling concurrent mission requests (API-04)

**Example:**
```python
# src/services/mission_queue.py
import json
import redis.asyncio as redis
from typing import Optional

class MissionQueue:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def enqueue(self, mission: dict) -> str:
        """Add mission to queue, returns mission ID"""
        mission_id = mission["id"]
        await self.redis.lpush("missions:pending", json.dumps(mission))
        return mission_id

    async def dequeue(self, timeout: int = 0) -> Optional[dict]:
        """Block until mission available, returns mission or None"""
        result = await self.redis.brpop("missions:pending", timeout=timeout)
        if result:
            _, mission_json = result
            return json.loads(mission_json)
        return None

    async def acquire_drone(self, drone_id: str, mission_id: str, ttl: int = 300) -> bool:
        """Atomically acquire drone for mission (lease model)"""
        # Use Redis SETNX for atomic acquire
        lock_key = f"drone:{drone_id}:lock"
        acquired = await self.redis.set(lock_key, mission_id, nx=True, ex=ttl)
        return bool(acquired)

    async def release_drone(self, drone_id: str):
        """Release drone back to idle"""
        await self.redis.delete(f"drone:{drone_id}:lock")

    async def get_drone_status(self, drone_id: str) -> dict:
        """Get current drone state from Redis cache"""
        status = await self.redis.hgetall(f"drone:{drone_id}:status")
        return status or {"state": "unknown"}

    async def update_drone_status(self, drone_id: str, state: str, battery: int = None):
        """Update drone status in Redis"""
        data = {"state": state}
        if battery is not None:
            data["battery"] = battery
        await self.redis.hset(f"drone:{drone_id}:status", mapping=data)
```

### Pattern 3: cflib Swarm Integration

**What:** Use CachedCfFactory and Swarm class for multi-drone control

**When to use:** Drone connection, flight commands, kill switch

**Example:**
```python
# src/services/flight_controller.py
import cflib.crtp
from cflib.crazyflie.swarm import CachedCfFactory, Swarm
from cflib.crazyflie import syncCrazyflie
from typing import Dict, Set

class FlightController:
    def __init__(self):
        self._swarm: Swarm = None
        self._uris: Set[str] = set()

    async def discover_drones(self) -> list[str]:
        """Scan for available Crazyflie drones"""
        cflib.crtp.init_drivers()
        available = cflib.crtp.scan_interfaces()
        uris = [iface[0] for iface in available]
        self._uris = set(uris)
        return uris

    async def connect_swarm(self, uris: list[str]):
        """Connect to swarm of drones"""
        if not uris:
            return
        factory = CachedCfFactory(rw_cache='./cache')
        self._swarm = Swarm(list(uris), factory=factory)
        await self._swarm.connect()

    async def kill_switch(self):
        """Emergency land all drones"""
        if not self._swarm:
            return
        # Execute land on all drones in parallel
        self._swarm.parallel_safe(self._land_drone)

    def _land_drone(self, scf: syncCrazyflie):
        """Land single drone"""
        scf.cf.commander.send_setpoint(0, 0, 0, 0)
        # Or use high-level API if available

    async def health_check(self, uri: str) -> dict:
        """Check drone health (battery, connection)"""
        # Query battery from cflib telemetry
        # This requires keeping a Crazyflie connection open
        pass
```

### Pattern 4: Background Tasks for Mission Execution

**What:** FastAPI BackgroundTasks for async mission processing

**When to use:** Long-running missions that return immediately to caller

**Example:**
```python
# src/api/routes/missions.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from src.services.mission_queue import MissionQueue

router = APIRouter()

class MissionRequest(BaseModel):
    waypoints: list[dict]
    duration_seconds: int
    callback_url: str | None = None

@router.post("/missions")
async def submit_mission(
    mission: MissionRequest,
    background_tasks: BackgroundTasks,
    queue: MissionQueue = Depends()
):
    # Create mission record in PostgreSQL via PostgREST
    mission_data = {
        "status": "pending",
        "waypoints": mission.waypoints,
        "duration_seconds": mission.duration_seconds,
        "callback_url": mission.callback_url
    }
    # ... create via PostgREST, get ID

    # Enqueue for processing
    await queue.enqueue(mission_data)

    # Schedule async processing
    background_tasks.add_task(process_missions)

    return {"mission_id": mission_id, "status": "pending"}

async def process_missions():
    """Background worker that processes missions from queue"""
    queue = MissionQueue()
    while True:
        mission = await queue.dequeue(timeout=5)
        if not mission:
            continue
        # Assign drone, execute mission, update status
        # Send callback on completion
```

### Anti-Patterns to Avoid

- **Direct PostgreSQL connections:** Must use PostgREST; violates architectural decision
- **Sync Redis in async FastAPI:** Use redis.asyncio, not sync redis client
- **Blocking cflib calls in request path:** cflib is blocking; use BackgroundTasks or run in thread pool
- **No drone ownership tracking:** Without lease model, concurrent requests will conflict

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client | urllib, requests | httpx | Async-first, built into FastAPI ecosystem |
| Mission queue | Custom async queue | Redis lists + BRPOP | Proven pattern, atomic operations |
| API validation | Manual validation | Pydantic | Built into FastAPI, reduces boilerplate |
| Drone communication | Custom radio protocol | cflib | Official Bitcraze library, handles all Crazyflie quirks |
| Real-time updates | Polling | Redis pub/sub | Efficient broadcast to WebSocket clients |

**Key insight:** The drone control domain has existing battle-tested solutions (cflib). Building custom radio communication would be reinventing wheels and introducing bugs. Focus effort on the integration layer.

---

## Common Pitfalls

### Pitfall 1: PostgREST Schema Not Configured
**What goes wrong:** API returns 404 or permission denied
**Why it happens:** PostgREST serves from configured schemas; default is "public"
**How to avoid:** Ensure database schema exists and is in PostgREST's `db-schemas` config; grant usage on schema to anon role
**Warning signs:** HTTP 404 on all endpoints; "relation does not exist" errors

### Pitfall 2: cflib Blocking Event Loop
**What goes wrong:** FastAPI requests hang when calling cflib
**Why it happens:** cflib is synchronous; blocks async event loop
**How to avoid:** Run cflib operations in thread pool with `asyncio.to_thread()` or use BackgroundTasks
**Warning signs:** Request timeouts; event loop blocked warnings

### Pitfall 3: Redis Connection Pool Exhaustion
**What goes wrong:** "Too many connections" errors under load
**Why it happens:** Creating new Redis connection per request
**How to avoid:** Use connection pool; share single async Redis client
**Warning signs:** Connection refused errors; Redis memory spike

### Pitfall 4: Mission State Inconsistency
**What goes wrong:** Mission shows "running" but drone disconnected
**Why it happens:** No timeout mechanism for stuck missions
**How to avoid:** Implement mission timeout in Redis; heartbeat from flight controller
**Warning signs:** Orphaned missions; drones marked busy but idle

### Pitfall 5: Race Condition in Drone Allocation
**What goes wrong:** Two missions assigned same drone simultaneously
**Why it happens:** Non-atomic check-then-set
**How to avoid:** Use Redis SETNX for atomic acquisition (see MissionQueue pattern)
**Warning signs:** Flaky mission failures; drone already busy errors

---

## Code Examples

### Mission Submission with Auto-Assignment
```python
# Source: Pattern from this research
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class MissionRequest(BaseModel):
    waypoints: list[dict]
    duration_seconds: int
    target_drone_id: Optional[int] = None  # None = auto-assign
    callback_url: Optional[str] = None

@router.post("/missions")
async def submit_mission(
    mission: MissionRequest,
    background_tasks: BackgroundTasks,
    # Dependencies...
):
    # If specific drone requested
    if mission.target_drone_id:
        drone = await get_drone(mission.target_drone_id)
        if drone.state != "idle":
            raise HTTPException(409, "Drone not available")
    else:
        # Auto-assign: find available drone
        drone = await find_available_drone()
        if not drone:
            # Return wait time estimate
            wait_time = await estimate_queue_wait()
            raise HTTPException(503, f"All drones busy. Estimated wait: {wait_time}s")

    # Create mission assigned to this drone
    mission_data = {
        "drone_id": drone.id,
        "status": "pending",
        # ...
    }
    # Persist via PostgREST
    # Enqueue to Redis

    background_tasks.add_task(process_mission, mission_data["id"])

    return {"mission_id": mission_data["id"], "assigned_drone": drone.id}
```

### Kill Switch Endpoint
```python
# Source: Pattern from this research
@router.post("/safety/kill-switch")
async def emergency_kill_switch(
    background_tasks: BackgroundTasks,
    flight_controller: FlightController = Depends()
):
    """Immediately land all drones"""
    background_tasks.add_task(flight_controller.kill_switch)
    return {"status": "kill_switch_triggered"}

# In flight_controller.py:
async def kill_switch(self):
    """Execute emergency land on all connected drones"""
    if not self._swarm:
        return

    # Get all drone connections
    def land_all(scf):
        scf.cf.commander.send_setpoint(0, 0, 0, 0)

    # Execute in parallel
    self._swarm.parallel_safe(land_all)

    # Update all drone states in Redis
    for uri in self._uris:
        await self.redis.hset(f"drone:{uri}:status", "state", "landed")
```

### Pre-flight Health Check
```python
# Source: Pattern from this research
async def preflight_health_check(drone_uri: str, controller: FlightController) -> dict:
    """Validate drone is ready for mission"""
    # Check battery level
    battery = await controller.get_battery(drone_uri)
    if battery < 20:  # 20% minimum
        return {"ready": False, "reason": f"Low battery: {battery}%"}

    # Check connection quality
    connection = await controller.get_connection_quality(drone_uri)
    if connection < 70:  # 70% minimum
        return {"ready": False, "reason": f"Poor connection: {connection}%"}

    # Check not already busy
    status = await controller.redis.get_drone_status(drone_uri)
    if status.get("state") != "idle":
        return {"ready": False, "reason": f"Drone state: {status.get('state')}"}

    return {"ready": True}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct SQL | PostgREST | Architectural decision | All DB access via REST API |
| Sync cflib | Async wrapper + BackgroundTasks | This phase | Non-blocking API |
| In-memory queue | Redis | Production-ready | Mission state survives restart |
| No safety system | Kill switch + health checks | This phase | Enables safe autonomous operation |

**Deprecated/outdated:**
- Sync FastAPI with gevent — async/await is standard now
- Raw socket communication with Crazyflie — cflib handles this

---

## Open Questions

1. **PostgREST Authentication**
   - What we know: PostgREST uses JWT or API key in `apikey` header
   - What's unclear: Exact role configuration for FastAPI service account
   - Recommendation: Create dedicated PostgreSQL role with minimal permissions; test in isolation

2. **cflib Reconnection Behavior**
   - What we know: CachedCfFactory manages connection caching
   - What's unclear: Latency of reconnection when drone temporarily loses signal
   - Recommendation: Implement retry with exponential backoff in flight controller

3. **Mission Abort Implementation**
   - What we know: Need to return drone to home position then land
   - What's unclear: How to interrupt in-flight mission in cflib
   - Recommendation: Test with actual hardware; may need to send hover command first

4. **Callback Implementation**
   - What we know: BackgroundTasks can send HTTP POST on completion
   - What's unclear: Retry logic if callback endpoint unavailable
   - Recommendation: Use exponential backoff; log failures for manual retry

---

## Sources

### Primary (HIGH confidence)
- Context7: /fastapi/fastapi — FastAPI async endpoints, WebSocket, background tasks
- Context7: /bitcraze/crazyflie-lib-python — cflib Swarm interface, drone control
- Context7: /websites/redis_io — Redis list operations, BRPOP queue pattern
- Context7: /websites/postgrest_en_v13 — PostgREST schema configuration

### Secondary (MEDIUM confidence)
- Context7: /encode/httpx — Async HTTP client patterns
- Context7: /websites/sqlalchemy_en_20 — Schema design patterns (for PostgREST tables)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Well-documented, verified with Context7
- Architecture: HIGH — Patterns confirmed with documentation
- Pitfalls: MEDIUM — Based on common async/Python patterns; some hardware-specific items need validation

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (30 days for stable stack)
