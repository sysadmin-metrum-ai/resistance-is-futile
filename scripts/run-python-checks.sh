#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="python3"
if command -v uv >/dev/null 2>&1; then
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python -m compileall src scripts tests test-*.py
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run ruff check src scripts tests test-*.py
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run pytest tests/test_commissioning_profile.py tests/test_demo_mission.py tests/test_mission_planning.py tests/test_mission_identity.py tests/test_preflight_logic.py
else
  "$PYTHON_BIN" -m compileall src scripts tests test-*.py
fi
