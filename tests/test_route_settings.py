import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from bot.configure import main
from bot.route_settings import (
    NAMANGAN_KEYS, TASHKENT_KEYS, destination, read_settings, settings_path,
)


class RouteSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"PERSIST_DIR": self.directory.name}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.directory.cleanup)

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return main(list(args))

    def configure(self):
        return self.run_cli(
            "tashkent", "--driver1=-101", "--driver2=-102", "--brand=-103",
            "--spectre=-104", "--archive=-105",
        )

    def test_configure_without_token_and_read_all_destinations(self):
        self.assertEqual(self.configure(), 0)
        self.assertEqual(len(read_settings()), 5)
        self.assertEqual(destination(TASHKENT_KEYS["spectre"]), "-104")
        self.assertEqual(self.run_cli("show"), 0)

    def test_local_values_override_existing_environment(self):
        self.assertEqual(self.configure(), 0)
        with patch.dict(os.environ, {"TASHKENT_BRAND_GROUP": "-999"}):
            self.assertEqual(destination("TASHKENT_BRAND_GROUP"), "-103")

    def test_noninteractive_namangan_spectre_preserves_tashkent_settings(self):
        self.assertEqual(self.configure(), 0)
        self.assertEqual(self.run_cli("namangan", "--spectre=-106"), 0)
        self.assertEqual(destination(NAMANGAN_KEYS["spectre"]), "-106")
        self.assertEqual(destination(TASHKENT_KEYS["brand"]), "-103")
        self.assertEqual(len(read_settings()), 6)

    def test_interactive_namangan_prompts_only_for_spectre(self):
        with patch("builtins.input", side_effect=["-106"]) as prompt:
            self.assertEqual(self.run_cli("namangan"), 0)
        prompt.assert_called_once()
        self.assertEqual(destination("NAMANGAN_SPECTRE_GROUP"), "-106")

    def test_tashkent_configuration_does_not_require_namangan_spectre(self):
        self.assertEqual(self.configure(), 0)
        self.assertNotIn(NAMANGAN_KEYS["spectre"], read_settings())
        self.assertEqual(self.run_cli("check"), 1)
        self.assertNotIn(
            "NAMANGAN_SPECTRE_GROUP", settings_path().read_text(encoding="utf-8")
        )

    def test_scoped_namangan_check_fails_cleanly_when_missing(self):
        self.assertEqual(self.run_cli("check", "--scope", "namangan"), 1)

    def test_update_keeps_other_fields_and_optional_driver_can_be_disabled(self):
        self.configure()
        self.assertEqual(self.run_cli("tashkent", "--brand=-200", "--driver2=none"), 0)
        self.assertEqual(destination("TASHKENT_BRAND_GROUP"), "-200")
        self.assertEqual(destination("TASHKENT_ARCHIVE_GROUP"), "-105")
        with patch.dict(os.environ, {"TASHKENT_DRIVER_GROUP_2": "-999"}):
            self.assertEqual(destination("TASHKENT_DRIVER_GROUP_2"), "")

    def test_invalid_or_incomplete_config_does_not_write(self):
        self.assertEqual(self.run_cli("tashkent", "--brand=-200"), 1)
        self.assertFalse(settings_path().exists())
        self.configure()
        before = settings_path().read_bytes()
        self.assertEqual(self.run_cli("tashkent", "--brand=abc"), 1)
        self.assertEqual(settings_path().read_bytes(), before)

    def test_interactive_setup_and_edit(self):
        with patch("builtins.input", side_effect=["-101", "-102", "-103", "-104", "-105"]):
            self.assertEqual(self.run_cli("tashkent"), 0)
        with patch("builtins.input", side_effect=["", "", "-222", "", ""]):
            self.assertEqual(self.run_cli("tashkent"), 0)
        self.assertEqual(destination("TASHKENT_BRAND_GROUP"), "-222")

    def test_missing_file_uses_environment_but_broken_file_fails_explicitly(self):
        with patch.dict(os.environ, {"TASHKENT_BRAND_GROUP": "-100"}):
            self.assertEqual(destination("TASHKENT_BRAND_GROUP"), "-100")
            settings_path().write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                destination("TASHKENT_BRAND_GROUP")

    def test_json_cannot_store_token_or_unknown_keys(self):
        settings_path().write_text('{"TELEGRAM_BOT_TOKEN": "not-a-token"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_settings()

    def test_check_without_configuration_or_token_fails_cleanly(self):
        self.assertEqual(self.run_cli("check"), 1)
        self.configure()
        self.assertEqual(self.run_cli("check"), 1)