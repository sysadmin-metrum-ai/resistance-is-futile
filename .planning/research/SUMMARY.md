# Project Research Summary

**Project:** Drone Swarm Agent Integration
**Domain:** Drone Swarm Control for AI Agent Integration & Datacenter Inspection
**Researched:** 2026-02-27
**Confidence:** MEDIUM

## Executive Summary

This project builds a drone swarm control platform enabling AI agents to programmatically dispatch physical missions for datacenter inspection. The system extends existing Crazyflie 2.1 + Loco Positioning hardware with an Agent API and web dashboard. Research strongly recommends FastAPI (async, native WebSocket support), React for the dashboard, and PostgreSQL + Redis for state management. The core value proposition is bridging software monitoring (IT Ops agents) with physical drone capabilities.

The critical path involves building a mission queue with drone ownership semantics before exposing an external Agent API. Safety must be built in from day one — a kill switch, geofencing, and position confidence monitoring are non-negotiable for live demos. The primary risk is UWB interference at the Dell Tech World 2026 venue, requiring optical flow fallback that should be validated before the event.

## Key Findings

### Recommended Stack

FastAPI is the clear choice for this project due to its native async support and built-in WebSocket handling — critical for real-time drone telemetry. React 18 provides the component ecosystem needed for complex dashboard state, while PostgreSQL ensures ACID compliance for mission logs and Redis handles sub-millisecond telemetry caching. Docker enables reproducible OTA deployments.

**Core technologies:**
- **FastAPI 0.115+** — REST API server with native WebSocket support for real-time telemetry
- **React 18.x** — Web dashboard with strong TypeScript ecosystem
- **PostgreSQL 16+** — ACID-compliant mission logs and drone registry
- **Redis 7.x** — Real-time telemetry cache and pub/sub for WebSocket broadcast
- **cflib** — Python library for Crazyflie control (existing)

**Supporting:** Pydantic 2.x for validation, SQLAlchemy 2.x for ORM, TailwindCSS for dashboard styling.

### Expected Features

**Must have (table stakes):**
- **Agent API** — REST endpoints for programmatic mission dispatch; requires mission queue and drone allocation
- **Mission Queue** — Async execution with retry logic; prevents race conditions from concurrent agent requests
- **Fleet Management** — Track drone state (battery, position, status) per drone URI
- **Kill Switch** — Emergency stop all drones; safety-critical for live demos
- **Web Dashboard** — Real-time position visualization, mission control, manual override

**Should have (competitive):**
- **LED Status Indication** — Visual drone state feedback for audience
- **Human-in-the-Loop Override** — Operator can pause/abort autonomous missions
- **Periodic Scheduling** — Cron-style mission triggers
- **Geofencing** — Software boundary enforcement

**Defer (v2+):**
- **OTA Mission Code Deployment** — Dynamic mission logic updates (requires stable base first)
- **Thermal Camera Integration** — High complexity, datacenter payload
- **Issue-Triggered Dispatch** — Webhook integration from monitoring alerts
- **Positioning Fallback** — Optical flow for UWB interference venues

### Architecture Approach

The system follows a layered architecture: External Agents -> Mission Control API -> Mission Orchestration -> Drone Controller -> Hardware. The key architectural patterns are **CQRS** (separate reads for high-frequency status from writes for mission dispatch), **Event-Driven Mission Execution** (async queue for parallel drone operations), and **Safety Watchdog** (background monitoring for emergency protocols).

Major components:
1. **Mission Control API** (FastAPI) — REST endpoints for agent dispatch, mission CRUD
2. **Mission Queue** — Async execution, priority handling, drone ownership
3. **Swarm Controller** — cflib Swarm class wrapper, flight command execution
4. **Safety Watchdog** — Geofence checking, emergency landing triggers
5. **State Store** — In-memory + persistence for drone positions, battery

### Critical Pitfalls

1. **Missing Safety Kill Switch** — Implement heartbeat-based kill switch; if no command for X seconds, trigger emergency land. Phase 1 must include this.

2. **UWB Positioning Failure at Venue** — Dell Tech World 2026 has 5GHz WiFi interference. Pre-validate LPS at venue and implement optical flow fallback before demo day.

3. **Agent API Race Conditions** — Multiple agents sending concurrent commands causes conflicts. Implement drone ownership/lease model and mission queue with FIFO ordering.

4. **OTA Deployment Bricking Drones** — Push buggy firmware to all drones simultaneously. Implement canary deployment (1 drone first, validate, then roll out) and require 80%+ battery.

5. **Dashboard False Health** — Stale data shows "ready" when drone is actually unavailable. Implement pre-mission health check API and stale-data warning indicators.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation & Safety
**Rationale:** Safety must be built before any autonomous operation; cannot expose API without kill switch
**Delivers:** FastAPI skeleton, drone registry with URI mapping, basic connectivity test, safety watchdog with geofencing
**Addresses:** Agent API (partial), Kill Switch, Fleet Management
**Avoids:** Pitfall 1 (Missing Safety Kill Switch), Pitfall 3 (Race Conditions), Pitfall 6 (Hardcoded URIs)

### Phase 2: Core Mission Execution
**Rationale:** Need working mission queue and flight control before agent integration
**Delivers:** Mission queue implementation, swarm controller wrapper, takeoff/hover/land commands, pre-mission health checks
**Addresses:** Mission Queue, Basic Flight Control, Drone Health Monitoring
**Avoids:** Pitfall 7 (No Reconnection Logic), Pitfall 8 (Scheduling Timeouts)

### Phase 3: Agent Integration
**Rationale:** Agents should dispatch to a system that is already safe and tested
**Delivers:** Mission dispatch endpoint, drone status endpoint, webhook callbacks for completion, API key validation
**Addresses:** Agent API, Webhook callbacks
**Avoids:** Pitfall 5 (Dashboard False Health)

### Phase 4: Dashboard & Visualization
**Rationale:** Operators need visual feedback for mission control
**Delivers:** Real-time WebSocket state, mission visualization, drone position plotting, manual override controls
**Addresses:** Web Dashboard, Human-in-the-Loop Override
**Avoids:** Pitfall 5 (stale data display)

### Phase 5: Advanced Features
**Rationale:** Only after stable core; these features add complexity
**Delivers:** OTA deployment service, optical flow positioning fallback, periodic scheduling
**Addresses:** OTA Deployment, LED Status, Geofencing, Periodic Scheduling, Positioning Fallback
**Avoids:** Pitfall 2 (UWB Failure), Pitfall 4 (OTA Bricked Drones)

### Phase Ordering Rationale

- **Safety first:** Kill switch and safety watchdog must exist before any external API exposure (PITFALLS.md explicitly maps this)
- **Core before agents:** Mission queue and flight control must work before agents can reliably dispatch missions
- **Dashboard after core:** Visualization is secondary to actual mission execution capability
- **OTA last:** Dynamic code deployment is advanced; requires stable base to avoid bricking during development

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Radio reconnection behavior — needs testing with actual hardware to verify cflib reconnection latency
- **Phase 5 (OTA):** Crazyflie wireless bootloader (cload) reliability — limited documentation, may need trial-and-error

Phases with standard patterns (skip research-phase):
- **Phase 3 (Agent API):** REST API patterns well-documented; FastAPI simplifies implementation
- **Phase 4 (Dashboard):** React + WebSocket is standard pattern; no domain-specific research needed

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Technologies well-documented, Context7 sources available, industry standard |
| Features | MEDIUM | Web search unavailable during research; based on Crazyflie docs and project context |
| Architecture | MEDIUM | Standard patterns documented, but cflib integration specifics need validation |
| Pitfalls | MEDIUM | Based on existing codebase analysis and domain knowledge; web search unavailable |

**Overall confidence:** MEDIUM — Stack is solid; features and architecture follow well-known patterns; main gap is hardware-specific validation (radio reconnection, LPS interference) that can only be resolved with physical testing.

### Gaps to Address

- **LPS interference at venue:** Cannot fully validate until on-site; plan for optical flow fallback (Phase 5)
- **cflib reconnection behavior:** Need to test actual reconnection latency and failure modes
- **Multi-drone radio contention:** Architecture supports 4-6 drones; need to verify with actual hardware

## Sources

### Primary (HIGH confidence)
- Context7: /bitcraze/crazyflie-lib-python — Crazyflie Python API, Swarm interface
- Context7: /fastapi/fastapi — FastAPI WebSocket and async documentation
- Context7: /facebook/react — React component ecosystem

### Secondary (MEDIUM confidence)
- Context7: /websites/postgresql_16 — Database design patterns
- Context7: /websites/redis_io — Pub/sub patterns
- Bitcraze firmware documentation — Commander watchdog behavior

### Tertiary (LOW confidence)
- Architecture patterns — adapted from general swarm control best practices
- Pitfall analysis — based on existing codebase CONCERNS.md and domain inference

---
*Research completed: 2026-02-27*
*Ready for roadmap: yes*
