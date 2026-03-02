---
phase: 02-dashboard-peripherals
plan: 05
type: execute
wave: 3
depends_on:
  - 03
autonomous: true

requirements:
  - LED-01

user_setup: []

files_modified: []
---

<objective>
Implement LED controller for drone state indication. LED shows green (ready), yellow (busy), red (error) based on drone state.
</objective>

**Tasks:**

1. **Create LEDController service**
   - Interface with Crazyflie LED (or placeholder)
   - Methods: set_color(color), blink(color, duration), off()
   - Colors: green (ready), yellow (busy), red (error)

2. **Create /led API endpoints**
   - POST /led/{drone_id}/set - set LED color
   - POST /led/{drone_id}/blink - blink LED
   - POST /led/{drone_id}/off - turn off LED

3. **Integrate LED control into DroneManager**
   - On drone state change, automatically set LED:
     - idle -> green
     - busy -> yellow
     - offline -> (blink green slowly)
     - error -> red
   - This provides automatic visual feedback
