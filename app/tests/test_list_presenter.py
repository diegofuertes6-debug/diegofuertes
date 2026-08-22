import unittest

from app.domain.stop_id import StopId
from app.ui.list_presenter import ListPresenter


class ListPresenterTests(unittest.TestCase):
    def test_label_for_notification_already_prefixed(self):
        stop = {"type": "notificacion", "id": "N3"}
        self.assertEqual(ListPresenter.label_for(stop), "N3")

    def test_label_for_adds_prefix_when_missing(self):
        stop = {"type": "notificacion", "id": "3"}
        self.assertEqual(ListPresenter.label_for(stop), "N3")

    def test_label_for_package_adds_p_prefix(self):
        stop = {"type": "paquete", "id": "5"}
        self.assertEqual(ListPresenter.label_for(stop), "P5")

    def test_label_for_does_not_double_prefix(self):
        # "NNA5" already starts with "N" — must be returned unchanged
        stop = {"type": "notificacion", "id": "NNA5"}
        self.assertEqual(ListPresenter.label_for(stop), "NNA5")

    def test_label_for_uses_code_when_id_absent(self):
        stop = {"type": "paquete", "code": "7"}
        self.assertEqual(ListPresenter.label_for(stop), "P7")

    def test_color_for_returns_correct_color(self):
        self.assertEqual(ListPresenter.color_for({"priority": "alta"}), "red")
        self.assertEqual(ListPresenter.color_for({"priority": "media"}), "orange")
        self.assertEqual(ListPresenter.color_for({"priority": "baja"}), "white")

    def test_badge_for_high_priority(self):
        self.assertEqual(ListPresenter.badge_for({"priority": "alta"}), "ALTA")
        self.assertEqual(ListPresenter.badge_for({"priority": "media"}), "")

    def test_has_cross_new(self):
        self.assertTrue(ListPresenter.has_cross({"state": "new"}, "new"))
        self.assertFalse(ListPresenter.has_cross({"state": "other"}, "new"))

    def test_has_cross_delete(self):
        self.assertTrue(ListPresenter.has_cross({"state": "deleted"}, "delete"))
        self.assertFalse(ListPresenter.has_cross({"state": "new"}, "delete"))


class StopIdMutationTests(unittest.TestCase):
    def test_reindex_does_not_mutate_original_dicts(self):
        stops = [
            {"type": "notificacion", "id": "N5"},
            {"type": "paquete", "id": "P3"},
        ]
        original_ids = [s["id"] for s in stops]
        StopId.reindex(stops)
        # Original dicts must be unchanged
        self.assertEqual([s["id"] for s in stops], original_ids)

    def test_reindex_returns_new_dicts_with_correct_ids(self):
        StopId.reset()
        stops = [{"type": "notificacion", "id": "N9"}, {"type": "paquete", "id": "P7"}]
        result = StopId.reindex(stops)
        self.assertEqual([s["id"] for s in result], ["N1", "P1"])
        # Must be different objects
        self.assertIsNot(result[0], stops[0])
        self.assertIsNot(result[1], stops[1])
