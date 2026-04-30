from src.swarm.executor import SwarmExecutor
from src.swarm.models import MissionSpec
from src.swarm.planner import build_swarm_plan


class FakeCommander:
    def __init__(self):
        self.calls = []

    def takeoff(self, absolute_height_m, duration_s, **kwargs):
        self.calls.append(("takeoff", absolute_height_m, duration_s))

    def go_to(self, x, y, z, yaw, duration_s, **kwargs):
        self.calls.append(("go_to", x, y, z, duration_s, kwargs.get("relative")))

    def land(self, absolute_height_m, duration_s, **kwargs):
        self.calls.append(("land", absolute_height_m, duration_s))

    def stop(self):
        self.calls.append(("stop",))


class FakeConnection:
    def __init__(self, uri, *, fail_config=False, battery_watch_triggered=False):
        self.uri = uri
        self.commander = FakeCommander()
        self.closed = False
        self.fail_config = fail_config
        self.battery_watch_triggered = battery_watch_triggered
        self.led_calls = []

    def configure(self):
        if self.fail_config:
            raise RuntimeError(f"{self.uri} configure failed")

    def set_led_blue(self):
        self.led_calls.append("blue")

    def set_led_off(self):
        self.led_calls.append("off")

    def can_blink_led(self):
        return True

    def start_battery_watch(self):
        self.led_calls.append("battery_watch_start")

    def stop_battery_watch(self):
        self.led_calls.append("battery_watch_stop")
        return self.battery_watch_triggered

    def close(self):
        self.closed = True


class FakeConnector:
    def __init__(self, *, fail_connect=None, fail_config=None, battery_watch_trigger=None):
        self.connections = {}
        self.specs = {}
        self.fail_connect = set(fail_connect or ())
        self.fail_config = set(fail_config or ())
        self.battery_watch_trigger = set(battery_watch_trigger or ())

    def connect(self, uri, spec):
        if uri in self.fail_connect:
            raise RuntimeError(f"{uri} connect failed")
        connection = FakeConnection(
            uri,
            fail_config=uri in self.fail_config,
            battery_watch_triggered=uri in self.battery_watch_trigger,
        )
        self.connections[uri] = connection
        self.specs[uri] = spec
        return connection


def test_executor_command_order_with_fake_cflib(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector()
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=3, pattern="hold", dry_run=False, arm=True)
    plan = build_swarm_plan(
        {
            "a": (0.0, 0.0, 0.55),
            "b": (0.0, 0.5, 0.55),
            "c": (0.0, -0.5, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)
    events = result.events

    assert sorted(events).count("a:takeoff") == 1
    assert result.plan.spec.swarm_size == 3
    assert "a:led_blink_start" in events
    assert "a:led_blink_stop" in events
    assert "a:battery_watch_start" in events
    assert "a:battery_watch_stop" in events
    for connection in connector.connections.values():
        names = [call[0] for call in connection.commander.calls]
        assert names == ["takeoff", "go_to", "go_to", "go_to", "land", "stop"]
        assert "blue" in connection.led_calls
        assert "off" in connection.led_calls
        assert connection.closed is True
    assert all(spec.enable_collision_avoidance for spec in connector.specs.values())


def test_executor_replans_four_drone_mission_when_one_connect_fails(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_connect={"e"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=5, pattern="hold", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, -0.9, 0.55),
            "b": (0.0, -0.45, 0.55),
            "c": (0.0, 0.0, 0.55),
            "d": (0.0, 0.45, 0.55),
            "e": (0.0, 0.9, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)
    events = result.events

    assert "e" not in connector.connections
    assert result.plan.spec.swarm_size == 4
    assert sorted(event for event in events if event.endswith(":takeoff")) == [
        "a:takeoff",
        "b:takeoff",
        "c:takeoff",
        "d:takeoff",
    ]


def test_executor_replans_three_drone_mission_when_two_configures_fail(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_config={"d", "e"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=5, pattern="hold", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, -0.9, 0.55),
            "b": (0.0, -0.45, 0.55),
            "c": (0.0, 0.0, 0.55),
            "d": (0.0, 0.45, 0.55),
            "e": (0.0, 0.9, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)
    events = result.events

    assert result.plan.spec.swarm_size == 3
    assert sorted(event for event in events if event.endswith(":takeoff")) == [
        "a:takeoff",
        "b:takeoff",
        "c:takeoff",
    ]
    assert connector.connections["d"].commander.calls == []
    assert connector.connections["e"].commander.calls == []


def test_executor_refuses_takeoff_when_majority_connects_fail(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_connect={"c", "d", "e"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=5, pattern="hold", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, -0.9, 0.55),
            "b": (0.0, -0.45, 0.55),
            "c": (0.0, 0.0, 0.55),
            "d": (0.0, 0.45, 0.55),
            "e": (0.0, 0.9, 0.55),
        },
        spec,
    )

    try:
        executor.execute(plan, arm=True)
    except RuntimeError as exc:
        assert "connect_quorum_lost" in str(exc)
    else:
        raise AssertionError("expected takeoff to be refused")

    assert connector.connections["a"].commander.calls == []
    assert connector.connections["b"].commander.calls == []


def test_executor_battery_watchdog_lands_and_fails_mission(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(battery_watch_trigger={"b"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=3, pattern="hold", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, 0.0, 0.55),
            "b": (0.0, 0.5, 0.55),
            "c": (0.0, -0.5, 0.55),
        },
        spec,
    )

    try:
        executor.execute(plan, arm=True)
    except RuntimeError as exc:
        assert "swarm execution failed" in str(exc)
        assert exc.__cause__ is not None
        assert "battery watchdog" in str(exc.__cause__)
    else:
        raise AssertionError("expected battery watchdog to fail mission")

    assert "battery_watch_stop" in connector.connections["b"].led_calls
    assert ("land", 0.0, 3.0) in connector.connections["b"].commander.calls
