#!/usr/bin/env python3
import argparse
import json
import sys
import time
from pathlib import Path
from threading import Event

import cflib.crtp
from cflib import crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.mem import MemoryElement
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from src.services.preflight_logic import (
    PositionSample,
    PositionStabilityThresholds,
    evaluate_position_stability,
    format_position_metrics,
)


def load_anchor_ids(path: Path) -> set[int]:
    ns = {}
    exec(path.read_text(), ns)
    anchors = ns.get("anchor_positions")
    if not isinstance(anchors, dict):
        raise ValueError("anchors file must define anchor_positions dict")
    return {int(k) for k in anchors.keys()}


def wait(event: Event, timeout_s: float, name: str) -> None:
    if not event.wait(timeout_s):
        raise RuntimeError(f"timeout waiting for {name}")


def read_anchor_validity(cf, timeout_s: float) -> dict[int, bool]:
    done = Event()
    failed = Event()
    cf.mem.refresh(done.set, failed.set)
    wait(done, timeout_s, "mem refresh")
    if failed.is_set():
        raise RuntimeError("mem refresh failed")

    mems2 = cf.mem.get_mems(MemoryElement.TYPE_LOCO2)
    if mems2:
        mem = mems2[0]
        ids_done = Event()
        data_done = Event()
        mem.update_id_list(lambda _: ids_done.set())
        wait(ids_done, timeout_s, "loco2 ids")
        mem.update_data(lambda _: data_done.set())
        wait(data_done, timeout_s, "loco2 data")
        return {aid: bool(mem.anchor_data[aid].is_valid) for aid in mem.anchor_data}

    mems = cf.mem.get_mems(MemoryElement.TYPE_LOCO)
    if mems:
        mem = mems[0]
        done = Event()
        mem.update(lambda _: done.set())
        wait(done, timeout_s, "loco data")
        return {idx: bool(a.is_valid) for idx, a in enumerate(mem.anchor_data)}

    raise RuntimeError("no loco memory found")


def main() -> int:
    p = argparse.ArgumentParser(description="LPS go/no-go preflight check")
    p.add_argument("--uri", default="radio://0/90/2M")
    p.add_argument("--anchors", default="scripts/anchors.py")
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--period-ms", type=int, default=200)
    p.add_argument("--z-spread-max", type=float, default=0.25)
    p.add_argument("--xy-spread-max", type=float, default=0.20)
    p.add_argument("--z-drift-max", type=float, default=0.20)
    p.add_argument("--force-tdoa3", action="store_true", default=True)
    p.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = p.parse_args()

    expected_ids = load_anchor_ids(Path(args.anchors))
    cflib.crtp.init_drivers()
    samples: list[PositionSample] = []
    reasons = []

    print(f"Connecting: {args.uri}")
    with SyncCrazyflie(args.uri, cf=crazyflie.Crazyflie(rw_cache="./cache")) as scf:
        cf = scf.cf
        if args.force_tdoa3:
            cf.param.set_value("loco.mode", "3")
            time.sleep(0.3)

        mode = int(float(cf.param.get_value("loco.mode")))
        est = int(float(cf.param.get_value("stabilizer.estimator")))
        deck_loco = int(float(cf.param.get_value("deck.bcLoco")))
        deck_uwb = int(float(cf.param.get_value("deck.bcDWM1000")))
        print(f"mode={mode} estimator={est} deck.bcLoco={deck_loco} deck.bcDWM1000={deck_uwb}")

        valid = read_anchor_validity(cf, timeout_s=12.0)
        present = set(valid.keys())
        missing = sorted(expected_ids - present)
        invalid = sorted([i for i in expected_ids if i in valid and not valid[i]])
        print(f"anchors expected={sorted(expected_ids)} present={sorted(present)}")
        if missing:
            reasons.append(f"missing anchors in memory: {missing}")
        if invalid:
            reasons.append(f"invalid anchors in memory: {invalid}")

        lg = LogConfig(name="Pos", period_in_ms=args.period_ms)
        lg.add_variable("kalman.stateX", "float")
        lg.add_variable("kalman.stateY", "float")
        lg.add_variable("kalman.stateZ", "float")

        def cb(_ts, data, _lg):
            samples.append(
                PositionSample(
                    x=data["kalman.stateX"],
                    y=data["kalman.stateY"],
                    z=data["kalman.stateZ"],
                )
            )

        cf.log.add_config(lg)
        lg.data_received_cb.add_callback(cb)
        lg.start()
        time.sleep(args.duration)
        lg.stop()

    stability = evaluate_position_stability(
        samples,
        PositionStabilityThresholds(
            required_samples=10,
            xy_spread_max_m=args.xy_spread_max,
            z_spread_max_m=args.z_spread_max,
            z_drift_max_m=args.z_drift_max,
        ),
    )
    print(format_position_metrics(stability.metrics))
    reasons.extend(stability.reasons)

    if mode != 3:
        reasons.append(f"loco.mode is {mode}, expected 3")
    if est != 2:
        reasons.append(f"estimator is {est}, expected 2")
    if deck_loco != 1 or deck_uwb != 1:
        reasons.append("loco/uwb deck not detected")

    ok = not reasons
    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "uri": args.uri,
                    "mode": mode,
                    "estimator": est,
                    "deck_loco": deck_loco,
                    "deck_uwb": deck_uwb,
                    "anchor_validity": {
                        "expected": sorted(expected_ids),
                        "present": sorted(present),
                        "missing": missing,
                        "invalid": invalid,
                    },
                    "stability": stability.to_dict(),
                    "reasons": reasons,
                },
                indent=2,
            )
        )
    if not ok:
        print("NO-GO")
        for r in reasons:
            print(f"- {r}")
        return 1
    print("GO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
