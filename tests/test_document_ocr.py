import json
import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
import httpx
from bot import document_ocr as ocr

class DocumentOCRTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def image_bytes():
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (300, 200), "white").save(buf, format="JPEG")
        return buf.getvalue()

    def test_validates_digits_dates_and_unknown_values(self):
        values=ocr.normalize({'pinfl':'1234 5678901234','birth_date':'31.02.2000',
              'license_expiry':'01.12.2030','birth_place':None,'license_number':12345})
        self.assertEqual(values['pinfl'],'12345678901234')
        self.assertIsNone(values['birth_date'])
        self.assertIsNone(values['license_number'])
        self.assertEqual(values['license_expiry'],'01.12.2030')

    def test_html_escaping_and_copyable_values(self):
        text=ocr.format_summary({'status':'partial','values':{'birth_place':'A < B & C'}})
        self.assertIn('<code>A &lt; B &amp; C</code>',text)
        self.assertIn('Aniqlanmadi',text)
        self.assertIn('asl hujjat',text)

    async def test_missing_key_does_not_download_photos(self):
        bot=N(get_file=AsyncMock())
        with patch.dict(os.environ,{'CODECRAFT_API_KEY':''}):
            result=await ocr.extract_documents(bot,{'passport_front':'file'})
        bot.get_file.assert_not_awaited()
        self.assertEqual(result['status'],'unavailable')

    async def test_conflicting_readings_are_not_guessed(self):
        bot=N()
        with patch('bot.document_ocr.httpx.AsyncClient', return_value=AsyncMock()), patch.dict(os.environ,{'CODECRAFT_API_KEY':'test-only'}), patch.object(
            ocr,'extract_one',AsyncMock(side_effect=[{'pinfl':'12345678901234'},
                                                   {'pinfl':'12345678901235'}])):
            result=await ocr.extract_documents(bot,{'passport_front':'a','passport_back':'b'})
        self.assertIsNone(result['values']['pinfl'])

    async def test_provider_failure_does_not_discard_other_fields(self):
        with patch('bot.document_ocr.httpx.AsyncClient', return_value=AsyncMock()), patch.dict(os.environ,{'CODECRAFT_API_KEY':'test-only'}), patch.object(
            ocr,'extract_one',AsyncMock(side_effect=[RuntimeError('no response'),
                                       {'vehicle_registration':'ABC1234567'}])):
            result=await ocr.extract_documents(N(),{'passport_front':'a','tech_front':'b'})
        self.assertEqual(result['values']['vehicle_registration'],'ABC1234567')
        self.assertEqual(result['failed_sources'],['passport_front'])

    async def test_result_is_cached_for_submission_retries(self):
        ctx=N(bot=N(),user_data={})
        extractor=AsyncMock(return_value={'status':'partial','values':{'pinfl':'12345678901234'}})
        with patch.object(ocr,'extract_documents',extractor):
            first=await ocr.prepare_document_summary(ctx)
            second=await ocr.prepare_document_summary(ctx)
        self.assertEqual(first,second)
        extractor.assert_awaited_once()

    async def test_vision_request_uses_bytes_not_telegram_token_url(self):
        import asyncio
        def respond(request):
            self.assertEqual(str(request.url),'https://codecraftapi.com/v1/chat/completions')
            body=json.loads(request.content)
            image=body['messages'][1]['content'][1]['image_url']['url']
            self.assertTrue(image.startswith('data:image/jpeg;base64,'))
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop',
                 'message':{'content':json.dumps({'pinfl':'12345678901234','vehicle_registration':'wrong source'})}}]})
        bot=N(get_file=AsyncMock(return_value=N(file_size=3,download_as_bytearray=AsyncMock(return_value=self.image_bytes()))))
        async with httpx.AsyncClient(base_url='https://codecraftapi.com',transport=httpx.MockTransport(respond)) as client:
            result=await ocr.extract_one(client,bot,'passport_front','file',asyncio.Semaphore(1),'vision-test')
        self.assertEqual(result['pinfl'],'12345678901234')
        self.assertNotIn('vehicle_registration',result)

    async def test_overlarge_document_rejected_before_download(self):
        import asyncio
        file=N(file_size=5_000_001,download_as_bytearray=AsyncMock())
        with self.assertRaises(ValueError):
            await ocr.extract_one(N(),N(get_file=AsyncMock(return_value=file)),
                                   'passport_front','file',asyncio.Semaphore(1),'model')
        file.download_as_bytearray.assert_not_awaited()

    async def test_missing_fields_reviewed_from_crops(self):
        import asyncio
        requests = []
        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            fields = {'pinfl': '12345678901234'} if len(requests) == 1 else {
                'birth_date': '01.02.1990', 'birth_place': 'TOSHKENT'}
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(fields)}}]})
        bot = N(get_file=AsyncMock(return_value=N(file_size=100,
            download_as_bytearray=AsyncMock(return_value=self.image_bytes()))))
        async with httpx.AsyncClient(base_url='https://codecraftapi.com',
                transport=httpx.MockTransport(respond)) as client:
            result = await ocr.extract_one(client, bot, 'passport_front', 'file',
                                          asyncio.Semaphore(1), 'vision-test')
        self.assertEqual(result['birth_place'], 'TOSHKENT')
        self.assertEqual(result['pinfl'], '12345678901234')
        self.assertEqual(len(requests[1]['messages'][1]['content']), 3)

    async def test_ai_disabled_sends_nothing(self):
        bot = N(get_file=AsyncMock())
        with patch.dict(os.environ, {'CODECRAFT_API_KEY': 'test-only', 'DOCUMENT_AI_ENABLED': '0'}):
            await ocr.extract_documents(bot, {'passport_front': 'file'})
        bot.get_file.assert_not_awaited()
