import importlib.util
from pathlib import Path
import sys
import types

from src.safety.geofence import box_from_top_corners
from src.safety.geofence import save_box


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

MODULE_PATH = ROOT / "tools" / "lighthouse_demos" / "lighthouse_dual_server_orbit.py"
SPEC = importlib.util.spec_from_file_location("lighthouse_dual_server_orbit", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_build_paths_uses_separate_z_heights(tmp_path: Path):
    box_path = tmp_path / "server_box.json"
    box = box_from_top_corners(
        [(0.0, 0.0, 0.5), (1.0, 0.0, 0.5), (1.0, 1.0, 0.5), (0.0, 1.0, 0.5)],
        margin=0.1,
    )
    save_box(box, box_path)

    args = module.parse_args(["--box", str(box_path), "--z-gap", "0.4", "--points-per-loop", "8"])
    paths, (z_a, z_b) = module.build_paths(args)

    assert z_b == z_a + 0.4
    assert {point[2] for point in paths["drone-a"]} == {z_a}
    assert {point[2] for point in paths["drone-b"]} == {z_b}
    assert paths["drone-a"][0][:2] != paths["drone-b"][0][:2]
