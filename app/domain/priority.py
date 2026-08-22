from __future__ import annotations

from enum import Enum


class Priority(Enum):
    HIGH = "alta"
    MEDIUM = "media"
    NONE = "sin prioridad"

    @classmethod
    def from_value(cls, value):
        if value is None:
            return cls.NONE
        normalized = str(value).strip().lower()
        mapping = {
            "alta": cls.HIGH,
            "media": cls.MEDIUM,
            "sin prioridad": cls.NONE,
            "sin_prioridad": cls.NONE,
            "baja": cls.NONE,
        }
        return mapping.get(normalized, cls.NONE)

    @property
    def color(self):
        return {
            Priority.HIGH: "red",
            Priority.MEDIUM: "orange",
            Priority.NONE: "blue",
        }.get(self, "blue")

    @property
    def order(self):
        return {
            Priority.HIGH: 0,
            Priority.MEDIUM: 1,
            Priority.NONE: 2,
        }.get(self, 2)
