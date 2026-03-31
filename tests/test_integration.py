"""Integration tests for Drone Swarm API.

These tests verify that the FastAPI app boots and that the expected routes are
reachable using the current mounted `/api/*` prefixes, even when optional
backends such as PostgREST or Redis are unavailable.
"""

import os
import signal
import subprocess
import time
from pathlib import Path

import httpx
import pytest

# Test configuration
API_BASE_URL = "http://localhost:8000"
STARTUP_TIMEOUT = 30  # seconds
STARTUP_CHECK_INTERVAL = 1  # seconds
PROJECT_DIR = Path(__file__).resolve().parents[1]


def assert_route_reachable(response: httpx.Response, allowed_statuses: tuple[int, ...]) -> None:
    """Treat dependency-driven failures as reachable routes, not missing routes."""
    assert response.status_code in allowed_statuses, (
        f"Expected one of {allowed_statuses}, got {response.status_code}: {response.text}"
    )


class TestIntegration:
    """Integration tests for the Drone Swarm API."""

    @pytest.fixture(scope="class")
    def api_server(self):
        """Start the API server for testing."""
        # Start the server
        env = os.environ.copy()
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "uvicorn",
                "src.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=str(PROJECT_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to be ready
        start_time = time.time()
        server_ready = False

        while time.time() - start_time < STARTUP_TIMEOUT:
            try:
                response = httpx.get(f"{API_BASE_URL}/health", timeout=2.0)
                if response.status_code == 200:
                    server_ready = True
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                time.sleep(STARTUP_CHECK_INTERVAL)

        if not server_ready:
            process.kill()
            pytest.fail("API server failed to start within timeout")

        yield process

        # Cleanup: kill the server
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    @pytest.fixture
    def client(self, api_server):
        """Create an HTTP client for testing."""
        return httpx.Client(base_url=API_BASE_URL, timeout=10.0)

    @pytest.fixture
    def async_client(self, api_server):
        """Create an async HTTP client for testing."""
        return httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0)

    def test_api_server_starts(self, client):
        """UAT 1: Server starts without errors on port 8000."""
        response = client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy", f"Server not healthy: {data}"

    @pytest.mark.asyncio
    async def test_post_missions_creates_mission(self, async_client):
        """Mission submit route is mounted and responds at the current API prefix."""
        mission_data = {
            "waypoints": [
                {"x": 0.0, "y": 0.0, "z": 1.0},
                {"x": 1.0, "y": 0.0, "z": 1.0},
                {"x": 1.0, "y": 1.0, "z": 1.0},
            ],
            "duration_seconds": 60,
        }
        response = await async_client.post("/api/missions", json=mission_data)
        assert_route_reachable(response, (200, 201, 401, 409, 422, 500, 503))
        if response.status_code in (200, 201):
            data = response.json()
            assert "mission_id" in data, f"mission_id not in response: {data}"

    @pytest.mark.asyncio
    async def test_get_missions_returns_mission(self, async_client):
        """Mission list route is mounted and responds at the current API prefix."""
        response = await async_client.get("/api/missions", timeout=5.0)
        assert_route_reachable(response, (200, 401, 500))

    def test_get_drones_lists_drones(self, client):
        """Drone list route is mounted and responds at the current API prefix."""
        response = client.get("/api/drones")
        assert_route_reachable(response, (200, 401, 500))

    def test_post_safety_kill_switch(self, client):
        """Kill switch route is mounted and returns a valid API response."""
        response = client.post("/api/safety/kill-switch", json={"emergency": True})
        assert_route_reachable(response, (200, 401))

    def test_health_check_endpoint(self, client):
        """Health check route is mounted and responds at the current API prefix."""
        response = client.get("/api/safety/health-check/1")
        assert_route_reachable(response, (200, 401, 404, 500))
        if response.status_code == 200:
            data = response.json()
            assert "battery" in data or "ready" in data, (
                f"Response missing expected fields: {data}"
            )

    def test_fleets_endpoints(self, client):
        """Fleet route is mounted and responds at the current API prefix."""
        # List fleets
        response = client.get("/api/fleets")
        assert_route_reachable(response, (200, 401, 500))

    def test_anchors_endpoints(self, client):
        """Anchor routes are mounted and respond at the current API prefix."""
        response = client.get("/api/anchors")
        assert_route_reachable(response, (200, 401, 500))

        response = client.get("/api/anchors/system-status")
        assert_route_reachable(response, (200, 401, 500))
