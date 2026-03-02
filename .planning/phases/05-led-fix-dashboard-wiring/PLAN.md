---
plan: 01
type: execute
wave: 1
depends_on:
  - 04-drone-control-api
autonomous: true
files_modified:
  - src/api/routes/led.py
  - dashboard/src/lib/api.ts
  - dashboard/src/types/index.ts
  - dashboard/src/components/*
requirements:
  - GAP-02
must_haves:
  truths:
    - "LED API fetches drone URI from PostgREST (not hardcoded)"
    - "Camera images accessible in Dashboard"
    - "LED state controllable from Dashboard"
  artifacts:
    - "src/api/routes/led.py - Fixed hardcoded URI bug"
    - "dashboard/src/lib/api.ts - Added camera/LED API functions"
    - "dashboard/src/types/index.ts - Added TypeScript types"
    - "dashboard/src/components/* - Added UI controls"
  key_links:
    - "LED API uses DroneManager.get_drone(drone_id) to get URI"
    - "Dashboard calls /images/* for camera view"
    - "Dashboard calls /led/{drone_id}/* for LED control"
---

# Phase 5: LED Fix + Dashboard Wiring - Plan

## Goal
Fix LED hardcoded URI bug, wire camera/LED to Dashboard

## Success Criteria (must_haves)
1. LED API fetches drone URI from PostgREST (not hardcoded)
2. Camera images accessible in Dashboard
3. LED state controllable from Dashboard

## Tasks

<task>
<files>src/api/routes/led.py</files>
<action>Replace hardcoded `f"drone-{drone_id}"` at lines 83, 123, 149 with actual URI fetched from PostgREST. Import and use DroneManager.get_drone(drone_id) to get the drone record with its URI.</action>
<verify>grep -q "drone_manager.get_drone" src/api/routes/led.py && ! grep -q 'f"drone-{drone_id}"' src/api/routes/led.py</verify>
<done>LED API uses drone URI from database, not hardcoded</done>
</task>

<task>
<files>dashboard/src/lib/api.ts, dashboard/src/types/index.ts</files>
<action>Add API client functions to fetch camera images: getMissionImages(missionId), getImageUrl(imageId). Add TypeScript types for image responses.</action>
<verify>grep -q "getMissionImages" dashboard/src/lib/api.ts && grep -q "getImageUrl" dashboard/src/lib/api.ts</verify>
<done>Dashboard can fetch and display mission images</done>
</task>

<task>
<files>dashboard/src/lib/api.ts, dashboard/src/components/*</files>
<action>Add API client functions to control LEDs: setLEDColor(droneId, color), blinkLED(droneId, color, duration), turnOffLED(droneId). Add UI controls to drone detail view.</action>
<verify>grep -q "setLEDColor" dashboard/src/lib/api.ts && grep -q "blinkLED" dashboard/src/lib/api.ts</verify>
<done>LED state controllable from Dashboard UI</done>
</task>

## Execution Order

Tasks must execute in this order:
1. **Task 1** (LED URI fix) - MUST complete first
2. **Tasks 2 & 3** (Camera/LED wiring) - Can execute in parallel after Task 1

Note: This is a single plan with internal task dependencies. The wave=1 in frontmatter indicates this is the first plan for Phase 5.

## Notes

- All three endpoints already exist in backend (LED at `/led/{drone_id}/*`, Camera at `/images/*`)
- This phase is wiring/fixing existing code, not implementing new features
- Use React Query mutations for LED control to handle loading/error states
- Consider adding LED controls only for online drones (check drone.state !== 'offline')
