# DTW 2026 Demo Slide Deck - Image Prompts

## Color Theme (Metrum AI)
- Primary gradient: #FF3132 → #EE0089 → #CC28AF → #9948CB → #465CDA
- Background: #000000 (black)
- Text: #FFFFFF (white)
- Secondary: #1a1a1a (dark gray)

---

## SLIDE 1: Title Slide

**Slide Title:** AI Ops Drone Swarm
**Subtitle:** Autonomous Physical Infrastructure Monitoring for Datacenters

**IMAGE PROMPT:**
A futuristic dark-themed slide background featuring a stylized datacenter environment with glowing blue and purple data streams. In the center, a sleek quadcopter drone (Crazyflie-style) hovers with glowing LED accents in cyan and magenta. The scene includes faint server rack silhouettes in the background with subtle heat map overlays in red/orange. The Metrum AI gradient accent bar runs along the bottom. Text overlay area on the right for title. Professional corporate tech presentation style, dark mode, high contrast, subtle particle effects, 3D render, ultra detailed, 4K.

**Tech Stack to Display:**
- Crazyflie 2.1
- Loco Positioning
- Python/FastAPI
- React/Next.js
- Redis + Postgres
- DTW 2026: May 18-21

---

## SLIDE 2: The Problem

**Slide Title:** The Problem
**Content:** AI Ops can detect anomalies via software sensors but CANNOT physically investigate or respond to issues requiring visual/thermal inspection.

**IMAGE PROMPT:**
A split-screen visualization showing on the left a datacenter server room with warning signs and heat wave effects emanating from a server rack in red/orange. On the right side, a frustrated robot/AI figure with question marks around its head, unable to "see" the physical problem. Dotted connection lines show the limitation. The Metrum gradient flows vertically between the two sides. Dramatic lighting, cyberpunk aesthetic, dark background, professional presentation style, high detail, 4K.

**Key Problems:**
- Thermal hotspot investigation requires manual walkdown
- Cable/connector inspection needs human visual check
- Physical security breaches only trigger camera alerts
- Post-incident investigation requires human response

---

## SLIDE 3: The Solution

**Slide Title:** The Solution
**Content:** Autonomous drone swarm extending AI infrastructure agents with physical capabilities

**IMAGE PROMPT:**
A dynamic illustration showing the complete AI Ops Drone Swarm system in action. Center: A stylized drone flying toward server racks. Surrounding elements: Sensor data streams flowing into an AI brain icon, which dispatches the drone mission, drone executing inspection, data flowing back to AI for analysis. Connected nodes with glowing lines in the Metrum gradient colors (red to blue). Clean circuit board patterns in background. Futuristic HUD elements showing mission status. Professional tech presentation, dark mode, 4K.

**Solution Flow:**
1. AI Agent Detection → 2. Drone Mission Dispatch → 3. Autonomous Inspection → 4. Multi-Sensor Capture → 5. Agent Analysis

---

## SLIDE 4: Key Value Propositions

**Slide Title:** Traditional vs Drone Swarm
**Content:** Comparison table showing 5 rows of capabilities

**IMAGE PROMPT:**
A sleek comparison table rendered as a 3D holographic display. Left column "Traditional" shows icons of human workers with clipboards walking through datacenter (gray tones). Right column "With Drone Swarm" shows autonomous drones flying (colorful with cyan/magenta accents). Each row has icons: Thermal hotspot (heat wave), Cable inspection (cables), Security (shield), Cooling (snowflake), Post-incident (clipboard). The Metrum gradient runs along the table header. Dark background with subtle grid, glass morphism effect on table, floating data points, professional presentation, 4K.

**Comparison Rows:**
| Capability | Traditional | With Drone Swarm |
|------------|-------------|------------------|
| Thermal hotspot investigation | Manual walkdown | Autonomous inspection |
| Cable/connector inspection | Visual inspection | Automated flight paths |
| Physical security breach | Camera alerts only | Drone deployed for verification |
| Cooling issue detection | Sensor alerts | Drone inspection + correlation |
| Post-incident investigation | Human response | Immediate autonomous documentation |

---

## SLIDE 5: System Architecture

**Slide Title:** System Architecture
**Content:** Backend (Python/FastAPI), Frontend (React/Next.js), Drone Control (cflib)

**IMAGE PROMPT:**
A detailed technical architecture diagram rendered as a glowing network visualization. Three main pillars: Backend (Python/FastAPI icon with Redis/PostgreSQL icons), Frontend (React/Next.js dashboard preview), Drone Control (Crazyflie icon with Loco Positioning anchors). Connecting data flow lines in gradient colors show: REST API, SSE events, Mission Queue, Drone Commands. Floating icons for: Kill Switch, LED Control, Mission Dispatch. Dark background with circuit traces, node connections, subtle particle effects. Professional technical diagram style, dark mode, 4K.

**Tech Stack Details:**
- REST API: mission dispatch, fleet management, safety
- Redis-backed mission queue (FIFO)
- Real-time events (SSE) for dashboard
- Crazyflie integration via cflib
- 2D map with drone positions

---

## SLIDE 6: Current Status - Milestone v1.0

**Slide Title:** Milestone v1.0 — Core Platform Status
**Content:** Phase status table showing 8 phases

**IMAGE PROMPT:**
A status dashboard showing all 8 project phases as floating cards or nodes. Green checkmarks for Complete phases, yellow gears for In Progress, gray blueprints for Design Only. The phases arranged in a timeline or grid. Metrum gradient accent on completed items. Dark background with subtle tech grid. Each card shows phase name and status icon. Professional project management dashboard aesthetic, dark mode, 4K.

**Phase Status Table:**
| Phase | Status | Features |
|-------|--------|----------|
| 01-Backend Core | ✅ Complete | Agent API, Fleet Management, Mission Queue, Safety |
| 02-Dashboard | ✅ Complete | Web UI, Drone Map, Mission Queue, Kill Switch |
| 03-Venue Setup | 📐 Design only | Site survey, anchor positioning |
| 04-Drone Control API | ✅ Complete | Takeoff/Land/GoTo/State endpoints |
| 05-LED + Wiring | 📐 Design only | Status LEDs, camera integration |
| 06-Validation | 📐 Design only | Pre-flight checks, mission validation |
| 07-Demo Missions | ✅ Complete | Pattern flights, P2P, agent-triggered |
| 08-Demo Booth | 🔄 In Progress | Power, network, safety requirements |

---

## SLIDE 7: How It Works

**Slide Title:** Runtime Flow
**Content:** 6-step mission execution workflow

**IMAGE PROMPT:**
A horizontal process flow diagram showing 6 connected steps with animated icons. Step 1: AI Agent with sensor data. Step 2: Mission submission (API call). Step 3: Scheduler assigns drone. Step 4: Pre-flight and execution (drone taking off). Step 5: Waypoint capture (camera icon). Step 6: Mission complete with callback. Each step connected by glowing arrows in Metrum gradient. Dark background with floating data elements. Professional workflow diagram, dark mode, 4K.

**Flow Steps:**
1. Agent submits mission (POST /missions)
2. Scheduler assigns drone from queue
3. Pre-flight checks → Execution
4. Capture at waypoints (image/thermal)
5. Mission end → Land command
6. Callback to agent with results

---

## SLIDE 8: Primary Demo - Thermal Anomaly

**Slide Title:** DTW 2026: Primary Demo
**Content:** AI-Detected Thermal Anomaly → Drone Investigation

**IMAGE PROMPT:**
A storyboard-style split image showing the demo sequence. Top: Dashboard alert "ALERT: Rack A3 thermal spike - 45°C". Middle: Drone dispatch sequence with LED turning yellow. Bottom: Drone flying inspection pattern around server rack with simulated thermal overlay. Corner badges show demo duration (90 seconds) and hardware (2x Crazyflie, Loco Positioning). Metrum gradient accent bars. Dark background with dashboard mockup elements. Cinematic presentation style, 4K.

**Demo Flow:**
1. AI Monitor shows alert
2. Agent dispatches drone
3. Pre-flight check passes
4. Autonomous flight + capture
5. Mission complete → callback
6. AI Analysis → ticket created

---

## SLIDE 9: Use Case - Physical Security

**Slide Title:** Use Case: Physical Security Breach
**Content:** Drone verifies camera alerts autonomously

**IMAGE PROMPT:**
A security-focused visualization showing a datacenter perimeter. Left: Security camera with motion detection alert. Center: Drone launching from charging station. Right: Drone capturing visual confirmation of area. Green checkmark overlay showing "Verified" result. Subtle warning tape/stripes aesthetic. Dark blue/purple tones with Metrum accent in cyan. Professional security operations center aesthetic, 4K.

**Use Case Flow:**
1. Security camera detects motion
2. AI Agent receives webhook alert
3. Agent dispatches drone to investigate
4. Drone captures visual confirmation
5. Agent logs event + triggers response

---

## SLIDE 10: Use Case - Cable Inspection

**Slide Title:** Use Case: Cable/Connector Inspection
**Content:** Automated inspection of network infrastructure

**IMAGE PROMPT:**
A datacenter cable rack scenario. Drone flying along cable trays with inspection beam/flashlight. Highlighted areas showing cable connections with diagnostic overlays (green = OK, red = fault). HUD elements showing "Latency detected" → "Physical inspection required". Futuristic inspection UI aesthetic. Dark background with cyan diagnostic lines. Metrum gradient accent. Professional infrastructure inspection style, 4K.

**Use Case Flow:**
1. AI detects anomalous network latency
2. Agent determines physical inspection needed
3. Agent dispatches drone with waypoints
4. Drone flies inspection route
5. Agent analyzes images → identifies fault

---

## SLIDE 11: Use Case - Post-Maintenance

**Slide Title:** Use Case: Post-Maintenance Verification
**Content:** Drone captures baseline imagery after maintenance

**IMAGE PROMPT:**
A maintenance verification scenario. Top: Technician completing work in datacenter. Bottom: Drone capturing baseline imagery. Side panel showing before/after comparison with "Maintenance verified complete" stamp. Green verification badge. Clean, professional aesthetic. Dark background with maintenance log elements. Metrum gradient for verified stamp. 4K.

**Use Case Flow:**
1. Maintenance team completes work
2. Agent schedules verification mission
3. Drone captures baseline imagery
4. Agent compares to previous baseline
5. Agent confirms maintenance complete

---

## SLIDE 12: Timeline Overview

**Slide Title:** DTW 2026 Release Timeline
**Content:** March - May 2026 timeline with key milestones

**IMAGE PROMPT:**
A horizontal timeline visualization. March 2026 section shows development phases (v1.0 → v1.1). April shows internal demos and stabilization. May 18-21 shows DTW event with celebration icon. Key dates marked: Mar 5, Mar 12, Mar 19, Mar 26, Apr 2, Apr 9, Apr 16, Apr 21. The timeline bar uses Metrum gradient from red to blue. Floating milestone icons at each date. Dark background with calendar grid. Professional project timeline, 4K.

**Key Dates:**
- Mar 5: Drone + booth baseline
- Mar 12: AI-DC ops + mock demo
- Mar 19: Web UI + lab integration
- Mar 26: Venue + validation
- Apr 2: Integration + thermal sim
- Apr 9: Internal Demo #1
- Apr 16: Internal Demo #2
- Apr 21: DTW ready
- May 18-21: DTW 2026 (Las Vegas)

---

## SLIDE 13: Weekly Milestones Detail

**Slide Title:** Weekly Milestones
**Content:** Detailed 8-week milestone table

**IMAGE PROMPT:**
A detailed milestone roadmap rendered as a sleek vertical timeline or Gantt-style chart. Each week row shows: Date, Milestone name, and Deliverables as bullet points. Color coding: Completed (green), In Progress (yellow), Upcoming (gray). The Metrum gradient vertical accent on the left. Dark background with subtle grid. Professional roadmap presentation, 4K.

**Milestones:**
| Week of | Milestone | Key Deliverables |
|---------|-----------|------------------|
| Mar 5 | Drone + booth baseline | Test drones, order equipment, finalize venue |
| Mar 12 | AI-DC ops + mock demo | API integration, mock missions |
| Mar 19 | Web UI + lab integration | Demo Web UI, test with lab |
| Mar 26 | Venue + validation | Deploy anchors, pre-flight validation |
| Apr 2 | Integration + thermal sim | Full mission flow, thermal demo |
| Apr 9 | Internal Demo #1 | Full demo run, feature freeze |
| Apr 16 | Internal Demo #2 | Bug fixes, final rehearsal |
| Apr 21 | DTW ready | Pre-DTW checklist, equipment packed |

---

## SLIDE 14: Success Metrics & CTA

**Slide Title:** Success Metrics & Next Steps
**Content:** Technical, Demo, and Post-DTW goals

**IMAGE PROMPT:**
A goal-setting dashboard with three sections. Section 1: Technical metrics with gauges (100% mission success, <30s dispatch, <5s updates). Section 2: Demo goals (3 successful demos, video recording, 10+ leads). Section 3: Post-DTW roadmap (beta customers, production roadmap, team training). Bottom: "Let's Build the Future of AI Ops" CTA with Metrum gradient button. Dark background with success checkmarks and metrics dashboards. Professional goal-tracking UI, 4K.

**Success Metrics:**
- Technical: 100% mission success, <30s dispatch, <5s dashboard updates
- Demo: 3 successful live demos, video recording, 10+ qualified leads
- Post-DTW: Beta customers, production roadmap, team trained

---

*Document generated for DTW 2026 Slide Deck*
*Metrum AI Color Theme Applied*
