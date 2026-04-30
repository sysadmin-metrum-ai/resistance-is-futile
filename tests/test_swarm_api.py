from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import swarm as swarm_route
from src.swarm.health import StaticHealthProbe
from src.swarm.models import DroneHealth
from src.swarm.service import SwarmDeployService
from src.swarm.session import SwarmSessionRunner


def make_client(health_by_uri: dict[str, DroneHealth], active_mission_id: str | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(swarm_route.router, prefix="/swarm")
    service = SwarmDeployService(SwarmSessionRunner(probe=StaticHealthProbe(health_by_uri)))
    service._active_mission_id = active_mission_id
    app.dependency_overrides[swarm_route.get_service] = lambda: service
    return TestClient(app)


def healthy(uri: str, score: float, y: float = 0.0) -> DroneHealth:
    return DroneHealth(
        uri=uri,
        ready=True,
        score=score,
        voltage=4.0,
        battery_percent=90,
        connection_quality=100,
        battery_pass=True,
        estimator_ready=True,
        lighthouse_ready=True,
        pose=(0.0, y, 0.0),
    )


def test_swarm_deploy_dry_run_returns_selection_and_plan():
    uris = ("a", "b", "c", "d")
    client = make_client({uri: healthy(uri, i + 80, i * 0.4) for i, uri in enumerate(uris)})

    response = client.post(
        "/swarm/deploy",
        json={"swarm_size": 3, "allowed_uris": list(uris), "dry_run": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "dry_run"
    assert len(data["selected"]) == 3
    assert data["plan"]["final_pose"] == [0.5, 0.0, 0.55]
    assert data["events"]


def test_swarm_deploy_refuses_insufficient_healthy_drones():
    health = {
        "a": healthy("a", 90),
        "b": DroneHealth("b", False, 0, reasons=("low_voltage",)),
        "c": DroneHealth("c", False, 0, reasons=("weak_connection",)),
    }
    client = make_client(health)

    response = client.post(
        "/swarm/deploy",
        json={"swarm_size": 3, "allowed_uris": ["a", "b", "c"], "dry_run": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "refused"
    assert data["message"] == "insufficient_healthy_drones"
    assert len(data["selected"]) == 1


def test_swarm_deploy_rejects_when_mission_already_active():
    client = make_client({}, active_mission_id="existing")

    response = client.post("/swarm/deploy", json={"allowed_uris": ["a", "b", "c"]})

    assert response.status_code == 409
    assert "already active" in response.json()["detail"]


def test_swarm_health_endpoint_returns_live_health(monkeypatch):
    app = FastAPI()
    app.include_router(swarm_route.router, prefix="/swarm")

    async def fake_check(candidates, *, probe, thresholds):
        return [healthy(candidate.uri, 90, index * 0.4) for index, candidate in enumerate(candidates)]

    monkeypatch.setattr(swarm_route, "check_candidates_concurrently", fake_check)
    client = TestClient(app)

    response = client.post("/swarm/health", json={"allowed_uris": ["a", "b", "c"]})

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 3
    assert all(item["ready"] for item in data["results"])

