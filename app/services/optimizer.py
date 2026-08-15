from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from app.domain.priority import Priority


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

    if now.hour < 18 or (now.hour == 18 and now.minute < 30):
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
        lon1 = float(a["lng"])
        lat2 = float(b["lat"])
        lon2 = float(b["lng"])
    except (KeyError, TypeError, ValueError):
        return float("inf")

    import math

    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(h), math.sqrt(1 - h))
