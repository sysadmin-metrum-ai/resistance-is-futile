---
wave: 1
depends_on: []
files_modified: []
autonomous: true
must_haves:
  - "Pattern Flights — Pre-computed waypoint sequences for circle, ellipse, figure-8 that can be submitted via API"
  - "Point-to-Point — A→B missions with configurable hover duration and return-to-origin"
  - "Agent-Triggered — An agent prompt that triggers a mission programmatically"
  - "Periodic Patrol — Scheduled mission execution at fixed intervals"
---

# Phase 7: Demo Missions Plan

## Overview

Execute impressive flight demonstrations at booth with four demo types: pattern flights, point-to-point missions, agent-triggered demos, and periodic patrol demos.

## Context

**From Phase 6:** Demo validation complete. Backend APIs exist (mission submission, drone control). Dashboard can submit missions.

**Requirements (DEMO-01 through DEMO-04):**
- DEMO-01: Pattern flights (circle, ellipse, figure-8)
- DEMO-02: Point-to-point missions with hover and return
- DEMO-03: Agent-triggered demo (AI dispatching drone)
- DEMO-04: Periodic patrol demo (scheduled autonomous missions)

## Must-Haves (Goal-Backward Verification)

1. **Pattern Flights** — Pre-computed waypoint sequences for circle, ellipse, figure-8 that can be submitted via API
2. **Point-to-Point** — A→B missions with configurable hover duration and return-to-origin
3. **Agent-Triggered** — An agent prompt that triggers a mission programmatically (e.g., Claude Code calling API)
4. **Periodic Patrol** — Scheduled mission execution at fixed intervals

## Tasks

### Task 1: Waypoint Pattern Generator

```xml
<task>
<id>07-01</id>
<requirement>DEMO-01</requirement>
<name>Create waypoint pattern generator module</name>
<description>Python module to generate waypoint sequences for pattern flights (circle, ellipse, figure-8). Accepts center point, radius, altitude, and waypoint count parameters. Returns list of {x, y, z} waypoints.</description>
<files>src/demo/waypoint_patterns.py</files>
<action>Implement generate_circle(), generate_ellipse(), generate_figure8() functions</action>
<verification>Module imports without errors; generate_circle(1.0, 1.5, 12) returns 12 waypoints forming circle</verification>
<done>false</done>
</task>
```

### Task 2: Point-to-Point Mission Generator

```xml
<task>
<id>07-02</id>
<requirement>DEMO-02</requirement>
<name>Create point-to-point mission generator</name>
<description>Python module to generate A→B→A missions with hover. Accepts start point, end point, hover_seconds, altitude. Returns waypoint list with hover waypoint and return.</description>
<files>src/demo/p2p_generator.py</files>
<action>Implement generate_p2p_hover() function with configurable hover and return</action>
<verification>Module imports; generate_p2p_hover(0,0, 2,2, hover=5) returns waypoints: start → hover → end → return</verification>
<done>false</done>
</task>
```

### Task 3: Demo Scripts for Pattern Flights

```xml
<task>
<id>07-03</id>
<requirement>DEMO-01</requirement>
<name>Create pattern flight demo scripts</name>
<description>Create demo scripts (circle_demo.py, ellipse_demo.py, figure8_demo.py) that use waypoint generator + mission API to execute patterns. Each script accepts --drone-id, --altitude, --radius and submits mission.</description>
<files>src/demo/circle_demo.py, src/demo/ellipse_demo.py, src/demo/figure8_demo.py</files>
<action>Implement CLI scripts using argparse, call waypoint generator and POST /missions</action>
<verification>Each script has --help showing usage; scripts parse args without error</verification>
<done>false</done>
</task>
```

### Task 4: Demo Script for Point-to-Point

```xml
<task>
<id>07-04</id>
<requirement>DEMO-02</requirement>
<name>Create p2p mission demo script</name></parameter>
<description>Create p2p_demo.py that uses p2p generator to execute A→B→A mission. Accepts --start-x, --start-y, --end-x, --end-y, --hover-seconds, --altitude.</description>
<files>src/demo/p2p_demo.py</files>
<action>Implement CLI script with argparse, call p2p generator and POST /missions</action>
<verification>Script has --help; parses args without error</verification>
<done>false</done>
</task>
```

### Task 5: Agent-Triggered Demo

```xml
<task>
<id>07-05</id>
<requirement>DEMO-03</requirement>
<name>Create agent-triggered demo script</name>
<description>Create trigger_demo.py that accepts natural language mission description, parses to waypoints, and submits via API. Shows agent dispatching drone (e.g., "Inspect the north corner").</description>
<files>src/demo/trigger_demo.py</files>
<action>Implement script with mission description parsing, waypoint generation, and API submission</action>
<verification>Script accepts mission description; calls POST /missions with parsed waypoints</verification>
<done>false</done>
</task>
```

### Task 6: Periodic Patrol Demo

```xml
<task>
<id>07-06</id>
<requirement>DEMO-04</requirement>
<name>Create periodic patrol demo script</name>
<description>Create patrol_demo.py that runs scheduled missions. Accepts --waypoints, --interval-seconds, --count. Uses Python scheduler or loop to submit missions periodically.</description>
<files>src/demo/patrol_demo.py</files>
<action>Implement script with time-based loop, interval handling, and repeated API submissions</action>
<verification>Script has --help; accepts interval and count parameters</verification>
<done>false</done>
</task>
```

## Dependencies

- Task 1 (wave 1) → Task 3, Task 4 (wave 2)
- Task 2 (wave 1) → Task 4 (wave 2)
- Task 1, Task 2, Task 3, Task 4, Task 5 (wave 2) → Task 6 (wave 3)

## Execution Notes

- All tasks are autonomous (self-contained scripts)
- Use existing `/missions` POST endpoint from Phase 1
- Waypoint coordinates should match demo venue scale (check Phase 3 coordinates)
- API key required via `X-API-Key` header (check config)
