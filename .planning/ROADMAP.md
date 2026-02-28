# Roadmap: Drone Swarm Agent Integration

## Phases

- [ ] **Phase 1: Backend Core** — Agent API, Fleet Management, Mission Control, Safety Systems
- [ ] **Phase 2: Dashboard & Peripherals** — Web Dashboard, Camera Capture, LED Status

## Phase Details

### Phase 1: Backend Core

**Goal:** Enable AI agents to programmatically dispatch drone missions with full safety guarantees

**Depends on:** Nothing (foundation phase)

**Requirements:** API-01, API-02, API-03, API-04, FLEET-01, FLEET-02, FLEET-03, FLEET-04, MISS-01, MISS-02, MISS-03, MISS-04, SAFE-01, SAFE-02, SAFE-03

**Success Criteria** (what must be TRUE):
1. Agent can submit mission request via REST API specifying target drone, waypoints, and duration
2. Agent can query drone status (battery, position, connection quality) via REST endpoint
3. Agent receives webhook callback when mission completes with results
4. API handles multiple concurrent mission requests without race conditions
5. System tracks all available drones by URI and their current state
6. System allocates drones to missions (one drone per mission)
7. Drone state persisted (idle, busy, offline, error) and queryable
8. Drones can be registered or removed from fleet at runtime
9. Mission queue accepts and orders mission requests
10. Mission lifecycle tracked (pending, running, completed, failed, cancelled)
11. Missions can be cancelled while in queue
12. Missions execute in sequence (one at a time per drone)
13. Kill switch command lands all drones immediately
14. Pre-flight health check validates battery and connection before takeoff
15. Mission abort command stops current mission and returns drone to idle

**Plans:** 3 (Infrastructure → Fleet/Mission → API/Safety)

---

### Phase 2: Dashboard & Peripherals

**Goal:** Provide visual mission control interface and drone status feedback

**Depends on:** Phase 1 (requires working backend)

**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04, CAM-01, CAM-02, LED-01

**Success Criteria** (what must be TRUE):
1. Dashboard displays real-time drone positions on 2D map
2. Dashboard shows mission queue and current status
3. Dashboard displays drone health (battery, connection)
4. Dashboard provides manual kill switch button
5. Drone captures images during mission for visual inspection
6. Images stored and accessible via API after mission
7. LED indicates drone state (green=ready, yellow=busy, red=error)

**Plans:** 3 (Infrastructure → Fleet/Mission → API/Safety)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Core | 0/1 | Not started | - |
| 2. Dashboard & Peripherals | 0/1 | Not started | - |

---

## Coverage

| Requirement | Phase |
|-------------|-------|
| API-01 | Phase 1 |
| API-02 | Phase 1 |
| API-03 | Phase 1 |
| API-04 | Phase 1 |
| FLEET-01 | Phase 1 |
| FLEET-02 | Phase 1 |
| FLEET-03 | Phase 1 |
| FLEET-04 | Phase 1 |
| MISS-01 | Phase 1 |
| MISS-02 | Phase 1 |
| MISS-03 | Phase 1 |
| MISS-04 | Phase 1 |
| SAFE-01 | Phase 1 |
| SAFE-02 | Phase 1 |
| SAFE-03 | Phase 1 |
| DASH-01 | Phase 2 |
| DASH-02 | Phase 2 |
| DASH-03 | Phase 2 |
| DASH-04 | Phase 2 |
| CAM-01 | Phase 2 |
| CAM-02 | Phase 2 |
| LED-01 | Phase 2 |

**Mapped:** 22/22 requirements

---

*Roadmap created: 2026-02-27*
