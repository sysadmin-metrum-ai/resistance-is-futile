# Phase 5: LED Fix + Dashboard Wiring - Research

**Researched:** 2026-02-28
**Domain:** Backend integration fix + Frontend dashboard wiring
**Confidence:** HIGH

## Summary

This phase addresses three gap closure items from the v1.0 audit:

1. **LED hardcoded URI bug**: The LED API uses hardcoded `f"drone-{drone_id}"` instead of fetching the actual URI from PostgREST database
2. **Camera API unwired**: Camera API exists (`/images/*`) but Dashboard has no way to view images
3. **LED API unwired**: LED API exists (`/led/{drone_id}/*`) but Dashboard has no control UI

All three issues are well-defined technical debt with clear fix paths. The backend fix requires using the existing `DroneManager.get_drone(drone_id)` method which returns the full drone record including `uri`. The frontend wiring requires adding API client functions and UI components following existing patterns.

**Primary recommendation:** Fix LED URI in backend first, then wire both camera and LED APIs to Dashboard using the established React Query + shadcn/ui pattern.

---

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **LED URI Fix**: Fetch drone URI from PostgREST database instead of hardcoding `f"drone-{drone_id}"`
   - Fix locations: led.py lines 83, 123, 149
   - Also fix drone_manager.py line 218 (same bug)

2. **Camera Wiring**: Camera API already exists at `/images/*` endpoints
   - Add image viewing capability to Dashboard (how is Planner's discretion)

3. **LED Dashboard Control**: LED API already exists at `/led/{drone_id}/*` endpoints
   - Add LED control UI to Dashboard (how is Planner's discretion)

### Claude's Discretion

- Exact UI placement for LED controls
- Exact UI placement for camera viewer
- API client implementation details
- State management approach

### Deferred Ideas (OUT OF SCOPE)

None — all items are within the gap closure scope.

</user_constraints>

---

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GAP-02 | LED URI fix + Dashboard wiring | Backend: DroneManager.get_drone() returns uri from PostgREST. Frontend: Existing API patterns in api.ts |

</phase_requirements>

---

## Standard Stack

### Backend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | latest | API framework | Existing project stack |
| httpx | latest | Async HTTP client | Already used in PostgREST client |
| PostgRESTClient | existing | Database access | Already exists, returns drone with uri field |

### Frontend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js 16 | 16.x | React framework | Existing project stack |
| React Query | 5.x | Server state management | Existing project stack |
| shadcn/ui | latest | Component library | Existing project stack |
| axios | latest | HTTP client | Already used in existing api.ts |

### Testing
| Library | Purpose | When to Use |
|---------|---------|-------------|
| pytest | Backend unit tests | LED URI fix verification |
| Vitest | Frontend unit tests | API client and component tests |

---

## Architecture Patterns

### Backend Fix Pattern: Fetch URI from PostgREST

The fix requires using the existing `DroneManager.get_drone(drone_id)` method which queries PostgREST:

```python
# Current (broken) - src/api/routes/led.py line 83
drone_uri = f"drone-{drone_id}"

# Fixed - uses existing service
from src.services.drone_manager import DroneManager, get_drone_manager

drone_manager = await get_drone_manager()
drone = await drone_manager.get_drone(drone_id)  # Returns {id, uri, name, state, ...}
drone_uri = drone["uri"]  # Actual URI from database
```

**Key insight:** The `DroneManager.get_drone()` method already exists (line 131-145 in drone_manager.py) and returns the full drone record including the `uri` field.

### Frontend Wiring Pattern: API Client + React Query

Existing pattern from api.ts:

```typescript
// 1. Add API function in lib/api.ts
export async function setLEDColor(droneId: number, color: string): Promise<LEDResponse> {
  const response = await apiClient.post<LEDResponse>(`/led/${droneId}/set`, { color });
  return response.data;
}

// 2. Use in component with React Query
const ledMutation = useMutation({
  mutationFn: ({ droneId, color }: { droneId: number; color: string }) =>
    setLEDColor(droneId, color),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['drones'] });
  },
});
```

### Image Display Pattern

```typescript
// Get mission images
export async function getMissionImages(missionId: string): Promise<ImageListResponse> {
  const response = await apiClient.get<ImageListResponse>(`/images/mission/${missionId}`);
  return response.data;
}

// Display in component - use Next.js Image or standard img tag
<img src={`${process.env.NEXT_PUBLIC_API_URL}/images/${imageId}`} alt="Capture" />
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fetching drone URI | Construct URI from ID | DroneManager.get_drone() | Already exists, handles DB |
| HTTP client in frontend | Fetch API or custom | axios (already in project) | Already configured with API key |
| Server state | local useState | React Query (already in project) | Caching, refetch, loading states |

---

## Common Pitfalls

### Pitfall 1: Forgetting drone_manager.py also has the bug
**What goes wrong:** Only fix led.py, miss drone_manager.py line 218
**Why it happens:** Same copy-paste bug exists in two files
**How to avoid:** Search for `f"drone-{` pattern across entire codebase
**Warning signs:** LED still doesn't work after fixing led.py

### Pitfall 2: Image storage path not accessible to frontend
**What goes wrong:** Images stored on server filesystem but Dashboard can't reach them
**Why it happens:** /images endpoint serves files directly, need proper routing
**How to avoid:** Use the existing /images/{image_id} endpoint which returns file with correct content-type

### Pitfall 3: LED control UI showing for offline drones
**What goes wrong:** User can try to control LED on disconnected drone
**Why it happens:** No state check before showing control UI
**How to avoid:** Only show LED controls when drone.state !== 'offline'

---

## Code Examples

### LED API Endpoints (already exist)
```
POST /led/{drone_id}/set   - Set solid color
POST /led/{drone_id}/blink - Blink color for duration
POST /led/{drone_id}/off   - Turn off LED
```

### Camera API Endpoints (already exist)
```
POST   /images/capture           - Capture image (mission_id required)
GET    /images/{image_id}       - Download image file
GET    /images/mission/{mission_id} - List images for mission
DELETE /images/{image_id}       - Delete image
```

### Database Schema (from drone_manager.py)
```python
drone_data = {
    "uri": uri,           # e.g., 'radio://0/80/1M/100M'
    "name": name,         # e.g., 'drone-1'
    "state": "idle",      # idle/busy/offline/error
    "battery": 0,
    "connection_quality": 0,
    "enabled": True,
}
```

---

## Open Questions

1. **Image gallery approach**
   - What we know: Dashboard shows mission list, images API exists
   - What's unclear: Best UX for viewing images (modal? gallery tab? per-drone?)
   - Recommendation: Add as tab in existing drone detail view or separate "Images" tab in main dashboard

2. **LED control placement**
   - What we know: LED API has set/blink/off, DroneCard shows drone info
   - What's unclear: Should LED controls be per-drone or global?
   - Recommendation: Add to DroneCard component (per-drone control)

---

## Validation Architecture

> Skipped - workflow.nyquist_validation not enabled in config.json

---

## State of the Art

This is a bug fix and integration task, not new feature development. No state of the art changes needed.

---

## Sources

### Primary (HIGH confidence)
- `/home/cgadgil/src/resistance-is-futile/src/api/routes/led.py` - LED API endpoints
- `/home/cgadgil/src/resistance-is-futile/src/services/drone_manager.py` - DroneManager.get_drone() method
- `/home/cgadgil/src/resistance-is-futile/src/api/routes/images.py` - Camera API endpoints
- `/home/cgadgil/src/resistance-is-futile/dashboard/src/lib/api.ts` - Existing frontend API patterns
- `/home/cgadgil/src/resistance-is-futile/dashboard/src/types/index.ts` - TypeScript type definitions

### Secondary (MEDIUM confidence)
- Project STATE.md - Documents Next.js + React Query stack
- v1.0 MILESTONE-AUDIT.md - Lists exact issues to fix

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing project libraries
- Architecture: HIGH - Leveraging existing patterns
- Pitfalls: HIGH - Issues are well-defined bugs, not architectural unknowns

**Research date:** 2026-02-28
**Valid until:** 90 days - Bug fix task, no external dependencies
