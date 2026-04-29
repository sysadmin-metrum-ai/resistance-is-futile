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
    def __init__(self, uri):
        self.uri = uri
        self.commander = FakeCommander()
        self.closed = False

    def close(self):
        self.closed = True


class FakeConnector:
    def __init__(self):
        self.connections = {}
        self.specs = {}

    def connect(self, uri, spec):
        connection = FakeConnection(uri)
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

    events = executor.execute(plan, arm=True)

    assert sorted(events).count("a:takeoff") == 1
    for connection in connector.connections.values():
        names = [call[0] for call in connection.commander.calls]
        assert names == ["takeoff", "go_to", "go_to", "go_to", "land", "stop"]
        assert connection.closed is True
    assert all(spec.enable_collision_avoidance for spec in connector.specs.values())
