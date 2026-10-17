import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.check_release_routes import validate_routes
from scripts import run_test_bot
from scripts.run_test_bot import group_routes


class ReleaseRouteTests(unittest.TestCase):
    def test_shared_test_defaults_are_unchanged_until_explicitly_separated(self):
        routes = group_routes({})
        self.assertEqual(routes['DRIVER_GROUP_1'], routes['TASHKENT_DRIVER_GROUP_1'])
        self.assertEqual(routes['BRAND_GROUP'], routes['TASHKENT_BRAND_GROUP'])

    def test_separate_mode_requires_every_application_and_review_destination(self):
        with self.assertRaises(ValueError):
            group_routes({'SEPARATE_REGION_GROUPS': '1'})
        values = dict(zip(('DRIVER_GROUP_1', 'DRIVER_GROUP_2', 'BRAND_GROUP',
                           'TASHKENT_DRIVER_GROUP_1', 'TASHKENT_DRIVER_GROUP_2',
                           'TASHKENT_BRAND_GROUP', 'NAMANGAN_SPECTRE_GROUP',
                           'TASHKENT_SPECTRE_GROUP', 'NAMANGAN_INCOMPLETE_GROUP',
                           'NAMANGAN_OTHER_PARK_GROUP', 'TASHKENT_INCOMPLETE_GROUP',
                           'TASHKENT_OTHER_PARK_GROUP', 'ARCHIVE_GROUP',
                           'TASHKENT_ARCHIVE_GROUP'),
                          ('-101', '-102', '-103', '-201', '-202', '-203', '-104', '-204',
                           '-105', '-106', '-205', '-206', '-107', '-207')))
        values['SEPARATE_REGION_GROUPS'] = '1'
        self.assertEqual(group_routes(values)['TASHKENT_ARCHIVE_GROUP'], '-207')
        values['TASHKENT_BRAND_GROUP'] = '-103'
        with self.assertRaises(ValueError):
            group_routes(values)

    def test_distinct_regions_are_accepted(self):
        routes = dict(zip(('DRIVER_GROUP_1', 'DRIVER_GROUP_2', 'BRAND_GROUP',
                           'TASHKENT_DRIVER_GROUP_1', 'TASHKENT_DRIVER_GROUP_2',
                           'TASHKENT_BRAND_GROUP', 'NAMANGAN_SPECTRE_GROUP',
                           'TASHKENT_SPECTRE_GROUP', 'NAMANGAN_INCOMPLETE_GROUP',
                           'NAMANGAN_OTHER_PARK_GROUP', 'TASHKENT_INCOMPLETE_GROUP',
                           'TASHKENT_OTHER_PARK_GROUP', 'ARCHIVE_GROUP',
                           'TASHKENT_ARCHIVE_GROUP'),
                          ('-101', '-102', '-103', '-201', '-202', '-203', '-104', '-204',
                           '-105', '-106', '-205', '-206', '-107', '-207')))
        self.assertEqual(validate_routes(routes), [])
        routes['TASHKENT_DRIVER_GROUP_2'] = ''
        self.assertTrue(any('TASHKENT_DRIVER_GROUP_2' in issue for issue in validate_routes(routes)))

    def test_test_bot_overlapping_destinations_are_blocked(self):
        routes = {'DRIVER_GROUP_1': '-101', 'BRAND_GROUP': '-103',
                  'TASHKENT_DRIVER_GROUP_1': '-101', 'TASHKENT_BRAND_GROUP': '-103',
                  'NAMANGAN_SPECTRE_GROUP': '-104', 'TASHKENT_SPECTRE_GROUP': '-104'}
        self.assertTrue(any('bitta guruhga' in issue for issue in validate_routes(routes)))

    def test_missing_region_never_passes(self):
        self.assertTrue(validate_routes({}))

    def test_shared_mode_writes_only_valid_route_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.env.test').write_text('TELEGRAM_BOT_TOKEN=8845908442:test\n')
            with patch.object(run_test_bot, 'ROOT', root), \
                 patch.object(run_test_bot, 'STATE', root / 'state'), \
                 patch.dict(os.environ, {}, clear=True):
                run_test_bot.configure()
                from bot.route_settings import read_settings
                settings = read_settings()
                self.assertNotIn('TASHKENT_ARCHIVE_GROUP', settings)
                self.assertNotIn('NAMANGAN_INCOMPLETE_GROUP', settings)
