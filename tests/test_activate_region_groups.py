import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import activate_region_groups as activation


class RegionActivationTests(unittest.TestCase):
    def routes(self):
        return {key: f'-{1000 + index}' for index, key in
                enumerate(activation.APPLICATION_KEYS + activation.CITY_KEYS)}

    def test_rewrite_keeps_credentials_and_replaces_old_routes(self):
        old = 'TELEGRAM_BOT_TOKEN=8845908442:example\nBRAND_SHEETS_SECRET=private\nDRIVER_GROUP_1=-42\nSEPARATE_REGION_GROUPS=0\n'
        rendered = activation.rewrite_env(old, self.routes()).decode()
        self.assertIn('BRAND_SHEETS_SECRET=private\n', rendered)
        self.assertIn('SEPARATE_REGION_GROUPS=1\n', rendered)
        self.assertNotIn('DRIVER_GROUP_1=-42\n', rendered)
        self.assertEqual(rendered.count('DRIVER_GROUP_1='), 2)  # Namangan and Toshkent

    def test_failed_preflight_restores_both_files_and_starts_old_bot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = root / 'state'
            state.mkdir()
            env = root / '.env.test'
            old = b'TELEGRAM_BOT_TOKEN=8845908442:example\nBRAND_SHEETS_SECRET=private\n'
            env.write_bytes(old)
            routes = state / 'bot_routes.json'
            routes.write_bytes(b'{"old":true}')
            def invoke(args, **kwargs):
                if '--check' in args:
                    return subprocess.CompletedProcess(args, 1)
                return subprocess.CompletedProcess(args, 0)
            with patch.object(activation, 'ROOT', root), patch.object(activation, 'ENVFILE', env), \
                 patch.object(activation, 'STATE', state), patch.object(activation.subprocess, 'run', side_effect=invoke) as run:
                with self.assertRaises(RuntimeError):
                    activation.activate(self.routes(), check_online=False)
            self.assertEqual(env.read_bytes(), old)
            self.assertEqual(routes.read_bytes(), b'{"old":true}')
            self.assertIn(['systemctl', 'restart', activation.SERVICE],
                          [call.args[0] for call in run.call_args_list])

    def test_incomplete_routes_do_not_stop_bot(self):
        with patch.object(activation.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                activation.activate({}, check_online=False)
        run.assert_not_called()
