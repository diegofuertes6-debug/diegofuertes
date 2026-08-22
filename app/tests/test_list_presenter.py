import unittest

from app.ui.list_presenter import ListPresenter


class ListPresenterTests(unittest.TestCase):
    def test_letter_labels_use_c_prefix(self):
        self.assertEqual(ListPresenter.label_for({"type": "carta", "id": 1}), "C1")

    def test_package_labels_include_size_prefix(self):
        self.assertEqual(
            ListPresenter.label_for({"type": "paquete", "package_size": "Pequeño", "id": 1}),
            "Pp1",
        )
        self.assertEqual(
            ListPresenter.label_for({"type": "paquete", "package_size": "Mediano", "id": 2}),
            "Pm2",
        )
        self.assertEqual(
            ListPresenter.label_for({"type": "paquete", "package_size": "Grande", "id": 3}),
            "PG3",
        )

    def test_stops_without_priority_are_blue(self):
        self.assertEqual(ListPresenter.color_for({"priority": None}), "blue")
