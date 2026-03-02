---
phase: 02-dashboard-peripherals
plan: 04
type: execute
wave: 3
depends_on:
  - 03
autonomous: true

requirements:
  - CAM-01
  - CAM-02

user_setup: []

files_modified: []
---

<objective>
Implement camera capture during missions and image API for retrieval. Camera captures images at mission start/intervals, stored and accessible via REST API.
</objective>

**Tasks:**

1. **Add camera configuration**
   - Config: IMAGE_STORAGE_PATH (default: ./captures)
   - Config: IMAGE_QUALITY (default: 85)

2. **Create CameraCapture service**
   - Interface with Crazyflie camera (or placeholder)
   - Capture image during mission execution
   - Save to filesystem with mission_id timestamp
   - Return file path

3. **Create /images API endpoints**
   - POST /images/capture - trigger capture, returns image_id
   - GET /images/{image_id} - download image file
   - GET /images/mission/{mission_id} - list images for mission
   - DELETE /images/{image_id} - remove image

4. **Integrate capture into MissionWorker**
   - Call CameraCapture.capture() at mission start and intervals
   - Associate images with mission in database
   - Handle capture failures gracefully (log and continue)
