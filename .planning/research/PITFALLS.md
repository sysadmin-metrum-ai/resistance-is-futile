# Pitfalls Research

**Domain:** Drone Swarm Agent Integration for Datacenter Inspection
**Researched:** 2026-02-27
**Confidence:** MEDIUM (web search unavailable; based on existing codebase analysis and domain knowledge)

## Critical Pitfalls

### Pitfall 1: Missing Safety Kill Switch

**What goes wrong:**
Drone becomes unresponsive or flies erratically during autonomous mission, causing crash or property damage. In live demo at Dell Tech World 2026, this could harm attendees or damage equipment.

**Why it happens:**
- No emergency kill switch implemented in current Python flight scripts
- Commander watchdog timeout (100ms stabilize, 500ms shutdown) in Crazyflie firmware is not actively managed by agent
- Agent API dispatch does not include immediate stop capability

**How to avoid:**
1. Implement heartbeat-based kill switch in agent API layer — if no command received for X seconds, trigger land emergency
2. Add physical emergency stop button accessible to dashboard operators
3. Implement geofencing boundaries that auto-trigger return-to-home if exceeded

**Warning signs:**
- Radio latency spikes > 200ms
- Position estimate becomes unstable
- Agent loses connection to drone for > 1 second

**Phase to address:** Phase 1 (Agent API) — safety must be built into mission dispatch from day one

---

### Pitfall 2: UWB Positioning Failure at Conference Venue

**What goes wrong:**
Loco Positioning System (LPS) provides unreliable position data due to WiFi and attendee device interference in the 5GHz range, causing drones to drift, lose position lock, or fly erratically during demo.

**Why it happens:**
- Dell Tech World has heavy WiFi traffic on 5GHz
- UWB channels overlap with conference venue RF noise
- LPS anchors have limited range (~30m) and require careful placement

**How to avoid:**
1. Pre-validate LPS at venue before demo day — test for position stability
2. Implement optical flow positioning as fallback (already identified in PROJECT.md)
3. Add position confidence scoring in agent — if position variance exceeds threshold, hold position or abort mission

**Warning signs:**
- Position estimates showing > 10cm variance between readings
- Drone drifting despite zero command input
- LPS anchor status showing "unstable" in dashboard

**Phase to address:** Phase 2 (Positioning fallback) — validate LPS early, have optical flow ready before venue

---

### Pitfall 3: Agent API Race Conditions in Mission Dispatch

**What goes wrong:**
Multiple agent requests or rapid mission dispatch causes drones to receive conflicting commands simultaneously — one agent says "go left" while another says "hover", resulting in unpredictable drone behavior or crashes.

**Why it happens:**
- Current architecture does not show a mission queue or mutex on drone state
- Agent API may accept parallel requests without ownership/lease semantics
- No single source of truth for drone state visible to agents

**How to avoid:**
1. Implement drone ownership model — an agent must acquire lease before dispatching commands
2. Use mission queue with FIFO ordering instead of direct command injection
3. Add state machine: IDLE → ASSIGNED → TAKEOFF → MISSION → RETURNING → LANDED → IDLE

**Warning signs:**
- Multiple simultaneous API calls to same drone
- Dashboard showing inconsistent drone state
- Logs showing command conflicts

**Phase to address:** Phase 1 (Agent API) — design with concurrency from the start

---

### Pitfall 4: OTA Deployment Bricked Drones

**What goes wrong:**
OTA code deployment pushes buggy firmware to drones mid-mission or during setup, rendering them unresponsive. At worst, all 10 Crazyflies become unusable before a critical demo.

**Why it happens:**
- No staged rollout — OTA pushes to all drones simultaneously
- No rollback capability documented
- No pre-deployment validation on "canary" drone before fleet-wide deployment
- Battery levels during OTA may be insufficient, causing incomplete flash

**How to avoid:**
1. Implement canary deployment: push to 1 drone, validate, then roll out to rest
2. Require minimum battery threshold (e.g., 80%) before OTA allowed
3. Maintain version inventory — know what version each drone is running
4. Document recovery procedure (USB DFU reflash) and keep hardware available

**Warning signs:**
- OTA push during critical demo prep
- Battery levels below 50% before deployment
- No test drone available for canary validation

**Phase to address:** Phase 3 (OTA deployment) — design before implementation

---

### Pitfall 5: Web Dashboard Gives False Sense of Drone Health

**What goes wrong:**
Dashboard shows drone as "ready" or "healthy" based on last-known radio connection, but actual drone state has changed (battery depleted, position lost, motor error). Operator dispatches mission unaware drone cannot complete it.

**Why it happens:**
- Dashboard polls state periodically (not pushed), so stale data displayed
- No health checks before mission dispatch
- Battery percentage shown may be outdated by minutes

**How to avoid:**
1. Implement pre-mission health check API — verify battery, position lock, radio connection within last 5 seconds
2. Add visual warning indicators for stale data (e.g., gray out if data > 5 seconds old)
3. Require dashboard to query health status before enabling mission dispatch button

**Warning signs:**
- Dashboard showing "connected" but last packet timestamp > 10 seconds ago
- Battery percentage not updating
- Position showing last-known instead of current

**Phase to address:** Phase 1 (Agent API) and Phase 2 (Dashboard) — health checks must be in API

---

## Moderate Pitfalls

### Pitfall 6: Hardcoded Radio URIs Cause Channel Conflicts

**What goes wrong:**
Multiple drones configured with same radio channel cannot be distinguished. Agent sends command to drone A but drone B responds. In multi-drone missions, wrong drone executes wrong command.

**Why it happens:**
- test-hover.py has hardcoded URI `radio://0/80/2M` (from CONCERNS.md)
- No configuration management for drone-to-channel mapping
- Agent API does not validate drone identity before dispatch

**How to avoid:**
1. Create drone registry with URI, channel, and drone ID mapping
2. Pass explicit drone ID in all agent API calls, validate against registry
3. Use environment variables or config file for URIs (not hardcoded)

**Warning signs:**
- Multiple drones responding to same command
- Dashboard showing unexpected drone positions
- Logs showing "connected" but wrong drone

**Phase to address:** Phase 1 (Agent API) — configuration management

---

### Pitfall 7: No Reconnection Logic for Radio Drops

**What goes wrong:**
During autonomous mission, radio connection drops momentarily. Drone continues last command (potentially flying into obstacle), but agent believes drone is still connected. No automatic reconnection or mission abort.

**Why it happens:**
- Python flight scripts have no reconnection logic (identified in CONCERNS.md)
- Agent API does not have connection monitoring
- No timeout/abort if drone goes silent

**How to avoid:**
1. Implement heartbeat monitoring in both drone and agent
2. On connection loss > 3 seconds, trigger "lost link" protocol (hover in place or return-to-home)
3. Agent should mark drone as "unavailable" in dashboard until reconnection confirmed

**Warning signs:**
- Radio latency increasing over time
- Packet loss detected
- Connection drops during high-traffic times

**Phase to address:** Phase 1 (Agent API) — reconnection is critical for autonomous operation

---

### Pitfall 8: Mission Scheduling Timeouts Not Handled

**What goes wrong:**
Periodic mission scheduled but drone still executing previous mission when scheduled time arrives. Queue overflows or previous mission gets pre-empted unexpectedly, causing drone to land mid-flight or behave erratically.

**Why it happens:**
- No mission queue or scheduling logic in current architecture
- Periodic scheduling may overlap with manual dispatch
- No handling for "drone busy" state

**How to avoid:**
1. Implement mission queue with max depth (e.g., 5 pending missions)
2. Return "BUSY" status if drone cannot accept new mission
3. Allow scheduling to specify "skip if busy" or "queue" behavior

**Warning signs:**
- Dashboard showing queue depth growing unbounded
- Drones executing missions at unexpected times
- Log warnings about dropped or delayed missions

**Phase to address:** Phase 1 (Agent API) — queue design

---

## Minor Pitfalls

### Pitfall 9: Trilateration Invalid Input Crashes

**What goes wrong:**
Drone-acharya receives malformed anchor coordinates or distance measurements, produces garbage output, which then gets flashed to drones, causing positioning to be completely wrong.

**Why it happens:**
- Missing input validation for negative/zero distances (identified in CONCERNS.md)
- Collinearity check only covers nodes 0,1,2, not all combinations (identified in CONCERNS.md)
- CSV parsing fails on missing cells with unclear error messages

**How to avoid:**
1. Add explicit validation in Solve() for all distance inputs
2. Expand collinearity check to all node combinations
3. Add more robust error messages showing exact validation failure

**Warning signs:**
- Warnings about "negative squared distance clamped to 0" during anchor setup
- Validation failures in logs
- Drone positions wildly inaccurate after anchor setup

**Phase to address:** Before Phase 1 — anchor setup happens before agent integration

---

### Pitfall 10: Python Dependency Chain Breaks on Python Version

**What goes wrong:**
cfclient/cflib incompatible with Python 3.11+, flight scripts fail to run, demo cannot proceed. All code dependent on these libraries becomes unusable.

**Why it happens:**
- Python dependencies not pinned to specific versions (identified in CONCERNS.md)
- No CI testing for Python version compatibility

**How to avoid:**
1. Pin cfclient/cflib to known-working versions in requirements.txt
2. Test against target Python version early (3.11 or 3.12)
3. Have fallback plan: use cflib directly without GUI dependencies

**Warning signs:**
- pip install failures
- Import errors in flight scripts
- Compatibility warnings from Bitcraze GitHub

**Phase to address:** Phase 1 (setup/validation)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip pre-mission health check | Faster dispatch | Drone dispatched but unable to fly | Never for safety-critical |
| Single radio for multi-drone | Cost savings | Cannot operate simultaneously | Only for single-drone demos |
| Hardcode drone URIs | Simpler code | Must edit code to change config | Never - use config files |
| Skip canary OTA | Faster deployment | All drones potentially bricked | Never for safety-critical |
| No mission queue | Simpler API design | Race conditions, dropped missions | Only for single sequential missions |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Agent API | Not checking drone availability before dispatch | Query status endpoint first |
| Radio (CRTP) | Assuming connection is stable | Implement heartbeat, handle drops |
| LPS anchors | Placing anchors in collinear arrangement | Use tetrahedron or similar 3D spread |
| Web dashboard | Polling state instead of push | Use WebSocket for real-time updates |
| OTA | Pushing without battery check | Require 80%+ battery before flash |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Python blocking I/O in flight loop | 500ms latency per position update (from CONCERNS.md) | Use async callbacks | At > 1 drone or fast maneuvers |
| O(n^2) trilateration validation | Slow anchor setup for large networks | Only needed for > 8 anchors | Scales to 50+ anchors |
| Single radio per drone | Cannot dispatch multiple drones simultaneously | Use different channels or multiple radios | Multi-drone demos |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No CRTP authentication | Someone else could send commands to drones | Fly in controlled RF environment |
| Web dashboard unauthenticated | Unauthorized mission dispatch | Add auth layer before production |
| OTA without verification | Malicious firmware pushed to drones | Sign firmware, verify before flash |
| Agent API without rate limiting | DoS from rapid dispatch requests | Implement rate limiting |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|------------------|
| No feedback during mission | User doesn't know if command succeeded | Show status updates, success/failure |
| Stale dashboard data | User makes decisions on old info | Show last-update timestamp, gray out stale |
| No emergency stop in UI | User cannot stop runaway drone | Prominent red button always visible |
| Confusing drone IDs | User doesn't know which drone is which | Consistent naming, color coding in UI |

---

## "Looks Done But Isn't" Checklist

- [ ] **Safety kill switch:** Often missing — verify it stops motors within 500ms
- [ ] **Position confidence:** Often missing — verify position variance displayed in UI
- [ ] **Reconnection logic:** Often missing — verify drone marked "offline" on radio drop
- [ ] **Pre-mission health check:** Often missing — verify status endpoint polled before dispatch
- [ ] **OTA rollback:** Often missing — verify canary deployment before fleet push
- [ ] **Mission queue:** Often missing — verify "busy" status returned when queue full

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Bricked OTA | HIGH | Use USB DFU to reflash (requires physical access) |
| Lost radio link | MEDIUM | Wait for reconnection, or manual recovery |
| Position lock lost | LOW | Drone hovers, wait for lock, or land manually |
| Agent race condition | LOW | Cancel mission, re-dispatch with lease |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Missing safety kill switch | Phase 1 (Agent API) | Test emergency stop, verify < 500ms motor stop |
| UWB positioning failure | Phase 2 (Positioning fallback) | Test LPS at venue, validate optical flow fallback |
| Agent API race conditions | Phase 1 (Agent API) | Concurrent dispatch test, verify state machine |
| OTA bricked drones | Phase 3 (OTA deployment) | Canary deployment test, verify rollback |
| Dashboard false health | Phase 1 + Phase 2 | Pre-mission health check test |
| Hardcoded URIs | Phase 1 (Agent API) | Config file test, verify registry lookup |
| No reconnection logic | Phase 1 (Agent API) | Radio drop test, verify reconnection |
| Mission scheduling timeouts | Phase 1 (Agent API) | Overlap test, verify queue behavior |

---

## Sources

- Existing codebase concerns analysis: `.planning/codebase/CONCERNS.md`
- Architecture patterns: `.planning/codebase/ARCHITECTURE.md`
- Project requirements: `.planning/PROJECT.md`
- Crazyflie firmware commander watchdog: Context7 `/bitcraze/crazyflie-firmware`
- Domain knowledge: Drone swarm control best practices, safety-critical system design

---

*Pitfalls research for: Drone Swarm Agent Integration*
*Researched: 2026-02-27*
