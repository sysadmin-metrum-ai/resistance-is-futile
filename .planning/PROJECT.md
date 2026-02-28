# Drone Swarm Agent Integration

## What This Is

A drone swarm platform that extends AI infrastructure agents (IT Ops, AI Datacenter Ops) with physical capabilities for datacenter inspection and surveillance. Drones can be dynamically assigned missions via an agent API, responding to issues that require physical visual inspection or thermal sensing.

## Core Value

Enable AI agents to dispatch physical drone missions for datacenter inspection — bridging the gap between software monitoring and physical reality.

## Requirements

### Validated

- ✓ Crazyflie 2.1+ drone control via Python cflib — existing
- ✓ Loco Positioning System for indoor 3D localization — existing
- ✓ Basic flight scripts (takeoff, hover, land) — existing
- ✓ drone-acharya CLI for anchor coordinate calculation — existing

### Active

- [ ] Agent API for mission dispatch (Agentfield or custom)
- [ ] Live web dashboard for mission control and visualization
- [ ] Camera module integration for visual feedback
- [ ] LED control for status indication
- [ ] OTA code deployment for dynamic mission programming
- [ ] Positioning fallback (optical flow for venue interference)
- [ ] Periodic mission scheduling
- [ ] Issue-triggered mission dispatch
- [ ] Human-in-the-loop override capability
- [ ] Demo Venue Setup (site survey, drone-acharya, node programming)
- [ ] Demo Validation (pre-flight tests, mission validation)
- [ ] Demo Missions (pattern flights, point-to-point, agent-triggered)
- [ ] Demo Booth Requirements (power, network, space, safety)

### Out of Scope

- Real-time video streaming — deferred
- Extended swarm coordination (10+ drones) — out of scope for demo
- Long-duration autonomous flight — safety constrained
- Outdoor operation — datacenter indoor focus
- Integration with existing enterprise ITSM systems — API only, no deep integration

## Context

**Existing codebase:**
- Python flight scripts using cfclient/cflib for Crazyflie control
- Go tool (drone-acharya) for Loco Positioning anchor coordinate calculation via trilateration
- Hardware: 10x Crazyflie 2.1 with Loco Positioning deck

**Venue considerations:**
- Dell Tech World 2026 — potential UWB interference from WiFi/attendee devices
- May need optical flow positioning as fallback/replacement for LPS
- Demo environment: likely simulated datacenter at booth

**Agent ecosystem:**
- Building API for agents to interact with drones
- Agentfield mentioned as potential integration point
- Default: autonomous dispatch with human-in-the-loop override

## Constraints

- **Safety**: Drones must have kill switch and geofencing — live demo, no crashes
- **Positioning**: UWB may be unreliable at venue — need optical flow fallback
- **Timeline**: Dell Tech World — May 2026 — build reusable, demo-focused
- **Hardware**: Limited to existing Crazyflies, may add brushless variants

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent API first | Agents need programmatic access before complex swarm logic | — Pending |
| Optical flow fallback | UWB interference expected at conference venue | — Pending |
| Auto + human override | Balance autonomy with safety for live demo | — Pending |

---
*Last updated: 2026-02-27 after adding demo phases*
