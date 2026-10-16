import asyncio
import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
from bot import neural_ocr as neural
from bot import document_ocr as ocr
from bot.fast_ocr import Word
from bot.neural_ocr_worker import fields_from_rows


def row(text, x=300, y=300, confidence=99, width=200, height=30):
    return Word(text, confidence, x, y, width, height)


class NeuralOCRTests(unittest.IsolatedAsyncioTestCase):
    def test_numbered_lines_without_spaces_and_expiry_anchor(self):
        values = fields_from_rows([row('4d12345678901234'), row('5.AB1234567'),
            row('4a.01.02.2020', y=200, width=150), row('4401.02.2030', x=500, y=200)],
            'license_front', 960, 1280)
        self.assertEqual(values['pinfl'], '12345678901234')
        self.assertEqual(values['license_number'], 'AB1234567')
        self.assertEqual(values['license_expiry'], '01.02.2030')
        self.assertIsNone(values['birth_date'])

    def test_address_and_wrong_baseline_are_not_birth_or_expiry(self):
        values = fields_from_rows([row('8.OTHER CITY'), row('4a.01.02.2020', y=200),
            row('01.02.2030', x=600, y=500)], 'license_front', 960, 1280)
        self.assertIsNone(values['birth_place'])
        self.assertIsNone(values['license_expiry'])

    def test_serial_excludes_control_number_outside_right_edge(self):
        values = fields_from_rows([row('VL1234567', x=550, y=600),
            row('ABC1234567', x=700, y=630), row('ABC7654321', x=400, y=1040)],
            'tech_back', 960, 1280)
        self.assertEqual(values['vehicle_registration'], 'ABC1234567')

    def test_conflicts_low_confidence_and_uncertain_digits_remain_blank(self):
        for rows in [[row('5.AB1234567'), row('5.AB1234568')],
                     [row('5.AB1234567', confidence=70)], [row('5.AB12345O7')]]:
            self.assertIsNone(fields_from_rows(rows, 'license_front', 960, 1280)['license_number'])

    async def test_dispatch_never_contacts_external_or_ollama(self):
        with patch.dict(os.environ, {'DOCUMENT_AI_ENABLED': '1', 'DOCUMENT_OCR_BACKEND': 'rapid'}), \
             patch.object(neural, 'extract_documents', AsyncMock(return_value={'backend': 'rapid'})), \
             patch.object(ocr, 'local_client') as client:
            self.assertEqual((await ocr.extract_documents(N(), {}))['backend'], 'rapid')
        client.assert_not_called()

    async def test_partial_worker_output_survives_and_other_images_are_marked_failed(self):
        file = N(file_size=4, download_as_bytearray=AsyncMock(return_value=b'data'))
        bot = N(get_file=AsyncMock(return_value=file))
        with patch.object(neural, 'worker', AsyncMock(return_value=[{
            'source': 'license_front', 'values': {'pinfl': '12345678901234'}}])):
            result = await neural.extract_documents(bot, {'license_front': 'one', 'tech_back': 'two', 'selfie': 'excluded'})
        self.assertEqual(result['values']['pinfl'], '12345678901234')
        self.assertEqual(result['failed_sources'], ['tech_back'])
        self.assertEqual(bot.get_file.await_count, 2)

    async def test_worker_timeout_kills_child_and_keeps_emitted_result(self):
        stdout = N(readline=AsyncMock(side_effect=[b'{"source":"license_front","values":{}}\n']))
        process = N(returncode=None, stdin=N(write=lambda _: None, drain=AsyncMock(), close=lambda: None),
            stdout=stdout, wait=AsyncMock(), kill=lambda: setattr(process, 'returncode', -9))
        async def timeout_after_one(awaitable, timeout):
            task = asyncio.create_task(awaitable)
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise asyncio.TimeoutError
        with patch.object(asyncio, 'create_subprocess_exec', AsyncMock(return_value=process)) as spawn, \
             patch.object(asyncio, 'wait_for', side_effect=timeout_after_one), \
             patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'do-not-inherit'}):
            result = await neural._worker([])
        self.assertEqual(len(result), 1)
        self.assertEqual(process.returncode, -9)
        self.assertNotIn('TELEGRAM_BOT_TOKEN', spawn.call_args.kwargs['env'])
