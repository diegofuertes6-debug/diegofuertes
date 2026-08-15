import unittest

from app.domain.stop_id import StopId


class StopIdTests(unittest.TestCase):
    def test_generates_independent_correlative_by_type(self):
        StopId.reset()
        self.assertEqual(StopId.next_id("notificacion"), "N1")
        self.assertEqual(StopId.next_id("notificacion"), "N2")
        self.assertEqual(StopId.next_id("paquete"), "P1")
        self.assertEqual(StopId.next_id("paquete"), "P2")

    def test_reindexes_after_delete(self):
        stops = [
            {"type": "notificacion", "id": "N2"},
            {"type": "paquete", "id": "P2"},
        ]
        reindexed = StopId.reindex(stops)
        self.assertEqual([s["id"] for s in reindexed], ["N1", "P1"])
