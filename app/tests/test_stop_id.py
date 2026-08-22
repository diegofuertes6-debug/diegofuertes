import unittest

from app.domain.stop_id import StopId


class StopIdTests(unittest.TestCase):
    def test_generates_independent_correlative_by_type(self):
        StopId.reset()
        self.assertEqual(StopId.next_id("carta"), "C1")
        self.assertEqual(StopId.next_id("carta"), "C2")
        self.assertEqual(StopId.next_id("paquete", "pequeño"), "Pp1")
        self.assertEqual(StopId.next_id("paquete", "pequeño"), "Pp2")
        self.assertEqual(StopId.next_id("paquete", "mediano"), "Pm1")
        self.assertEqual(StopId.next_id("paquete", "grande"), "PG1")

    def test_reindexes_after_delete(self):
        stops = [
            {"type": "carta", "id": "C2"},
            {"type": "paquete", "package_size": "Pequeño", "id": "Pp9"},
            {"type": "paquete", "package_size": "Mediano", "id": "Pm3"},
            {"type": "paquete", "package_size": "Grande", "id": "PG8"},
        ]
        reindexed = StopId.reindex(stops)
        self.assertEqual([s["id"] for s in reindexed], ["C1", "Pp1", "Pm1", "PG1"])
