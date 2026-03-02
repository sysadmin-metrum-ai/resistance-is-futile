# Phase 2: Dashboard & Peripherals - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Visual mission control dashboard for displaying drone status, mission tracking, and live LLM code generation. Used at demo venue to show "what's happening behind the scenes." Separate from Phase 1 backend API.

</domain>

<decisions>
## Implementation Decisions

### UI Framework
- **React/Next.js** with **shadcn/ui** components
- Customizable logos for different demo situations
- Single custom stylesheet that can be adapted per venue
- Not server-side templating

### Real-time Updates
- **Server-Sent Events (SSE)** for receiving updates
- Used for: drone status changes, mission progress, LLM streaming output
- Simpler than WebSockets, works well for one-way streaming

### LLM Code Display
- **Terminal-style panel** showing streaming code as it arrives
- Similar to Claude Code output - tokens appear in real-time
- Shows "what's happening behind the scenes" at demo

### Dashboard Sections
- Drone status cards (battery, position, state)
- Missions list/tracking
- LLM code generation panel (streaming)
- Status: connected/disconnected indicators

</decisions>

<specifics>
## Specific Ideas

- "I need to be able to see drone status, missions created, code being generated live using an LLM API (can show streaming code)"
- "This is for showing whats happening behind the scenes at the demo venue"
- Customizable appearance (logos, stylesheet) for different demo situations

</specifics>

<code_context>
## Existing Code Insights

### Backend API (Phase 1)
- FastAPI at `src/main.py` with routes for missions, drones, safety
- Endpoints: POST /missions, GET /drones, /safety/kill-switch, /safety/health-check
- Redis-backed mission queue
- PostgREST for database

### Integration Points
- Dashboard will consume Phase 1 REST APIs
- SSE endpoint needed (not yet implemented) - connects to backend
- API key authentication via X-API-Key header

### No Existing Frontend
- This is greenfield - no existing React/Vue code
- Start fresh with Next.js + shadcn

</code_context>

<deferred>
## Deferred Ideas

- Mobile-responsive version - future phase
- Authentication/user management - separate phase if needed
- Historical mission analytics - separate phase

</deferred>

---

*Phase: 02-dashboard-peripherals*
*Context gathered: 2026-02-28*
