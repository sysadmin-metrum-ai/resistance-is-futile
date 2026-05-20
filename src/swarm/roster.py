"""Drone discovery and healthiest-swarm selection."""

from __future__ import annotations

import os

from src.swarm.health import normalize_uri
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import MIN_EXECUTION_SWARM_SIZE
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.models import SwarmSelection

DEFAULT_DISCOVERY_URI_PREFIX = "radio://0/80/2M/E7E7E7E7"
DEFAULT_DISCOVERY_COUNT = 9
DEFAULT_DISCOVERY_FLEET = (
    "radio://0/80/2M/E7E7E7E701",
    "radio://0/80/2M/E7E7E7E700",
    "radio://1/90/2M/E7E7E7E709",
)
DEFAULT_FULL_FLEET = tuple(
    [*(f"radio://0/80/2M/E7E7E7E7{index:02d}" for index in range(0, 5)),
     *(f"radio://1/90/2M/E7E7E7E7{index:02d}" for index in range(5, 10))]
)


def discover_candidates(allowed_uris: tuple[str, ...] = ()) -> list[DroneCandidate]:
    """Discover available Crazyflie URIs, or use a caller-provided allowlist."""

    if allowed_uris:
        return [DroneCandidate(uri=normalize_uri(uri)) for uri in allowed_uris]
    if os.getenv("CRAZYFLIE_DISCOVERY_MODE", "configured").lower() != "scan":
        return default_radio_candidates()

    try:
        import cflib.crtp
    except ImportError:
        return []

    cflib.crtp.init_drivers()
    scanned = [DroneCandidate(uri=normalize_uri(uri)) for uri, _info in cflib.crtp.scan_interfaces()]
    if scanned:
        return scanned
    return default_radio_candidates()


def default_radio_candidates() -> list[DroneCandidate]:
    """Fallback when Crazyradio scan misses known same-channel fleet URIs."""

    uri_list = os.getenv("CRAZYFLIE_URI_LIST")
    if uri_list:
        return [DroneCandidate(uri=normalize_uri(uri)) for uri in _split_uri_list(uri_list)]

    if "CRAZYFLIE_URI_PREFIX" not in os.environ and "CRAZYFLIE_URI_COUNT" not in os.environ:
        return [DroneCandidate(uri=uri) for uri in DEFAULT_DISCOVERY_FLEET]

    prefix = os.getenv("CRAZYFLIE_URI_PREFIX", DEFAULT_DISCOVERY_URI_PREFIX)
    count = int(os.getenv("CRAZYFLIE_URI_COUNT", str(DEFAULT_DISCOVERY_COUNT)))
    return [DroneCandidate(uri=f"{prefix}{index:02d}") for index in range(1, count + 1)]


def _split_uri_list(value: str) -> list[str]:
    return [part for chunk in value.split(",") for part in chunk.split() if part]


def filter_candidates(
    candidates: list[DroneCandidate],
    *,
    allowed_uris: tuple[str, ...] = (),
    denied_uris: tuple[str, ...] = (),
) -> list[DroneCandidate]:
    allowed = {normalize_uri(uri) for uri in allowed_uris}
    denied = {normalize_uri(uri) for uri in denied_uris}
    result: list[DroneCandidate] = []
    seen: set[str] = set()

    for candidate in candidates:
        uri = normalize_uri(candidate.uri)
        if uri in seen or uri in denied:
            continue
        if allowed and uri not in allowed:
            continue
        seen.add(uri)
        result.append(DroneCandidate(uri=uri, name=candidate.name))
    return result


def select_healthiest_swarm(
    health: list[DroneHealth],
    swarm_size: int,
    *,
    minimum_size: int | None = None,
) -> SwarmSelection:
    """Select the highest scoring ready drones, allowing degraded geometry."""

    if not MIN_EXECUTION_SWARM_SIZE <= swarm_size <= MAX_SWARM_SIZE:
        raise ValueError(f"swarm_size must be {MIN_EXECUTION_SWARM_SIZE}..{MAX_SWARM_SIZE}")
    required_size = minimum_size if minimum_size is not None else swarm_size
    if required_size < MIN_EXECUTION_SWARM_SIZE or required_size > swarm_size:
        raise ValueError("minimum_size must be between MIN_EXECUTION_SWARM_SIZE and swarm_size")

    ready = sorted((item for item in health if item.ready), key=lambda item: item.score, reverse=True)
    selected_size = min(swarm_size, len(ready))
    selected = tuple(ready[:selected_size])
    selected_uris = {item.uri for item in selected}
    rejected = tuple(
        sorted(
            (item for item in health if item.uri not in selected_uris),
            key=lambda item: (item.ready, item.score),
            reverse=True,
        )
    )
    return SwarmSelection(selected=selected, rejected=rejected, required_size=required_size)


def candidates_for_spec(spec: MissionSpec) -> list[DroneCandidate]:
    return filter_candidates(
        discover_candidates(spec.allowed_uris),
        allowed_uris=spec.allowed_uris,
        denied_uris=spec.denied_uris,
    )
