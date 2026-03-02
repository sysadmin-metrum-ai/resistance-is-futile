---
name: phase-06-demo-validation
description: Validate system readiness before live demo - pre-flight checklist, mission validation, system health check
wave: 1
depends_on: []
files_modified:
  - src/api/routes/safety.py
  - dashboard/src/lib/api.ts
  - dashboard/src/types/index.ts
  - dashboard/src/components/ValidationPanel.tsx
autonomous: false
requirements:
  - VALID-01
  - VALID-02
  - VALID-03
---

# Phase 6: Demo Validation Plan

## Goal
Validate system readiness before live demo with three success criteria:
1. Pre-flight checklist executes and reports all systems go
2. Mission validation confirms drone can execute planned flight paths
3. System health check reports battery, connection, positioning status

## Must-Haves (Goal-Backward)

| Requirement | Status | What Exists | What to Build |
|-------------|--------|-------------|---------------|
| VALID-01 | PARTIAL | `/safety/pre-flight/{drone_id}` endpoint, `preFlightCheck()` frontend API | Integrate into ValidationPanel UI |
| VALID-02 | GAP | Nothing | New `/safety/validate-mission` endpoint, frontend API client, ValidationPanel integration |
| VALID-03 | DONE | `/safety/health-check` endpoint, `healthCheckDrone()`/`healthCheckAllDrones()` frontend API | Already shows in Dashboard (refetchInterval: 30000) |

## Tasks

### Task 1: Add Mission Validation Endpoint (VALID-02 - GAP CLOSURE)
**File:** `src/api/routes/safety.py`

Add new endpoint `/safety/validate-mission` that validates if a planned mission can be executed:

```python
class MissionValidationRequest(BaseModel):
    drone_id: int
    waypoints: List[Waypoint]  # Reuse from missions.py
    duration_seconds: int

class MissionValidationResponse(BaseModel):
    valid: bool
    checks: dict  # battery_sufficient, waypoints_in_range, drone_ready
    warnings: List[str]
```

**Validation logic:**
1. **Drone ready check:** Drone exists, enabled, state is idle
2. **Battery sufficient check:** `battery >= (duration_seconds / 30) + 20` (conservative: 1% per 30s + 20% buffer)
3. **Waypoints in range check:** All waypoints within max operational radius (default 5m from origin for demo)

### Task 2: Add Frontend API Client for Mission Validation
**File:** `dashboard/src/lib/api.ts`

Add `validateMission()` function:
```typescript
export async function validateMission(
  droneId: number,
  waypoints: Waypoint[],
  durationSeconds: number
): Promise<MissionValidationResponse>
```

**File:** `dashboard/src/types/index.ts`

Add types:
```typescript
export interface MissionValidationRequest {
  drone_id: number;
  waypoints: Waypoint[];
  duration_seconds: number;
}

export interface MissionValidationResponse {
  valid: boolean;
  checks: {
    drone_ready: boolean;
    battery_sufficient: boolean;
    waypoints_in_range: boolean;
  };
  warnings: string[];
}
```

### Task 3: Add ValidationPanel Component
**File:** `dashboard/src/components/ValidationPanel.tsx`

Create new component that orchestrates validation workflow:
- Uses existing `preFlightCheck()` and `healthCheckDrone()` APIs
- Uses new `validateMission()` API
- Displays pass/fail indicators with details
- Disables mission submit button when validation fails

**UI Structure:**
```
ValidationPanel
├── PreFlightSection (calls preFlightCheck)
│   └── Shows: enabled, state_idle, battery_ok, connection_ok
├── HealthSection (calls healthCheckDrone)
│   └── Shows: battery level, connection quality
└── MissionValidationSection (calls validateMission)
    └── Shows: drone_ready, battery_sufficient, waypoints_in_range
```

**Validation Workflow (Sequential, Fail-Fast):**
1. Pre-flight check (fast, local data)
2. Health check (requires drone connection)
3. Mission validation (battery + waypoints)
4. All pass: enable submit button

## Wave Assignments

**Wave 1 (Sequential - each task builds on previous):**
- Task 1: Add mission validation endpoint (foundation)
- Task 2: Add frontend API client (depends on Task 1)
- Task 3: Add ValidationPanel component (depends on Task 2)

## Dependencies

- Task 1 has no dependencies (pure backend addition)
- Task 2 depends on Task 1 (needs endpoint to exist)
- Task 3 depends on Task 2 (needs API client function)

## Verification Criteria

1. **VALID-01 (Pre-flight):** `GET /safety/pre-flight/{drone_id}` returns `{"ready": true, "checks": {...}}` when all checks pass
2. **VALID-02 (Mission validation):** `POST /safety/validate-mission` returns `{"valid": true, "checks": {...}}` when mission can execute
3. **VALID-03 (Health check):** `GET /safety/health-check/{drone_id}` returns battery and connection quality

## Notes

- Pre-flight (VALID-01) and Health (VALID-03) endpoints already exist - no backend work needed
- ValidationPanel should use existing DroneCard display or add validation panel (Planner's discretion per CONTEXT.md)
- Battery estimation uses conservative rule: 1% per 30 seconds + 20% buffer (per RESEARCH.md)
- Waypoint range limit: 5m default radius for demo (per RESEARCH.md)
