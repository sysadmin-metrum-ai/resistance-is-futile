# Architecture Research

**Domain:** Drone Swarm Control System for Agent Integration and Datacenter Operations
**Researched:** 2026-02-27
**Confidence:** MEDIUM

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         External Agents Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │  IT Ops Agent   │  │ Datacenter Ops  │  │   Other AI Agents      │ │
│  │  (dispatch)     │  │    (trigger)     │  │   (future integration) │ │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬────────────┘ │
└───────────┼────────────────────┼─────────────────────────┼──────────────┘
            │                    │                         │
            └────────────────────┼─────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Mission Control API Layer                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI Server                               │   │
│  │  /api/v1/missions    /api/v1/drones    /api/v1/status          │   │
│  │  POST/GET/DELETE     GET/PATCH          GET                     │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Mission Orchestration Layer                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  Mission Queue   │  │  Scheduler       │  │  Safety Controller  │  │
│  │  (mission queue) │  │  (cron/periodic) │  │  (kill/geofence)    │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
└───────────┼─────────────────────┼─────────────────────────┼─────────────┘
            │                     │                         │
            ▼                     ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Drone Controller Layer                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │               Crazyflie Swarm Controller (Python)                │    │
│  │  CachedCfFactory → Swarm → parallel_safe/sequential → Commands  │    │
│  └────────────────────────────┬────────────────────────────────────┘    │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Hardware Layer                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌────────────────┐  │
│  │Crazyflie│  │Crazyflie│  │Crazyflie│  │Crazyflie│  │  LPS Deck /    │  │
│  │   #1    │  │   #2    │  │   #3    │  │   #4    │  │  Optical Flow  │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Mission Control API | REST API for agent dispatch, mission CRUD, drone status | FastAPI (Python) |
| Mission Queue | Async mission execution, retry logic, priority handling | In-memory queue or Redis |
| Scheduler | Periodic mission triggers, cron-style scheduling | Python asyncio + schedule |
| Safety Controller | Kill switch, geofencing, emergency landing | Python watchdog thread |
| Swarm Controller | Manage multiple Crazyflie connections, execute flight sequences | cflib Swarm class |
| Drone State Store | Track drone position, battery, status | In-memory + persistence |
| Web Dashboard | Real-time visualization, mission control UI | React/Svelte + WebSocket |
| OTA Service | Deploy updated mission scripts to drones | Custom HTTP endpoint |

## Recommended Project Structure

```
src/
├── api/                        # FastAPI application
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── routers/
│   │   ├── missions.py        # Mission CRUD endpoints
│   │   ├── drones.py          # Drone management endpoints
│   │   └── status.py          # System status endpoints
│   ├── models/
│   │   ├── mission.py         # Pydantic mission models
│   │   └── drone.py           # Pydantic drone models
│   └── dependencies.py        # FastAPI dependencies
│
├── swarm/                      # Drone control layer
│   ├── __init__.py
│   ├── controller.py          # Swarm controller class
│   ├── commander.py           # High-level command wrappers
│   ├── safety.py              # Safety monitoring (geofence, kill)
│   └── state.py               # Drone state management
│
├── mission/                    # Mission orchestration
│   ├── __init__.py
│   ├── queue.py               # Mission queue implementation
│   ├── scheduler.py           # Periodic mission scheduler
│   └── executor.py            # Mission execution logic
│
├── services/                  # External integrations
│   ├── __init__.py
│   ├── ota.py                 # OTA deployment service
│   └── events.py              # Event publishing (agent callbacks)
│
├── dashboard/                 # Web dashboard (optional frontend)
│   ├── static/
│   │   └── index.html
│   └── ws.py                  # WebSocket for real-time updates
│
└── config/
    ├── __init__.py
    └── settings.py           # Configuration management
```

### Structure Rationale

- **`api/routers`:** Separates concerns by domain (missions, drones, status) for maintainability
- **`swarm/controller`:** Encapsulates all Crazyflie-specific logic, isolating hardware dependencies
- **`mission/executor`:** Separates mission logic from API concerns, enables testing without hardware
- **`services/ota`:** Isolated service for code deployment, independent of mission execution
- **`config/settings`:** Centralized configuration for URIs, safety bounds, API keys

## Architectural Patterns

### Pattern 1: Command-Query Responsibility Segregation (CQRS)

**What:** Separate read operations (status, telemetry) from write operations (mission dispatch, control commands)
**When to use:** When you need high-frequency status updates alongside bursty command traffic
**Trade-offs:** Increased complexity, eventual consistency concerns

**Example:**
```python
# Command side - mission dispatch
@app.post("/api/v1/missions")
async def create_mission(mission: MissionCreate):
    mission_id = await mission_queue.enqueue(mission)
    return {"mission_id": mission_id, "status": "queued"}

# Query side - drone status (high frequency)
@app.get("/api/v1/drones/{drone_id}/status")
async def get_drone_status(drone_id: str):
    return drone_state.get(drone_id)  # Cached, refreshed by background task
```

### Pattern 2: Event-Driven Mission Execution

**What:** Missions are queued and executed asynchronously via an event loop, allowing multiple drones to operate independently
**When to use:** For parallel drone operations, mission scheduling, and agent integration
**Trade-offs:** Requires careful handling of async race conditions

**Example:**
```python
import asyncio
from dataclasses import dataclass
from enum import Enum

class MissionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Mission:
    id: str
    drone_uri: str
    waypoints: list[tuple[float, float, float, float]]  # x, y, z, duration
    status: MissionStatus = MissionStatus.PENDING

class MissionQueue:
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: dict[str, Mission] = {}

    async def enqueue(self, mission: Mission):
        await self._queue.put(mission)

    async def execute_next(self):
        mission = await self._queue.get()
        self._running[mission.id] = mission
        mission.status = MissionStatus.RUNNING
        try:
            await self._execute_mission(mission)
            mission.status = MissionStatus.COMPLETED
        except Exception as e:
            mission.status = MissionStatus.FAILED
            raise
        finally:
            del self._running[mission.id]
```

### Pattern 3: Safety Watchdog Pattern

**What:** A background watchdog monitors drone state and triggers emergency protocols (land/kill) when safety bounds are exceeded
**When to use:** Always for autonomous drone operations - required for live demos
**Trade-offs:** Adds latency to emergency responses, but prevents catastrophic failures

**Example:**
```python
import asyncio
from dataclasses import dataclass

@dataclass
class SafetyBounds:
    min_z: float = 0.1   # Minimum altitude (meters)
    max_z: float = 3.0   # Maximum altitude
    max_velocity: float = 2.0  # m/s
    geofence_radius: float = 5.0  # meters from origin

class SafetyWatchdog:
    def __init__(self, swarm, bounds: SafetyBounds):
        self.swarm = swarm
        self.bounds = bounds
        self._running = False

    async def start(self):
        self._running = True
        while self._running:
            await self._check_positions()
            await asyncio.sleep(0.1)  # 10Hz check rate

    async def _check_positions(self):
        for drone in self.swarm.drones:
            pos = drone.position  # Assume updated from telemetry
            if pos.z < self.bounds.min_z:
                await self.emergency_land(drone, "below minimum altitude")
            elif pos.z > self.bounds.max_z:
                await self.emergency_land(drone, "above maximum altitude")
            # ... additional checks

    async def emergency_land(self, drone, reason: str):
        print(f"EMERGENCY LAND: {drone.uri} - {reason}")
        await drone.land()
```

## Data Flow

### Mission Dispatch Flow (from Agent)

```
[Agent] --HTTP POST--> [Mission API] --validate--> [Mission Queue]
                                                      │
                                                      ▼
                                              [Mission Executor]
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                            [Swarm Controller]  [Safety Watchdog]  [State Store]
                                    │                 │                 │
                                    ▼                 ▼                 ▼
                            [Crazyflie #1]    [Position Updates]  [Status Cache]
```

1. Agent dispatches mission via HTTP POST to `/api/v1/missions`
2. API validates mission parameters (coordinates, drone availability)
3. Mission is enqueued in async queue
4. Executor picks up mission, registers with safety watchdog
5. Swarm controller sends high-level commands to Crazyflie
6. Position updates flow back through state store
7. Status is cached for API queries

### Agent Integration Flow

```
[AI Agent] --Webhook/SDK--> [Mission API] --async--> [Result Callback]
                                                    │
                                                    ▼
                                           [Mission Execution]
                                                    │
                                                    ▼
                                           [Event Webhook to Agent]
```

### State Management

```
[Drone Telemetry] --10Hz--> [State Store] --1Hz cache--> [API Responses]
                               │
                               ▼
                        [WebSocket Broadcast] --10Hz--> [Dashboard]
```

### Key Data Flows

1. **Mission Dispatch:** Agent -> API -> Queue -> Executor -> Swarm -> Drone
2. **Telemetry:** Drone -> cflib callbacks -> State Store -> API/Dashboard
3. **Safety:** Watchdog -> Position check -> Emergency protocols
4. **OTA Update:** API -> OTA Service -> Drone script deployment

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-4 drones | Single Python process with cflib Swarm. All operations synchronous within process. |
| 5-10 drones | Consider multiple radio adapters (cflib supports multiple USB radios). May need separate controller processes per radio. |
| 10+ drones | Architecture may need redesign. Crazyflie firmware has per-radio limits. Consider multiple swarm controller instances with load balancer. |
| Agent integration | Stateless API tier scales horizontally. Redis for mission queue if scaling beyond single instance. |

### Scaling Priorities

1. **First bottleneck: Radio capacity** — Each USB radio handles limited concurrent drones. Plan for multiple radios early.
2. **Second bottleneck: Python GIL** — cflib is single-threaded. Heavy mission loads may need process isolation.
3. **Third bottleneck: State consistency** — At scale, consider Redis for distributed state instead of in-memory.

## Anti-Patterns

### Anti-Pattern 1: Blocking API Calls to Drones

**What people do:** Making synchronous HTTP requests that wait for drone to complete full mission before responding
**Why it's wrong:** Drone missions take seconds to minutes. API timeouts, no real-time feedback, poor UX
**Do this instead:** Use async mission queue, return mission ID immediately, provide status endpoint for polling

### Anti-Pattern 2: No Safety Boundaries

**What people do:** Directly executing coordinates from agents without validation
**Why it's wrong:** Agents may send invalid coordinates (out of range, collisions), causing crashes or flyaways
**Do this instead:** Always wrap agent commands with safety validation (geofence, altitude limits, velocity limits)

### Anti-Pattern 3: Single Point of Failure in Swarm

**What people do:** One drone failing stops entire mission
**Why it's wrong:** Hardware fails. One bad drone shouldn't cascade to others
**Do this instead:** Design missions as independent per-drone operations. Use try/except around each drone command.

### Anti-Pattern 4: No Human Override

**What people do:** Fully autonomous operation with no manual intervention capability
**Why it's wrong:** Live demos require human intervention when things go wrong. No override = crashed demo
**Do this instead:** Implement emergency stop, manual control mode, and "abort all" capability accessible via dashboard

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| AI Agents | REST API + Webhook callbacks | Agentfield or custom API |
| Mission Control Dashboard | WebSocket + REST | Real-time position updates |
| ITSM Systems | Webhook integration | Future: incident-triggered missions |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| API ↔ Swarm | Async queue (asyncio.Queue) | Decouples HTTP handlers from drone control |
| Swarm ↔ Drones | cflib SyncCrazyflie | Blocking per-drone, parallel across drones |
| Safety ↔ Swarm | Callback/observer pattern | Safety watchdog observes drone state |

## Build Order and Dependencies

```
Phase 1: Foundation
├── API skeleton (FastAPI)
├── Mission models
└── Basic drone connectivity test

Phase 2: Core Mission Execution
├── Mission queue implementation
├── Swarm controller wrapper
├── Basic take-off/land/hover commands
└── Safety watchdog (critical path)

Phase 3: Agent Integration
├── Mission dispatch endpoint
├── Drone status endpoint
├── Webhook callbacks for mission completion
└── Basic auth/API key validation

Phase 4: Dashboard & Visualization
├── Real-time state via WebSocket
├── Mission visualization
├── Drone position plotting
└── Manual override controls

Phase 5: Advanced Features
├── OTA deployment service
├── Optical flow fallback positioning
├── Periodic scheduling
└── Issue-triggered dispatch
```

### Dependency Rationale

1. **Foundation first:** Need working API and basic connectivity before any mission logic
2. **Safety before agents:** Critical to have safety watchdog working before accepting external commands
3. **Agent after safety:** Agents should only dispatch missions to a system that is already safe
4. **Dashboard after core:** Dashboard is nice-to-have; core mission execution is essential
5. **OTA last:** Dynamic code deployment is advanced feature, requires stable base first

## Sources

- [Crazyflie Python Library - Swarm Interface](https://github.com/bitcraze/crazyflie-lib-python/blob/master/docs/user-guides/sbs_swarm_interface.md)
- [Crazyflie Python Library - Python API](https://github.com/bitcraze/crazyflie-lib-python/blob/master/docs/user-guides/python_api.md)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

*Architecture research for: Drone Swarm Agent Integration*
*Researched: 2026-02-27*
