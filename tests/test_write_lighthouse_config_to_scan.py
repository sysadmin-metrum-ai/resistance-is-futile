import importlib.util
from pathlib import Path
import sys
import types


def install_fake_cflib():
    cflib = types.ModuleType("cflib")
    cflib.crtp = types.ModuleType("cflib.crtp")
    cflib.crtp.init_drivers = lambda: None
    cflib.crtp.scan_interfaces = lambda: []

    crazyflie_mod = types.ModuleType("cflib.crazyflie")
    crazyflie_mod.Crazyflie = type("Crazyflie", (), {})

    mem_mod = types.ModuleType("cflib.crazyflie.mem")
    mem_mod.LighthouseMemHelper = type("LighthouseMemHelper", (), {})

    sync_mod = types.ModuleType("cflib.crazyflie.syncCrazyflie")
    sync_mod.SyncCrazyflie = type("SyncCrazyflie", (), {})

    localization_mod = types.ModuleType("cflib.localization")
    config_mod = types.ModuleType("cflib.localization.lighthouse_config_manager")
    config_mod.LighthouseConfigWriter = type("LighthouseConfigWriter", (), {})

    sys.modules["cflib"] = cflib
    sys.modules["cflib.crtp"] = cflib.crtp
    sys.modules["cflib.crazyflie"] = crazyflie_mod
    sys.modules["cflib.crazyflie.mem"] = mem_mod
    sys.modules["cflib.crazyflie.syncCrazyflie"] = sync_mod
    sys.modules["cflib.localization"] = localization_mod
    sys.modules["cflib.localization.lighthouse_config_manager"] = config_mod


install_fake_cflib()

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "write-lighthouse-config-to-scan.py"
SPEC = importlib.util.spec_from_file_location("write_lighthouse_config_to_scan", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_parse_args_defaults_to_source_drone_and_requires_yes():
    args = module.parse_args([])

    assert args.source_uri == "radio://0/80/2M/E7E7E7E702"
    assert args.target_uri == []
    assert args.no_scan is False
    assert args.yes is False
    assert args.system_type == 2
    assert args.base_station_count is None


def test_target_uris_skips_exact_source_and_dedupes():
    targets = module.target_uris(
        [
            "radio://0/80/2M/E7E7E7E702",
            "radio://0/80/2M/E7E7E7E701/",
        ],
        ["radio://0/80/2M/E7E7E7E701"],
        "radio://0/80/2M/E7E7E7E702",
        include_source=False,
    )

    assert targets == ["radio://0/80/2M/E7E7E7E701"]


def test_target_uris_can_include_source_when_requested():
    targets = module.target_uris(
        ["radio://0/80/2M/E7E7E7E702"],
        [],
        "radio://0/80/2M/E7E7E7E702",
        include_source=True,
    )

    assert targets == ["radio://0/80/2M/E7E7E7E702"]


def test_valid_objects_keeps_only_valid_data():
    valid = types.SimpleNamespace(valid=True)
    invalid = types.SimpleNamespace(valid=False)
    missing = types.SimpleNamespace()

    assert module.valid_objects({0: valid, 1: invalid, 2: missing}) == {0: valid}


def test_base_station_count_infers_slots_from_highest_id():
    assert module.base_station_count({0: object(), 1: object()}, {}) == 2
    assert module.base_station_count({}, {3: object()}) == 4
