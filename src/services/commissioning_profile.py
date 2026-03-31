"""Shared commissioning profiles for new Crazyflie bring-up."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CommissioningProfile:
    """Desired runtime parameters for a commissioned drone."""

    loco_mode: int
    estimator: int
    tdoa3_stddev: float
    robust_tdoa: int
    high_level_commander: int

    def to_param_map(self) -> dict[str, str]:
        """Return Crazyflie parameter values as strings."""

        return {
            "loco.mode": str(self.loco_mode),
            "stabilizer.estimator": str(self.estimator),
            "tdoa3.stddev": f"{self.tdoa3_stddev:.2f}",
            "kalman.robustTdoa": str(self.robust_tdoa),
            "commander.enHighLevel": str(self.high_level_commander),
        }

    def to_dict(self) -> dict:
        return asdict(self)


def default_tdoa3_profile() -> CommissioningProfile:
    """Recommended demo profile for 6-8 anchor TDoA3 operation."""

    return CommissioningProfile(
        loco_mode=3,
        estimator=2,
        tdoa3_stddev=0.15,
        robust_tdoa=0,
        high_level_commander=1,
    )


def default_twr_profile() -> CommissioningProfile:
    """Recommended single-drone profile for 4-anchor TWR benches."""

    return CommissioningProfile(
        loco_mode=1,
        estimator=2,
        tdoa3_stddev=0.15,
        robust_tdoa=0,
        high_level_commander=1,
    )
