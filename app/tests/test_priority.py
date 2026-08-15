import unittest

from app.domain.priority import Priority


class PriorityTests(unittest.TestCase):
    def test_priority_colors_and_order(self):
        self.assertEqual(Priority.HIGH.color, "red")
        self.assertEqual(Priority.MEDIUM.color, "orange")
        self.assertEqual(Priority.LOW.color, "white")
        self.assertLess(Priority.HIGH.order, Priority.MEDIUM.order)
        self.assertLess(Priority.MEDIUM.order, Priority.LOW.order)
