import unittest

from scripts.check_release_routes import validate_routes


class ReleaseRouteTests(unittest.TestCase):
    def test_distinct_regions_are_accepted(self):
        routes = dict(zip(('DRIVER_GROUP_1', 'DRIVER_GROUP_2', 'BRAND_GROUP',
                           'TASHKENT_DRIVER_GROUP_1', 'TASHKENT_DRIVER_GROUP_2',
                           'TASHKENT_BRAND_GROUP', 'NAMANGAN_SPECTRE_GROUP',
                           'TASHKENT_SPECTRE_GROUP'),
                          ('-101', '-102', '-103', '-201', '', '-203', '-104', '-204')))
        self.assertEqual(validate_routes(routes), [])

    def test_test_bot_overlapping_destinations_are_blocked(self):
        routes = {'DRIVER_GROUP_1': '-101', 'BRAND_GROUP': '-103',
                  'TASHKENT_DRIVER_GROUP_1': '-101', 'TASHKENT_BRAND_GROUP': '-103',
                  'NAMANGAN_SPECTRE_GROUP': '-104', 'TASHKENT_SPECTRE_GROUP': '-104'}
        self.assertTrue(any('bitta guruhga' in issue for issue in validate_routes(routes)))

    def test_missing_region_never_passes(self):
        self.assertTrue(validate_routes({}))
