import threading
import time

from src.swarm.executor import BatteryWatch
from src.swarm.executor import CflibDroneConnector
from src.swarm.executor import RTL_LAND_SEQUENCE_DELAY_S
from src.swarm.executor import SwarmExecutor
from src.swarm.executor import _build_schedule
from src.swarm.models import MissionSpec
from src.swarm.planner import DronePlan
from src.swarm.planner import SwarmPlan
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
    def __init__(self, uri, *, fail_config=False, fail_refresh=False, battery_watch_triggered=False, can_blink=True):
        self.uri = uri
        self.commander = FakeCommander()
        self.closed = False
        self.fail_config = fail_config
        self.fail_refresh = fail_refresh
        self.battery_watch_triggered = battery_watch_triggered
        self._can_blink = can_blink
        self.led_calls = []

    def configure(self):
        if self.fail_config:
            raise RuntimeError(f"{self.uri} configure failed")

    def refresh_launch_authorization(self):
        if self.fail_refresh:
            raise RuntimeError(f"{self.uri} refresh failed")

    def set_led_red(self):
        self.led_calls.append("red")

    def set_led_blue(self):
        self.led_calls.append("blue")

    def set_led_orange(self):
        self.led_calls.append("orange")

    def set_led_green(self):
        self.led_calls.append("green")

    def set_led_yellow(self):
        self.led_calls.append("yellow")

    def set_led_cyan(self):
        self.led_calls.append("cyan")

    def set_led_purple(self):
        self.led_calls.append("purple")

    def set_led_off(self):
        self.led_calls.append("off")

    def can_blink_led(self):
        return self._can_blink

    def start_battery_watch(self):
        self.led_calls.append("battery_watch_start")

    def stop_battery_watch(self):
        self.led_calls.append("battery_watch_stop")
        return self.battery_watch_triggered

    def is_battery_watch_triggered(self):
        return self.battery_watch_triggered

    def close(self):
        self.closed = True


class FakeConnector:
    def __init__(
        self,
        *,
        fail_connect=None,
        fail_config=None,
        fail_refresh=None,
        battery_watch_trigger=None,
        connect_delay=0.0,
        can_blink=True,
    ):
        self.connections = {}
        self.specs = {}
        self.fail_connect = set(fail_connect or ())
        self.fail_config = set(fail_config or ())
        self.fail_refresh = set(fail_refresh or ())
        self.battery_watch_trigger = set(battery_watch_trigger or ())
        self.connect_delay = connect_delay
        self.can_blink = can_blink
        self.active_connects = 0
        self.max_active_connects = 0
        self._lock = threading.Lock()

    def connect(self, uri, spec):
        if uri in self.fail_connect:
            raise RuntimeError(f"{uri} connect failed")
        with self._lock:
            self.active_connects += 1
            self.max_active_connects = max(self.max_active_connects, self.active_connects)
        try:
            if self.connect_delay:
                time.sleep(self.connect_delay)
        finally:
            with self._lock:
                self.active_connects -= 1
        connection = FakeConnection(
            uri,
            fail_config=uri in self.fail_config,
            fail_refresh=uri in self.fail_refresh,
            battery_watch_triggered=uri in self.battery_watch_trigger,
            can_blink=self.can_blink,
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
    assert "a:led_blue_blink_start" in events
    assert "a:led_orange" in events
    assert "a:led_orange_blink_start" not in events
    assert "a:led_green_blink_start" in events
    assert "a:led_blink_stop" in events
    assert "a:battery_watch_start" in events
    assert "a:battery_watch_stop" in events
    for connection in connector.connections.values():
        names = [call[0] for call in connection.commander.calls]
        assert names == ["takeoff", "go_to", "go_to", "go_to", "land", "stop"]
        assert "green" in connection.led_calls
        assert "blue" in connection.led_calls
        assert "orange" in connection.led_calls
        assert "green" in connection.led_calls
        assert "off" in connection.led_calls
        assert connection.closed is True
    assert all(spec.enable_collision_avoidance for spec in connector.specs.values())


def test_schedule_uses_landing_settle_after_final_return(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.monotonic", lambda: 100.0)
    spec = MissionSpec(
        swarm_size=3,
        takeoff_s=2.0,
        move_s=4.0,
        pattern_s=1.0,
        hold_s=3.0,
        landing_settle_s=0.5,
        land_s=3.0,
    )

    schedule = _build_schedule(spec, n_formation=1, n_pattern=1, n_return=2)

    assert schedule.return_fire_ats == (
        (131.3, 138.3),
        (131.3, 145.8 + RTL_LAND_SEQUENCE_DELAY_S),
        (131.3, 153.3 + 2 * RTL_LAND_SEQUENCE_DELAY_S),
    )
    assert schedule.land_ats == (
        142.8,
        150.3 + RTL_LAND_SEQUENCE_DELAY_S,
        157.8 + 2 * RTL_LAND_SEQUENCE_DELAY_S,
    )
    assert schedule.land_at == 161.8


def test_schedule_sends_closest_formation_routes_first(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.monotonic", lambda: 100.0)
    spec = MissionSpec(swarm_size=3, takeoff_s=1.0, move_s=2.0, hold_s=1.0, no_fly_zone_paths=())
    plan = SwarmPlan(
        spec=spec,
        assignment_cost=0.0,
        drones=(
            DronePlan("far", (0.0, 0.0, 0.55), (1.0, 0.0, 0.55), ((1.0, 0.0, 0.55),), (), (), (0.0, 0.0, 0.55)),
            DronePlan("close", (0.0, 0.0, 0.55), (0.1, 0.0, 0.55), ((0.1, 0.0, 0.55),), (), (), (0.0, 0.0, 0.55)),
            DronePlan("mid", (0.0, 0.0, 0.55), (0.5, 0.0, 0.55), ((0.5, 0.0, 0.55),), (), (), (0.0, 0.0, 0.55)),
        ),
    )

    schedule = _build_schedule(plan, n_formation=1, n_pattern=0, n_return=0)

    assert schedule.formation_fire_ats[1][0] < schedule.formation_fire_ats[2][0] < schedule.formation_fire_ats[0][0]


def test_schedule_sends_closest_home_first_after_shared_return_step(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.monotonic", lambda: 100.0)
    spec = MissionSpec(swarm_size=3, takeoff_s=1.0, move_s=2.0, hold_s=1.0, no_fly_zone_paths=())
    final_pose = (0.0, 0.0, 0.55)
    plan = SwarmPlan(
        spec=spec,
        assignment_cost=0.0,
        drones=(
            DronePlan("far", (1.0, 0.0, 0.55), final_pose, (), (), (final_pose, (1.0, 0.0, 0.55)), (1.0, 0.0, 0.55)),
            DronePlan("close", (0.1, 0.0, 0.55), final_pose, (), (), (final_pose, (0.1, 0.0, 0.55)), (0.1, 0.0, 0.55)),
            DronePlan("mid", (0.5, 0.0, 0.55), final_pose, (), (), (final_pose, (0.5, 0.0, 0.55)), (0.5, 0.0, 0.55)),
        ),
    )

    schedule = _build_schedule(plan, n_formation=0, n_pattern=0, n_return=2)

    assert schedule.return_fire_ats[1][1] < schedule.return_fire_ats[2][1] < schedule.return_fire_ats[0][1]


def test_executor_turns_orange_after_final_pattern_waypoint(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(can_blink=False)
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=3, pattern="square", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, 0.0, 0.55),
            "b": (0.0, 0.5, 0.55),
            "c": (0.0, -0.5, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)

    drone_events = [event for event in result.events if event.startswith("a:")]
    pattern_indices = [index for index, event in enumerate(drone_events) if event == "a:pattern"]
    assert len(pattern_indices) == 4
    assert drone_events.index("a:led_orange") > pattern_indices[-1]


def test_crazy_pinwheel_uses_staggered_multicolor_in_flight_blinks(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector()
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(
        swarm_size=10,
        formation="diamond",
        pattern="crazy_pinwheel",
        final_pose=(0.45, 0.0, 0.62),
        slot_spacing_m=0.42,
        dry_run=False,
        arm=True,
        no_fly_zone_paths=(),
    )
    from src.swarm.planner import formation_slots

    slots = formation_slots(spec)
    plan = build_swarm_plan({f"d{i}": (slot[0], slot[1], 0.55) for i, slot in enumerate(slots)}, spec)

    result = executor.execute(plan, arm=True)

    assert any(event.endswith(":led_cyan_blink_start") for event in result.events)
    assert any(event.endswith(":led_purple_blink_start") for event in result.events)
    assert any(event.endswith(":led_yellow_blink_start") for event in result.events)
    assert any(event.endswith(":led_blue_blink_start") for event in result.events)
    assert any(event.endswith(":led_green_blink_start") for event in result.events)
    assert not any(event.endswith(":led_orange") for event in result.events)
    assert sum(event.endswith(":led_green_blink_start") for event in result.events) == 1


def test_launch_up_turns_orange_at_peak_then_blue_before_landing(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(can_blink=False)
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(
        swarm_size=2,
        pattern="launch_up",
        final_pose=(0.0, 0.0, 1.0),
        dry_run=False,
        arm=True,
        no_fly_zone_paths=(),
    )
    plan = build_swarm_plan(
        {
            "a": (0.0, 0.0, 0.55),
            "b": (0.0, 0.5, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)

    drone_events = [event for event in result.events if event.startswith("a:")]
    assert drone_events.index("a:led_orange") > drone_events.index("a:pattern")
    assert drone_events.index("a:led_blue") > drone_events.index("a:return")
    assert drone_events.index("a:land") > drone_events.index("a:led_blue")
    assert connector.connections["a"].led_calls.count("blue") >= 2
    assert "orange" in connector.connections["a"].led_calls


def test_emergency_stop_turns_active_leds_off():
    connection = FakeConnection("a")
    executor = SwarmExecutor()
    executor._set_active_connections([connection])

    stopped = executor.emergency_stop_active()

    assert stopped == ["a"]
    assert connection.commander.calls == [("land", 0.0, 1.0), ("stop",)]
    assert connection.led_calls == ["off"]


def test_executor_opens_selected_links_in_parallel():
    connector = FakeConnector(connect_delay=0.05, can_blink=False)
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

    started = time.monotonic()
    connections, green_blinks = executor._connect_in_parallel(plan)
    elapsed = time.monotonic() - started

    assert len(connections) == 5
    assert green_blinks == []
    assert connector.max_active_connects == 5
    assert elapsed < 0.15


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


def test_executor_refuses_degraded_connect_when_full_swarm_required(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_connect={"e"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=5, pattern="hold", dry_run=False, arm=True, require_full_swarm=True, no_fly_zone_paths=())
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
        raise AssertionError("expected full-swarm takeoff to be refused")


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
    assert connector.connections["d"].commander.calls == [("land", 0.0, 1.0), ("stop",)]
    assert connector.connections["e"].commander.calls == [("land", 0.0, 1.0), ("stop",)]


def test_ready_green_blink_only_starts_after_successful_configure(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_config={"e"})
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

    prepared = executor.prepare(plan)

    assert [connection.uri for connection in prepared.connections] == ["a", "b", "c", "d"]
    assert "green" not in connector.connections["e"].led_calls
    for uri in ("a", "b", "c", "d"):
        assert "green" in connector.connections[uri].led_calls


def test_executor_replans_two_drone_mission_when_one_connect_fails(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_connect={"b"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=2, pattern="hold", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, 0.0, 0.55),
            "b": (0.0, 0.5, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)

    assert result.plan.spec.swarm_size == 1
    assert [drone.uri for drone in result.plan.drones] == ["a"]
    assert "a:takeoff" in result.events
    assert "b" not in connector.connections


def test_executor_drops_one_drone_when_launch_refresh_fails(monkeypatch):
    monkeypatch.setattr("src.swarm.executor.time.sleep", lambda _seconds: None)
    connector = FakeConnector(fail_refresh={"b"})
    executor = SwarmExecutor(connector=connector)
    spec = MissionSpec(swarm_size=2, pattern="hold", dry_run=False, arm=True, no_fly_zone_paths=())
    plan = build_swarm_plan(
        {
            "a": (0.0, 0.0, 0.55),
            "b": (0.0, 0.5, 0.55),
        },
        spec,
    )

    result = executor.execute(plan, arm=True)

    assert result.plan.spec.swarm_size == 1
    assert [drone.uri for drone in result.plan.drones] == ["a"]
    assert "a:takeoff" in result.events
    assert connector.connections["b"].commander.calls == [("land", 0.0, 1.0), ("stop",)]


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


def test_executor_battery_watchdog_landing_does_not_fail_mission(monkeypatch):
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

    result = executor.execute(plan, arm=True)

    assert "b:battery_watch_landed" in result.events
    assert "battery_watch_stop" in connector.connections["b"].led_calls
    assert ("land", 0.0, 3.0) not in connector.connections["b"].commander.calls
    assert not any(call[0] == "go_to" for call in connector.connections["b"].commander.calls)


class FakeLog:
    def __init__(self, *args, **kwargs):
        self.variables = []
        self.data_received_cb = self

    def add_variable(self, variable, kind):
        self.variables.append((variable, kind))

    def add_callback(self, callback):
        self.callback = callback

    def start(self):
        pass

    def stop(self):
        pass

    def delete(self):
        pass


class FakeCf:
    class Log:
        def add_config(self, log):
            self.log = log

    def __init__(self):
        self.log = self.Log()


class FakeScf:
    def __init__(self):
        toc = type("Toc", (), {"toc": {}})()
        param = type("Param", (), {"toc": toc})()
        self.cf = type("Cf", (), {"high_level_commander": FakeCommander(), "param": param})()
        self.closed = False

    def close_link(self):
        self.closed = True


def test_cflib_connector_reuses_retained_sync_crazyflie():
    scf = FakeScf()
    connector = CflibDroneConnector({"radio://0/80/2M/E7E7E7E701": scf})

    connection = connector.connect("radio://0/80/2M/E7E7E7E701", MissionSpec(no_fly_zone_paths=()))

    assert connection._scf is scf
    connection.close()
    assert scf.closed is True


def test_battery_watch_ignores_transient_percent_sag_when_voltage_is_healthy():
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog)

    for _ in range(4):
        watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 5}, None)

    assert watch.triggered is False
    assert watch.low_samples == 4
    assert commander.calls == []


def test_battery_watch_lands_after_sustained_five_percent_battery():
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog)

    for _ in range(4):
        watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 5}, None)
    assert commander.calls == []

    watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 5}, None)

    assert watch.triggered is True
    assert watch.trigger_reason == "critical_battery_percent"
    assert commander.calls == [("land", 0.0, 3.0)]


def test_battery_watch_does_not_land_on_voltage_without_five_percent_battery():
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog)

    for _ in range(6):
        watch._on_data(0, {"pm.vbat": 3.44, "pm.batteryLevel": 80}, None)

    assert watch.triggered is False
    assert commander.calls == []


def test_battery_watch_publishes_realtime_sample():
    samples = []
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog, lambda uri, sample: samples.append((uri, sample)))

    watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 42}, None)

    assert samples[0][0] == "b"
    assert samples[0][1]["voltage"] == 3.8
    assert samples[0][1]["battery_percent"] == 42
    assert samples[0][1]["watchdog_landed"] is False
    assert samples[0][1]["trigger_reason"] is None


def test_battery_watch_does_not_land_below_ten_percent_when_voltage_is_healthy():
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog)

    for _ in range(6):
        watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 9}, None)

    assert watch.triggered is False
    assert watch.low_samples == 0
    assert commander.calls == []


def test_battery_watch_recovery_resets_low_sample_counter():
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog)

    watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 5}, None)
    watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 5}, None)
    assert watch.low_samples == 2

    watch._on_data(0, {"pm.vbat": 3.9, "pm.batteryLevel": 6}, None)

    assert watch.low_samples == 0
    assert watch.triggered is False
    assert commander.calls == []


def test_battery_watch_publishes_landing_reason():
    samples = []
    commander = FakeCommander()
    watch = BatteryWatch("b", commander, FakeCf(), FakeLog, lambda uri, sample: samples.append((uri, sample)))

    for _ in range(5):
        watch._on_data(0, {"pm.vbat": 3.8, "pm.batteryLevel": 5}, None)

    assert samples[-1][1]["watchdog_landed"] is True
    assert samples[-1][1]["trigger_reason"] == "critical_battery_percent"
