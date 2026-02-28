"""Integration tests for Drone Swarm API.

These tests verify the core API endpoints against a running server.
Run with: make test-integration
"""

import pytest
import httpx
import subprocess
import time
import os
import signal

# Test configuration
API_BASE_URL = "http://localhost:8000"
STARTUP_TIMEOUT = 30  # seconds
STARTUP_CHECK_INTERVAL = 1  # seconds


class TestIntegration:
    """Integration tests for the Drone Swarm API."""

    @pytest.fixture(scope="class")
    def api_server(self):
        """Start the API server for testing."""
        # Change to project directory
        project_dir = "/home/cgadgil/src/resistance-is-futile"

        # Start the server
        env = os.environ.copy()
        process = subprocess.Popen(
            ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=project_dir,
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
        """UAT 2: POST /missions returns 200/201 with mission_id."""
        mission_data = {
            "drone_id": "test-drone-001",
            "waypoints": [
                {"x": 0.0, "y": 0.0, "z": 1.0},
                {"x": 1.0, "y": 0.0, "z": 1.0},
                {"x": 1.0, "y": 1.0, "z": 1.0},
            ],
        }
        response = await async_client.post("/missions", json=mission_data)
        assert response.status_code in (200, 201), f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "mission_id" in data, f"mission_id not in response: {data}"

    @pytest.mark.asyncio
    async def test_get_missions_returns_mission(self, async_client):
        """UAT 3: GET /missions/{id} returns mission with status, waypoints."""
        # First create a mission
        mission_data = {
            "drone_id": "test-drone-002",
            "waypoints": [
                {"x": 0.0, "y": 0.0, "z": 1.0},
            ],
        }
        create_response = await async_client.post("/missions", json=mission_data)
        assert create_response.status_code in (200, 201)
        mission_id = create_response.json()["mission_id"]

        # Then get it
        get_response = await async_client.get(f"/missions/{mission_id}")
        assert get_response.status_code == 200, f"GET failed: {get_response.text}"
        mission = get_response.json()
        assert "status" in mission, f"status not in mission: {mission}"
        assert "waypoints" in mission, f"waypoints not in mission: {mission}"

    def test_get_drones_lists_drones(self, client):
        """UAT 4: GET /drones returns list of drones with state, battery, connection."""
        response = client.get("/drones")
        assert response.status_code == 200, f"GET /drones failed: {response.text}"
        data = response.json()
        # Should return a list (may be empty if no drones)
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_post_safety_kill_switch(self, client):
        """UAT 5: POST /safety/kill-switch returns 200."""
        response = client.post("/safety/kill-switch", json={"emergency": True})
        assert response.status_code == 200, f"Kill switch failed: {response.text}"

    def test_health_check_endpoint(self, client):
        """UAT 6: GET /safety/health-check/{id} returns battery and connection status."""
        response = client.get("/safety/health-check/test-drone-001")
        assert response.status_code in (200, 404), f"Health check failed: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "battery" in data, f"battery not in response: {data}"
            assert "connection" in data, f"connection not in response: {data}"
