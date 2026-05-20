import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import swarm as swarm_route
from src.swarm.executor import ExecutionResult
from src.swarm.executor import PreparedExecution
from src.swarm.health import StaticHealthProbe
from src.swarm.models import DEFAULT_MIN_SEPARATION_M
from src.swarm.models import DroneHealth
from src.swarm.models import CRAZY_PINWHEEL_COMPACT_SWARM_SIZE
from src.swarm.models import CRAZY_PINWHEEL_SWARM_SIZE
from src.swarm.models import DEFAULT_SWARM_SIZE
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.roster import DEFAULT_CRAZY_PINWHEEL_COMPACT_FLEET
from src.swarm.roster import DEFAULT_FULL_FLEET
from src.swarm.service import SwarmDeployService
from src.swarm.session import SwarmSessionRunner


class FakeExecutor:
    def execute(self, plan, *, arm, **_kwargs):
        return ExecutionResult(events=(), plan=plan)

    def prepare(self, plan, *, phase_callback=None):
        if phase_callback:
            phase_callback("ready_to_deploy", {"selected": [drone.uri for drone in plan.drones]})
        return PreparedExecution(plan=plan, connections=())

    def launch(self, prepared, *, phase_callback=None, **_kwargs):
        if phase_callback:
            phase_callback("taking_off", {})
            phase_callback("returning", {})
            phase_callback("completed", {})
        return ExecutionResult(events=("takeoff", "return", "land"), plan=prepared.plan)


class EmergencyExecutor(FakeExecutor):
    def emergency_stop_active(self):
        return ["radio://0/80/2M/E7E7E7E701"]


def test_swarm_request_default_minimum_separation_matches_demo_clearance():
    assert swarm_route.SwarmDeployRequest().min_separation_m == DEFAULT_MIN_SEPARATION_M == 0.20


class CapturingRunner(SwarmSessionRunner):
    def __init__(self, *args, captured_specs, **kwargs):
        super().__init__(*args, **kwargs)
        self.captured_specs = captured_specs

    async def prepare(self, spec, candidates=None):
        self.captured_specs.append(spec)
        return await super().prepare(spec, candidates)


def make_client(
    health_by_uri: dict[str, DroneHealth],
    active_mission_id: str | None = None,
    *,
    executor=None,
) -> TestClient:
    app = FastAPI()
    app.include_router(swarm_route.router, prefix="/swarm")
    service = SwarmDeployService(SwarmSessionRunner(probe=StaticHealthProbe(health_by_uri), executor=executor))
    service._active_mission_id = active_mission_id
    app.dependency_overrides[swarm_route.get_service] = lambda: service
    return TestClient(app)


def healthy(
    uri: str,
    score: float,
    y: float = 0.0,
    *,
    pose: tuple[float, float, float] | None = None,
) -> DroneHealth:
    launch_pose = pose if pose is not None else (0.0, y, 0.0)
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
        pose=launch_pose,
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
    assert data["infra_status"] == "success"
    assert data["infra_continue"] is True
    assert data["swarm_success"] is True
    assert data["swarm_safe_to_fly"] is True
    assert len(data["selected"]) == 3
    assert data["plan"]["final_pose"] == [0.5, 0.0, 0.55]
    assert data["events"]


def test_swarm_battery_endpoint_returns_mission_samples():
    uris = ("a", "b", "c")
    client = make_client({uri: healthy(uri, i + 80, i * 0.4) for i, uri in enumerate(uris)})
    deploy = client.post(
        "/swarm/deploy",
        json={"swarm_size": 3, "allowed_uris": list(uris), "dry_run": True},
    )

    response = client.get(f"/swarm/deploy/{deploy.json()['mission_id']}/battery")

    assert response.status_code == 200
    assert response.json()["telemetry"] == {}


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
    assert data["infra_status"] == "success"
    assert data["infra_continue"] is True
    assert data["swarm_success"] is False
    assert data["swarm_safe_to_fly"] is False
    assert len(data["selected"]) == 1


def test_swarm_deploy_rejects_when_mission_already_active():
    client = make_client({}, active_mission_id="existing")

    response = client.post("/swarm/deploy", json={"allowed_uris": ["a", "b", "c"]})

    assert response.status_code == 409
    assert "already active" in response.json()["detail"]


def test_swarm_deploy_posts_callback_for_terminal_result(monkeypatch):
    calls = []

    async def fake_callback(self, result, spec):
        calls.append((spec.callback_url, result.state.value, result.message))

    monkeypatch.setattr(SwarmDeployService, "_post_callback", fake_callback)
    client = make_client({uri: healthy(uri, i + 80, i * 0.4) for i, uri in enumerate(("a", "b", "c"))})

    response = client.post(
        "/swarm/deploy",
        json={
            "swarm_size": 3,
            "allowed_uris": ["a", "b", "c"],
            "dry_run": True,
            "callback_url": "http://localhost:8765/drone/swarm-complete",
        },
    )

    assert response.status_code == 200
    assert calls == [("http://localhost:8765/drone/swarm-complete", "dry_run", "dry_run")]


def test_dtw_drone_trigger_prepares_then_launches_swarm(tmp_path, monkeypatch):
    uris = swarm_route.DEFAULT_DISCOVERY_FLEET
    captured_path = tmp_path / "demo_path.json"
    captured_path.write_text(
        '{"start":[1.0,1.0,0.55],"pattern_s":1.0,"relative_points":[[0.2,0.0,0.0]],"yaw_points_rad":[-1.5708]}'
    )
    monkeypatch.setattr(swarm_route, "_DEFAULT_CAPTURED_PATH", captured_path)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    captured_specs = []
    service = SwarmDeployService(
        CapturingRunner(
            probe=StaticHealthProbe({uri: healthy(uri, i + 80, i * 0.4) for i, uri in enumerate(uris)}),
            executor=FakeExecutor(),
            captured_specs=captured_specs,
        )
    )
    app.dependency_overrides[swarm_route.get_service] = lambda: service

    with TestClient(app) as client:
        trigger = client.post("/drone/trigger")

        assert trigger.status_code == 200
        sequence_id = trigger.json()["sequence_id"]
        assert sequence_id.startswith("SEQ-")
        assert trigger.json()["status"] == "dispatched"
        for _ in range(100):
            if captured_specs:
                break
            time.sleep(0.01)
        assert captured_specs[0].swarm_size == DEFAULT_SWARM_SIZE
        assert captured_specs[0].health_timeout_s == 40.0
        assert captured_specs[0].max_concurrent_checks == 5
        assert captured_specs[0].allowed_uris == ()
        assert captured_specs[0].pattern == "captured_path"
        assert captured_specs[0].captured_path == str(captured_path)
        assert captured_specs[0].final_pose == (0.6, 0.6, 0.5)

        for _ in range(100):
            status_response = client.get(f"/drone/status/{sequence_id}")
            if status_response.json()["phase"] == "ready_to_deploy":
                break
            time.sleep(0.01)
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "dispatched"
        assert status_response.json()["phase"] == "ready_to_deploy"

        launch_response = client.post(f"/drone/launch/{sequence_id}")
        assert launch_response.status_code == 200

        for _ in range(100):
            result_response = client.get(f"/drone/result/{sequence_id}")
            if result_response.json()["status"] == "confirmed":
                break
            time.sleep(0.01)
        assert result_response.status_code == 200
        assert result_response.json()["status"] == "confirmed"


def test_dtw_demo_battery_endpoint_checks_fixed_drones(monkeypatch):
    calls = []
    uris = swarm_route.DEFAULT_DISCOVERY_FLEET

    async def fake_check_candidates_concurrently(candidates, probe, thresholds):
        calls.append((candidates, probe, thresholds))
        return [
            healthy(uris[0], 90),
            DroneHealth(
                uris[1],
                False,
                0,
                reasons=("low_battery_percent",),
                voltage=3.7,
                battery_percent=20,
            ),
            *(healthy(uri, 80) for uri in uris[2:]),
        ]

    monkeypatch.setattr(swarm_route, "check_candidates_concurrently", fake_check_candidates_concurrently)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    client = TestClient(app)

    response = client.get("/drone/battery")

    assert response.status_code == 200
    data = response.json()
    assert [item["uri"] for item in data["results"]] == list(uris)
    assert data["results"][0]["battery_percent"] == 90
    assert data["results"][1]["reasons"] == ["low_battery_percent"]
    candidates, _probe, thresholds = calls[0]
    assert [candidate.uri for candidate in candidates] == list(uris)
    assert thresholds.health_timeout_s == 10.0
    assert thresholds.max_concurrent_checks == len(uris)


def test_dtw_demo_battery_endpoint_supports_compact_fleet(monkeypatch):
    calls = []
    uris = DEFAULT_CRAZY_PINWHEEL_COMPACT_FLEET

    async def fake_check_candidates_concurrently(candidates, probe, thresholds):
        calls.append((candidates, probe, thresholds))
        return [healthy(candidate.uri, 90) for candidate in candidates]

    monkeypatch.setattr(swarm_route, "check_candidates_concurrently", fake_check_candidates_concurrently)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    client = TestClient(app)

    response = client.get("/drone/battery", params={"fleet": "compact", "health_timeout_s": 3.0})

    assert response.status_code == 200
    candidates, _probe, thresholds = calls[0]
    assert [candidate.uri for candidate in candidates] == list(uris)
    assert thresholds.health_timeout_s == 3.0
    assert thresholds.max_concurrent_checks == len(uris)


def test_dtw_demo_battery_endpoint_supports_explicit_uris(monkeypatch):
    calls = []

    async def fake_check_candidates_concurrently(candidates, probe, thresholds):
        calls.append((candidates, probe, thresholds))
        return [healthy(candidate.uri, 90) for candidate in candidates]

    monkeypatch.setattr(swarm_route, "check_candidates_concurrently", fake_check_candidates_concurrently)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    client = TestClient(app)

    response = client.get(
        "/drone/battery",
        params=[
            ("uri", "radio://0/80/2M/E7E7E7E700"),
            ("uri", "radio://1/90/2M/E7E7E7E708"),
        ],
    )

    assert response.status_code == 200
    candidates, _probe, thresholds = calls[0]
    assert [candidate.uri for candidate in candidates] == [
        "radio://0/80/2M/E7E7E7E700",
        "radio://1/90/2M/E7E7E7E708",
    ]
    assert thresholds.max_concurrent_checks == 2


def test_dtw_crazy_trigger_prepares_pinwheel_swarm():
    from src.swarm.planner import formation_slots

    uris = DEFAULT_FULL_FLEET
    pinwheel_spec = MissionSpec(
        swarm_size=CRAZY_PINWHEEL_SWARM_SIZE,
        formation="diamond",
        pattern="crazy_pinwheel",
        final_pose=(0.5, -0.6, 1.12),
        slot_spacing_m=0.42,
        hover_z=1.05,
        no_fly_zone_paths=(),
    )
    slots = formation_slots(pinwheel_spec)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    captured_specs = []
    service = SwarmDeployService(
        CapturingRunner(
            probe=StaticHealthProbe(
                {
                        uri: healthy(uri, i + 80, pose=(slot[0], slot[1], pinwheel_spec.hover_z))
                    for i, (uri, slot) in enumerate(zip(uris, slots))
                }
            ),
            executor=FakeExecutor(),
            captured_specs=captured_specs,
        )
    )
    app.dependency_overrides[swarm_route.get_service] = lambda: service

    with TestClient(app) as client:
        trigger = client.post("/drone/crazy-trigger")

        assert trigger.status_code == 200
        sequence_id = trigger.json()["sequence_id"]
        for _ in range(100):
            if captured_specs:
                break
            time.sleep(0.01)
        assert captured_specs[0].formation == "diamond"
        assert captured_specs[0].pattern == "crazy_pinwheel"
        assert captured_specs[0].swarm_size == CRAZY_PINWHEEL_SWARM_SIZE
        assert captured_specs[0].allowed_uris == DEFAULT_FULL_FLEET
        assert captured_specs[0].max_concurrent_checks == CRAZY_PINWHEEL_SWARM_SIZE
        assert captured_specs[0].final_pose == (0.5, -0.6, 1.12)
        assert captured_specs[0].hover_z == 1.05
        assert captured_specs[0].pattern_s == 1.2

        for _ in range(100):
            status_response = client.get(f"/drone/status/{sequence_id}")
            if status_response.json()["phase"] == "ready_to_deploy":
                break
            time.sleep(0.01)
        assert status_response.status_code == 200
        assert status_response.json()["phase"] == "ready_to_deploy"


def test_dtw_crazy_trigger_compact_prepares_five_drone_pinwheel():
    from src.swarm.planner import formation_slots

    uris = DEFAULT_CRAZY_PINWHEEL_COMPACT_FLEET
    pinwheel_spec = MissionSpec(
        swarm_size=CRAZY_PINWHEEL_COMPACT_SWARM_SIZE,
        formation="diamond",
        pattern="crazy_pinwheel",
        crazy_pinwheel_compact=True,
        final_pose=(0.5, -0.6, 1.12),
        slot_spacing_m=0.42,
        hover_z=1.05,
        no_fly_zone_paths=(),
    )
    slots = formation_slots(pinwheel_spec)
    assert len(slots) == 5
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    captured_specs = []
    service = SwarmDeployService(
        CapturingRunner(
            probe=StaticHealthProbe(
                {
                    uri: healthy(uri, i + 80, pose=(slot[0], slot[1], pinwheel_spec.hover_z))
                    for i, (uri, slot) in enumerate(zip(uris, slots))
                }
            ),
            executor=FakeExecutor(),
            captured_specs=captured_specs,
        )
    )
    app.dependency_overrides[swarm_route.get_service] = lambda: service

    with TestClient(app) as client:
        trigger = client.post("/drone/crazy-trigger", params={"compact": True})

        assert trigger.status_code == 200
        sequence_id = trigger.json()["sequence_id"]
        for _ in range(100):
            if captured_specs:
                break
            time.sleep(0.01)
        assert captured_specs[0].crazy_pinwheel_compact is True
        assert captured_specs[0].swarm_size == CRAZY_PINWHEEL_COMPACT_SWARM_SIZE
        assert captured_specs[0].allowed_uris == DEFAULT_CRAZY_PINWHEEL_COMPACT_FLEET
        assert captured_specs[0].max_concurrent_checks == CRAZY_PINWHEEL_COMPACT_SWARM_SIZE

        for _ in range(100):
            status_response = client.get(f"/drone/status/{sequence_id}")
            if status_response.json()["phase"] == "ready_to_deploy":
                break
            time.sleep(0.01)
        assert status_response.status_code == 200
        assert status_response.json()["phase"] == "ready_to_deploy"


def test_dtw_abort_safe_lands_all_known_drones_without_sequence(monkeypatch):
    calls = []

    def fake_emergency_land(target_uris, land_duration_s, stop_delay_s):
        calls.append((target_uris, land_duration_s, stop_delay_s))
        return [{"uri": uri, "status": "landed", "error": None} for uri in target_uris]

    monkeypatch.setattr(swarm_route, "_emergency_land_uris", fake_emergency_land)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    service = SwarmDeployService(SwarmSessionRunner(probe=StaticHealthProbe({}), executor=EmergencyExecutor()))
    app.dependency_overrides[swarm_route.get_service] = lambda: service
    client = TestClient(app)

    response = client.post("/drone/abort")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "emergency_land_sent"
    assert data["active_stopped"] == ["radio://0/80/2M/E7E7E7E701"]
    targets, land_duration_s, stop_delay_s = calls[0]
    assert targets == swarm_route.DEFAULT_DISCOVERY_FLEET
    assert land_duration_s == 2.0
    assert stop_delay_s == 2.5


def test_dtw_abort_ignores_sequence_id_and_safe_lands_all_known_drones(monkeypatch):
    calls = []

    def fake_emergency_land(target_uris, land_duration_s, stop_delay_s):
        calls.append(target_uris)
        return [{"uri": uri, "status": "landed", "error": None} for uri in target_uris]

    monkeypatch.setattr(swarm_route, "_emergency_land_uris", fake_emergency_land)
    app = FastAPI()
    app.include_router(swarm_route.dtw_router)
    service = SwarmDeployService(SwarmSessionRunner(probe=StaticHealthProbe({}), executor=EmergencyExecutor()))
    app.dependency_overrides[swarm_route.get_service] = lambda: service
    client = TestClient(app)

    response = client.post("/drone/abort/SEQ-DOES-NOT-MATTER")

    assert response.status_code == 200
    assert response.json()["status"] == "emergency_land_sent"
    assert calls == [swarm_route.DEFAULT_DISCOVERY_FLEET]


def test_swarm_deploy_preparing_blocks_infra_continuation():
    client = make_client(
        {uri: healthy(uri, i + 80, i * 0.4) for i, uri in enumerate(("a", "b", "c"))},
        executor=FakeExecutor(),
    )

    response = client.post(
        "/swarm/deploy",
        json={"swarm_size": 3, "allowed_uris": ["a", "b", "c"], "dry_run": False, "arm": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "accepted"
    assert data["message"] == "preparing"
    assert data["infra_status"] == "pending"
    assert data["infra_continue"] is False
    assert data["swarm_safe_to_fly"] is True


def test_emergency_land_endpoint_stops_active_and_direct_targets(monkeypatch):
    calls = []

    def fake_emergency_land(target_uris, land_duration_s, stop_delay_s):
        calls.append((target_uris, land_duration_s, stop_delay_s))
        return [{"uri": uri, "status": "landed", "error": None} for uri in target_uris]

    monkeypatch.setattr(swarm_route, "_emergency_land_uris", fake_emergency_land)
    app = FastAPI()
    app.include_router(swarm_route.router, prefix="/swarm")
    service = SwarmDeployService(SwarmSessionRunner(probe=StaticHealthProbe({}), executor=EmergencyExecutor()))
    app.dependency_overrides[swarm_route.get_service] = lambda: service
    client = TestClient(app)

    response = client.post(
        "/swarm/emergency-land",
        json={"target_uris": ["u1", "u2"], "land_duration_s": 0.2, "stop_delay_s": 0.0},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "emergency_land_sent"
    assert data["active_stopped"] == ["radio://0/80/2M/E7E7E7E701"]
    assert [item["uri"] for item in data["results"]] == ["u1", "u2"]
    assert calls == [(("u1", "u2"), 0.2, 0.0)]


def test_emergency_land_endpoint_defaults_to_all_ten_known_drones(monkeypatch):
    calls = []

    def fake_emergency_land(target_uris, land_duration_s, stop_delay_s):
        calls.append((target_uris, land_duration_s, stop_delay_s))
        return [{"uri": uri, "status": "landed", "error": None} for uri in target_uris]

    monkeypatch.setattr(swarm_route, "_emergency_land_uris", fake_emergency_land)
    client = make_client({})

    response = client.post("/swarm/emergency-land")

    assert response.status_code == 200
    targets, land_duration_s, stop_delay_s = calls[0]
    assert targets == swarm_route.DEFAULT_DISCOVERY_FLEET
    assert land_duration_s == 2.0
    assert stop_delay_s == 2.5
    assert [item["uri"] for item in response.json()["results"]] == list(targets)


def test_emergency_led_cleanup_ignores_missing_decks():
    calls = []

    class FakeParam:
        def set_value(self, name, value):
            calls.append((name, value))

    class FakeCf:
        param = FakeParam()

    swarm_route._turn_off_known_led_decks(FakeCf())

    assert calls == [("colorLedBot.wrgb8888", "0"), ("ring.effect", "0")]


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


def test_swarm_health_endpoint_defaults_to_configured_fleet(monkeypatch):
    app = FastAPI()
    app.include_router(swarm_route.router, prefix="/swarm")
    captured = []

    async def fake_check(candidates, *, probe, thresholds):
        captured.extend(candidate.uri for candidate in candidates)
        return [healthy(candidate.uri, 90, index * 0.4) for index, candidate in enumerate(candidates)]

    monkeypatch.setattr(swarm_route, "check_candidates_concurrently", fake_check)
    client = TestClient(app)

    response = client.post("/swarm/health", json={})

    assert response.status_code == 200
    assert tuple(captured) == swarm_route.DEFAULT_DISCOVERY_FLEET
    assert len(response.json()["results"]) == 3

