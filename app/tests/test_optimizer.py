import unittest
from datetime import datetime

from app.services.optimizer import optimize_initial, optimize_pending_with_priority


class OptimizerTests(unittest.TestCase):
    def test_optimize_initial_without_priority(self):
        stops = [
            {"id": "A", "lat": 40.0, "lng": 0.0},
            {"id": "B", "lat": 40.0, "lng": 0.5},
            {"id": "C", "lat": 40.5, "lng": 0.0},
        ]
        ordered = optimize_initial(stops)
        self.assertEqual([s["id"] for s in ordered], ["A", "B", "C"])

    def test_optimize_pending_with_priority_after_1830(self):
        stops = [
            {"id": "N1", "priority": "baja", "pending": True, "lat": 40.0, "lng": 0.0},
            {"id": "N2", "priority": "alta", "pending": True, "lat": 40.0, "lng": 1.0},
            {"id": "N3", "priority": "media", "pending": True, "lat": 39.0, "lng": 0.0},
            {"id": "N4", "priority": "alta", "pending": False, "lat": 41.0, "lng": 0.0},
        ]
        ordered = optimize_pending_with_priority(stops, datetime(2026, 1, 1, 18, 30))
        self.assertEqual([s["id"] for s in ordered], ["N2", "N3", "N1"])
