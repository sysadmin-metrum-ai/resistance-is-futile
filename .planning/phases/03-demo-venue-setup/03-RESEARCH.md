# Phase 3: Demo Venue Setup - Research

**Researched:** 2026-02-28
**Domain:** Crazyflie Loco Positioning System setup and anchor coordinate configuration
**Confidence:** MEDIUM

## Summary

Phase 3 enables rapid venue setup for demo deployment by documenting the site survey procedure, integrating with drone-acharya for anchor coordinate generation, and determining how to push coordinates to Loco Positioning nodes. The drone-acharya tool already exists in the codebase and provides the coordinate computation capability. The primary research gap is the exact mechanism for pushing coordinates to Loco Positioning nodes via radio API — this appears to use either cfloader for OTA-style programming or direct serial configuration of each anchor.

**Primary recommendation:** Document the complete site survey procedure using laser distance meter, use drone-acharya for coordinate generation (already implemented), and implement anchor programming via the Crazyflie radio link using the Loco Positioning deck communication protocol.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Manual measurement** with laser "tape" (distance meter) - measure distances between anchor positions manually
- **Interactive input** - user enters measurements, drone-acharya computes coordinates - CLI-based workflow for entering distance data
- **cfloader CLI** - push coordinates to Loco Positioning nodes via Crazyradio - standard tool workflow
- **Test flight pattern** - small square pattern to verify positioning accuracy - fly pattern, verify position readout matches expected

### Claude's Discretion
- Research exact mechanism for pushing coordinates to Loco Positioning nodes
- Document site survey procedure steps

### Deferred Ideas (OUT OF SCOPE)
- RTK GPS for survey - future improvement
- Automated verification scripts - future phase

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VENUE-01 | Site survey procedure documents anchor position measurement steps | laser distance meter measurement workflow documented |
| VENUE-02 | drone-acharya generates anchor coordinates from measurement input | drone-acharya tool already exists with template/solve commands |
| VENUE-03 | Coordinates pushed to Loco Positioning nodes via radio API | Crazyradio 2.0 communication protocol needs |

 implementation</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| drone-acharya | Latest (Go) | Trilateration calculator for anchor coordinates | Custom tool in codebase, generates coordinates from distance matrix |
| Crazyradio 2.0 | USB dongle | 2.4GHz radio communication with Loco Positioning nodes | Required hardware for wireless anchor programming |
| cflib | Latest | Crazyflie Python library for radio communication | Official Bitcraze library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cfloader | Latest | OTA firmware deployment tool | May be usable for anchor coordinate programming |
| Laser distance meter | Any | Manual measurement of distances between anchors | Required for VENUE-01 survey procedure |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual laser measurement | RTK GPS survey | More accurate but deferred to future |
| cfloader for anchors | Direct serial connection to each anchor | More reliable but less convenient |

**Installation:**
```bash
# drone-acharya already in codebase
go install github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya@latest

# For Crazyflie communication
pip install cfclient cflib
```

---

## Architecture Patterns

### Recommended Project Structure
```
tools/drone-acharya/        # Existing - coordinate calculator
docs/
  venue-survey-procedure.md  # New - step-by-step measurement guide
scripts/
  push-anchors.py           # New - push coordinates via radio
  verify-position.py        # New - test flight pattern verification
```

### Pattern 1: Site Survey Workflow
**What:** Manual measurement of pairwise distances between anchor nodes followed by coordinate computation
**When to use:** Setting up a new venue or repositioning anchors
**Example:**
```bash
# Step 1: Generate measurement template
drone-acharya template --nodes 6 -o distances.csv

# Step 2: Fill in measured distances (manual with laser meter)
# Edit distances.csv with actual measurements

# Step 3: Compute coordinates
drone-acharya solve distances.csv --crazyflie -o anchors.py

# Step 4: Push to Loco Positioning nodes
python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M

# Step 5: Verify with test flight
python scripts/verify-position.py --pattern square --size 1.0
```

### Pattern 2: Anchor Coordinate Programming
**What:** Push computed coordinates to Loco Positioning nodes via Crazyradio
**When to use:** After computing coordinates with drone-acharya
**Example:**
```python
# Conceptual - actual implementation needed
from cflib import crtp
from cflib.lps import lpp

# Initialize radio
crtp.init_drivers()
radio = crtp.RadioManager.open_any()

# Push anchor positions via LPP (Loco Positioning Protocol)
anchor_positions = {0: (0.0, 0.0, 0.0), 1: (4.0, 0.0, 0.0), ...}
lpp.set_anchor_positions(radio, anchor_positions)
```

### Anti-Patterns to Avoid
- **Collinear anchor placement:** Anchors in a straight line cannot provide 3D positioning — ensure anchors form a 3D volume (e.g., tetrahedron or rectangular prism)
- **Skipping validation:** Always run `drone-acharya solve --validate` before pushing coordinates — large errors indicate measurement mistakes
- **Insufficient anchor count:** Need minimum 4 anchors for 3D positioning, 6+ recommended for better coverage

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coordinate computation | Custom trilateration algorithm | drone-acharya | Already implemented with validation and error reporting |
| Distance matrix parsing | Custom CSV parser | drone-acharya input format | Handles the triangular matrix correctly |
| Radio communication | Raw CR | cflibTP packets + lpp | Official library handles protocol details |

**Key insight:** The drone-acharya tool already handles the complex trilateration mathematics with proper error handling for collinearity, inconsistent measurements, and validation.

---

## Common Pitfalls

### Pitfall 1: Inconsistent Distance Measurements
**What goes wrong:** Measured distances don't satisfy triangle inequality, causing drone-acharya to produce degenerate coordinates or warnings
**Why it happens:** Laser meter reading errors, measuring wrong pairs, units confusion (meters vs feet)
**How to avoid:**
- Use a single measurement unit consistently (meters)
- Measure each pair twice and verify
- Run with `--validate` flag and re-measure pairs with >2% error
**Warning signs:** "Negative squared distance clamped to 0" warnings

### Pitfall 2: Collinear Anchor Placement
**What goes wrong:** First three anchors (N0, N1, N2) form a straight line, causing solver to fail with fatal error
**Why it happens:** Placing anchors in a rectangle on the floor without considering 3D height
**How to avoid:**
- Place at least one anchor at different height (e.g., on a shelf or elevated position)
- Ensure N2 forms a triangle with N0-N1, not a straight line
**Warning signs:** Fatal error "Nodes 0,1,2 are collinear"

### Pitfall 3: Anchor Coordinate Programming Failure
**What goes wrong:** Coordinates successfully computed but fail to load into Loco Positioning nodes
**Why it happens:** Wrong communication protocol, radio not connected, anchor not in programming mode
**How to avoid:**
- Verify Crazyradio is recognized (`lsusb` shows `1915:7777`)
- Ensure Loco Positioning nodes are powered on and in range
- Use correct protocol (LPP for wireless programming)
**Warning signs:** "Failed to connect" or timeout errors

### Pitfall 4: Position Accuracy Worse Than Expected
**What goes wrong:** Drones localize but with 50cm+ error despite correct anchor coordinates
**Why it happens:** Anchor positions suboptimal, UWB interference, antenna orientation
**How to avoid:**
- Follow test flight pattern to verify accuracy before demo
- Place anchors at consistent height where possible
- Avoid metallic objects near anchors
**Warning signs:** Position readout drifts significantly from expected during test flight

---

## Code Examples

### drone-acharya Template Generation
```bash
# Generate template for 6 anchors
drone-acharya template --nodes 6 --format csv -o distances.csv
```

### drone-acharya Solve with Validation
```bash
# Solve and validate measurements
drone-acharya solve distances.csv --validate --crazyflie
```

### Expected Output Format (--crazyflie)
```python
anchor_positions = {
    0: (0.00, 0.00, 0.00),
    1: (4.00, 0.00, 0.00),
    2: (4.00, 3.00, 0.00),
    3: (0.00, 3.00, 0.00),
    4: (0.00, 0.00, 2.50),
    5: (4.00, 0.00, 2.50),
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual coordinate calculation | drone-acharya trilateration | 2026-02-27 | Eliminates geometry errors |
| Hardcoded anchor positions | Configurable via input file | 2026-02-27 | Enables venue reconfiguration |
| Serial cable programming | Radio-based programming (future) | This phase | Faster setup, no cable management |

**Deprecated/outdated:**
- Manual geometry calculation using spreadsheet formulas — error-prone, no validation

---

## Open Questions

1. **How exactly to push anchor coordinates via radio?**
   - What we know: cflib has Loco Positioning Protocol (LPP) support; cfloader is mentioned for OTA
   - What's unclear: Exact API calls to push anchor positions via Crazyradio
   - Recommendation: Research cflib LPP module or implement using Loco Positioning node serial interface as fallback

2. **What is the Loco Positioning node programming protocol?**
   - What we know: Nodes can be configured via serial (USB) or wirelessly
   - What's unclear: Is cfloader usable for anchor programming or only for drone firmware?
   - Recommendation: Test with physical hardware or find Bitcraze documentation

3. **Test flight verification thresholds**
   - What we know: Square pattern flight can verify positioning accuracy
   - What's unclear: What error threshold is acceptable? How to automatically detect failure?
   - Recommendation: Define acceptable accuracy (e.g., <20cm) and implement automated pass/fail

---

## Validation Architecture

> Skip this section entirely if workflow.nyquist_validation is false in .planning/config.json

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Go testing (drone-acharya) + Python (scripts) |
| Config file | None — see Wave 0 |
| Quick run command | `go test ./tools/drone-acharya/...` |
| Full suite command | `go test ./tools/drone-acharya/... -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VENUE-01 | Site survey procedure documented | Manual | N/A | No |
| VENUE-02 | drone-acharya generates coordinates | Unit | `go test ./tools/drone-acharya/...` | Yes |
| VENUE-03 | Coordinates pushed to nodes | Integration | Requires hardware | No |

### Sampling Rate
- **Per task commit:** `go test ./tools/drone-acharya/... -short`
- **Per wave merge:** Full test suite
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scripts/push-anchors.py` — implements VENUE-03 (radio API programming)
- [ ] `docs/venue-survey-procedure.md` — documents VENUE-01 (survey steps)
- [ ] `scripts/verify-position.py` — test flight pattern verification
- [ ] Go test coverage for edge cases in trilateration

---

## Sources

### Primary (HIGH confidence)
- drone-acharya source code: `/home/cgadgil/src/resistance-is-futile/tools/drone-acharya/` — verified implementation details
- drone-acharya README.md — verified CLI usage and output formats

### Secondary (MEDIUM confidence)
- Bitcraze Crazyflie documentation — Loco Positioning system general architecture
- .planning/research/FEATURES.md — mentions cfloader for OTA deployment

### Tertiary (LOW confidence)
- Web search unavailable — used existing codebase context
- Need to verify Loco Positioning anchor programming protocol with actual hardware

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - drone-acharya verified in codebase
- Architecture: MEDIUM - site survey workflow defined, anchor programming needs verification
- Pitfalls: MEDIUM - based on existing pitfall research and drone-acharya documentation

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (30 days for stable domain)
