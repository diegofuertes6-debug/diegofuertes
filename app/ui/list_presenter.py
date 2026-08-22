from __future__ import annotations

from app.domain.priority import Priority
from app.domain.stop_id import StopId


class ListPresenter:
    @staticmethod
    def label_for(stop):
        stop_type = str(stop.get("type", "notificacion")).strip().lower()
        prefix = StopId.type_prefix(stop_type)
        number = stop.get("id") or stop.get("code") or "1"
        if not str(number).startswith(prefix):
            return f"{prefix}{str(number).lstrip(prefix)}"
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
