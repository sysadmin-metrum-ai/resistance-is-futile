# Phase 7: Demo Missions - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Execute impressive flight demonstrations at booth. Four demo types:
1. Pattern flights (circle, ellipse, figure-8)
2. Point-to-point missions with hover and return
3. Agent-triggered demo (AI dispatching drone)
4. Periodic patrol demo (scheduled autonomous missions)

</domain>

<decisions>
## Implementation Decisions

### Demo Types
- Pattern flights: Pre-defined waypoint sequences
- Point-to-point: Simple A→B missions
- Agent-triggered: Show AI dispatching from prompt
- Periodic patrol: Scheduled mission execution

### Demo Execution
- How to trigger: Planner's discretion (API, Dashboard, or both)
- Waypoint definitions: Hardcoded or configurable (Planner's discretion)

### Claude's Discretion
- Exact flight patterns
- UI for triggering demos
- Mission parameters

</decisions>

<specifics>
## Existing Infrastructure

- Mission submission API exists
- Drone control endpoints exist (takeoff, land, go_to)
- Dashboard can submit missions

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>

---

*Phase: 07-demo-missions*
*Context gathered: 2026-02-28*
