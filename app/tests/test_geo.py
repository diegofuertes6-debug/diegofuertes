import unittest

from app.services.geo import coords_valid, haversine_km


class GeoTests(unittest.TestCase):
    def test_haversine_same_point_is_zero(self):
        self.assertAlmostEqual(haversine_km(40.0, -3.0, 40.0, -3.0), 0.0, places=6)

    def test_haversine_known_distance(self):
        # Madrid (40.4168, -3.7038) -> Barcelona (41.3851, 2.1734) ≈ 504 km
        d = haversine_km(40.4168, -3.7038, 41.3851, 2.1734)
        self.assertAlmostEqual(d, 504.0, delta=5.0)

    def test_coords_valid_accepts_valid(self):
        self.assertTrue(coords_valid(40.0, -3.0))
        self.assertTrue(coords_valid(0.0, 0.0))
        self.assertTrue(coords_valid(-90.0, -180.0))
        self.assertTrue(coords_valid(90.0, 180.0))

    def test_coords_valid_rejects_out_of_range(self):
        self.assertFalse(coords_valid(91.0, 0.0))
        self.assertFalse(coords_valid(-91.0, 0.0))
        self.assertFalse(coords_valid(0.0, 181.0))
        self.assertFalse(coords_valid(0.0, -181.0))

    def test_coords_valid_rejects_non_numeric(self):
        self.assertFalse(coords_valid("40", 0.0))
        self.assertFalse(coords_valid(None, 0.0))

    def test_coords_valid_rejects_booleans(self):
        self.assertFalse(coords_valid(True, 0.0))
        self.assertFalse(coords_valid(0.0, False))

    def test_coords_valid_rejects_inf_and_nan(self):
        import math
        self.assertFalse(coords_valid(math.inf, 0.0))
        self.assertFalse(coords_valid(math.nan, 0.0))
