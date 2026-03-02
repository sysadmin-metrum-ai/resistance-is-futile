# Phase 1: Backend Core - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable AI agents to programmatically dispatch drone missions with full safety guarantees. This phase delivers the Agent API, Fleet Management, Mission Control, and Safety Systems.

</domain>

<decisions>
## Implementation Decisions

### Drone Discovery
- Manual scan trigger — admin clicks button to scan for available Crazyflie drones
- Drones get sequential IDs mapped to radio URI: drone-1 = radio-0-80-1M-0, drone-2 = radio-0-80-1M-1, etc.
- Admin can enable/disable drone discovery

### Mission Allocation
- Auto-assign — submit mission without specifying drone; system picks available drone
- System returns wait time estimate if all drones busy
- Available drone = connected + healthy battery + not busy + not manually disabled

### Fleet Management
- Dynamic drone registration at runtime
- Drone state tracked: idle, busy, offline, error
- Manual availability override — admin can mark drones out of service

### API Design
- Framework: FastAPI with async support
- Authentication: API key/token in header
- All database interaction via PostgREST (not directly to PostgreSQL)

### Data Storage
- PostgreSQL database
- PostgREST for all DB API access (not direct Postgres connections)
- Mission logs, drone state, fleet configuration persisted

### Safety
- Kill switch: API endpoint triggers immediate land for all drones
- Pre-flight health check: validates battery % and connection quality before takeoff
- Mission abort: drone returns to home position, then lands

</decisions>

<specifics>
## Specific Ideas

- Drones will need to be dynamically discovered and assigned missions
- Admin/operator can decide to start discovery and stop
- More drones than can fly at a time (battery limits) — dynamic allocation key
- Crazyflie-compatible approach

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-backend-core*
*Context gathered: 2026-02-27*
