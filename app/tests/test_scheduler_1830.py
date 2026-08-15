import unittest
from datetime import datetime

from app.services.scheduler import Scheduler


class SchedulerTests(unittest.TestCase):
    def test_scheduler_triggers_auto_optimization_at_1830(self):
        self.assertFalse(Scheduler.should_auto_optimize(datetime(2026, 1, 1, 18, 29)))
        self.assertTrue(Scheduler.should_auto_optimize(datetime(2026, 1, 1, 18, 30)))
        self.assertTrue(Scheduler.should_auto_optimize(datetime(2026, 1, 1, 19, 0)))
