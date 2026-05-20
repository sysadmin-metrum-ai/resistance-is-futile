import importlib.util
from pathlib import Path
import sys
import types


def install_fake_cflib() -> None:
    cflib = types.ModuleType("cflib")
    cflib.crtp = types.ModuleType("cflib.crtp")
    cflib.crtp.init_drivers = lambda: None

    crazyflie_mod = types.ModuleType("cflib.crazyflie")
    crazyflie_mod.Crazyflie = type("Crazyflie", (), {})

    log_mod = types.ModuleType("cflib.crazyflie.log")
    log_mod.LogConfig = type("LogConfig", (), {})

    sync_mod = types.ModuleType("cflib.crazyflie.syncCrazyflie")
    sync_mod.SyncCrazyflie = type("SyncCrazyflie", (), {})

    sys.modules["cflib"] = cflib
    sys.modules["cflib.crtp"] = cflib.crtp
    sys.modules["cflib.crazyflie"] = crazyflie_mod
    sys.modules["cflib.crazyflie.log"] = log_mod
    sys.modules["cflib.crazyflie.syncCrazyflie"] = sync_mod


install_fake_cflib()

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dual-drone-hover.py"
SPEC = importlib.util.spec_from_file_location("dual_drone_hover", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_parse_args_defaults_to_drones_04_and_09() -> None:
    args = module.parse_args([])

    assert args.uri_a == "radio://0/80/2M/E7E7E7E704"
    assert args.uri_b == "radio://1/90/2M/E7E7E7E709"
    assert args.height == 1.0
    assert args.hover == 5.0


def test_hover_drone_takeoff_hover_land(monkeypatch) -> None:
    calls = []

    class FakeCommander:
        def takeoff(self, height, takeoff_time, yaw=None):
            calls.append(("takeoff", height, takeoff_time, yaw))

        def land(self, height, land_time, yaw=None):
            calls.append(("land", height, land_time, yaw))

        def stop(self):
            calls.append(("stop",))

    class FakeScf:
        cf = types.SimpleNamespace(high_level_commander=FakeCommander())

    class FakeBarrier:
        def wait(self):
            calls.append(("barrier",))

    args = module.parse_args(["--height", "1.2", "--hover", "3", "--takeoff-time", "2", "--land-time", "4"])
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module.hover_drone("drone-a", FakeScf(), args, FakeBarrier())

    assert calls == [
        ("barrier",),
        ("takeoff", 1.2, 2.0, None),
        ("land", 0.0, 4.0, None),
        ("stop",),
    ]
