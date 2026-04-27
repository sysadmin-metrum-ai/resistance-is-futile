import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock
from unittest.mock import call


def install_fake_cflib():
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

MODULE_PATH = Path(__file__).resolve().parents[1] / "lighthouse_dual_x_step.py"
SPEC = importlib.util.spec_from_file_location("lighthouse_dual_x_step", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_parse_args_defaults_to_channels_80_and_90():
    args = module.parse_args([])

    assert args.uri_a == "radio://0/80/2M/E7E7E7E701"
    assert args.uri_b == "radio://0/80/2M/E7E7E7E702"
    assert args.x_distance == 0.50
    assert args.height == 0.40
    assert args.return_home is False
    assert args.blue_led is True


def test_parse_args_supports_return_home_and_motion_overrides():
    args = module.parse_args(
        [
            "--x-distance",
            "0.25",
            "--height",
            "0.35",
            "--return-home",
        ]
    )

    assert args.x_distance == 0.25
    assert args.height == 0.35
    assert args.return_home is True


def test_set_bottom_color_led_blue_writes_color_led_param(monkeypatch):
    cf = MagicMock()
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    module.set_bottom_color_led_blue(cf, "drone-a")

    assert cf.param.set_value.call_args_list == [
        call("colorLedBot.wrgb8888", "255"),
    ]
