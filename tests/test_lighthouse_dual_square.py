import importlib.util
from pathlib import Path
import sys
import types


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

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "lighthouse_demos" / "lighthouse_dual_square.py"
SPEC = importlib.util.spec_from_file_location("lighthouse_dual_square", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_square_steps_return_to_origin():
    assert module.square_steps(0.5) == [
        (0.5, 0.0, 0.0),
        (0.0, 0.5, 0.0),
        (-0.5, 0.0, 0.0),
        (0.0, -0.5, 0.0),
    ]


def test_mirrored_square_steps_start_negative_x_and_negative_y():
    assert module.square_steps(0.5, mirrored=True) == [
        (-0.5, 0.0, 0.0),
        (0.0, -0.5, 0.0),
        (0.5, 0.0, 0.0),
        (0.0, 0.5, 0.0),
    ]


def test_parse_args_defaults_to_addressed_channel_80_drones():
    args = module.parse_args([])

    assert args.uri_a == "radio://0/80/2M/E7E7E7E701"
    assert args.uri_b == "radio://0/80/2M/E7E7E7E702"
    assert args.side == 0.50
    assert args.height == 0.40
    assert args.blue_led is True
