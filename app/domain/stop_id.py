from __future__ import annotations

from typing import Iterable, List


class StopId:
    """Genera identificadores N1/N2/P1/P2 por tipo y renumera tras borrar."""

    _last_ids = {"N": 0, "P": 0}

    @staticmethod
    def type_prefix(stop_type: str) -> str:
        """Return ``"N"`` for notification stops or ``"P"`` for package stops."""
        return "N" if str(stop_type).strip().lower() in {"n", "notificacion", "notification"} else "P"

    @classmethod
    def next_id(cls, stop_type: str) -> str:
        prefix = cls.type_prefix(stop_type)
        cls._last_ids[prefix] += 1
        return f"{prefix}{cls._last_ids[prefix]}"

    @classmethod
    def reindex(cls, stops: Iterable[dict]) -> List[dict]:
        numbered = []
        counters = {"N": 0, "P": 0}
        for stop in stops:
            if not isinstance(stop, dict):
                continue
            stop_type = str(stop.get("type", "notificacion")).strip().lower()
            prefix = cls.type_prefix(stop_type)
            counters[prefix] += 1
            stop["id"] = f"{prefix}{counters[prefix]}"
            stop["type"] = "notificacion" if prefix == "N" else "paquete"
            numbered.append(stop)
        cls._last_ids = {"N": counters["N"], "P": counters["P"]}
        return numbered

    @classmethod
    def reset(cls):
        cls._last_ids = {"N": 0, "P": 0}
