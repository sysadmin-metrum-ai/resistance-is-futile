---
phase: 02-dashboard-peripherals
plan: 01
type: execute
wave: 1
depends_on: []
autonomous: true

requirements:
  - DASH-01
  - DASH-02
  - DASH-03
  - DASH-04

user_setup: []

files_modified: []
---

<objective>
Initialize Next.js + shadcn/ui dashboard foundation with TypeScript types and API client wrapper. This establishes the frontend infrastructure for all subsequent dashboard plans.
</objective>

**Tasks:**

1. **Initialize Next.js project with shadcn/ui**
   - Run `npx create-next-app@latest dashboard --typescript --tailwind --eslint`
   - Initialize shadcn/ui with default settings
   - Add core components: card, button, badge, table, tabs, alert
   - Install dependencies: @tanstack/react-query, use-sse, xterm, @xterm/react, react-simple-maps, d3-scale

2. **Create TypeScript types mirroring backend**
   - Define `Drone` interface (id, uri, name, state, battery, connection_quality, enabled, x, y)
   - Define `Mission` interface (id, mission_id, drone_id, waypoints, duration_seconds, status, callback_url, result)
   - Define `SSEMessage` type for real-time events

3. **Build API client wrapper**
   - Create axios client with base URL from env
   - Add X-API-Key header interceptor
   - Export typed functions: getDrones(), getMissions(), createMission(), triggerKillSwitch()

4. **Create basic dashboard layout**
   - Setup DashboardLayout component with header, main content area
   - Add customizable logo support via public/logos/ directory
   - Add env configuration for API URL and key
