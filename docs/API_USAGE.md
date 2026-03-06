# Drone Swarm API Usage Examples

This document provides comprehensive examples for using the Drone Swarm Agent API.

## Base URLs

- **API Server**: `http://localhost:8000`
- **Dashboard UI**: `http://localhost:3003`
- **PostgREST**: `http://localhost:3000`

## Quick Start

### 1. Check System Health

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "redis": true
}
```

## Fleet Management

### List All Fleets

```bash
curl http://localhost:8000/fleets
```

Response:
```json
{
  "fleets": [
    {
      "id": 1,
      "name": "inventory",
      "description": "Inventory inspection and stock counting fleet",
      "category": "inventory",
      "color": "#22c55e",
      "max_drones": 20,
      "enabled": true,
      "drone_count": 0
    },
    {
      "id": 2,
      "name": "security",
      "description": "Security patrol and breach verification fleet",
      "category": "security",
      "color": "#ef4444",
      "max_drones": 10,
      "enabled": true,
      "drone_count": 0
    }
  ]
}
```

### Create a New Fleet

```bash
curl -X POST http://localhost:8000/fleets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "patrol-north",
    "description": "North wing patrol fleet",
    "category": "security",
    "color": "#3b82f6",
    "max_drones": 5
  }'
```

### Assign Drone to Fleet

```bash
curl -X POST http://localhost:8000/fleets/1/assign \
  -H "Content-Type: application/json" \
  -d '{
    "drone_id": 1,
    "notes": "Assigned for inventory duty"
  }'
```

### Bulk Assign Drones to Fleet

```bash
curl -X POST http://localhost:8000/fleets/1/assign-bulk \
  -H "Content-Type: application/json" \
  -d '{
    "drone_ids": [1, 2, 3, 4, 5],
    "notes": "Bulk assignment for warehouse inspection"
  }'
```

## Drone Management

### Register a Single Drone

```bash
curl -X POST http://localhost:8000/drones \
  -H "Content-Type: application/json" \
  -d '{
    "uri": "radio://0/80/1M/100M",
    "name": "drone-alpha",
    "fleet_id": 1
  }'
```

### Bulk Register Drones

```bash
curl -X POST http://localhost:8000/drones/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "drones": [
      {"uri": "radio://0/80/1M/101M", "name": "drone-1"},
      {"uri": "radio://0/80/1M/102M", "name": "drone-2"},
      {"uri": "radio://0/80/1M/103M", "name": "drone-3"}
    ],
    "fleet_id": 1
  }'
```

### List All Drones

```bash
curl http://localhost:8000/drones
```

### Update Drone State

```bash
curl -X PATCH http://localhost:8000/drones/1 \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

### Discover Available Drones (Crazyflie Scan)

```bash
curl -X POST http://localhost:8000/drones/discover
```

## Anchor (Loco Positioning) Management

Anchor positions use **NED** (North-East-Down): X = North, Y = East, Z = Down (positive Z = down). If your source is Z-up (e.g. height above ground), use drone-acharya with `--z-down` or convert before posting.

### List All Anchors

```bash
curl http://localhost:8000/anchors
```

### Get System Status

```bash
curl http://localhost:8000/anchors/system-status
```

Response:
```json
{
  "total_anchors": 4,
  "online_anchors": 3,
  "offline_anchors": 1,
  "calibrating_anchors": 0,
  "error_anchors": 0,
  "positioning_mode": "TWR",
  "system_ready": true,
  "coverage_area": {
    "x_min": 0.0,
    "x_max": 10.0,
    "y_min": 0.0,
    "y_max": 10.0,
    "z_min": 0.0,
    "z_max": 3.0
  }
}
```

### Register a Single Anchor

```bash
curl -X POST http://localhost:8000/anchors \
  -H "Content-Type: application/json" \
  -d '{
    "anchor_id": 0,
    "name": "anchor-northwest",
    "x": 0.0,
    "y": 0.0,
    "z": 2.5,
    "mode": "TWR",
    "notes": "Corner anchor NW"
  }'
```

### Bulk Register Anchors

```bash
curl -X POST http://localhost:8000/anchors/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "anchors": [
      {"anchor_id": 0, "name": "anchor-0", "x": 0, "y": 0, "z": 2, "mode": "TWR"},
      {"anchor_id": 1, "name": "anchor-1", "x": 10, "y": 0, "z": 2, "mode": "TWR"},
      {"anchor_id": 2, "name": "anchor-2", "x": 10, "y": 10, "z": 2, "mode": "TWR"},
      {"anchor_id": 3, "name": "anchor-3", "x": 0, "y": 10, "z": 2, "mode": "TWR"}
    ]
  }'
```

### Update Anchor Position

```bash
curl -X PATCH http://localhost:8000/anchors/0/position \
  -H "Content-Type: application/json" \
  -d '{
    "x": 0.5,
    "y": 0.5,
    "z": 2.5
  }'
```

### Send Heartbeat (Mark as Online)

```bash
curl -X POST "http://localhost:8000/anchors/0/heartbeat?battery_level=85"
```

## Mission Management

### Create a Mission

```bash
curl -X POST http://localhost:8000/missions \
  -H "Content-Type: application/json" \
  -d '{
    "waypoints": [
      {"x": 0, "y": 0, "z": 1},
      {"x": 2, "y": 0, "z": 1},
      {"x": 2, "y": 2, "z": 1},
      {"x": 0, "y": 2, "z": 1}
    ],
    "duration_seconds": 120,
    "target_drone_id": 1
  }'
```

### List All Missions

```bash
curl http://localhost:8000/missions
```

### Cancel a Mission

```bash
curl -X POST http://localhost:8000/missions/1/cancel
```

## Safety Operations

### Trigger Emergency Kill Switch

```bash
curl -X POST http://localhost:8000/safety/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"emergency": true}'
```

### Health Check All Drones

```bash
curl -X POST http://localhost:8000/safety/health-check
```

### Pre-flight Check

```bash
curl http://localhost:8000/safety/pre-flight/1
```

## LED Control

### Set LED Color

```bash
curl -X POST http://localhost:8000/led/1/set \
  -H "Content-Type: application/json" \
  -d '{"color": "green"}'
```

### Blink LED

```bash
curl -X POST http://localhost:8000/led/1/blink \
  -H "Content-Type: application/json" \
  -d '{"color": "red", "duration": 5}'
```

### Turn Off LED

```bash
curl -X POST http://localhost:8000/led/1/off
```

## Python Client Example

```python
import httpx

# Initialize client
client = httpx.Client(base_url="http://localhost:8000")

# Register a fleet
response = client.post("/fleets", json={
    "name": "inspection-team-a",
    "category": "inspection",
    "max_drones": 10
})
fleet_id = response.json()["id"]

# Register drones and assign to fleet
drones = []
for i in range(5):
    response = client.post("/drones", json={
        "uri": f"radio://0/80/1M/{100+i}M",
        "name": f"drone-{i+1}",
        "fleet_id": fleet_id
    })
    drones.append(response.json()["id"])

# Register anchors for positioning
anchors = [
    {"anchor_id": 0, "name": "corner-nw", "x": 0, "y": 0, "z": 2},
    {"anchor_id": 1, "name": "corner-ne", "x": 10, "y": 0, "z": 2},
    {"anchor_id": 2, "name": "corner-se", "x": 10, "y": 10, "z": 2},
    {"anchor_id": 3, "name": "corner-sw", "x": 0, "y": 10, "z": 2},
]
client.post("/anchors/bulk", json={"anchors": anchors})

# Create a mission
response = client.post("/missions", json={
    "waypoints": [
        {"x": 5, "y": 5, "z": 1},
        {"x": 5, "y": 5, "z": 2},
        {"x": 5, "y": 5, "z": 1}
    ],
    "duration_seconds": 60,
    "target_drone_id": drones[0]
})
mission_id = response.json()["mission_id"]

print(f"Created mission {mission_id} with fleet {fleet_id}")
```

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK` - Success
- `201 Created` - Resource created successfully
- `204 No Content` - Success with no body (e.g., DELETE)
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Missing or invalid API key
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource already exists
- `500 Internal Server Error` - Server error

## Fleet Categories

Predefined fleet categories:

| Category | Purpose | Max Drones (Default) |
|----------|---------|----------------------|
| `inventory` | Stock counting, inventory inspection | 20 |
| `security` | Patrol, breach verification | 10 |
| `cable-monitoring` | Cable/connector inspection | 15 |
| `inspection` | General infrastructure | 10 |
| `emergency` | Emergency response | 5 |
| `general` | General purpose | 10 |

## Anchor Positioning Modes

- `TWR` - Two-Way Ranging (requires 4+ anchors)
- `TDoA2` - Time Difference of Arrival 2 (requires 6+ anchors)
- `TDoA3` - Time Difference of Arrival 3 (requires 6+ anchors)

## Dashboard Navigation

The web UI provides these main sections:

- **Dashboard** (`/`) - Overview with fleet map and status
- **Drones** (`/drones`) - Full drone management with fleet assignment
- **Missions** (`/missions`) - Mission creation and monitoring
- **Fleets** (`/fleets`) - Fleet organization and drone assignment
- **Anchors** (`/anchors`) - Loco Positioning node configuration

## Testing with Docker Compose

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# Run integration tests
make test-integration

# View API logs
docker logs -f drone-swarm-api

# View dashboard logs
docker logs -f drone-swarm-dashboard
```
