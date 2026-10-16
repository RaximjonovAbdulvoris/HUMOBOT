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



def configuration():
    url = os.environ.get('BRAND_SHEETS_WEBHOOK_URL', '').strip()
    secret = os.environ.get('BRAND_SHEETS_SECRET', '').strip()
    if not url and not secret:
        return None
    if not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', url) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', secret):
        raise ValueError('Invalid Google Sheets export configuration')
    return url, secret


def region_key(region):
    aliases = {'tashkent': 'tashkent', 'namangan': 'namangan',
               'Toshkent shahri': 'tashkent', 'Namangan shahri': 'namangan'}
    if region not in aliases:
        raise ValueError('Unknown export region; no fallback destination')
    return aliases[region]


def normalize_payload(payload):
    if 'row' not in payload:
        return payload
    row = payload['row']
    return {'code': payload['code'], 'kind': 'brand', 'region': region_key(row[2]),
            'created_at': row[1], 'fields': dict(zip(
                ('name', 'phone', 'model', 'year', 'color', 'plate'), row[3:9]))}


def enqueue(context, data, user, code, region, kind='brand'):
    if kind not in ('brand', 'spectre'):
        raise ValueError('Unknown export kind')
    outbox = context.bot_data.setdefault('brand_sheets_outbox', {})
    outbox.setdefault(code, {'status': 'pending', 'payload': {
        'code': code, 'kind': kind, 'region': region_key(region),
        'created_at': datetime.now(ZoneInfo('Asia/Tashkent')).isoformat(timespec='seconds'),
        'fields': {target: str(data.get(source, '')) for target, source in (
            ('name', 'b_name'), ('phone', 'b_phone'), ('model', 'b_model'),
            ('year', 'b_year'), ('color', 'b_color'), ('plate', 'b_plate'))},
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
                    payload = normalize_payload(item['payload'])
                    await post_export(client, *config, payload)
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
                    continue
