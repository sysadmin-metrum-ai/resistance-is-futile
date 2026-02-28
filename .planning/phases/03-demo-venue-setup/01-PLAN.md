---
wave: 1
depends_on: []
files_modified:
  - .planning/STATE.md
  - .planning/ROADMAP.md
  - .planning/REQUIREMENTS.md
autonomous: false
---

# Phase 3: Demo Venue Setup - Plan

## Phase Goal

Enable rapid venue setup for demo deployment by documenting site survey procedure, integrating with drone-acharya for anchor coordinate generation, and pushing coordinates to Loco Positioning nodes.

## Requirements Coverage

| Requirement | Description | Status |
|-------------|-------------|--------|
| VENUE-01 | Site survey procedure documents anchor position measurement steps | Pending - needs documentation |
| VENUE-02 | drone-acharya generates anchor coordinates from measurement input | Exists - needs verification |
| VENUE-03 | Coordinates pushed to Loco Positioning nodes via radio API | Pending - needs implementation |

## Must-Haves (Goal-Backward Verification)

The phase is complete when:
1. [ ] Site survey procedure document exists at `docs/venue-survey-procedure.md`
2. [ ] User can run `drone-acharya template --nodes 6` to generate measurement template
3. [ ] User can run `drone-acharya solve` to generate anchor coordinates
4. [ ] Script `scripts/push-anchors.py` exists and can push coordinates via Crazyradio
5. [ ] Script `scripts/verify-position.py` exists for test flight verification
6. [ ] drone-acharya tests pass: `go test ./tools/drone-acharya/...`

## Tasks

### Task 1: Document Site Survey Procedure
**Purpose:** Create clear step-by-step documentation for measuring anchor positions

**Requirements addressed:** VENUE-01

**Files to create:**
- `docs/venue-survey-procedure.md`

**Files to modify:**
- None

**Steps:**
1. Create `docs/venue-survey-procedure.md` with:
   - Equipment needed (laser distance meter, Crazyradio, Loco Positioning nodes)
   - Anchor placement guidelines (minimum 4 anchors, recommend 6+, avoid collinearity, 3D volume)
   - Step-by-step measurement workflow
   - Measurement template generation using `drone-acharya template`
   - Tips for accurate measurements (measure twice, use meters, avoid interference)
   - Troubleshooting common measurement errors

**Verification:**
- Document is created and follows the manual measurement workflow from CONTEXT.md
- Document references drone-acharya for template generation
- Document includes anchor placement diagrams or descriptions

---

### Task 2: Implement Anchor Programming Script
**Purpose:** Push computed anchor coordinates to Loco Positioning nodes via Crazyradio

**Requirements addressed:** VENUE-03

**Files to create:**
- `scripts/push-anchors.py`

**Files to modify:**
- None

**Steps:**
1. Create `scripts/push-anchors.py` that:
   - Accepts anchor coordinates via file (JSON or Python format from drone-acharya --crazyflie output)
   - Uses cflib to communicate with Loco Positioning nodes via Crazyradio
   - Implements Loco Positioning Protocol (LPP) for anchor position programming
   - Supports specifying radio address (e.g., 0/80/2M)
   - Reports success/failure for each anchor
   - Handles connection errors gracefully

2. The script should follow this workflow:
   ```bash
   python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M
   ```

**Research notes:**
- cflib provides LPP (Loco Positioning Protocol) support
- Need to verify exact API calls - may require testing with physical hardware
- cfloader is an alternative but may be limited to firmware OTA

**Verification:**
- Script exists and is executable
- Script accepts anchor coordinates from drone-acharya output format
- Script documents required dependencies (cflib, Crazyradio)

---

### Task 3: Implement Test Flight Verification Script
**Purpose:** Verify positioning accuracy with a test flight pattern

**Requirements addressed:** VENUE-03 (verification part)

**Files to create:**
- `scripts/verify-position.py`

**Files to modify:**
- None

**Steps:**
1. Create `scripts/verify-position.py` that:
   - Accepts pattern type (square, circle, figure-8) and size parameters
   - Commands drone to execute the pattern via the existing API
   - Records position estimates from Loco Positioning during flight
   - Computes error between expected and actual positions
   - Reports pass/fail based on threshold (default: <20cm RMS error)
   - Outputs summary statistics

2. The script should follow this workflow:
   ```bash
   python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2
   ```

**Verification:**
- Script exists and is executable
- Script integrates with existing mission API from Phase 1/2
- Script defines acceptable error threshold (documented)
- Script reports pass/fail clearly

---

### Task 4: Verify and Extend drone-acharya Tests
**Purpose:** Ensure existing tool has adequate test coverage

**Requirements addressed:** VENUE-02

**Files to modify:**
- `tools/drone-acharya/integration_test.go` (if needed)

**Steps:**
1. Run existing tests: `go test ./tools/drone-acharya/... -v`
2. If tests pass, verify edge case coverage is adequate:
   - Collinear anchor detection
   - Invalid distance matrix handling
   - 6+ anchor configurations
3. If gaps found, add additional test cases to `integration_test.go`

**Verification:**
- All tests pass
- Test coverage includes edge cases from RESEARCH.md pitfalls

---

## Dependencies

```
Task 1 (Survey Docs)
    |
    +---> Task 2 (Push Anchors) ---> Task 3 (Verify)
    |
    +---> Task 4 (Verify Tests)
```

**Wave assignments:**
- **Wave 1 (can run in parallel):**
  - Task 1: Document Site Survey Procedure
  - Task 4: Verify drone-acharya tests
- **Wave 2 (depends on Task 1):**
  - Task 2: Implement Anchor Programming Script
  - Task 3: Implement Test Flight Verification Script

---

## Notes

- Task 2 and 3 may require physical hardware (Crazyradio, Loco Positioning nodes) for full verification
- The cfloader tool was mentioned in user decisions but research suggests it may be for firmware OTA only - script should use cflib directly
- Anchor placement is critical - documentation should emphasize 3D volume (not collinear) and recommend 6+ anchors

---

*Plan created: 2026-02-28*
