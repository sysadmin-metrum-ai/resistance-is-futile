---
phase: 02-dashboard-peripherals
plan: 02
type: execute
wave: 2
depends_on:
  - 01
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
Build dashboard UI components: DroneCard, DroneMap, MissionQueue, LLMTerminal, KillSwitch. Integrate into main page layout with grid.
</objective>

**Tasks:**

1. **Build DroneCard component**
   - Display drone name, state badge (color-coded)
   - Show battery percentage with icon (color by level)
   - Show connection quality percentage
   - Handle error state with warning icon

2. **Build DroneMap component**
   - Use react-simple-maps for 2D visualization
   - Render drone positions as markers
   - Color markers by drone state
   - Add simple coordinate scaling for display

3. **Build MissionQueue component**
   - List all missions with status badges
   - Show drone assignment (if any)
   - Display waypoints summary
   - Color-code by status (pending=yellow, running=blue, completed=green, failed=red)

4. **Build LLMTerminal component**
   - Wrap xterm.js for terminal display
   - Configure dark theme (like Claude Code)
   - Handle token streaming via prop callback
   - Limit scrollback to prevent memory leaks

5. **Build KillSwitch component**
   - Red destructive button
   - Confirmation step before triggering
   - Loading state during API call
   - Success/error feedback

6. **Integrate components into main dashboard page**
   - Grid layout: drones left, map center, missions right
   - Terminal panel at bottom (collapsible)
   - Kill switch in header or safety section
