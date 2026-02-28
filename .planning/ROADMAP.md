# Roadmap: Drone Swarm Agent Integration

## Phases

- [x] **Phase 1: Backend Core** — Agent API, Fleet Management, Mission Control, Safety Systems (completed 2026-02-28)
- [ ] **Phase 2: Dashboard & Peripherals** — Web Dashboard, Camera Capture, LED Status
- [ ] **Phase 3: Demo Venue Setup** — Site survey, drone-acharya positioning, node programming
- [ ] **Phase 4: Demo Validation** — Pre-flight tests, mission validation, system health check
- [ ] **Phase 5: Demo Missions** — Pattern flights, point-to-point, agent-triggered scenarios
- [ ] **Phase 6: Demo Booth** — Power, network, space, safety requirements

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

**Plans:** 3/3 plans complete

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

### Phase 3: Demo Venue Setup

**Goal:** Enable rapid venue setup for demo deployment

**Depends on:** Phase 2 (requires working drone control system)

**Requirements:** VENUE-01, VENUE-02, VENUE-03

**Success Criteria** (what must be TRUE):
1. Site survey procedure documented for measuring anchor positions
2. drone-acharya tool generates anchor coordinates from measurements
3. Coordinates programmatically pushed to Loco Positioning nodes via radio API

**Plans:** TBD

---

### Phase 4: Demo Validation

**Goal:** Validate system readiness before live demo

**Depends on:** Phase 3 (requires venue setup complete)

**Requirements:** VALID-01, VALID-02, VALID-03

**Success Criteria** (what must be TRUE):
1. Pre-flight checklist executes and reports all systems go
2. Mission validation confirms drone can execute planned flight paths
3. System health check reports battery, connection, positioning status

**Plans:** TBD

---

### Phase 5: Demo Missions

**Goal:** Execute impressive flight demonstrations at booth

**Depends on:** Phase 4 (requires validation complete)

**Requirements:** DEMO-01, DEMO-02, DEMO-03, DEMO-04

**Success Criteria** (what must be TRUE):
1. Drones execute pattern flights (circle, ellipse, figure-8)
2. Drones execute point-to-point missions with hover and return
3. Agent-triggered demo shows AI dispatching drone for inspection
4. Periodic patrol demo shows scheduled autonomous missions

**Plans:** TBD

---

### Phase 6: Demo Booth

**Goal:** Document booth requirements for conference logistics

**Depends on:** Phase 5 (requires demo missions defined)

**Requirements:** BOOTH-01, BOOTH-02, BOOTH-03

**Success Criteria** (what must be TRUE):
1. Power requirements documented (NUC, radios, charging)
2. Network requirements documented (WiFi, radio frequencies)
3. Safety requirements documented (demo area, observer, emergency procedures)

**Plans:** TBD

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Core | 3/3 | Complete    | 2026-02-28 |
| 2. Dashboard & Peripherals | 2/3 | In progress | 2026-02-28 |
| 3. Demo Venue Setup | 0/1 | Not started | - |
| 4. Demo Validation | 0/1 | Not started | - |
| 5. Demo Missions | 0/1 | Not started | - |
| 6. Demo Booth | 0/1 | Not started | - |

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
