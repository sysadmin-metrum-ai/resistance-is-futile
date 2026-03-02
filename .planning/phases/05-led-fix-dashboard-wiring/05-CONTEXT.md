# Phase 5: LED Fix + Dashboard Wiring - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Gap closure from v1.0 audit. Fix three specific integration issues:
1. LED API uses hardcoded drone URI (bug in src/api/routes/led.py)
2. Camera API exists but not wired to Dashboard
3. LED API exists but not controllable from Dashboard

This is technical debt closure — scope is fixed by the audit findings.

</domain>

<decisions>
## Implementation Decisions

### LED URI Fix
- Fetch drone URI from PostgREST database instead of hardcoding `f"drone-{drone_id}"`
- Fix locations: led.py lines 83, 123, 149

### Camera Wiring
- Camera API already exists at `/images/*` endpoints
- Add image viewing capability to Dashboard (how is Planner's discretion)

### LED Dashboard Control
- LED API already exists at `/led/{drone_id}/*` endpoints
- Add LED control UI to Dashboard (how is Planner's discretion)

### Claude's Discretion
- Exact UI placement for LED controls
- Exact UI placement for camera viewer
- API client implementation details
- State management approach

</decisions>

<specifics>
## Specific Issues from v1.0 Audit

1. **led-hardcoded-uri** (Phase 2)
   - Path: src/api/routes/led.py
   - Lines: 83, 123, 149
   - Issue: `drone_uri = f"drone-{drone_id}"` should fetch from PostgREST

2. **CAM-01, CAM-02** (Phase 2 tech debt)
   - Camera API exists but not consumed by Dashboard

3. **LED-01** (Phase 2 tech debt)
   - LED API exists but not called from Dashboard

</specifics>

<deferred>
## Deferred Ideas

None — all items are within the gap closure scope.

</deferred>

---

*Phase: 05-led-fix-dashboard-wiring*
*Context gathered: 2026-02-28*
