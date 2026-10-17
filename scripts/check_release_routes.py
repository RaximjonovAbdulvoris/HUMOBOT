"""Read-only production preflight; prints no tokens, secrets or group IDs."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.brand_sheets import configuration
from bot.route_settings import destination


def validate_routes(routes):
    errors = []
    required = ('DRIVER_GROUP_1', 'BRAND_GROUP', 'TASHKENT_DRIVER_GROUP_1',
                'TASHKENT_BRAND_GROUP', 'NAMANGAN_SPECTRE_GROUP',
                'TASHKENT_SPECTRE_GROUP', 'NAMANGAN_INCOMPLETE_GROUP',
                'NAMANGAN_OTHER_PARK_GROUP', 'TASHKENT_INCOMPLETE_GROUP',
                'TASHKENT_OTHER_PARK_GROUP', 'ARCHIVE_GROUP',
                'TASHKENT_ARCHIVE_GROUP')
    optional = ('DRIVER_GROUP_2', 'TASHKENT_DRIVER_GROUP_2')
    for key in required + optional:
        value = routes.get(key, '')
        if not value and key in optional:
            continue
        if not re.fullmatch(r'-[1-9][0-9]*', value):
            errors.append(f'{key}: haqiqiy guruh ID sozlanmagan')
    used = {}
    for key in required + optional:
        value = routes.get(key, '')
        if not value or not re.fullmatch(r'-[1-9][0-9]*', value):
            continue
        if value in used:
            errors.append(f'{used[value]} va {key}: bitta guruhga yo‘naltirilgan')
        else:
            used[value] = key
    return errors


def main():
    if os.environ.get('TELEGRAM_BOT_TOKEN', '').split(':')[0] == '8845908442':
        print('Bu test bot tokeni; asosiy bot sozlamasini alohida tekshiring.')
        return 1
    keys = ('DRIVER_GROUP_1', 'DRIVER_GROUP_2', 'BRAND_GROUP', 'ARCHIVE_GROUP')
    routes = {key: os.environ.get(key, '').strip() for key in keys}
    try:
        for key in ('TASHKENT_DRIVER_GROUP_1', 'TASHKENT_DRIVER_GROUP_2',
                    'TASHKENT_BRAND_GROUP', 'NAMANGAN_SPECTRE_GROUP',
                    'TASHKENT_SPECTRE_GROUP', 'NAMANGAN_INCOMPLETE_GROUP',
                    'NAMANGAN_OTHER_PARK_GROUP', 'TASHKENT_INCOMPLETE_GROUP',
                    'TASHKENT_OTHER_PARK_GROUP', 'TASHKENT_ARCHIVE_GROUP'):
            routes[key] = destination(key)
        errors = validate_routes(routes)
        if configuration() is None:
            errors.append('Google Sheets webhook yoki maxfiy kalit sozlanmagan')
    except (ValueError, OSError):
        errors = ['Guruh yoki Google Sheets sozlamasi noto‘g‘ri']
    for error in errors:
        print(error)
    if errors:
        return 1
    print('Asosiy bot hudud guruhlari alohida; Google Sheets ulanishi sozlangan.')
    print('Google ruxsatlari va haqiqiy yozuvni alohida test arizasi bilan tasdiqlang.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
