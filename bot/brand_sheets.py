"""Durable, signed, idempotent brand exports. No document images enter Sheets."""
import asyncio
import base64
from datetime import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import time
from weakref import WeakKeyDictionary
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)
_LOCKS = WeakKeyDictionary()
HEADERS = ('Ariza kodi', 'Sana', 'Hudud', 'F.I.Sh.', 'Telefon', 'Model', 'Yili',
           'Rangi', 'Davlat raqami', 'Telegram username', 'Telegram ID')


def configuration():
    url = os.environ.get('BRAND_SHEETS_WEBHOOK_URL', '').strip()
    secret = os.environ.get('BRAND_SHEETS_SECRET', '').strip()
    if not url and not secret:
        return None
    if not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url) or len(secret) < 32:
        raise ValueError('Invalid Google Sheets export configuration')
    return url, secret


def enqueue(context, data, user, code, region):
    outbox = context.bot_data.setdefault('brand_sheets_outbox', {})
    outbox.setdefault(code, {'status': 'pending', 'payload': {
        'code': code,
        'row': [code, datetime.now(ZoneInfo('Asia/Tashkent')).isoformat(timespec='seconds'),
                region, str(data.get('b_name', '')), str(data.get('b_phone', '')),
                str(data.get('b_model', '')), str(data.get('b_year', '')),
                str(data.get('b_color', '')), str(data.get('b_plate', '')),
                str(user.username or ''), str(user.id)],
    }})


def signed(payload, secret, timestamp=None):
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False,
        separators=(',', ':')).encode()).decode('ascii')
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = hmac.new(secret.encode(), f'{timestamp}.{encoded}'.encode(), hashlib.sha256).hexdigest()
    return {'timestamp': timestamp, 'payload': encoded, 'signature': signature}


async def post_export(client, url, secret, payload):
    response = await client.post(url, json=signed(payload, secret))
    # Google ContentService redirects only its result. Never resend applicant
    # data/signatures to the redirect target or forward any credentials.
    if response.status_code in (302, 303):
        target = httpx.URL(response.headers['location'])
        if target.scheme != 'https' or target.host != 'script.googleusercontent.com' or target.userinfo:
            raise ValueError('Untrusted Sheets result redirect')
        response = await client.get(str(target))
    response.raise_for_status()
    result = response.json()
    if result.get('ok') is not True or result.get('code') != payload['code']:
        raise ValueError('Sheets export not acknowledged')


async def flush(context):
    try:
        config = configuration()
    except ValueError:
        logger.warning('Brand Sheets configuration needs attention')
        return
    if config is None:
        return
    lock = _LOCKS.setdefault(asyncio.get_running_loop(), asyncio.Lock())
    if lock.locked():
        return
    async with lock:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
            for code, item in list(context.bot_data.get('brand_sheets_outbox', {}).items()):
                if item.get('status') != 'pending':
                    continue
                try:
                    await post_export(client, *config, item['payload'])
                    item['status'] = 'sent'
                    item.pop('payload', None)
                    application = getattr(context, 'application', None)
                    if application is not None and application.persistence is not None:
                        await application.update_persistence()
                        await application.persistence.flush()
                except Exception as error:
                    # The durable item remains pending; retrying the same code
                    # cannot duplicate a row when using the supplied receiver.
                    logger.warning('Brand Sheets export pending (%s)', type(error).__name__)
                    break
