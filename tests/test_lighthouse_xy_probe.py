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

    sync_mod = types.ModuleType("cflib.crazyflie.syncCrazyflie")
    sync_mod.SyncCrazyflie = type("SyncCrazyflie", (), {})

    sys.modules["cflib"] = cflib
    sys.modules["cflib.crtp"] = cflib.crtp
    sys.modules["cflib.crazyflie"] = crazyflie_mod
    sys.modules["cflib.crazyflie.syncCrazyflie"] = sync_mod


def install_fake_lighthouse_x_step() -> None:
    lighthouse_x_step = types.ModuleType("lighthouse_x_step")
    lighthouse_x_step.arm_if_supported = lambda _cf: None
    lighthouse_x_step.reset_estimator = lambda _cf: None
    lighthouse_x_step.status = lambda _message: None
    lighthouse_x_step.wait_for_estimator = lambda _cf, _timeout: None
    sys.modules["tools.lighthouse_demos.lighthouse_x_step"] = lighthouse_x_step


install_fake_cflib()
install_fake_lighthouse_x_step()

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "lighthouse_demos" / "lighthouse_xy_probe.py"
SPEC = importlib.util.spec_from_file_location("lighthouse_xy_probe", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_parse_args_defaults_to_motion_only_probe() -> None:
    args = module.parse_args([])

    assert args.step == 0.1
    assert args.move_time == 2.0
    assert args.post_estimator_hold == 2.0


def test_parse_args_supports_motion_overrides() -> None:
    args = module.parse_args(["--step", "0.3", "--move-time", "4", "--post-estimator-hold", "3"])

    assert args.step == 0.3
    assert args.move_time == 4
    assert args.post_estimator_hold == 3


def test_run_probe_moves_forward_left_right_from_origin(monkeypatch) -> None:
    calls = []

    class FakeCommander:
        def takeoff(self, height, takeoff_s, yaw=None):
            calls.append(("takeoff", height, takeoff_s, yaw))

        def go_to(self, dx, dy, dz, yaw, move_s, relative):
            calls.append(("go_to", dx, dy, dz, yaw, move_s, relative))

        def land(self, height, land_s, yaw=None):
            calls.append(("land", height, land_s, yaw))

        def stop(self):
            calls.append(("stop",))

    class FakeCf:
        high_level_commander = FakeCommander()

    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module.run_probe(FakeCf(), step=1.0, takeoff_s=2.5, move_s=4.0, settle=0.0, height=0.55, land_s=3.0)

    assert calls == [
        ("takeoff", 0.55, 2.5, None),
        ("go_to", 1.0, 0.0, 0.0, 0.0, 4.0, True),
        ("go_to", -1.0, 0.0, 0.0, 0.0, 4.0, True),
        ("go_to", 0.0, 1.0, 0.0, 0.0, 4.0, True),
        ("go_to", 0.0, -1.0, 0.0, 0.0, 4.0, True),
        ("go_to", 0.0, -1.0, 0.0, 0.0, 4.0, True),
        ("go_to", 0.0, 1.0, 0.0, 0.0, 4.0, True),
        ("land", 0.0, 3.0, None),
        ("stop",),
    ]
