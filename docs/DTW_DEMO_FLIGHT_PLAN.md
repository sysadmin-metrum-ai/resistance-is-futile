# DTW Demo Flight Plan

This document is the implementation target for the DTW demo mission.

## Demo Goal

An AI agent running on the server detects a condition that requires visual
inspection. It triggers a drone mission. The available Crazyflie 2.1+
brushless drones take off from the side staging area, move to inspection poses
in front of the central server, capture or stream imagery, then return to their
landing pads.

The system must work with:

- 3 drones available: simultaneous inspection
- 2 drones available: partial parallel inspection with one pose reassigned
- 1 drone available: sequential single-drone mission

## Physical Layout

- Flight volume: approximately `10m x 10m`
- Acrylic enclosure around demo field
- `8` LPS nodes around the perimeter, with low and high placement
- Server positioned near the center of the field
- Drone home pads on one side of the field

## Control and Video Plan

- Flight control and localization commands use `Crazyradio`
- AI-deck WiFi is reserved for image/video transport
- Mission logic must not depend on WiFi round-trip control timing

This split is intentional. It reduces the chance that camera traffic degrades
control stability during the demo.

## Mission Phases

Every mission, whether single-drone or swarm, uses the same high-level phases:

1. `preflight`
2. `arm`
3. `takeoff`
4. `transit_to_staging`
5. `transit_to_inspection`
6. `inspect_and_capture`
7. `return_to_home`
8. `land`
9. `postflight`

For multi-drone runs, these phases should be barriered. The swarm advances
together, and a critical failure in one drone aborts the mission for all.

## Waypoint Model

Mission waypoints must be 3D and explicit. The runtime should support at least:

```json
{
  "x": 0.0,
  "y": 0.0,
  "z": 0.8,
  "yaw_deg": 0.0,
  "hold_s": 2.0,
  "capture": true,
  "label": "inspect-center"
}
```

Recommended waypoint semantics:

- `x`, `y`, `z`: world coordinates in meters
- `yaw_deg`: optional facing direction for camera framing
- `hold_s`: hover duration at the waypoint
- `capture`: whether to trigger capture/stream emphasis at the pose
- `label`: human-readable mission stage label

## Demo Poses

The initial production mission should use fixed, known-good poses:

- `home_left`
- `home_center`
- `home_right`
- `staging_left`
- `staging_center`
- `staging_right`
- `inspect_left`
- `inspect_center`
- `inspect_right`

These poses should be prevalidated in the field and reused instead of relying
on ad hoc path generation during the demo.

## Dynamic Assignment Rules

The same API mission should adapt to available healthy drones:

### Three drones available

- One drone per inspection pose
- Simultaneous capture/streaming at the front of the server

### Two drones available

- Assign drones to `inspect_left` and `inspect_right`
- After capture, reassign one drone to `inspect_center`
- Keep the overall mission shape and return path the same

### One drone available

- Visit `inspect_left`, `inspect_center`, then `inspect_right` sequentially
- Return home at the end

## Mission Safety Rules

- A mission must not start without a recent GO result from the sanity-check flow
- If localization spread/drift exceeds threshold, refuse takeoff
- If a critical drone fails during a swarm mission, abort the whole swarm
- If video capture fails, the drone should still be able to return and land
- Home pads and inspection poses must stay inside the validated anchor volume

## Human Test Flow

The human verification flow should stay simple:

1. Run one bash sanity-check command
2. Confirm overall `GO`
3. Run a single-drone hover litmus test if needed
4. Run a multi-drone smoke test if more than one drone is active
5. Trigger the API mission

The operator should not need to remember multiple conflicting scripts or
thresholds.

## Morning Verification Checklist

- API starts cleanly
- Single-drone sanity flow returns `GO` on a healthy drone
- Multi-drone sanity flow returns `GO` on the intended demo set
- Mission API accepts a 3D mission request
- Mission planner degrades cleanly from 3 drones to 2 to 1
- Camera subsystem exposes capture/stream hooks per drone
- Abort path works and returns drones to home/land safely
