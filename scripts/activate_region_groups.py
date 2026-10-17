"""Safely switch the test bot to fourteen distinct city destinations.

Read a JSON map from stdin. No bot tokens, document images or private
credentials are accepted in the map or printed by this script.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_release_routes import validate_routes
from scripts.run_test_bot import APPLICATION_KEYS, CITY_KEYS, STATE

ENVFILE = ROOT / '.env.test'
SERVICE = 'humobot-test'
ROUTE_KEYS = frozenset(APPLICATION_KEYS + CITY_KEYS)


def rewrite_env(original, routes):
    lines = [line for line in original.splitlines()
             if line.partition('=')[0].strip() not in ROUTE_KEYS | {'SEPARATE_REGION_GROUPS'}]
    return ('\n'.join(lines + [f'{key}={routes[key]}' for key in
                           APPLICATION_KEYS + CITY_KEYS] + ['SEPARATE_REGION_GROUPS=1']) + '\n').encode()


def replace_private(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.region-', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


async def check_memberships(token, routes):
    from telegram import Bot
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30)
    async with Bot(token, request=request) as bot:
        me = bot.bot
        if me.username.lower() != 'testthumo_bot':
            raise ValueError('Bu token testthumo_bot uchun emas.')
        for key in APPLICATION_KEYS + CITY_KEYS:
            try:
                member = await bot.get_chat_member(int(routes[key]), me.id)
            except Exception as error:
                raise ValueError(f'{key}: bot guruhga kira olmadi ({type(error).__name__}).') from None
            if member.status not in ('administrator', 'creator') or (
                    member.status != 'creator' and not member.can_delete_messages):
                raise ValueError(f'{key}: botga administrator va xabar o‘chirish huquqi bering.')


def activate(routes, *, check_online=True):
    if (not isinstance(routes, dict) or set(routes) != ROUTE_KEYS
            or any(not isinstance(value, str) for value in routes.values())):
        raise ValueError('Aynan 14 ta guruh kaliti va matnli ID kerak.')
    problems = validate_routes(routes)
    if problems:
        raise ValueError('; '.join(problems))
    original = ENVFILE.read_bytes()
    lines = original.decode().splitlines()
    token = next((line.split('=', 1)[1].strip().strip('"\'') for line in lines
                  if line.startswith('TELEGRAM_BOT_TOKEN=')), '')
    if token.split(':')[0] != '8845908442':
        raise ValueError('Test bot tokeni topilmadi; sozlamalar o‘zgartirilmadi.')
    if check_online:
        asyncio.run(asyncio.wait_for(check_memberships(token, routes), timeout=90))

    state_file = STATE / 'bot_routes.json'
    old_state = state_file.read_bytes() if state_file.exists() else None
    subprocess.run(['systemctl', 'stop', SERVICE], check=True)
    try:
        replace_private(ENVFILE, rewrite_env(original.decode(), routes))
        check = subprocess.run([sys.executable, str(ROOT / 'scripts/run_test_bot.py'), '--check'],
                               cwd=ROOT, timeout=120, check=False)
        if check.returncode:
            raise RuntimeError('Test bot tekshiruvi o‘tmadi.')
        subprocess.run(['systemctl', 'start', SERVICE], check=True)
        subprocess.run(['systemctl', 'is-active', '--quiet', SERVICE], check=True)
    except Exception:
        replace_private(ENVFILE, original)
        if old_state is None:
            state_file.unlink(missing_ok=True)
        else:
            replace_private(state_file, old_state)
        subprocess.run(['systemctl', 'restart', SERVICE], check=False)
        raise
    print('Test botning Toshkent va Namangan guruhlari alohida sozlandi; xizmat active.')


def main():
    try:
        routes = json.load(sys.stdin)
        activate(routes)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError,
            json.JSONDecodeError, asyncio.TimeoutError) as error:
        # Do not print arbitrary Telegram exception strings containing a token.
        message = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
        print('Guruhlar yoqilmadi: ' + message, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
