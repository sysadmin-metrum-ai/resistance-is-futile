# Phase 6: Demo Validation - Research

**Researched:** 2026-02-28
**Domain:** Pre-flight validation, mission validation, system health monitoring
**Confidence:** HIGH

## Summary

Phase 6: Demo Validation focuses on ensuring the drone swarm system is ready for live demonstration. The existing backend already provides pre-flight check (`/safety/pre-flight/{drone_id}`) and health check (`/safety/health-check`) endpoints. The frontend already has API client functions for these. The main gap is **mission validation** - validating that a planned mission can actually be executed before submission.

**Primary recommendation:** Create a new `/safety/validate-mission` endpoint that validates mission feasibility (battery, waypoint range, drone state), then add a validation panel in the Dashboard that orchestrates pre-flight + health + mission validation before allowing mission submission.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Pre-flight checks: API endpoints already exist at `/safety/pre-flight/{drone_id}`
- Pre-flight display: Use existing DroneCard or add validation panel (Planner's discretion)
- Health checks: API endpoints already exist at `/safety/health-check`
- Health display: Already shows in Dashboard (refetchInterval: 30000)

### Claude's Discretion
- Exact UI placement for validation controls
- Validation sequence/ordering
- Error handling approach

### Deferred Ideas (OUT OF SCOPE)
None - all items within scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VALID-01 | Pre-flight checklist validates all systems before takeoff | Backend endpoint exists: `/safety/pre-flight/{drone_id}`, Frontend `preFlightCheck()` exists |
| VALID-02 | Mission validation confirms planned paths are executable | **GAP** - Need new endpoint to validate mission feasibility |
| VALID-03 | System health check reports battery, connection, positioning status | Backend endpoint exists: `/safety/health-check`, Frontend `healthCheckDrone()`/`healthCheckAllDrones()` exists |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | Latest | Backend API framework | Already in use (Phase 1) |
| React + TypeScript | Next.js 16 | Frontend framework | Already in use (Phase 2) |
| React Query | Latest | Server state management | Already in use (Phase 2) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| axios | Latest | HTTP client | Already in use |
| shadcn/ui | Latest | UI components | Already in use |

**Installation:**
No new packages needed - all required APIs and client functions already exist.

---

## Architecture Patterns

### Recommended Project Structure
```
src/api/routes/
├── safety.py           # Existing - pre-flight, health-check endpoints
└── missions.py         # Existing - mission submission

dashboard/src/
├── lib/api.ts          # Existing - preFlightCheck, healthCheckDrone, healthCheckAllDrones
├── components/
│   ├── ValidationPanel.tsx   # NEW - orchestrates validation workflow
│   └── MissionForm.tsx       # Existing - add validation before submit
```

### Pattern 1: Mission Validation Endpoint

**What:** Backend endpoint to validate if a planned mission can be executed
**When to use:** Before mission submission to prevent failed missions

**Backend implementation (new endpoint in safety.py):**
```python
class MissionValidationRequest(BaseModel):
    drone_id: int
    waypoints: List[Waypoint]
    duration_seconds: int

class MissionValidationResponse(BaseModel):
    valid: bool
    checks: dict  # battery_sufficient, waypoints_in_range, drone_ready
    warnings: List[str]

@router.post("/validate-mission", response_model=MissionValidationResponse)
async def validate_mission(
    request: MissionValidationRequest,
    drone_manager: DroneManager = Depends(get_drone_manager),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """
    Validate that a mission can be executed by the target drone.
    """
    # Check 1: Drone exists and is ready
    # Check 2: Battery sufficient for duration (estimate: 1% per 30 seconds)
    # Check 3: Waypoints within operational range (max 10m from origin for demo)
    # Returns: valid (bool), checks (dict), warnings (list)
```

**Frontend API client (new function in api.ts):**
```typescript
export async function validateMission(
  droneId: number,
  waypoints: Waypoint[],
  durationSeconds: number
): Promise<MissionValidationResponse> {
  const response = await apiClient.post<MissionValidationResponse>('/safety/validate-mission', {
    drone_id: droneId,
    waypoints,
    duration_seconds: durationSeconds,
  });
  return response.data;
}
```

### Pattern 2: Validation Panel Component

**What:** UI component that orchestrates validation workflow
**When to use:** Before mission submission in Dashboard

**Component structure:**
```
ValidationPanel
├── PreFlightSection (calls preFlightCheck)
├── HealthSection (calls healthCheckDrone)
└── MissionValidationSection (calls validateMission)
```

### Pattern 3: Sequential Validation Workflow

**What:** Run validations in order, fail fast
**When to use:** User clicks "Validate" button before submitting mission

```
1. Pre-flight check (fast, local data)
   └─ If fail: show errors, disable submit
2. Health check (requires drone connection)
   └─ If fail: show errors, disable submit
3. Mission validation (battery + waypoints)
   └─ If fail: show specific issues
4. All pass: enable submit button
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Battery estimation | Custom calculation | Use empirical rule: ~1% per 30 seconds | Simple, works for demo |
| Connection retry logic | Custom retry | FlightController.health_check() | Already handles timeouts |
| State management | Custom state | React Query with refetchInterval | Already in use |

---

## Common Pitfalls

### Pitfall 1: Validation Not Blocking Mission Submission
**What goes wrong:** User can submit mission even if validation fails
**Why it happens:** No enforcement in UI - button not disabled
**How to avoid:** Disable submit button when `validation.valid === false`
**Warning signs:** Users reporting failed missions despite "validation"

### Pitfall 2: Stale Validation Results
**What goes wrong:** Validation passes but drone state changes before takeoff
**Why it happens:** Validation is a snapshot, not continuous
**How to avoid:** Re-validate immediately before takeoff, or add time-to-live to validation results
**Warning signs:** Battery suddenly drops to 0% during mission

### Pitfall 3: Battery Estimation Too Optimistic
**What goes wrong:** Mission runs out of battery mid-flight
**Why it happens:** Estimating based on ideal conditions
**How to avoid:** Add safety margin (e.g., require battery >= duration/25 + 20%)
**Warning signs:** Drones landing mid-mission

### Pitfall 4: Waypoint Range Not Enforced
**What goes wrong:** User plans mission outside UWB coverage area
**Why it happens:** No bounds checking on waypoints
**How to avoid:** Define max operational radius (e.g., 5m from anchor origin for demo)
**Warning signs:** Drone fails to reach waypoints, mission timeout

---

## Code Examples

### Existing Pre-Flight Check (Reference)
```typescript
// Source: dashboard/src/lib/api.ts
export async function preFlightCheck(droneId: number): Promise<PreFlightCheckResponse> {
  const response = await apiClient.get<PreFlightCheckResponse>(`/safety/pre-flight/${droneId}`);
  return response.data;
}
```

### Existing Health Check (Reference)
```typescript
// Source: dashboard/src/lib/api.ts
export async function healthCheckDrone(droneId: number): Promise<HealthCheckResponse> {
  const response = await apiClient.get<HealthCheckResponse>(`/safety/health-check/${droneId}`);
  return response.data;
}

export async function healthCheckAllDrones(): Promise<BulkHealthCheckResponse> {
  const response = await apiClient.post<BulkHealthCheckResponse>('/safety/health-check');
  return response.data;
}
```

### Backend Pre-Flight Implementation (Reference)
```python
# Source: src/api/routes/safety.py (lines 249-309)
@router.get("/pre-flight/{drone_id}", response_model=PreFlightCheckResponse)
async def pre_flight_check(drone_id: int, ...):
    checks = {}
    # Check 1: Enabled status
    checks["enabled"] = drone.get("enabled", True)
    # Check 2: State is idle
    checks["state_idle"] = drone.get("state", "offline") == "idle"
    # Check 3: Battery threshold (>= 20%)
    checks["battery_ok"] = battery >= DroneManager.MIN_BATTERY_THRESHOLD
    # Check 4: Connection quality (>= 70%)
    checks["connection_ok"] = health.connection_quality >= DroneManager.MIN_CONNECTION_QUALITY
    ready = all([checks["enabled"], checks["state_idle"], checks["battery_ok"], checks["connection_ok"]])
    return PreFlightCheckResponse(ready=ready, checks=checks)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual drone health check | API-driven health check | Phase 1 | Automated, real-time |
| No pre-flight validation | Pre-flight endpoint | Phase 1 | Prevents unsafe launches |
| Submit first, fail later | Validate before submit | **Phase 6 (this phase)** | Prevents failed missions |

**Deprecated/outdated:**
- None for this phase - building on existing safety infrastructure

---

## Open Questions

1. **Battery estimation formula**
   - What we know: MIN_BATTERY_THRESHOLD = 20%, demo flights are ~1-2 minutes
   - What's unclear: Exact battery consumption rate for Crazyflie with payload
   - Recommendation: Use conservative estimate (1% per 30 seconds) + 20% buffer

2. **Waypoint range limits**
   - What we know: UWB anchors define the operational volume
   - What's unclear: Max distance from anchor origin for reliable positioning
   - Recommendation: Default to 5m radius for demo (conservative), make configurable

3. **Validation time-to-live**
   - What we know: Validation results are snapshots
   - What's unclear: How fresh validation needs to be before takeoff
   - Recommendation: Require re-validation if > 60 seconds old

---

## Sources

### Primary (HIGH confidence)
- Existing code: `/home/cgadgil/src/resistance-is-futile/src/api/routes/safety.py` - Pre-flight and health check implementation
- Existing code: `/home/cgadgil/src/resistance-is-futile/dashboard/src/lib/api.ts` - Frontend API client
- Existing code: `/home/cgadgil/src/resistance-is-futile/src/services/drone_manager.py` - DroneManager with MIN_BATTERY_THRESHOLD=20, MIN_CONNECTION_QUALITY=70

### Secondary (MEDIUM confidence)
- Context from 06-CONTEXT.md - User decisions and existing infrastructure
- Context from REQUIREMENTS.md - VALID-01, VALID-02, VALID-03 requirements
- Context from STATE.md - Current project state and accumulated context

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing APIs and patterns already in codebase
- Architecture: HIGH - Following established patterns from Phase 1/2
- Pitfalls: HIGH - Based on existing safety code review and domain knowledge

**Research date:** 2026-02-28
**Valid until:** 30 days (validation patterns are stable)
