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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "tools" / "lighthouse_demos" / "lighthouse_single_server_orbit.py"
SPEC = importlib.util.spec_from_file_location("lighthouse_single_server_orbit", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_square_is_default_path():
    args = module.parse_args([])

    assert args.path == "square"


def test_square_points_stay_on_box_perimeter():
    points = module.square_points(cx=1.0, cy=2.0, z=0.3, half_side=0.5)

    assert points == [
        (1.5, 1.5, 0.3),
        (1.5, 2.5, 0.3),
        (0.5, 2.5, 0.3),
        (0.5, 1.5, 0.3),
    ]


def test_square_path_starts_on_nearest_edge_from_home():
    points = module.square_path_from_home(cx=1.0, cy=2.0, z=0.3, half_side=0.5, home=(1.8, 2.1, 0.0))

    assert points[0] == (1.5, 2.1, 0.3)
    assert points[1:] == [
        (1.5, 2.5, 0.3),
        (0.5, 2.5, 0.3),
        (0.5, 1.5, 0.3),
        (1.5, 1.5, 0.3),
    ]


def test_approach_points_split_diagonal_entry():
    points = module.approach_points(home=(0.0, 0.0, 0.0), entry=(1.0, 2.0, 0.3))

    assert points == [
        (1.0, 0.0, 0.3),
        (1.0, 2.0, 0.3),
    ]
