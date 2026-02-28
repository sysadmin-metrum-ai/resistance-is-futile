# External Integrations

**Analysis Date:** 2026-02-27

## APIs & External Services

**Drone Control:**
- Bitcraze Crazyflie API - Low-level drone protocol
  - Client: cflib (Python library)
  - Communication: 2.4GHz radio via Crazyradio 2.0 USB dongle
  - URI format: `radio://[dongle_id]/[channel]/[data_rate]` (e.g., `radio://0/80/2M`)

**No cloud services detected:**
- No external REST APIs
- No cloud databases
- No SaaS integrations

## Data Storage

**Databases:**
- None - Project is robotics/embedded with no persistent data storage

**File Storage:**
- Local filesystem only
- CSV/TSV files for distance matrices and coordinate output (drone-acharya)
- Cache file `./cache` for Crazyflie firmware metadata (`test-hover.py` line 52)

**Caching:**
- None - No caching layer detected

## Authentication & Identity

**Auth Provider:**
- None - No authentication required
- Hardware-based access control (physical USB dongle possession)

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking services
- Console logging via print statements in Python scripts

**Logs:**
- cfclient GUI displays real-time telemetry
- Python scripts print to stdout/stderr
- No structured logging framework

## CI/CD & Deployment

**Hosting:**
- None - Local hardware project
- No cloud deployment

**CI Pipeline:**
- None detected
- No GitHub Actions, GitLab CI, or other CI systems
- Manual build/test process

## Environment Configuration

**Required env vars:**
- `LIBGL_ALWAYS_SOFTWARE=1` - Required for cfclient on some systems (OpenGL workaround)
- `python3` environment - Virtual environment via `python3 -m venv`

**Secrets location:**
- None - No secrets required
- Hardware-bound access (physical USB devices)

## Webhooks & Callbacks

**Incoming:**
- None - No webhook endpoints

**Outgoing:**
- None - No outgoing webhooks

## Hardware Interfaces

**USB Devices:**
- Crazyradio 2.0 (USB ID `1915:7777` Nordic Semiconductor)
- Crazyflie 2.1 (USB ID `0483:5740`)
- Loco Positioning nodes (serial over USB, `/dev/ttyACM*`)

**Radio Communication:**
- 2.4GHz frequency band
- Supported data rates: 1M, 2M (used in test-hover.py)

## Positioning System

**Loco Positioning System (LPS):**
- Ultra-Wideband (UWB) ranging
- Supports TWR (Two-Way Ranging), TDoA 2, TDoA 3 modes
- 4-8 anchor nodes for 3D positioning
- Kalman filter for position estimation on drone

---

*Integration audit: 2026-02-27*
