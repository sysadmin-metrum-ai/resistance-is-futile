from src.services.commissioning_profile import (
    default_tdoa3_profile,
    default_twr_profile,
)


def test_default_tdoa3_profile_matches_demo_defaults():
    profile = default_tdoa3_profile()

    assert profile.to_param_map() == {
        "loco.mode": "3",
        "stabilizer.estimator": "2",
        "tdoa3.stddev": "0.15",
        "kalman.robustTdoa": "0",
        "commander.enHighLevel": "1",
    }


def test_default_twr_profile_uses_twr_mode():
    profile = default_twr_profile()

    assert profile.to_param_map()["loco.mode"] == "1"
    assert profile.to_param_map()["stabilizer.estimator"] == "2"
