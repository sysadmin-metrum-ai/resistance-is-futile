# DTW 2026 Demo & Release Plan

## AI Ops Drone Swarm for Datacenter Physical Infrastructure Monitoring

---

## 1. Executive Vision

### The Problem

Modern AI infrastructure requires constant physical monitoring of datacenters — cooling systems, cable integrity, physical security, environmental hotspots. Current AI Ops can detect anomalies via software sensors but **cannot physically investigate or respond** to issues that require visual inspection or physical intervention.

### The Solution

An **autonomous drone swarm** of **palm-sized Crazyflie 2.x nano drones** that extends AI infrastructure agents with physical capabilities:

1. **AI Agent Detection** → AI monitors datacenter sensors (temperature, humidity, power, security cameras)
2. **Drone Mission Dispatch** → Agent dispatches drone(s) to investigate anomalies
3. **Autonomous Inspection** → Drones execute pre-planned or dynamic flight paths
4. **Multi-Sensor Capture** → Visual capture at waypoints
5. **Agent Analysis** → Drone data fed back to AI for diagnosis and action

### Key Value Propositions


| Capability                    | Traditional        | With Drone Swarm                                 |
| ----------------------------- | ------------------ | ------------------------------------------------ |
| Hotspot / cooling investigation | Manual walkdown   | Autonomous inspection               |
| Cable/connector inspection     | Visual inspection | Automated flight paths              |
| Physical security breach       | Camera alerts only | Drone deployed for verification    |
| Cooling issue detection        | Sensor alerts     | Drone inspection correlation        |
| Post-incident investigation   | Human response     | Immediate autonomous documentation               |


---

## 2. System Architecture (DTW Demo)

The demo architecture **must** center on **AMD Instinct MI350P (PCIe)** as the Gen AI backbone. The following is the target design for the DTW booth and slides.

### High-level picture

- **Drone layer:** A swarm of **palm-sized Crazyflie 2.x nano drones** (e.g. 10–20) in a demo enclosure. They use visual capture (no thermal in scope), indoor positioning (e.g. Loco Positioning 2.1 / Lighthouse), and communicate via 2.4 GHz OTA (e.g. Crazyradio PA) with the control server.
- **Server layer:** A **Dell PowerEdge** (or equivalent) server hosting the “AI Swarm Brain,” powered by **AMD Instinct MI350P (PCIe)** GPUs. This server runs all Gen AI inference and is the only place where large language/code models run.
- **Closed loop:** Telemetry and sensor feeds from the drones → server; AI analyzes and generates mission plans and **mission code** → code is executed in a sandbox → flight commands sent back to the swarm. Loop: **See → Reason → Generate code → Execute → Fly → Repeat.**

### AMD MI350P (PCIe) — roles in the architecture

The **AMD Instinct MI350P (PCIe)** accelerators are **required** in the architecture and must be explicitly called out in all diagrams and narrative. They are used for:

1. **AI analysis (infra monitoring, log analysis)**  
   - Run vision/language models for scene understanding, anomaly detection, asset recognition, and correlation with infrastructure/log data.  
   - Example workloads: real-time detection (people, cables, equipment, anomalies), multimodal reasoning, OCR, asset scanning.  
   - Implemented with models suitable for the MI350P memory (e.g. vision-language and detection models on ROCm/PyTorch).

2. **Dynamic mission generation**  
   - Decide **what** to do and **which** drones to use: mission planning and coordination for a **variable number of drones per mission** (1 to N).  
   - Output: mission intent, waypoints, and assignment of drones. This feeds into the code-generation step.

3. **Mission code generation (code gen on MI350P)**  
   - Generate the actual **mission code** (e.g. Python `cflib` scripts: `go_to()`, `upload_trajectory()`, hover patterns) from the mission plan.  
   - Code is produced by a **code-generation model** running on the MI350P, then executed in a **sandboxed runtime** with safety checks before any command is sent to the drones.  
   - This is the differentiator: “Generated Python code → physical drone movement.”

### Code-generation model (~32B-class)

For mission **code** generation on the MI350P, the target is a **~32B parameter code-generation model** to balance quality and fit on PCIe card memory. - **Qwen3-Coder** (Alibaba; series at 3.x): agentic code gen, long context, tool calling. **Qwen3-Coder-30B-A3B-Instruct** — 30B total params, 3B active per token (MoE); 65K context; strong for code generation and agentic workflows; on Hugging Face. Suitable for generating Crazyflie `cflib`-style Python from high-level mission descriptions.
- **Qwen3-Coder-Next** (80B MoE, 3B active) is the larger flagship; 30B-A3B fits the “~32B” target for single-card deployment.

The architecture doc and slides should name **AMD Instinct MI350P (PCIe)** and **“mission code generated on MI350P”** (e.g. Qwen3-Coder-30B-A3B on MI350P) explicitly.

### Software stack (server)

- **ROCm** (e.g. 7.0) for MI350P.
- **PyTorch** for training/adaptation and inference.
- **vLLM** (or equivalent) for FP8/quantized inference of large models.
- Detection/vision stack (e.g. Ultralytics YOLO) for real-time scene analysis.
- **Python sandbox + safety checks** for executing generated `cflib` code before sending commands to the drones.

### What must appear in architecture diagrams

- **Palm-sized Crazyflie 2.x** swarm (with visual sensors and indoor positioning; no thermal).
- **Dell PowerEdge** (or equivalent) server.
- **AMD Instinct MI350P (PCIe)** as the Gen AI engine — clearly labeled.
- Data flow: drones → telemetry/sensor → server; server → AI analysis + mission planning + **code generation** → sandboxed execution → flight commands → drones.
- Optional: callouts for “AI analysis (log/infra),” “Dynamic mission planning (variable N drones),” “Mission code gen (~32B model on MI350P).”

---

## 3. Current Status

### Milestone v1.0 — Core Platform: Base Design in Place

**Not yet tested with actual drones.** The following is implemented in code and design; hardware integration (venue, LEDs, validation on real aircraft) is not complete.


| Phase                | Status         | Features                                                                   |
| -------------------- | -------------- | -------------------------------------------------------------------------- |
| 01-Backend Core      | ✅ Complete     | Agent API, Fleet Management, Mission Queue, Safety                         |
| 02-Dashboard         | ✅ Complete     | Web UI, Drone Map, Mission Queue, Kill Switch                              |
| 03-Venue Setup       | 📐 Design only | Site survey, anchor positioning, node programming — not deployed/validated |
| 04-Drone Control API | ✅ Complete     | Takeoff/Land/GoTo/State endpoints (cflib; untested on real CF)             |
| 05-LED + Wiring      | 📐 Design only | Status LEDs, camera integration — wiring not complete                      |
| 06-Validation        | 📐 Design only | Pre-flight checks, mission validation — not run on real drones             |
| 07-Demo Missions     | ✅ Complete     | Pattern flights, P2P, agent-triggered (mock/sim)                           |
| 08-Demo Booth        | 🔄 In Progress | Power, network, safety requirements                                        |


### What the Base Design Actually Is

**Backend (Python/FastAPI)** — implemented and runnable:

- REST API: mission dispatch (`POST /missions`), fleet (`GET/POST/DELETE /drones`), safety (`POST /safety/kill-switch`), images (`/images/`*), LED (`/led/*`)
- Redis-backed mission queue (FIFO); mission/drone state in Postgres (PostgREST)
- Real-time events (SSE) for dashboard

**Frontend (React/Next.js)** — implemented and runnable:

- 2D map with drone positions, mission queue UI, drone health (battery/connection)
- Manual kill switch, LED control UI, mission validation panel

**Drone control (code path exists; not validated on hardware):**

- Crazyflie 2.1 integration via cflib: takeoff, land, goto, state
- Waypoint generators: circle, ellipse, figure-8; P2P with hover
- Agent-triggered dispatch; **mock mode** for testing without drones


### How the design is intended to work (runtime flow)

1. **Agent submits a mission** — External AI (or operator) sends `POST /missions` with waypoints, duration_seconds, optional target_drone_id and callback_url. Backend enqueues the mission in Redis (FIFO) and persists to Postgres.
2. **Scheduler assigns a drone** — A worker picks the next mission from the queue, selects an available drone (e.g. nearest to target or first idle), and marks that drone as busy. Mission state (queued → assigned → running) is updated and pushed to the dashboard via SSE.
3. **Pre-flight and execution** — Backend invokes pre-flight checks (design: battery, connection, positioning; not yet validated on real CF). If pass, it sends takeoff and then a sequence of waypoints to the drone via cflib (goto with hover). Drone state (position, battery, etc.) is streamed back and reflected on the dashboard map in real time.
4. **Capture at waypoints** — At each waypoint the design calls a capture hook (image). Captured data is associated with position and timestamp for the mission report.
5. **Mission end and callback** — When the last waypoint is done, backend commands land and marks the mission complete. If a callback URL was provided, backend POSTs a summary (e.g. mission id, status, list of captures with positions/timestamps) to the agent. Drone is marked idle again; next mission can be assigned.
6. **Safety** — Kill switch (API + dashboard) sets a global “land immediately” flag. All running missions are aborted and drones receive land commands. Pre-flight and in-mission checks can abort and re-queue the mission if conditions fail.

**Venue / LEDs / validation (design intent):** Anchors are placed and calibrated so Loco Positioning gives a stable frame; drones report position in that frame. LEDs are driven from backend state (e.g. green = idle, yellow = busy, red = error). Validation is the set of checks run before takeoff and optionally between waypoints; all of this is designed but not yet wired or proven on real drones.

### Gap Analysis


| Gap                      | Impact                                  | Resolution                                                     |
| ------------------------ | --------------------------------------- | -------------------------------------------------------------- |
| Camera capture           | Placeholder only (no real drone camera) | Future milestone                                               |
| Real hardware testing    | Not yet run on physical drones          | Schedule lab time; validate venue, LEDs, validation            |
| Venue / LED / Validation | Design only                             | Deploy anchors, complete LED wiring, run validation on real CF |
| DTW booth requirements   | Not yet planned                         | Phase 8                                                        |


---

## 4. DTW 2026 Demo Scenarios

### Primary Demo: AI Ops Incident Response

**Scenario: Datacenter anomaly (e.g. rack alert)**

```
┌─────────────────────────────────────────────────────────────────────┐
│  DEMO: AI-Detected Anomaly → Drone Investigation                    │
└─────────────────────────────────────────────────────────────────────┘

1. AI MONITOR (Dashboard shows alert)
   └─> "ALERT: Rack A3 anomaly detected (e.g. temperature threshold exceeded)"
   
2. AI AGENT
   └─> Agent determines: "Visual inspection required"
   └─> Agent calls: POST /missions with waypoints for Rack A3

3. DRONE DISPATCH (Dashboard shows drone assigned)
   └─> Drone 1 (nearest to Rack A3) receives mission
   └─> LED turns YELLOW (busy)
   └─> Pre-flight check passes

4. AUTONOMOUS FLIGHT
   └─> Drone takes off → flies to Rack A3
   └─> Executes inspection pattern (hover positions)
   └─> Camera captures images at each waypoint
   └─> Visual capture at waypoints

5. MISSION COMPLETE
   └─> Drone returns to base
   └─> LED turns GREEN (ready)
   └─> Callback sent to AI agent with images + positions

6. AI ANALYSIS (Dashboard shows results)
   └─> Agent receives: [images, positions, timestamps]
   └─> Agent analyzes: "Cooling unit vents blocked by debris"
   └─> Agent creates ticket: "HVAC maintenance required"
```

**Demo Duration:** 90 seconds

**Hardware Requirements:**

- 2x palm-sized Crazyflie 2.x drones (demo + backup)
- Loco Positioning anchors (4-6 nodes)
- Laptop with API server + Dashboard
- Wireless access point

**Visual Elements:**

- Large screen: Dashboard showing drone positions
- Large screen: Demo dashboard / mission view
- Projector: AI agent decision logs

---

### Secondary Demo Scenarios

#### Scenario B: Physical Security Breach

```
1. Security camera detects motion in restricted area
2. AI Agent receives webhook alert
3. Agent dispatches drone to investigate
4. Drone captures visual confirmation
5. Agent logs event + triggers security response
```

#### Scenario C: Cable/Connector Inspection

```
1. AI detects anomalous network latency
2. Agent determines: "Physical cable inspection needed"
3. Agent dispatches drone with inspection waypoints
4. Drone flies predetermined inspection route
5. Agent analyzes images → identifies faulty connector
```

#### Scenario D: Post-Maintenance Verification

```
1. Maintenance team completes work in datacenter
2. Agent schedules verification mission
3. Drone captures baseline imagery
4. Agent compares to previous baseline
5. Agent confirms: "Maintenance verified complete"
```

---

## 5. Detailed Release Plan

### Timeline

**DTW 2026: May 18–21, 2026**
**COMPLETION DEADLINE: April 21, 2026**

Internal demos in April; timeline to April 21.

### Hardware, venue & event logistics

**Current hardware:** 10-drone bundle (Loco Positioning 2.1+).

**Potential additional orders (by Mar 5; refresh as evaluation/testing reveals needs):**

- More drones (beyond current bundle)
- Brushless (e.g. brushless Crazyflie / decks)
- LED decks
- More positioning options (e.g. optical flow, other positioning)
- Peripherals as needed from testing

**Event profile:** DTW is **3 days, ~9 hours/day**. Plan requires:

- **Chargers & charge stations** — enough capacity to keep demo fleet flying across the day; rotation/battery strategy
- **Logistics plan** — transport, setup/teardown, daily schedule, spare parts, who runs the booth
- **Venue/booth requirements** — power, network, safety, footprint, anchor placement; finalized by Mar 5 and signed off in Phase 8

All of the above are part of the plan and reflected in the Mar 5 milestone and Pre-DTW checklist.

### Timeline Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        DTW 2026 RELEASE TIMELINE                            │
│                        ⚠️ MAY 18–21, 2026 - LAS VEGAS                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MARCH 2026                  APRIL 2026                MAY 2026            │
│  W1   W2   W3   W4           W1   W2   W3   W4         W1   W2           │
│  ───  ───  ───  ───          ───  ───  ───  ───        ───  ───           │
│                                                                              │
│  ████████████████████████████████████████████████████████                   │
│                      v1.0 → v1.1 DTW READY by Apr 21                         │
│                      + Internal demos (April) + Stabilization                │
│                                                                              │
│       📹 Internal Demo #1   📹 Demo #2    🚀 DTW                             │
│       (April)               (April)       (May 18–21)                        
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Weekly milestones


| Week of    | Milestone                 | Deliverables                                                                                                                                                                                                                                                                                          |
| ---------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mar 5**  | Drone + booth baseline    | Test drones with Python API only (no built-in GUIs). Order as needed: more drones, brushless, LED decks, positioning options (e.g. optical); incorporate new requirements from evaluation/testing. Finalize venue/booth requirements, logistics plan (3-day / ~9 hr-day), chargers & charge stations. |
| **Mar 12** | AI-DC ops + mock demo     | Define API integration with AI-DC ops agent. Mock flight missions. Mock UI for demo.                                                                                                                                                                                                                  |
| **Mar 19** | Web UI + lab integration  | Actual Web UI for demo solution. Test API integration with Dell Round Rock lab Operations.                                                                                                                                                                                                            |
| **Mar 26** | Venue + validation        | Deploy/validate venue (anchors, positioning). Run pre-flight/mission validation on real drones. LED wiring complete.                                                                                                                                                                                  |
| **Apr 2**  | Integration + demo script | Full mission flow with real hardware. Demo script ready. Phase 8 (booth) signed off.                                                                                                                                                                                                   |
| **Apr 9**  | Internal Demo #1          | Full demo run for stakeholders. Record demo video. Feature freeze.                                                                                                                                                                                                                                    |
| **Apr 16** | Internal Demo #2          | Bug fixes from demo #1. Final rehearsal. 5 consecutive clean runs.                                                                                                                                                                                                                                    |
| **Apr 21** | DTW ready                 | Pre-DTW checklist complete. Equipment packed. Ready for May 18–21.                                                                                                                                                                                                                                    |


**Feature Freeze:** April 9, 2026 — No new features after this.

---

#### Pre-DTW Checklist (April 17-21)

- 10 consecutive successful mission runs
- Demo script rehearsed 10+ times
- Logistics plan done (3 days × ~9 hr/day: rotation, charge strategy, booth staffing)
- Chargers & charge stations procured and tested; capacity for full show days
- Backup hardware tested (drones, batteries, spare anchors, spare peripherals)
- All equipment packed:
  - Crazyflie drones (from 10-drone bundle + any additional) + batteries (charged)
  - Loco Positioning 2.1 anchors (+ any optical/other positioning)
  - LED decks, brushless/peripherals as needed
  - USB radio dongles
  - Chargers & charge stations
  - Laptop with API server + Dashboard
  - Wireless access point
  - Power strips, cables
  - Kill switch backup (manual)
- Venue/booth requirements confirmed with venue
- Travel booking confirmed
- Demo video recorded as backup
- Full anomaly/demo run
- Invite: Internal stakeholders, management

---

### Testing Schedule

#### Daily Tests (March 5 – April 21)


| Day | Focus                 | Success Criteria                |
| --- | --------------------- | ------------------------------- |
| Mon | API endpoints         | All REST calls return 200       |
| Tue | Mission execution     | Drones execute full flight path |
| Wed | Dashboard integration | Real-time updates < 1s latency  |
| Thu | Safety systems        | Kill switch < 500ms response    |
| Fri | Full demo run         | End-to-end works                |


#### Weekly integration (align with milestones)


| Week of | Focus                            | Success Criteria                                                                                                                              |
| ------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Mar 5   | Python API + drones + HW + booth | Drones via API (no GUIs); orders for drones/brushless/LED/positioning as needed; venue/booth + logistics (chargers, 3-day/9hr plan) finalized |
| Mar 12  | AI-DC agent + mock               | API contract defined; mock missions + mock UI run                                                                                             |
| Mar 19  | Web UI + Round Rock              | Demo Web UI; API tested with Dell Round Rock lab                                                                                              |
| Mar 26  | Venue + validation               | Anchors/positioning validated; pre-flight on real CF                                                                                          |
| Apr 2   | Full mission flow                | End-to-end with real hardware; demo script                                                                                           |
| Apr 9   | Internal Demo #1                 | Recorded run; feature freeze                                                                                                                  |
| Apr 16  | Internal Demo #2                 | Clean runs; rehearsal complete                                                                                                                |
| Apr 21  | DTW ready                        | Checklist done; equipment packed                                                                                                              |


---

## 6. Demo Script — DTW Primary Presentation

### Setup (2 minutes before)

- Power on drones, verify battery > 80%
- Start API server (`make run`)
- Start Dashboard (`cd dashboard && npm run dev`)
- Verify Loco Positioning anchors online
- Clear mission queue



#### 0:00-0:30 — Introduction

```
"Imagine you're an AI infrastructure agent. You monitor thousands of 
servers, but you can only see what software tells you. You can't see 
environmental hotspots. You can't check cable integrity. You can't verify 
physical security.

Until now.

[SHOW: Dashboard with idle drone]

This is our drone swarm — an extension of AI operations into the 
physical world."
```

#### 0:30-1:00 — The Problem

```
"Let's say your AI detects an anomaly in Rack A3 (e.g. sensor threshold). Traditional 
response: Open a ticket, wait for human to investigate.

[SHOW: Dashboard alert]

Our AI agent detects the anomaly and dispatches a drone immediately."

[TRIGGER: Simulated alert on screen]
```

#### 1:00-2:00 — The Solution

```
"[SHOW: Agent API call in logs]
The agent calls our mission API, specifying the location and mission type.

[SHOW: Drone state changes]
The drone receives the mission, runs pre-flight checks, takes off.

[SHOW: Drone on map moving]
This is the drone executing the inspection pattern — capturing visual 
data at each waypoint.

[SHOW: Images appearing in dashboard]
Mission complete. The agent receives images, positions, and timestamps."
```

#### 2:00-2:30 — The Technology

```
"Under the hood:
• REST API for agent integration
• Redis-backed mission queue for reliability  
• Crazyflie drones with Loco Positioning
• Real-time dashboard with mission tracking
• Kill switch for safety

[SHOW: API documentation]
Simple integration — any AI agent can dispatch missions."
```

#### 2:30-3:00 — Use Cases

```
"Beyond this inspection scenario:

[SHOW use case 1]
• Physical security — drone verifies camera alerts

[SHOW use case 2]  
• Cable integrity — drone inspects network infrastructure

[SHOW use case 3]
• Post-maintenance verification — drone captures baseline imagery

[SHOW use case 4]
• Emergency response — drone documents incidents before human entry"
```

#### 3:00-4:00 — Live Demo

```
"Now let's see it in action."

[EXECUTE: Full anomaly demo]
- Trigger simulated alert
- Dispatch mission
- Watch drone execute
- Show callback results

"If anything goes wrong — [PRESS KILL SWITCH] — instant landing."
```

#### 4:00-5:00 — Wrap Up

```
"Questions?

• Integration: REST API, webhooks
• Hardware: Crazyflie 2.1, Loco Positioning
• Timeline: Beta in Q3, production in Q4 2026

[SHOW: QR code to demo video]"
```

---

## 7. Visual Assets Needed

### For Slide Generation (Text-to-Image)


| Slide        | Description          | Prompt Keywords                                     |
| ------------ | -------------------- | --------------------------------------------------- |
| Title        | AI Ops Drone Swarm   | datacenter, drone, AI, futuristic, glowing          |
| Problem      | Rack / hotspot alert | server rack, warning lights, alert state             |
| Solution     | Drone inspection     | drone flying, server rack, inspection view          |
| Architecture | System diagram       | flowchart, API, drone, dashboard, icons             |
| Dashboard    | Monitoring screen    | dashboard, map, drones, mission queue, dark mode    |
| Use Cases    | Multiple scenarios   | security camera, cable rack, cooling unit           |
| Demo         | Live demo screenshot | dashboard, drone positions, mission log             |


### For Video Recording

- Screen capture: Dashboard + API logs
- Drone POV: First-person flight footage
- Split screen: AI alerts → drone response

---

## 8. Risk Mitigation


| Risk                   | Likelihood | Impact | Mitigation                          |
| ---------------------- | ---------- | ------ | ----------------------------------- |
| Drone hardware failure | Medium     | High   | 2x backup drones, pre-flight checks |
| Positioning drift      | Medium     | Medium | Manual re-calibration before demo   |
| WiFi interference      | Low        | High   | Dedicated radio channel             |
| API timeout            | Low        | Medium | Retry logic + timeout handling      |
| Demo nerves            | High       | High   | 10+ rehearsal runs                  |


---

## 9. Success Metrics

### Technical

- 100% mission success rate in testing
- < 30 second mission dispatch to takeoff
- < 5 second dashboard real-time updates

### Demo

- 3 successful live demos
- Video recording for marketing
- 10+ qualified leads collected

### Post-DTW

- Beta customers identified
- Production roadmap finalized
- Team trained on system

---

## 10. Action Items

### By Mar 5

- Test drones with Python API only (no built-in GUIs)
- Order as needed: more drones, brushless, LED decks, positioning options (e.g. optical); add orders for new requirements from evaluation/testing
- Finalize venue/booth requirements
- Logistics plan (3-day event, ~9 hr/day): chargers, charge stations, rotation strategy, booth staffing

### By Mar 12

- Define API integration with AI-DC ops agent
- Mock flight missions running
- Mock UI for demo

### By Mar 19

- Actual Web UI for demo solution
- Test API integration with Dell Round Rock lab Operations

### By Mar 26

- Venue deployed/validated (anchors, positioning)
- Pre-flight/mission validation on real drones
- LED wiring complete

### By Apr 2

- Full mission flow with real hardware
- Demo script
- Phase 8 (booth) signed off

### By Apr 9 — Internal Demo #1

- Full demo run for stakeholders
- Record demo video
- Feature freeze (no new features after Apr 9)

### By Apr 16 — Internal Demo #2

- Bug fixes from demo #1
- Final rehearsal; 5 consecutive clean runs

### By Apr 21

- Pre-DTW checklist complete
- Equipment packed; ready for DTW (May 18–21)

---

*Document Version: 1.1 — DTW May 18–21*
*Updated: March 1, 2026*
*Owner: AI Ops Drone Swarm Team*