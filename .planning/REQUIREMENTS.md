# Requirements: Drone Swarm Agent Integration

**Defined:** 2026-02-27
**Core Value:** Enable AI agents to dispatch physical drone missions for datacenter inspection — bridging the gap between software monitoring and physical reality.

## v1 Requirements

### Agent API

- [x] **API-01**: Agent can submit mission request via REST API (target drone, waypoints, duration)
- [x] **API-02**: Agent can query drone status (battery, position, connection quality)
- [x] **API-03**: Agent receives mission completion callback with results
- [x] **API-04**: API handles concurrent mission requests without race conditions

### Fleet Management

- [x] **FLEET-01**: System tracks available drones by URI
- [x] **FLEET-02**: System allocates drones to missions (one drone per mission initially)
- [x] **FLEET-03**: Drone state persisted (idle, busy, offline, error)
- [x] **FLEET-04**: Drones can be registered/removed from fleet at runtime

### Mission Control

- [x] **MISS-01**: Mission queue accepts and orders mission requests
- [x] **MISS-02**: Mission lifecycle tracked (pending, running, completed, failed, cancelled)
- [x] **MISS-03**: Missions can be cancelled while in queue
- [x] **MISS-04**: Missions execute in sequence (one at a time per drone)

### Safety

- [x] **SAFE-01**: Kill switch command lands all drones immediately
- [x] **SAFE-02**: Pre-flight health check validates battery and connection before takeoff
- [x] **SAFE-03**: Mission abort command stops current mission and returns drone to idle

### Dashboard

- [ ] **DASH-01**: Dashboard displays real-time drone positions on 2D map
- [ ] **DASH-02**: Dashboard shows mission queue and current status
- [ ] **DASH-03**: Dashboard displays drone health (battery, connection)
- [ ] **DASH-04**: Dashboard provides manual kill switch button

### Camera & LED

- [ ] **CAM-01**: Drone captures images during mission for visual inspection
- [ ] **CAM-02**: Images stored and accessible via API after mission
- [x] **LED-01**: LED indicates drone state (green=ready, yellow=busy, red=error)

## v2 Requirements

### Scheduling & Automation

- **SCHED-01**: Periodic missions can be scheduled (cron-style)
- **SCHED-02**: Issue-triggered dispatch via webhook from monitoring systems

### Advanced Safety

- **GEO-01**: Geofencing prevents drones from leaving defined bounds
- **GEO-02**: Altitude limits enforced on all missions

### Positioning

- **POS-01**: Optical flow positioning fallback when UWB unavailable

### OTA

- **OTA-01**: Mission code can be pushed to drones wirelessly
- **OTA-02**: OTA updates use canary deployment (one drone first)

### Demo Venue Setup

- **VENUE-01**: Site survey procedure documents anchor position measurement steps
- **VENUE-02**: drone-acharya generates anchor coordinates from measurement input
- **VENUE-03**: Coordinates pushed to Loco Positioning nodes via radio API

### Demo Validation

- **VALID-01**: Pre-flight checklist validates all systems before takeoff
- **VALID-02**: Mission validation confirms planned paths are executable
- **VALID-03**: System health check reports battery, connection, positioning status

### Demo Missions

- **DEMO-01**: Drones execute pattern flights (circle, ellipse, figure-8)
- **DEMO-02**: Drones execute point-to-point missions with hover and return
- **DEMO-03**: Agent-triggered demo dispatches drone on inspection mission
- **DEMO-04**: Periodic patrol demo shows scheduled autonomous missions

### Demo Booth

- **BOOTH-01**: Power requirements documented (NUC, radios, charging station)
- **BOOTH-02**: Network requirements documented (WiFi, radio frequencies)
- **BOOTH-03**: Safety requirements documented (demo area, observer, emergency)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time video streaming | Crazyflie lacks encoding; bandwidth insufficient |
| 10+ drone swarm coordination | Radio contention; demo scope limited to 4-6 |
| Extended autonomous flight (>10 min) | Battery limits; safety for live demo |
| Outdoor GPS operation | Indoor datacenter focus |
| Deep ITSM integration | API-only sufficient for demo |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| API-01 | Phase 1 | Complete |
| API-02 | Phase 1 | Complete |
| API-03 | Phase 1 | Complete |
| API-04 | Phase 1 | Complete |
| FLEET-01 | Phase 1 | Complete |
| FLEET-02 | Phase 1 | Complete |
| FLEET-03 | Phase 1 | Complete |
| FLEET-04 | Phase 1 | Complete |
| MISS-01 | Phase 1 | Complete |
| MISS-02 | Phase 1 | Complete |
| MISS-03 | Phase 1 | Complete |
| MISS-04 | Phase 1 | Complete |
| SAFE-01 | Phase 1 | Complete |
| SAFE-02 | Phase 1 | Complete |
| SAFE-03 | Phase 1 | Complete |
| DASH-01 | Phase 2 | Complete |
| DASH-02 | Phase 2 | Complete |
| DASH-03 | Phase 2 | Complete |
| DASH-04 | Phase 2 | Complete |
| CAM-01 | Phase 2 | Complete |
| CAM-02 | Phase 2 | Complete |
| LED-01 | Phase 2 | Complete |
| VENUE-01 | Phase 3 | Done |
| VENUE-02 | Phase 3 | Done |
| VENUE-03 | Phase 3 | Done |
| VALID-01 | Phase 4 | Pending |
| VALID-02 | Phase 4 | Pending |
| VALID-03 | Phase 4 | Pending |
| DEMO-01 | Phase 5 | Pending |
| DEMO-02 | Phase 5 | Pending |
| DEMO-03 | Phase 5 | Pending |
| DEMO-04 | Phase 5 | Pending |
| BOOTH-01 | Phase 8 | Pending |
| BOOTH-02 | Phase 8 | Pending |
| BOOTH-03 | Phase 8 | Pending |
| GAP-01 | Phase 4 | Pending | Drone control endpoints for verify-position |
| GAP-02 | Phase 5 | Pending | LED URI fix + Dashboard wiring |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-27*
*Last updated: 2026-02-27 after research synthesis*
