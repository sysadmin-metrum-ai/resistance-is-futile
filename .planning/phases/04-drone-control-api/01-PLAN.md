---
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/api/routes/drones.py
  - scripts/verify-position.py
autonomous: true
requirements:
  - GAP-01
must_haves:
  truths:
    - "POST /drones/{id}/takeoff endpoint exists and works"
    - "POST /drones/{id}/land endpoint exists and works"
    - "POST /drones/{id}/go_to exists and works"
    - "GET /drones/{id}/state exists and works"
    - "verify-position.py uses correct API path"
  artifacts:
    - "src/api/routes/drones.py - Four new control endpoints"
    - "scripts/verify-position.py - Fixed API paths"
  key_links:
    - "verify-position.py calls /drones/{id}/takeoff, /land, /go_to, /state"
---

# Phase 4: Drone Control API - Plan

## Gap Context
The verify-position.py script (Phase 3) is broken:
1. Uses wrong API prefix: `/api/drones/...` instead of `/drones/...`
2. Calls endpoints that don't exist

## Tasks

<task>
<files>src/api/routes/drones.py</files>
<action>Add four endpoints: POST /drones/{id}/takeoff, POST /drones/{id}/land, POST /drones/{id}/go_to, GET /drones/{id}/state. Each updates Redis state and returns JSON.</action>
<verify>curl -X POST http://localhost:8000/drones/1/takeoff -H "Content-Type: application/json" -H "X-API-Key: test" -d '{"height": 0.5}'</verify>
<done>All four endpoints return 200 OK</done>
</task>

<task>
<files>scripts/verify-position.py</files>
<action>Fix API paths: remove /api prefix from all endpoint calls. Change /api/drones/ to /drones/.</action>
<verify>grep -q "/drones/" scripts/verify-position.py && ! grep -q "/api/drones/" scripts/verify-position.py</verify>
<done>Script uses correct /drones/ prefix</done>
</task>
