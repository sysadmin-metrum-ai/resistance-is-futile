# Drone Swarm Agent API

This project exposes Crazyflie brushless drones as an API-controlled inspection tool. Remote agents running on other servers call the FastAPI endpoints, the API commands the drones through Crazyradio/cflib, Lighthouse positioning decks keep the swarm localized inside the data center, and AI deck images are saved back on the server.

## Core Flow

```text
Remote agent server
  -> HTTP API tool call
  -> FastAPI app in src/main.py
  -> src/swarm service, planner, health checks, executor
  -> Crazyradio/cflib
  -> Crazyflie brushless drones with Lighthouse decks
  -> AI deck image stream
  -> stored captures returned by the API
```

## What Matters

- `src/api/routes/swarm.py` exposes `/api/swarm/*` and the remote-agent `/drone/*` trigger/status/launch flow.
- `src/swarm/` selects healthy drones, builds safe plans, runs Lighthouse-ready preflight checks, and executes synchronized high-level commander flights.
- `src/services/camera_capture.py` stores mission images and can pull frames from an AI deck stream when `AIDECK_CAMERA_HOST` is set.
- `src/services/aideck_camera.py` contains the reusable AI deck JPEG/PGM stream reader.
- `aideck_camera_poc/` contains hardware scripts for proving the AI deck camera path outside the API.
- `dashboard/`, `docker-compose.yml`, `Dockerfile.api`, and `Caddyfile` support the demo/deployment stack.
- `tools/drone-acharya/` and selected `scripts/` support hardware calibration and operations.

## Install

```bash
make install
```

Equivalent direct command:

```bash
uv sync
```

## Run The API

```bash
make run
```

Health check:

```bash
curl http://localhost:8000/health
```

## Agent API Calls

Prepare a normal datacenter inspection sequence:

```bash
curl -X POST http://localhost:8000/drone/trigger
```

Launch a prepared sequence:

```bash
curl -X POST http://localhost:8000/drone/launch/SEQ_ID
```

Check sequence status:

```bash
curl http://localhost:8000/drone/status/SEQ_ID
```

Dry-run the explicit swarm endpoint:

```bash
curl -X POST http://localhost:8000/api/swarm/deploy \
  -H 'Content-Type: application/json' \
  -d '{"swarm_size":3,"dry_run":true}'
```

## Real Flight Guardrails

Real flight requires both `dry_run=false` and `arm=true`. Keep `MOCK_MODE=true` for dashboard/API demos that must not touch hardware.

Before arming:

- Close `cfclient`; only one process can own the radio.
- Verify Crazyradio USB permissions and firmware.
- Verify each drone has current Lighthouse geometry and a stable Kalman estimate.
- Confirm `src/swarm/roster.py` matches the physical drones on the bench.
- Keep `/drone/abort` or `/api/swarm/abort` available for emergency landing.

## Camera Capture

Without camera settings, image capture writes a placeholder JPEG for tests and dry-run demos.

For real AI deck capture, set:

```bash
export AIDECK_CAMERA_HOST=192.168.4.1
export AIDECK_CAMERA_PORT=5000
export AIDECK_CAMERA_TIMEOUT_S=5
```

Then call:

```bash
curl -X POST 'http://localhost:8000/api/images/capture?mission_id=demo&drone_id=cf01'
```

## Tests

Run the normal test suite:

```bash
uv run pytest
```

Run service-backed integration tests:

```bash
make test-integration
```

## Hardware And Tools

- Lighthouse demo flights live in `tools/lighthouse_demos/`; run them as modules, for example `uv run python -m tools.lighthouse_demos.lighthouse_hover`.
- LPS and radio operation scripts stay in `scripts/`.
- Manual hardware diagnostics are in `tools/hardware-diagnostics/`.
- Presentation generation is in `tools/presentation/`.
- Anchor solving lives in `tools/drone-acharya/`.
