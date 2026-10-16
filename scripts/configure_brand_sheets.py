"""Save Apps Script settings privately on the test VPS; never echo the secret."""
from getpass import getpass
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.brand_sheets import configuration


def main():
    path = ROOT / '.env.test'
    if not path.is_file() or path.is_symlink():
        raise SystemExit('Existing regular .env.test file required.')
    url = input('Google Apps Script /exec URL: ').strip()
    secret = getpass('Script properties dagi HUMO_SECRET: ').strip()
    os.environ.update(BRAND_SHEETS_WEBHOOK_URL=url, BRAND_SHEETS_SECRET=secret)
    configuration()
    keys = {'BRAND_SHEETS_WEBHOOK_URL', 'BRAND_SHEETS_SECRET'}
    lines = [line for line in path.read_text().splitlines() if line.split('=', 1)[0].strip() not in keys]
    lines += ['BRAND_SHEETS_WEBHOOK_URL=' + url, 'BRAND_SHEETS_SECRET=' + secret]
    fd, temporary = tempfile.mkstemp(prefix='.env-sheets-', dir=ROOT)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(lines) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Settings saved privately. Restart humobot-test when ready.')


if __name__ == '__main__':
    main()
