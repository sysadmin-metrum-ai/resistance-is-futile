# Stack Research

**Domain:** Drone Swarm Control System with Agent API and Web Dashboard
**Researched:** 2026-02-27
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI | 0.115+ | REST API server + WebSocket endpoints | Built-in async support, native WebSocket for real-time drone telemetry, automatic OpenAPI docs, Pydantic integration. Industry standard for Python APIs. |
| React | 18.x | Web dashboard frontend | Component-based, excellent ecosystem, strong TypeScript support. Context7: /facebook/react |
| TypeScript | 5.x | Frontend type safety | Catches errors at compile time, better DX for complex drone state management |
| PostgreSQL | 16+ | Mission logs, drone registry, scheduling | ACID compliance for mission history, JSONB for flexible telemetry storage. Context7: /websites/postgresql_16 |
| Redis | 7.x | Real-time telemetry cache, pub/sub | Sub-millisecond latency for live drone positions, natural fit for WebSocket broadcast |
| Docker | Latest | Container deployment | Standard for OTA deployment, reproducible environments |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | 2.x | Data validation | All API request/response models (FastAPI native support) |
| Socket.IO | 4.x | Real-time bidirectional communication | When you need fallback transports, rooms, auto-reconnect. Alternative: FastAPI native WebSockets |
| python-socketio | 5.x | Python Socket.IO server | If using Socket.IO on backend |
| fastapi-mqtt | Latest | MQTT integration | For drone-to-server messaging (QoS, retained messages) |
| SQLAlchemy | 2.x | ORM | Database operations, migrations |
| asyncpg | Latest | Async PostgreSQL driver | Non-blocking DB queries for high-frequency telemetry |
| Uvicorn | Latest | ASGI server | Production ASGI server for FastAPI |
| httpx | Latest | HTTP client | For agent API calls, external integrations |
| python-multipart | Latest | File uploads | For OTA firmware uploads |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Vite | Frontend build | Faster than webpack, native TS support |
| TailwindCSS | Styling | Rapid UI development for dashboard |
| Pyright | Python type checking | Fast, accurate type checking |
| pre-commit | Git hooks | Code quality enforcement |
| docker-compose | Local development | Full stack local dev |

## Installation

```bash
# Backend
pip install fastapi uvicorn[standard] pydantic sqlalchemy asyncpg redis python-socketio fastapi-mqtt python-multipart

# Frontend
npm create vite@latest dashboard -- --template react-ts
npm install @socket.io/client axios @tanstack/react-query zustand

# Dev
npm install -D tailwindcss postcss autoprefixer @types/node
pip install pytest pytest-asyncio httpx
```

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| API Framework | FastAPI | Flask | When you need simpler synchronous code, but FastAPI is better for async drone comms |
| API Framework | FastAPI | aiohttp | FastAPI provides better validation, docs, and WebSocket handling |
| Web Dashboard | React | Vue | Personal preference; React has larger ecosystem for complex state |
| Real-time | Native WebSockets | Socket.IO | Socket.IO adds overhead; use only if you need fallback transports |
| Database | PostgreSQL | SQLite | SQLite fine for single-machine demos, but no concurrent write support |
| Cache/Pub-sub | Redis | In-memory | Redis needed for multi-instance deployment, persistence |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Django | Overkill for this use case, async support less mature | FastAPI |
| cfclient (GUI) | Desktop client, not suitable for API server | cflib (library) directly |
| MQTT over HTTP | Polling inefficient for real-time | WebSockets or MQTT (paho-mqtt) |
| MongoDB | Less suitable for structured mission logs with ACID needs | PostgreSQL |
| Celery | Task queue adds complexity; use async for I/O-bound drone ops | Native async or Redis queues |

## Stack Patterns by Variant

**If deploying to a single Raspberry Pi/edge device:**
- Use SQLite instead of PostgreSQL
- Use native WebSockets instead of Socket.IO
- Consider running Python backend directly (no Docker)

**If need multi-drone high-frequency telemetry (50+ Hz):**
- Use Redis Pub/Sub as message bus between cflib readers and WebSocket writers
- Consider separate "telemetry collector" process per drone
- Use binary message encoding (MessagePack) for bandwidth

**If agent integration requires MCP (Model Context Protocol):**
- Build FastAPI endpoints following MCP tool schema
- Use Pydantic models matching MCP tool definitions
- Agent can treat drone API as "tools" it can invoke

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI 0.115+ | Python 3.9+ | Required for modern Pydantic v2 |
| Pydantic 2.x | FastAPI 0.100+ | Breaking changes in Pydantic v2 |
| SQLAlchemy 2.x | Python 3.9+ | Full async support |
| React 18 | TypeScript 5.x | Use tsconfig "jsx": "react-jsx" |
| Socket.IO 4.x | python-socketio 5.x | Protocol-compatible |

## Architecture Notes

### Drone Communication Path

```
Crazyflie (radio) --> cflib (Python) --> MQTT/WebSocket --> FastAPI --> React Dashboard
                                       --> PostgreSQL (logs)
                                       --> Redis (live cache)
```

### Agent API Pattern

```
Agent --> REST POST /missions --> FastAPI --> Queue/Process --> cflib --> Crazyflie
                      |
                      v
                 WebSocket --> Agent (async status updates)
```

### OTA Deployment Pattern

```
Dashboard (upload) --> FastAPI --> /tmp or object storage --> Docker build --> Push to device
                                                               |
                                                         Use docker save/load
                                                         or registry pull
```

## Sources

- Context7: /fastapi/fastapi — FastAPI WebSocket documentation
- Context7: /websites/fastapi_tiangolo — FastAPI framework overview
- Context7: /facebook/react — React library
- Context7: /websites/react_dev — React documentation
- Context7: /websites/socket_io_v4 — Socket.IO real-time communication
- Context7: /websites/postgresql_16 — PostgreSQL database
- Context7: /websites/redis_io — Redis in-memory store
- Context7: /websites/pydantic_dev — Pydantic data validation
- Context7: /bitcraze/crazyflie-lib-python — Crazyflie Python API
- Context7: /miguelgrinberg/python-socketio — Python Socket.IO
- Context7: /websites/docker — Docker containerization

---
*Stack research for: Drone Swarm Agent Integration*
*Researched: 2026-02-27*
