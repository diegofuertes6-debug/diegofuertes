from __future__ import annotations

from enum import Enum


class Priority(Enum):
    HIGH = "alta"
    MEDIUM = "media"
    LOW = "baja"

    @classmethod
    def from_value(cls, value):
        if value is None:
            return cls.MEDIUM
        normalized = str(value).strip().lower()
        mapping = {"alta": cls.HIGH, "media": cls.MEDIUM, "baja": cls.LOW}
        return mapping.get(normalized, cls.MEDIUM)

    @property
    def color(self):
        return _PRIORITY_COLORS.get(self, "orange")

    @property
    def order(self):
        return _PRIORITY_ORDER.get(self, 1)


_PRIORITY_COLORS = {
    Priority.HIGH: "red",
    Priority.MEDIUM: "orange",
    Priority.LOW: "white",
}

_PRIORITY_ORDER = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}
