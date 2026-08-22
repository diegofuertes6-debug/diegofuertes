from __future__ import annotations

from app.domain.priority import Priority


class ListPresenter:
    @staticmethod
    def _prefix_for(stop):
        stop_type = str(stop.get("type", "carta")).strip().lower()
        if stop_type in {"c", "carta", "letter"}:
            return "C"
        size = str(stop.get("package_size") or stop.get("paqueteria") or "").strip().lower()
        if size in {"pequeño", "pequeno", "small"}:
            return "Pp"
        if size in {"grande", "large"}:
            return "PG"
        return "Pm"

    @staticmethod
    def label_for(stop):
        prefix = ListPresenter._prefix_for(stop)
        number = stop.get("id") or stop.get("code") or "1"
        text_number = str(number).strip()
        if not text_number:
            return f"{prefix}1"
        if text_number.lower().startswith(prefix.lower()):
            suffix = text_number[len(prefix):].strip()
            return f"{prefix}{suffix or '1'}"
        numeric = "".join(ch for ch in text_number if ch.isdigit())
        return f"{prefix}{numeric or '1'}"

    @staticmethod
    def color_for(stop):
        priority = Priority.from_value(stop.get("priority"))
        return priority.color

    @staticmethod
    def has_cross(stop, action: str):
        if action == "new":
            return stop.get("state") == "new"
        if action == "delete":
            return stop.get("state") == "deleted"
        return False

    @staticmethod
    def badge_for(stop):
        if Priority.from_value(stop.get("priority")) == Priority.HIGH:
            return "ALTA"
        return ""
