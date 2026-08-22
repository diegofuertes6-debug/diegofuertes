from __future__ import annotations

from typing import Iterable, List


class StopId:
    """Genera identificadores C1 y Pp/Pm/PG por tipo y tamaño."""

    _last_ids = {"C": 0, "Pp": 0, "Pm": 0, "PG": 0}

    @classmethod
    def _prefix_for(cls, stop_type: str, package_size: str | None = None) -> str:
        normalized_type = str(stop_type or "carta").strip().lower()
        normalized_size = str(package_size or "").strip().lower()

        if normalized_type in {"c", "carta", "carta(s)", "letter", "letters"}:
            return "C"

        if normalized_size in {"pequeño", "pequeno", "small"}:
            return "Pp"
        if normalized_size in {"grande", "large"}:
            return "PG"
        if normalized_size in {"mediano", "medio", "median", "medium"}:
            return "Pm"

        if normalized_type in {"pp", "paquete_pequeno", "paquete pequeño"}:
            return "Pp"
        if normalized_type in {"pg", "paquete_grande"}:
            return "PG"
        return "Pm"

    @classmethod
    def next_id(cls, stop_type: str, package_size: str | None = None) -> str:
        prefix = cls._prefix_for(stop_type, package_size)
        cls._last_ids[prefix] += 1
        return f"{prefix}{cls._last_ids[prefix]}"

    @classmethod
    def reindex(cls, stops: Iterable[dict]) -> List[dict]:
        numbered = []
        counters = {"C": 0, "Pp": 0, "Pm": 0, "PG": 0}
        for stop in stops:
            if not isinstance(stop, dict):
                continue
            stop_type = str(stop.get("type", "carta")).strip().lower()
            package_size = stop.get("package_size") or stop.get("paqueteria")
            prefix = cls._prefix_for(stop_type, package_size)
            counters[prefix] += 1
            stop["id"] = f"{prefix}{counters[prefix]}"
            if prefix == "C":
                stop["type"] = "carta"
                stop.pop("package_size", None)
            else:
                stop["type"] = "paquete"
                stop["package_size"] = {
                    "Pp": "Pequeño",
                    "Pm": "Mediano",
                    "PG": "Grande",
                }[prefix]
            numbered.append(stop)
        cls._last_ids = {
            "C": counters["C"],
            "Pp": counters["Pp"],
            "Pm": counters["Pm"],
            "PG": counters["PG"],
        }
        return numbered

    @classmethod
    def reset(cls):
        cls._last_ids = {"C": 0, "Pp": 0, "Pm": 0, "PG": 0}
