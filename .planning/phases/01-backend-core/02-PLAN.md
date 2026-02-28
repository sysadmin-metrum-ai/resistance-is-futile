---
phase: 01-backend-core
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified: []
autonomous: true
requirements: [FLEET-01, FLEET-02, FLEET-03, FLEET-04, MISS-01, MISS-02, MISS-03, MISS-04]
user_setup: []

must_haves:
  truths:
    - "Drone discovery scans and registers available Crazyflie drones"
    - "Drone state (idle/busy/offline/error) is tracked and queryable"
    - "Drones can be registered or removed at runtime"
    - "Missions are queued and processed in FIFO order"
    - "Each drone executes one mission at a time"
    - "Pending missions can be cancelled before execution"
  artifacts:
    - "src/services/drone_manager.py - Fleet state management"
    - "src/services/flight_controller.py - cflib integration for drone control"
    - "src/services/mission_worker.py - Background worker for mission execution"
  key_links:
    - "DroneManager uses PostgREST for persistence and Redis for real-time state"
    - "MissionWorker uses MissionQueue for FIFO processing"
    - "FlightController uses cflib for Crazyflie communication"
---

<objective>
Implement fleet management and mission execution: drone discovery, state tracking, registration/removal, mission queue processing, and per-drone sequential execution.

Purpose: Enable the system to track available drones and process missions in order.
Output: Drone manager, flight controller, mission worker services.
</objective>

<execution_context>
@/Users/cgadgil/.claude/get-shit-done/workflows/execute-plan.md
@/Users/cgadgil/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-backend-core/01-PLAN.md
@.planning/phases/01-backend-core/01-CONTEXT.md
@.planning/phases/01-backend-core/01-RESEARCH.md
</context>

<interfaces>
<!-- Key interfaces from Plan 1 for reference -->
<!-- PostgRESTClient from src/core/postgrest.py:
async def get_drones() -> list
async def post_mission(mission: dict) -> dict
async def patch_drone(drone_id: int, data: dict) -> dict

<!-- MissionQueue from src/services/mission_queue.py:
async def enqueue(mission: dict) -> str
async def dequeue(timeout: int) -> Optional[dict]
async def acquire_drone(drone_id: str, mission_id: str, ttl: int) -> bool
async def release_drone(drone_id: str) -> None
async def get_drone_status(drone_id: str) -> dict
async def update_drone_status(drone_id: str, state: str, battery: int = None) -> None
 -->

DroneManager Interface:
```python
class DroneManager:
    async def discover_drones(self) -> list[str]  # Scans for available Crazyflies
    async def register_drone(self, uri: str, name: str) -> Drone  # Adds to fleet
    async def unregister_drone(self, drone_id: int) -> None  # Removes from fleet
    async def get_available_drone(self) -> Optional[Drone]  # Auto-assign logic
    async def get_drone(self, drone_id: int) -> Drone
    async def list_drones(self) -> list[Drone]
    async def update_drone_state(self, drone_id: int, state: str, battery: int = None) -> None
```

FlightController Interface:
```python
class FlightController:
    async def connect_swarm(self, uris: list[str]) -> None  # Connect to drones
    async def disconnect(self) -> None  # Disconnect all
    async def kill_switch(self) -> None  # Emergency land all
    async def health_check(self, uri: str) -> dict  # Battery, connection quality
    async def execute_mission(self, drone_uri: str, waypoints: list, duration_seconds: int) -> dict
    async def abort_mission(self, drone_uri: str) -> None  # Return home and land
```

MissionWorker Interface:
```python
class MissionWorker:
    async def process_next_mission(self) -> None  # Dequeue and execute one mission
    async def run_continuously(self) -> None  # Background task loop
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create DroneManager service</name>
  <files>src/services/drone_manager.py</files>
  <action>
Create src/services/drone_manager.py implementing DroneManager:

1. Import PostgRESTClient from src.core.postgrest
2. Import MissionQueue from src.services.mission_queue
3. Implement:
   - discover_drones() - uses cflib.crtp to scan for available Crazyflie interfaces
   - register_drone(uri, name) - creates drone record via PostgREST, returns drone
   - unregister_drone(drone_id) - deletes via PostgREST, updates Redis state
   - get_available_drone() - finds connected + healthy + idle + enabled drone (per CONTEXT.md)
   - get_drone(drone_id) - gets single drone via PostgREST
   - list_drones() - gets all drones via PostgREST
   - update_drone_state(drone_id, state, battery) - updates both PostgREST and Redis

4. Use Redis to track real-time state (battery, connection) for fast queries
5. For auto-assign: find first drone where state=idle, enabled=true, battery>20%, connected

Per CONTEXT.md: "Available drone = connected + healthy battery + not busy + not manually disabled"
  </action>
  <verify>python -c "from src.services.drone_manager import DroneManager; print('OK')"</verify>
  <done>DroneManager implements all fleet management requirements (FLEET-01, FLEET-02, FLEET-03, FLEET-04)</done>
</task>

<task type="auto">
  <name>Task 2: Create FlightController service</name>
  <files>src/services/flight_controller.py</files>
  <action>
Create src/services/flight_controller.py implementing FlightController:

1. Import cflib modules: crtp, Swarm, CachedCfFactory, syncCrazyflie
2. Implement:
   - connect_swarm(uris) - connects to all drone URIs using CachedCfFactory
   - disconnect() - disconnects swarm
   - kill_switch() - sends emergency land command to ALL drones using swarm.parallel_safe
   - health_check(uri) - returns {battery, connection_quality} from cflib telemetry
   - execute_mission(drone_uri, waypoints, duration_seconds) - runs waypoint sequence
   - abort_mission(drone_uri) - returns to home position then lands

3. IMPORTANT: cflib is synchronous - wrap blocking calls with asyncio.to_thread() or run in BackgroundTasks
4. Use cflib.crtp.init_drivers() before scanning
5. Battery threshold: 20% minimum per SAFE-02 research
6. Connection quality threshold: 70% minimum per research

This integrates with Crazyflie hardware for flight control.
  </action>
  <verify>python -c "from src.services.flight_controller import FlightController; print('OK')"</verify>
  <done>FlightController implements drone control and safety operations</done>
</task>

<task type="auto">
  <name>Task 3: Create MissionWorker for queue processing</name>
  <files>src/services/mission_worker.py</files>
  <action>
Create src/services/mission_worker.py implementing MissionWorker:

1. Import MissionQueue, DroneManager, FlightController
2. Implement process_next_mission():
   - Dequeue next mission from Redis (blocking BRPOP)
   - Acquire drone using MissionQueue.acquire_drone() - atomic, prevents race conditions
   - Update mission status to "running" in PostgreSQL via PostgREST
   - Run pre-flight health check (battery >= 20%, connection >= 70%)
   - If health check fails: mark mission failed, release drone, continue
   - Execute mission using FlightController
   - On completion: update mission status, store result, send callback if URL provided
   - Release drone back to idle

3. Implement run_continuously():
   - While loop calling process_next_mission()
   - Handle exceptions gracefully (log and continue)
   - Use timeout on dequeue to allow periodic health checks

4. Per CONTEXT.md: missions execute in sequence (one at a time per drone) - achieved via drone locking

This implements MISS-01 (queue), MISS-02 (lifecycle), MISS-04 (sequential execution).
  </action>
  <verify>python -c "from src.services.mission_worker import MissionWorker; print('OK')"</verify>
  <done>MissionWorker processes queue in FIFO order with per-drone locking</done>
</task>

<task type="auto">
  <name>Task 4: Create mission cancellation handler</name>
  <files>src/services/mission_cancellation.py</files>
  <action>
Create src/services/mission_cancellation.py:

1. Implement cancel_mission(mission_id: int) -> bool:
   - Check mission status in PostgreSQL via PostgREST
   - If status == "pending": remove from Redis queue, update status to "cancelled", return True
   - If status == "running": call FlightController.abort_mission(), update status, return True
   - If status in ["completed", "failed", "cancelled"]: return False (already terminal)
   - Use Redis to track pending mission IDs for O(1) removal

2. Implement estimate_queue_wait() -> int:
   - Count pending missions in queue
   - Estimate based on average mission duration (use configured default)
   - Return wait time in seconds

This implements MISS-03: missions can be cancelled while in queue.
  </action>
  <verify>python -c "from src.services.mission_cancellation import cancel_mission, estimate_queue_wait; print('OK')"</verify>
  <done>cancel_mission works for pending and running missions</done>
</task>

</tasks>

<verification>
- [ ] DroneManager imports successfully
- [ ] FlightController imports successfully
- [ ] MissionWorker imports successfully
- [ ] All fleet and mission requirements addressed
</verification>

<success_criteria>
Fleet management (discovery, registration, state tracking) and mission execution (queue, processing, cancellation) functional.
</success_criteria>

<output>
After completion, create `.planning/phases/01-backend-core/02-SUMMARY.md`
</output>
