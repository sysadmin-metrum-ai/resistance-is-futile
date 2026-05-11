"""Side-by-side Crazyflie + Lighthouse sanity dump for two URIs.

Runs two sequential connections (one Crazyradio): firmware, estimator, LH type,
deck detection, and Lighthouse memory valid geometry/calibration counts.

Usage (from repo root):

    uv run python scripts/lighthouse_compare_drones.py \\
        --uri-a radio://0/80/2M/E7E7E7E702 \\
        --uri-b radio://0/80/2M/E7E7E7E704

Params missing from TOC show ``<not in TOC>``.
"""

from __future__ import annotations

import argparse
import sys
import time
from threading import Event
from typing import Any

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.mem import LighthouseMemHelper
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

try:
    from lighthouse_dual_x_step import cache_dir_for_uri
except ImportError:

    def cache_dir_for_uri(uri: str) -> str:
        suffix = uri.rstrip("/").split("/")[-1]
        return f"./cache/{suffix}"


def _wait(ev: Event, timeout_s: float, name: str) -> None:
    if not ev.wait(timeout_s):
        raise RuntimeError(f"Timed out waiting for {name}")


def _valid_lh_objects(objects: dict[int, Any]) -> dict[int, Any]:
    return {bs_id: data for bs_id, data in objects.items() if getattr(data, "valid", False)}


def _get_param(cf: Crazyflie, full: str) -> str:
    try:
        return str(cf.param.get_value(full)).strip()
    except KeyError:
        return "<not in TOC>"
    except Exception as exc:
        return f"<error {exc}>"


def _gather_one(uri: str, timeout_s: float, param_settle_s: float) -> dict[str, Any]:
    out: dict[str, Any] = {}

    param_names = (
        "firmware.revision0",
        "firmware.modified",
        "platform.version",
        "system.selftestPassed",
        "stabilizer.estimator",
        "commander.enHighLevel",
        "lighthouse.systemType",
        "motion.disable",
    )

    deck_params = (
        "deck.bcLoco",
        "deck.bcDWM1000",
        "deck.bcLighthouse",
        "deck.bcMultiranger",
        "deck.bcZRanger",
        "deck.bcBigQuad",
        "deck.bcLedRing",
    )

    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir_for_uri(uri))) as scf:
        cf = scf.cf
        time.sleep(param_settle_s)

        for full in param_names:
            key = full.replace(".", "_")
            out[key] = _get_param(cf, full)

        for full in deck_params:
            short = full.split(".", 1)[1]
            out[f"deck_{short}"] = _get_param(cf, full)

        try:
            prot = getattr(cf.platform, "get_protocol_version", None)
            out["platform_protocol"] = str(prot()) if callable(prot) else "<no get_protocol_version>"
        except Exception as exc:
            out["platform_protocol"] = f"<error {exc}>"

        helper = LighthouseMemHelper(cf)
        geos_ready = Event()
        cals_ready = Event()
        geos: dict[int, Any] = {}
        cals: dict[int, Any] = {}

        def geos_done(g: dict) -> None:
            nonlocal geos
            geos = dict(g)
            geos_ready.set()

        def cals_done(c: dict) -> None:
            nonlocal cals
            cals = dict(c)
            cals_ready.set()

        helper.read_all_geos(geos_done)
        _wait(geos_ready, timeout_s, "Lighthouse geometry read")

        helper.read_all_calibs(cals_done)
        _wait(cals_ready, timeout_s, "Lighthouse calibration read")

        vg = _valid_lh_objects(geos)
        vc = _valid_lh_objects(cals)
        out["lh_valid_geometries"] = len(vg)
        out["lh_valid_calibrations"] = len(vc)
        out["lh_raw_geometry_ids"] = sorted(geos.keys())
        out["lh_raw_calib_ids"] = sorted(cals.keys())

    return out


def _print_table(left: dict[str, Any], right: dict[str, Any], label_a: str, label_b: str) -> None:
    keys = sorted(set(left) | set(right))

    exclude_raw = {"lh_raw_geometry_ids", "lh_raw_calib_ids"}

    printable = [k for k in keys if k not in exclude_raw]

    width = max((len(k) for k in printable), default=18)

    print(f"\n{'parameter':<{width}}  {label_a:>26}  {label_b:>26}  match")
    print("-" * (width + 26 + 26 + 10))

    diffs = 0
    for k in printable:
        va = left.get(k, "")
        vb = right.get(k, "")
        sa, sb = str(va), str(vb)
        ok = sa == sb
        if not ok:
            diffs += 1
        mark = "yes" if ok else "DIFF"
        print(f"{k:<{width}}  {sa:>26}  {sb:>26}  {mark}")

    for k in ("lh_raw_geometry_ids", "lh_raw_calib_ids"):
        if k in left or k in right:
            print(f"\n{k}:")
            print(f"  {label_a}: {left.get(k)}")
            print(f"  {label_b}: {right.get(k)}")

    print(f"\nTotal differing scalar rows: {diffs}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compare two Crazyflies (firmware / LH / decks)")
    p.add_argument("--uri-a", default="radio://0/80/2M/E7E7E7E702")
    p.add_argument("--uri-b", default="radio://0/80/2M/E7E7E7E704")
    p.add_argument("--timeout", type=float, default=30.0, help="Lighthouse memory read timeout (s)")
    p.add_argument(
        "--param-settle",
        type=float,
        default=1.5,
        help="Sleep after link up before reading params (s)",
    )
    args = p.parse_args(argv)

    ua, ub = args.uri_a.rstrip("/"), args.uri_b.rstrip("/")
    tag_a = ua.split("/")[-1][:12]
    tag_b = ub.split("/")[-1][:12]

    try:
        cflib.crtp.init_drivers()

        print(f"Gathering A: {ua}")
        da = _gather_one(ua, args.timeout, args.param_settle)

        print(f"Gathering B: {ub}")
        db = _gather_one(ub, args.timeout, args.param_settle)

        _print_table(da, db, tag_a, tag_b)
        return 0

    except Exception as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
