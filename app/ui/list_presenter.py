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
        if text_number.startswith(prefix):
            return text_number
        numeric = "".join(ch for ch in text_number if ch.isdigit()) or "1"
        if numeric == "0":
            numeric = "1"
        if not text_number:
            numeric = "1"
        if text_number and text_number[0].isdigit():
            return f"{prefix}{text_number}"
        if text_number.lower().startswith(prefix.lower()):
            return f"{prefix}{text_number[len(prefix):]}"
        if text_number.isdigit():
            return f"{prefix}{text_number}"
        if text_number.isalnum():
            return f"{prefix}{numeric}"
        if not text_number.startswith(prefix):
            return f"{prefix}{numeric}"
        return str(number)

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
