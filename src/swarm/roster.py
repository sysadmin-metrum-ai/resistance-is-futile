"""Drone discovery and healthiest-swarm selection."""

from __future__ import annotations

from src.swarm.health import normalize_uri
from src.swarm.models import DroneCandidate
from src.swarm.models import DroneHealth
from src.swarm.models import MAX_SWARM_SIZE
from src.swarm.models import MIN_SWARM_SIZE
from src.swarm.models import MissionSpec
from src.swarm.models import SwarmSelection


def discover_candidates(allowed_uris: tuple[str, ...] = ()) -> list[DroneCandidate]:
    """Discover available Crazyflie URIs, or use a caller-provided allowlist."""

    if allowed_uris:
        return [DroneCandidate(uri=normalize_uri(uri)) for uri in allowed_uris]

    try:
        import cflib.crtp
    except ImportError:
        return []

    cflib.crtp.init_drivers()
    return [DroneCandidate(uri=normalize_uri(uri)) for uri, _info in cflib.crtp.scan_interfaces()]


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


def select_healthiest_swarm(health: list[DroneHealth], swarm_size: int) -> SwarmSelection:
    """Select the highest scoring ready drones and reject the rest."""

    if not MIN_SWARM_SIZE <= swarm_size <= MAX_SWARM_SIZE:
        raise ValueError(f"swarm_size must be {MIN_SWARM_SIZE}..{MAX_SWARM_SIZE}")

    ready = sorted((item for item in health if item.ready), key=lambda item: item.score, reverse=True)
    selected = tuple(ready[:swarm_size])
    selected_uris = {item.uri for item in selected}
    rejected = tuple(
        sorted(
            (item for item in health if item.uri not in selected_uris),
            key=lambda item: (item.ready, item.score),
            reverse=True,
        )
    )
    return SwarmSelection(selected=selected, rejected=rejected, required_size=swarm_size)


def candidates_for_spec(spec: MissionSpec) -> list[DroneCandidate]:
    return filter_candidates(
        discover_candidates(spec.allowed_uris),
        allowed_uris=spec.allowed_uris,
        denied_uris=spec.denied_uris,
    )
