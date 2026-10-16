import hashlib
import hmac
import json
import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
import httpx
from bot import brand_sheets as sheets

URL = 'https://script.google.com/macros/s/testdeployment/exec'
SECRET = 'synthetic-test-secret-not-real-123456'


class BrandSheetsTests(unittest.IsolatedAsyncioTestCase):
    def context(self):
        return N(bot_data={}, application=None)

    def enqueue(self, ctx):
        sheets.enqueue(ctx, {'b_name': '=1+1', 'b_phone': '+998000000000',
            'b_model': 'TEST', 'b_year': '2020', 'b_color': 'Oq', 'b_plate': '01A123BC'},
            N(username='test', id=123), 'HM-000001', 'Toshkent')

    def test_signature_covers_timestamp_and_payload(self):
        body = sheets.signed({'code': 'HM-000001', 'row': ['example']}, SECRET, 1700000000)
        expected = hmac.new(SECRET.encode(),
            f"{body['timestamp']}.{body['payload']}".encode(), hashlib.sha256).hexdigest()
        self.assertEqual(body['signature'], expected)
        self.assertNotIn(SECRET, json.dumps(body))

    def test_enqueue_is_idempotent_and_minimal(self):
        ctx = self.context()
        self.enqueue(ctx)
        self.enqueue(ctx)
        self.assertEqual(len(ctx.bot_data['brand_sheets_outbox']), 1)
        item = ctx.bot_data['brand_sheets_outbox']['HM-000001']
        self.assertEqual(len(item['payload']['row']), len(sheets.HEADERS))
        self.assertNotIn('passport', json.dumps(item))

    def test_endpoint_must_be_google_apps_script(self):
        for url in ('http://script.google.com/macros/s/test/exec', 'https://example.com',
                    'https://script.google.com.evil.example/macros/s/test/exec'):
            with patch.dict(os.environ, {'BRAND_SHEETS_WEBHOOK_URL': url, 'BRAND_SHEETS_SECRET': SECRET}):
                with self.assertRaises(ValueError):
                    sheets.configuration()

    async def test_redirect_fetch_does_not_forward_applicant_payload(self):
        seen = []
        def respond(request):
            seen.append(request)
            if len(seen) == 1:
                return httpx.Response(302, headers={'location': 'https://script.googleusercontent.com/macros/result'})
            self.assertEqual(request.method, 'GET')
            self.assertEqual(request.content, b'')
            self.assertNotIn('authorization', request.headers)
            return httpx.Response(200, json={'ok': True, 'code': 'HM-000001'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond), follow_redirects=False) as client:
            await sheets.post_export(client, URL, SECRET, {'code': 'HM-000001'})
        self.assertEqual(len(seen), 2)

    async def test_untrusted_redirect_rejected(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(302, headers={'location': 'https://example.com'}))) as client:
            with self.assertRaises(ValueError):
                await sheets.post_export(client, URL, SECRET, {'code': 'HM-000001'})

    async def test_wrong_code_response_not_acknowledged(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, json={'ok': True, 'code': 'HM-000002'}))) as client:
            with self.assertRaises(ValueError):
                await sheets.post_export(client, URL, SECRET, {'code': 'HM-000001'})

    async def test_failure_stays_pending_then_retry_removes_private_payload(self):
        ctx = self.context()
        self.enqueue(ctx)
        with patch.object(sheets, 'configuration', return_value=(URL, SECRET)), \
             patch.object(sheets, 'post_export', AsyncMock(side_effect=RuntimeError('sensitive-body'))):
            with self.assertLogs(sheets.logger, 'WARNING') as logs:
                await sheets.flush(ctx)
        self.assertNotIn('sensitive-body', '\n'.join(logs.output))
        item = ctx.bot_data['brand_sheets_outbox']['HM-000001']
        self.assertEqual(item['status'], 'pending')
        with patch.object(sheets, 'configuration', return_value=(URL, SECRET)), \
             patch.object(sheets, 'post_export', AsyncMock()):
            await sheets.flush(ctx)
        self.assertEqual(item, {'status': 'sent'})

    async def test_unconfigured_export_does_not_send(self):
        ctx = self.context()
        self.enqueue(ctx)
        with patch.object(sheets, 'configuration', return_value=None), \
             patch.object(sheets, 'post_export', AsyncMock()) as send:
            await sheets.flush(ctx)
        send.assert_not_awaited()
