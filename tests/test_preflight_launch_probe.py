from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROBE_DIR = Path(__file__).resolve().parents[1] / "preflight_launch_probe"
if str(PROBE_DIR) not in sys.path:
    sys.path.insert(0, str(PROBE_DIR))

import probe  # noqa: E402


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_probe", PROBE_DIR / "run_probe.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_uri_list_accepts_space_and_comma_values() -> None:
    assert probe.parse_uri_list(["a,b", "c", "a"]) == ["a", "b", "c"]


def test_parse_args_defaults_to_single_safe_probe() -> None:
    module = load_runner_module()

    args = module.parse_args([])

    assert args.uris == [module.DEFAULT_URI]
    assert args.height_m == 0.55
    assert args.schedule_buffer_s == 0.25
    assert args.preflight_only is False


def test_variance_ready_requires_stable_window() -> None:
    stable = [0.0002] * probe.VARIANCE_WINDOW
    unstable = [0.0, 0.01] * probe.VARIANCE_WINDOW

    assert probe._variance_ready(stable, stable, stable) is True
    assert probe._variance_ready(unstable, stable, stable) is False
