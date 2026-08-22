import unittest
from datetime import datetime

from app.services.optimizer import optimize_initial, optimize_pending_with_priority
from app.services.scheduler import Scheduler


class OptimizerRobustnessTests(unittest.TestCase):
    def test_stops_without_coords_are_preserved_at_end(self):
        """Stops with no lat/lng must not be silently dropped."""
        stops = [
            {"id": "A", "lat": 40.0, "lng": 0.0},
            {"id": "B"},  # no coords
            {"id": "C", "lat": 40.1, "lng": 0.1},
        ]
        result = optimize_initial(stops)
        ids = [s["id"] for s in result]
        self.assertIn("B", ids)
        self.assertEqual(ids[-1], "B")

    def test_all_no_coord_stops_returned(self):
        stops = [{"id": "X"}, {"id": "Y"}]
        result = optimize_initial(stops)
        self.assertEqual({s["id"] for s in result}, {"X", "Y"})

    def test_pending_with_priority_preserves_no_coord_stops(self):
        """No-coord stops must survive optimize_pending_with_priority."""
        stops = [
            {"id": "A", "priority": "alta", "pending": True, "lat": 40.0, "lng": 0.0},
            {"id": "B", "priority": "media", "pending": True},  # no coords
        ]
        now = datetime(2026, 1, 1, 18, 30)
        result = optimize_pending_with_priority(stops, now)
        ids = [s["id"] for s in result]
        self.assertIn("B", ids)


class SchedulerRunTests(unittest.TestCase):
    def test_run_auto_optimization_before_cutoff_returns_original_order(self):
        stops = [{"id": "X"}, {"id": "Y"}]
        result = Scheduler.run_auto_optimization(stops, datetime(2026, 1, 1, 18, 29))
        self.assertEqual([s["id"] for s in result], ["X", "Y"])

    def test_run_auto_optimization_at_cutoff_optimizes(self):
        stops = [
            {"id": "N1", "priority": "baja", "pending": True, "lat": 40.0, "lng": 0.0},
            {"id": "N2", "priority": "alta", "pending": True, "lat": 40.0, "lng": 1.0},
        ]
        result = Scheduler.run_auto_optimization(stops, datetime(2026, 1, 1, 18, 30))
        # alta comes first
        self.assertEqual(result[0]["id"], "N2")
