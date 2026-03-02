---
phase: 02-dashboard-peripherals
plan: 03
type: execute
wave: 2
depends_on:
  - 01
autonomous: true

requirements: []

user_setup: []

files_modified: []
---

<objective>
Implement SSE backend endpoint for real-time drone and mission updates. Creates EventBroadcaster service and /events endpoint.
</objective>

**Tasks:**

1. **Create EventBroadcaster service**
   - Implement pub/sub pattern using Redis
   - Methods: subscribe(channel), publish(channel, message), unsubscribe(channel)
   - Handle connection lifecycle

2. **Create /events SSE endpoint**
   - Endpoint: GET /events
   - Streams drone updates, mission updates, LLM tokens
   - Uses sse-starlette for response formatting
   - Includes CORS headers

3. **Integrate event emission into DroneManager**
   - Emit 'drone_update' events on state changes
   - Include full drone object in payload
   - Emit on: registration, state change, battery update, position update

4. **Integrate event emission into MissionWorker**
   - Emit 'mission_update' events on status changes
   - Include mission ID and new status
   - Emit on: created, started, completed, failed, cancelled

5. **Add LLM token streaming support**
   - Create /events/llm endpoint for token streaming
   - Backend proxies LLM API calls (from Phase 1)
   - Streams tokens to frontend via SSE
