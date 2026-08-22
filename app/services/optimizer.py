from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from app.domain.priority import Priority
from app.services.geo import haversine_km


def is_after_cutoff(now: datetime) -> bool:
    """Return True once the 18:30 daily optimization cut-off has been reached."""
    return now.hour > 18 or (now.hour == 18 and now.minute >= 30)


def optimize_initial(stops: Iterable[dict]) -> List[dict]:
    """Sin prioridad: devuelve la secuencia más corta por distancia."""
    items = [stop for stop in stops if isinstance(stop, dict)]
    if not items:
        return []
    valid = [stop for stop in items if isinstance(stop.get("lat"), (int, float)) and isinstance(stop.get("lng"), (int, float))]
    if not valid:
        return list(items)

    ordered = [valid[0]]
    remaining = valid[1:]
    while remaining:
        current = ordered[-1]
        next_stop = min(remaining, key=lambda stop: distance_km(current, stop))
        ordered.append(next_stop)
        remaining.remove(next_stop)
    return ordered


def optimize_pending_with_priority(stops: Iterable[dict], now: datetime) -> List[dict]:
    """Desde 18:30, aplica prioridad alta > media > baja y dentro de cada grupo optimiza distancia."""
    items = [stop for stop in stops if isinstance(stop, dict)]
    if not items:
        return []

    if not is_after_cutoff(now):
        return optimize_initial(items)

    pending = [stop for stop in items if stop.get("pending", False)]
    source = pending if pending else items
    grouped = {Priority.HIGH: [], Priority.MEDIUM: [], Priority.LOW: []}
    for stop in source:
        priority = Priority.from_value(stop.get("priority"))
        grouped[priority].append(stop)

    ordered = []
    for priority in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
        if grouped[priority]:
            ordered.extend(optimize_initial(grouped[priority]))
    return ordered


def distance_km(a: dict, b: dict) -> float:
    try:
        lat1 = float(a["lat"])
        lng1 = float(a["lng"])
        lat2 = float(b["lat"])
        lng2 = float(b["lng"])
    except (KeyError, TypeError, ValueError):
        return float("inf")
    return haversine_km(lat1, lng1, lat2, lng2)
