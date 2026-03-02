---
phase: 01-backend-core
plan: 06
type: execute
wave: 1
depends_on:
  - 05
autonomous: true
gap_closure: true

requirements: []

user_setup: []

files_modified: []
---

<objective>
Create pytest integration tests matching UAT scenarios.
</objective>

**Tasks:**

1. **Add pytest dependencies to pyproject.toml:**
   - pytest>=7.0.0
   - pytest-asyncio>=0.23.0

2. **Create tests/test_integration.py:**
   - test_api_server_starts - Server starts on port 8000
   - test_post_missions_creates_mission - POST /missions returns 200/201
   - test_get_missions_returns_mission - GET /missions/{id} returns mission
   - test_get_drones_lists_drones - GET /drones returns drone list
   - test_post_safety_kill_switch - POST /safety/kill-switch returns 200
   - test_health_check_endpoint - GET /safety/health-check/{id} works

   Use pytest-asyncio for async tests, httpx.AsyncClient for API calls
