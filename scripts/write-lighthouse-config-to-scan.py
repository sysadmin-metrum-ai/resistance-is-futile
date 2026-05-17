"""Copy Lighthouse config from one Crazyflie to scanned Crazyflies.

Usage:
    uv run python scripts/write-lighthouse-config-to-scan.py --fleet --yes
    uv run python scripts/write-lighthouse-config-to-scan.py --scan --yes
    uv run python scripts/write-lighthouse-config-to-scan.py --source-uri radio://0/80/2M/E7E7E7E706 --target-uri radio://0/80/2M/E7E7E7E701 --yes

This follows the Bitcraze documented flow:
read with LighthouseMemHelper, write and persist with LighthouseConfigWriter.write_and_store_config().
"""

import argparse
import sys
from threading import Event

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.mem import LighthouseMemHelper
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.localization.lighthouse_config_manager import LighthouseConfigWriter


DEFAULT_SOURCE_URI = "radio://0/80/2M/E7E7E7E701"


def status(message: str) -> None:
    print(message, flush=True)


def wait(event: Event, timeout_s: float, name: str) -> None:
    if not event.wait(timeout_s):
        raise RuntimeError(f"Timed out waiting for {name}")


def normalize_uri(uri: str) -> str:
    return uri.rstrip("/")


def valid_objects(objects: dict) -> dict:
    return {bs_id: data for bs_id, data in objects.items() if getattr(data, "valid", False)}


def scan_uris() -> list[str]:
    return [uri for uri, _info in cflib.crtp.scan_interfaces()]


def default_fleet_uris() -> list[str]:
    return [
        *(f"radio://0/80/2M/E7E7E7E7{index:02d}" for index in range(0, 5)),
        *(f"radio://1/90/2M/E7E7E7E7{index:02d}" for index in range(5, 10)),
    ]


def target_uris(
    scanned: list[str],
    explicit: list[str],
    source_uri: str,
    include_source: bool,
    fleet: list[str] | None = None,
) -> list[str]:
    source = normalize_uri(source_uri)
    result = []

    for uri in [*scanned, *(fleet or []), *explicit]:
        normalized = normalize_uri(uri)
        if not include_source and normalized == source:
            continue
        if normalized not in result:
            result.append(normalized)

    return result


def read_lighthouse_config(source_uri: str, timeout_s: float) -> tuple[dict, dict]:
    status(f"Reading Lighthouse config from {source_uri}...")
    with SyncCrazyflie(source_uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        helper = LighthouseMemHelper(scf.cf)

        geos_ready = Event()
        calibs_ready = Event()
        result: dict[str, dict] = {}

        def geos_done(geos: dict) -> None:
            result["geos"] = valid_objects(geos)
            geos_ready.set()

        def calibs_done(calibs: dict) -> None:
            result["calibs"] = valid_objects(calibs)
            calibs_ready.set()

        helper.read_all_geos(geos_done)
        wait(geos_ready, timeout_s, "Lighthouse geometry read")

        helper.read_all_calibs(calibs_done)
        wait(calibs_ready, timeout_s, "Lighthouse calibration read")

    geos = result["geos"]
    calibs = result["calibs"]
    if not geos:
        raise RuntimeError("Source has no valid Lighthouse geometry")
    if not calibs:
        raise RuntimeError("Source has no valid Lighthouse calibration")

    status(f"Read {len(geos)} valid geometries and {len(calibs)} valid calibrations.")
    return geos, calibs


def base_station_count(geos: dict, calibs: dict) -> int:
    ids = [*geos.keys(), *calibs.keys()]
    if not ids:
        raise RuntimeError("No Lighthouse base station data to write")
    return max(ids) + 1


def write_lighthouse_config(
    uri: str,
    geos: dict,
    calibs: dict,
    timeout_s: float,
    system_type: int,
    nr_of_base_stations: int,
) -> None:
    status(f"Writing Lighthouse config to {uri}...")
    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        stored = Event()
        result = {"ok": False}

        def data_stored(ok: bool) -> None:
            result["ok"] = ok
            stored.set()

        writer = LighthouseConfigWriter(scf.cf, nr_of_base_stations=nr_of_base_stations)
        writer.write_and_store_config(data_stored, geos=geos, calibs=calibs, system_type=system_type)
        wait(stored, timeout_s, "Lighthouse config write and persist")

    if not result["ok"]:
        raise RuntimeError(f"Write failed for {uri}")
    status(f"Wrote and persisted Lighthouse config to {uri}.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write source Lighthouse config to scanned Crazyflies")
    parser.add_argument("--source-uri", default=DEFAULT_SOURCE_URI)
    parser.add_argument("--target-uri", action="append", default=[], help="Explicit target URI; repeatable")
    parser.add_argument("--fleet", action="store_true", help="Include default fleet 00-09 split across channels 80/90")
    parser.add_argument("--scan", action="store_true", help="Also include scanned Crazyflies")
    parser.add_argument("--no-scan", dest="scan", action="store_false", help=argparse.SUPPRESS)
    parser.add_argument("--include-source", action="store_true", help="Allow writing back to the source URI")
    parser.add_argument("--system-type", type=int, default=2, choices=[1, 2], help="Lighthouse system type")
    parser.add_argument("--base-station-count", type=int, default=None, help="Default: infer from source config")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--yes", action="store_true", help="Actually write config")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        cflib.crtp.init_drivers()
        scanned = scan_uris() if args.scan else []
        fleet = default_fleet_uris() if args.fleet else []
        targets = target_uris(scanned, args.target_uri, args.source_uri, args.include_source, fleet)

        status(f"Source: {args.source_uri}")
        status(f"Scanned targets: {scanned if scanned else 'none'}")
        status(f"Fleet targets: {fleet if fleet else 'none'}")
        status(f"Will write targets: {targets if targets else 'none'}")

        if not targets:
            raise RuntimeError("No target Crazyflies found")
        if not args.yes:
            raise RuntimeError("Refusing to write without --yes")

        geos, calibs = read_lighthouse_config(args.source_uri, args.timeout)
        nr_of_base_stations = args.base_station_count or base_station_count(geos, calibs)
        status(f"Using {nr_of_base_stations} Lighthouse base station slots.")
        for uri in targets:
            write_lighthouse_config(uri, geos, calibs, args.timeout, args.system_type, nr_of_base_stations)

        status("Done.")
        return 0
    except Exception as exc:
        status(f"ABORT: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
