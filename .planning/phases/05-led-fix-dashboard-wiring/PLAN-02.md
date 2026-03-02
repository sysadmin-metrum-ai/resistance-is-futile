---
wave: 1
depends_on: []
files_modified:
  - dashboard/src/components/DroneCard.tsx
  - dashboard/src/components/MissionImages.tsx
  - dashboard/src/app/page.tsx
autonomous: true
---

# Phase 5 Plan 02: Gap Closure - Camera/LED Dashboard Wiring

## Goal

Wire camera images and LED controls to Dashboard UI to complete GAP-02.

## Gap Analysis

**Gap 1: Camera images not accessible in Dashboard**
- API functions exist: `getMissionImages()`, `getImageUrl()`, `captureImage()`, `deleteImage()`
- Missing: UI component that displays mission images

**Gap 2: LED state not controllable from Dashboard**
- API functions exist: `setLEDColor()`, `blinkLED()`, `turnOffLED()`
- Missing: UI controls that trigger these functions

## Implementation Plan

### Wave 1: Core Components (Parallel)

**Task 1: Create MissionImages Component**
- Create `dashboard/src/components/MissionImages.tsx`
- Props: missionId, onClose callback
- Features:
  - Fetch images using `getMissionImages(missionId)`
  - Display images in a grid using `getImageUrl(imageId)` for URLs
  - Show loading and error states
  - Use existing Card component for container

**Task 2: Add LED Controls to DroneCard**
- Modify `dashboard/src/components/DroneCard.tsx`
- Add LED control buttons:
  - Color picker or preset buttons (green, yellow, red, blue)
  - Blink button with duration
  - Off button
- Use React Query useMutation for LED actions
- Show success/error feedback via toast or inline message

### Wave 2: Integration

**Task 3: Wire Components to Dashboard Page**
- Modify `dashboard/src/app/page.tsx`:
  - Add state for selected mission (for images panel)
  - Add MissionImages panel/dialog when mission selected
  - Ensure DroneCard has LED controls

## UI/UX Design

### MissionImages Component
```
[Mission Images Header]
[Loading spinner | Grid of images | "No images" message]
```

### LED Controls in DroneCard
```
[Drone Name] [State Badge]
Battery: 85% | Signal: 90%
Position: (1.2, 3.4)

[LED Controls - Collapsible Section]
[Green] [Yellow] [Red] [Blue] [Blink] [Off]
[Status message: "LED set to green" or error]
```

## Verification Criteria

| # | Truth | Verification Method |
|---|-------|-------------------|
| 1 | Camera images accessible in Dashboard | Select a mission with images, verify grid displays |
| 2 | LED state controllable from Dashboard | Click LED button, verify drone LED changes color |

## Must-Haves (for goal-backward verification)

- [ ] MissionImages.tsx component created with getMissionImages integration
- [ ] DroneCard.tsx has working LED control buttons
- [ ] Buttons call correct API functions (setLEDColor, blinkLED, turnOffLED)
- [ ] UI shows feedback on LED action success/failure
- [ ] Images render correctly when mission has captured images

## API Functions to Use

```typescript
// From dashboard/src/lib/api.ts
import { getMissionImages, getImageUrl, setLEDColor, blinkLED, turnOffLED } from '@/lib/api';

// Camera
getMissionImages(missionId: string): Promise<ImageListResponse>
getImageUrl(imageId: string): string

// LED
setLEDColor(droneId: number, color: string): Promise<LEDResponse>
blinkLED(droneId: number, color: string, duration: number): Promise<LEDResponse>
turnOffLED(droneId: number): Promise<LEDResponse>
```

## Colors for LED

Standard LED colors to support:
- green (#00FF00)
- yellow (#FFFF00)
- red (#FF0000)
- blue (#0000FF)
- white (#FFFFFF)
- off (turn off LED)

---

*Plan created: 2026-02-28*
*Phase: 05-led-fix-dashboard-wiring (gap closure)*
