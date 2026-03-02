---
phase: 01-backend-core
plan: 04
type: execute
wave: 1
depends_on: []
autonomous: true
gap_closure: true

requirements: []

user_setup: []

files_modified: []
---

<objective>
Create Makefile with self-contained test infrastructure. Targets: install, services-up, services-down, run, test, test-integration, clean.
</objective>

**Tasks:**

1. **Create Makefile with targets:**
   - `make install` - Install Python dependencies via uv
   - `make services-up` - Start Redis via Docker
   - `make services-down` - Stop services
   - `make run` - Start API server on port 8000
   - `make test` - Run pytest unit tests
   - `make test-integration` - Run integration tests against running API
   - `make clean` - Cleanup temp files and containers
   - Use `uv` for Python package management
   - Use Docker for Redis service (redis:alpine)
