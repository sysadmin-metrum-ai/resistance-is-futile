# Phase 2: Dashboard & Peripherals - Research

**Researched:** 2026-02-28
**Domain:** Web Dashboard, Real-time Updates, Drone Hardware Integration
**Confidence:** HIGH (standard stack with well-documented patterns)

## Summary

Phase 2 builds a visual mission control dashboard for the Drone Swarm system. The dashboard displays drone status, mission tracking, and streaming LLM code generation. It integrates with the Phase 1 FastAPI backend via REST APIs and a new SSE endpoint for real-time updates. This phase also implements camera capture and LED status indicators for the drones.

**Primary recommendation:** Use Next.js 14 (App Router) with shadcn/ui for the dashboard, implement SSE for real-time updates, and create a modular frontend architecture that separates dashboard components from API integration logic.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **UI Framework:** React/Next.js with shadcn/ui components
- **Real-time Updates:** Server-Sent Events (SSE)
- **LLM Display:** Terminal-style panel with streaming tokens
- **Integration:** Consumes Phase 1 REST APIs, needs new SSE endpoint
- **Authentication:** API key via X-API-Key header (from Phase 1)

### Claude's Discretion
- Dashboard layout and visual design (card-based, grid layout recommended)
- Specific shadcn/ui components to use (Card, Table, Button, Badge patterns)
- Terminal component implementation approach
- Map visualization library for drone positions

### Deferred Ideas (OUT OF SCOPE)
- Mobile-responsive version - future phase
- Authentication/user management - separate phase if needed
- Historical mission analytics - separate phase
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | Dashboard displays real-time drone positions on 2D map | Map library selection, SSE for position updates |
| DASH-02 | Dashboard shows mission queue and current status | REST API consumption, polling/SSE strategy |
| DASH-03 | Dashboard displays drone health (battery, connection) | REST API drone endpoints, real-time state |
| DASH-04 | Dashboard provides manual kill switch button | REST API safety endpoint integration |
| CAM-01 | Drone captures images during mission for visual inspection | Camera integration architecture |
| CAM-02 | Images stored and accessible via API after mission | Storage strategy, API endpoint design |
| LED-01 | LED indicates drone state (green=ready, yellow=busy, red=error) | LED control architecture |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 14.x | React framework with App Router | Industry standard for React dashboards |
| React | 18.x | UI library | Required by Next.js |
| shadcn/ui | latest | Component library | Built on Radix UI, highly customizable |
| TypeScript | 5.x | Type safety | Standard for Next.js projects |
| Tailwind CSS | 3.x | Styling | Required by shadcn/ui |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @tanstack/react-query | 5.x | Data fetching/caching | REST API consumption |
| use-sse | 2.x | SSE client hook | Real-time updates |
| react-simple-maps | 3.x | 2D map visualization | DASH-01 drone positions |
| xterm | 5.x | Terminal emulator | LLM streaming display |
| @xterm/react | 1.x | React wrapper for xterm | Terminal panel integration |

### Backend Additions (for SSE)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | 1.x | SSE support in FastAPI | SSE endpoint implementation |
| python-sse | latest | SSE utilities | Streaming responses |

**Installation:**
```bash
# Frontend
npx create-next-app@latest dashboard --typescript --tailwind --eslint
cd dashboard
npx shadcn@latest init
npx shadcn@latest add card button badge table tabs

# For data fetching
npm install @tanstack/react-query use-sse

# For terminal
npm install xterm @xterm/react

# For maps
npm install react-simple-maps d3-scale

# Backend (add to Phase 1)
pip install sse-starlette
```

---

## Architecture Patterns

### Recommended Project Structure
```
dashboard/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Main dashboard page
│   │   ├── api/                # API routes (if needed)
│   │   └── globals.css         # Global styles
│   ├── components/
│   │   ├── ui/                 # shadcn/ui components
│   │   ├── dashboard/          # Dashboard-specific components
│   │   │   ├── DroneCard.tsx
│   │   │   ├── DroneMap.tsx
│   │   │   ├── MissionQueue.tsx
│   │   │   ├── LLMTerminal.tsx
│   │   │   └── KillSwitch.tsx
│   │   └── layout/
│   │       └── DashboardLayout.tsx
│   ├── lib/
│   │   ├── api.ts              # API client wrapper
│   │   ├── sse.ts               # SSE client setup
│   │   └── types.ts             # TypeScript interfaces
│   └── hooks/
│       ├── useDrones.ts
│       ├── useMissions.ts
│       └── useSSE.ts
├── public/
│   └── logos/                   # Customizable logos per venue
├── tailwind.config.ts
└── next.config.js
```

### Pattern 1: API Client Wrapper
**What:** Centralized API client that handles authentication and error handling
**When to use:** All API calls should go through this wrapper
**Example:**
```typescript
// Source: Standard React Query + Axios pattern
import { QueryClient } from '@tanstack/react-query';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add API key to all requests
apiClient.interceptors.request.use((config) => {
  const apiKey = process.env.NEXT_PUBLIC_API_KEY;
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

// Drone types (mirrors Phase 1)
export interface Drone {
  id: number;
  uri: string;
  name: string;
  state: 'idle' | 'busy' | 'offline' | 'error';
  battery: number | null;
  connection_quality: number | null;
  enabled: boolean;
  x?: number;  // Position X (from SSE)
  y?: number;  // Position Y (from SSE)
}

export interface Mission {
  id: number;
  mission_id: string;
  drone_id: number | null;
  waypoints: { x: number; y: number; z: number }[];
  duration_seconds: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  callback_url: string | null;
  result: Record<string, unknown> | null;
}
```

### Pattern 2: SSE Hook for Real-time Updates
**What:** Custom hook that manages SSE connection and state
**When to use:** For drone positions, mission status updates
**Example:**
```typescript
// Source: Standard SSE implementation pattern
import { useEffect, useState, useCallback } from 'react';

interface SSEMessage {
  type: 'drone_update' | 'mission_update' | 'llm_token';
  payload: unknown;
}

export function useSSE(endpoint: string) {
  const [data, setData] = useState<SSEMessage | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const eventSource = new EventSource(`${endpoint}`);

    eventSource.onopen = () => {
      setConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as SSEMessage;
        setData(parsed);
      } catch (e) {
        console.error('Failed to parse SSE message:', e);
      }
    };

    eventSource.onerror = () => {
      setConnected(false);
      setError(new Error('SSE connection failed'));
      eventSource.close();
    };

    return () => {
      eventSource.close();
      setConnected(false);
    };
  }, [endpoint]);

  return { data, error, connected };
}
```

### Pattern 3: Terminal Component for LLM Streaming
**What:** Xterm.js wrapper for displaying streaming code
**When to use:** LLM code generation panel
**Example:**
```typescript
// Source: @xterm/react documentation pattern
'use client';

import { useEffect, useRef } from 'react';
import { Terminal as XTerminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

interface TerminalProps {
  onToken?: (token: string) => void;
}

export function LLMTerminal({ onToken }: TerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerminal | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    const term = new XTerminal({
      theme: {
        background: '#0d1117',  // Dark theme like Claude Code
        foreground: '#c9d1d9',
        cursor: '#c9d1d9',
      },
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.4,
      cursorBlink: true,
      convertEol: true,  // Treat \n as new line
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit();
    });
    resizeObserver.observe(terminalRef.current);

    return () => {
      resizeObserver.disconnect();
      term.dispose();
    };
  }, []);

  // Expose method to write tokens
  const writeToken = useCallback((token: string) => {
    xtermRef.current?.write(token);
  }, []);

  const clear = useCallback(() => {
    xtermRef.current?.clear();
  }, []);

  return (
    <div
      ref={terminalRef}
      className="h-full w-full overflow-hidden rounded-md border border-slate-700"
    />
  );
}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UI Components | Build from scratch | shadcn/ui | Accessibility handled, consistent design, well-tested |
| Map Visualization | Custom canvas rendering | react-simple-maps | Built-in projections, SVG-based, lighter than Leaflet |
| Terminal Emulator | Custom text display | xterm.js | Terminal emulation is complex (cursor, colors, input) |
| Data Fetching | useEffect + fetch | TanStack Query | Caching, deduplication, error handling built-in |
| SSE Connection | Raw EventSource | use-sse or custom hook | Reconnection logic, cleanup handled |
| Form Validation | Custom validation | React Hook Form + Zod | Industry standard, TypeScript support |

---

## Common Pitfalls

### Pitfall 1: SSE Reconnection on Network Issues
**What goes wrong:** EventSource doesn't automatically reconnect after network interruption
**Why it happens:** Browser EventSource spec doesn't mandate reconnection
**How to avoid:** Use a library like `use-sse` or implement manual reconnection with exponential backoff
**Warning signs:** Dashboard shows stale data after network blip

### Pitfall 2: CORS Issues with SSE
**What goes wrong:** SSE requests blocked by CORS when frontend and backend on different origins
**Why it happens:** FastAPI doesn't include CORS headers for SSE by default
**How to avoid:** Ensure CORS middleware is configured in FastAPI (already done in Phase 1)
**Warning signs:** "EventSource failed to load" errors in console

### Pitfall 3: Terminal Memory Leaks
**What goes wrong:** Xterm.js buffer grows indefinitely with long streaming output
**Why it happens:** Default buffer holds unlimited scrollback
**How to avoid:** Set `scrollback` option to limit buffer size (e.g., 10000 lines)
**Warning signs:** Browser memory usage grows over time during long demos

### Pitfall 4: API Polling vs SSE Trade-off
**What goes wrong:** Over-polling API or under-utilizing SSE
**Why it happens:** Choosing wrong strategy for data type
**How to avoid:**
- SSE: Drone positions, mission status updates (frequent, low-latency)
- Polling (React Query): Drone list, mission list (on-demand, every 5-10s)
**Warning signs:** High API load, stale data, or unnecessary complexity

### Pitfall 5: Type Mismatch with Backend
**What goes wrong:** TypeScript types don't match Python backend response shapes
**Why it happens:** No shared types between frontend and backend
**How to avoid:** Mirror Pydantic models in TypeScript interfaces (already documented above)
**Warning signs:** Runtime errors from unexpected response shapes

---

## Code Examples

### Drone Status Card Component
```typescript
// Source: shadcn/ui Card + standard React patterns
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Battery, Wifi, AlertTriangle } from 'lucide-react';

interface DroneCardProps {
  drone: Drone;
}

export function DroneCard({ drone }: DroneCardProps) {
  const stateColors = {
    idle: 'bg-green-500',
    busy: 'bg-yellow-500',
    offline: 'bg-gray-500',
    error: 'bg-red-500',
  };

  const batteryColor = drone.battery
    ? drone.battery > 50 ? 'text-green-500'
    : drone.battery > 20 ? 'text-yellow-500'
    : 'text-red-500'
    : 'text-gray-500';

  return (
    <Card className="w-[280px]">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{drone.name}</CardTitle>
          <Badge className={stateColors[drone.state]}>{drone.state}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Battery className={`h-4 w-4 ${batteryColor}`} />
            <span className={batteryColor}>
              {drone.battery !== null ? `${drone.battery}%` : 'N/A'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Wifi className="h-4 w-4" />
            <span>
              {drone.connection_quality !== null
                ? `${drone.connection_quality}%`
                : 'N/A'}
            </span>
          </div>
          {drone.state === 'error' && (
            <div className="flex items-center gap-2 text-red-500">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm">Check drone logs</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

### Kill Switch Button
```typescript
// Source: shadcn/ui Button + API integration
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

export function KillSwitch() {
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const handleKillSwitch = async () => {
    if (!confirmed) {
      setConfirmed(true);
      return;
    }

    setLoading(true);
    try {
      await apiClient.post('/safety/kill-switch');
      alert('Kill switch activated - all drones landing');
    } catch (error) {
      console.error('Kill switch failed:', error);
      alert('Failed to activate kill switch');
    } finally {
      setLoading(false);
      setConfirmed(false);
    }
  };

  return (
    <Button
      variant={confirmed ? 'destructive' : 'outline'}
      size="lg"
      onClick={handleKillSwitch}
      disabled={loading}
      className={confirmed ? 'animate-pulse' : ''}
    >
      {loading ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      ) : (
        <AlertTriangle className="mr-2 h-4 w-4" />
      )}
      {confirmed ? 'CONFIRM - LAND ALL DRONES' : 'Emergency Kill Switch'}
    </Button>
  );
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| WebSocket for real-time | SSE for unidirectional | 2020+ | Simpler, works over HTTP/1.1, automatic reconnection |
| CRA (Create React App) | Next.js App Router | 2023 | Server components, better SEO, simplified routing |
| class components | Functional + hooks | 2019+ | Simpler code, better composition |
| Redux | TanStack Query | 2020+ | Less boilerplate, built-in caching |
| Custom CSS | Tailwind CSS + shadcn | 2021+ | Faster development, consistent design system |

**Deprecated/outdated:**
- `create-react-app`: No longer recommended, Next.js is preferred
- Redux for server state: TanStack Query is the standard now
- Class components: Modern React uses functional components exclusively

---

## Open Questions

1. **SSE Endpoint Design**
   - What we know: SSE should stream drone positions, mission status changes, and LLM tokens
   - What's unclear: Should there be separate SSE endpoints per data type or one multiplexed endpoint?
   - Recommendation: Single `/events` endpoint with message type field is simpler and sufficient

2. **Map Coordinate System**
   - What we know: Drones have x, y, z coordinates from UWB positioning
   - What's unclear: What's the origin and scale for the 2D map display?
   - Recommendation: Start with simple scaling, refine during Phase 3 (Venue Setup)

3. **LLM Integration**
   - What we know: Terminal panel shows streaming code
   - What's unclear: Where does the LLM API call happen - frontend or backend proxy?
   - Recommendation: Backend proxy in Phase 1, frontend receives tokens via SSE

4. **Camera Image Storage**
   - What we know: CAM-01 requires image capture, CAM-02 requires API access
   - What's unclear: Local drone storage or centralized? File system or object storage?
   - Recommendation: Local file system initially, move to S3/object storage if scale requires

---

## Validation Architecture

> Skipped: workflow.nyquist_validation is not enabled in config.json

For future consideration when validation is enabled:
- Test Framework: Jest + React Testing Library
- E2E: Playwright (for full dashboard testing)
- Visual Regression: Chromatic (optional)

---

## Sources

### Primary (HIGH confidence)
- Next.js 14 Documentation - https://nextjs.org/docs
- shadcn/ui Documentation - https://ui.shadcn.com
- TanStack Query Documentation - https://tanstack.com/query
- xterm.js Documentation - https://xtermjs.org

### Secondary (MEDIUM confidence)
- FastAPI SSE patterns - Standard community implementations
- react-simple-maps - GitHub repository examples

### Tertiary (LOW confidence)
- Specific version compatibility - Should verify during implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Well-established Next.js + shadcn/ui stack
- Architecture: HIGH - Standard patterns for React dashboards
- Pitfalls: MEDIUM - Common pitfalls documented, some are framework-specific

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (standard stack is stable, ~30 days)
