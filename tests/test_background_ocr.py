import asyncio
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch
from bot import background_ocr as bg


class BackgroundOCRTests(unittest.IsolatedAsyncioTestCase):
    def app(self):
        record = dict(code='HM-000001', applicant_id=9, kind='driver', group_chat_id=-2001,
            kb_msg_id=100, ocr_status='pending', ocr_input={'passport_front': 'file'},
            ocr_prefix='PREFIX\n', ocr_suffix='\nSUFFIX', archive_state={})
        key = (-2001, 100)
        app = N(bot_data={'applications': {key: record}}, persistence=None,
            bot=N(edit_message_text=AsyncMock(), send_message=AsyncMock()))
        return app, key, record

    async def test_existing_card_enriched_with_current_progress(self):
        app, key, record = self.app()
        app.bot_data['progress_state'] = {key: True}
        with patch.object(bg, 'extract_documents', AsyncMock(return_value={
                'status': 'partial', 'values': {'pinfl': '12345678901234'}})):
            await bg.enrich(app, record['code'], 9)
        args = app.bot.edit_message_text.await_args.kwargs
        self.assertEqual(args['chat_id'], -2001)
        self.assertIn('12345678901234', args['text'])
        self.assertTrue(any('🟡' in button.text for row in args['reply_markup'].inline_keyboard for button in row))
        self.assertEqual(record['ocr_status'], 'complete')
        self.assertNotIn('ocr_input', record)
        app.bot.send_message.assert_not_awaited()

    async def test_deleted_application_never_recreated(self):
        app, key, record = self.app()
        async def extract(*args):
            app.bot_data['applications'].clear()
            return {'status': 'partial', 'values': {}}
        with patch.object(bg, 'extract_documents', side_effect=extract):
            await bg.enrich(app, record['code'], 9)
        app.bot.edit_message_text.assert_not_awaited()
        app.bot.send_message.assert_not_awaited()

    async def test_move_follows_destination_and_preserves_review_buttons(self):
        app, key, record = self.app()
        child = dict(record, group_chat_id=-2002, kb_msg_id=200, queue_kind='incomplete')
        async def extract(*args):
            record['_transfer'] = {'destination_key': (-2002, 200)}
            app.bot_data['applications'][(-2002, 200)] = child
            return {'status': 'partial', 'values': {}}
        with patch.object(bg, 'extract_documents', side_effect=extract):
            await bg.enrich(app, record['code'], 9)
        args = app.bot.edit_message_text.await_args.kwargs
        self.assertEqual((args['chat_id'], args['message_id']), (-2002, 200))
        self.assertEqual(sum(len(row) for row in args['reply_markup'].inline_keyboard), 3)
        self.assertEqual(child['ocr_status'], 'complete')

    async def test_archive_in_progress_not_overwritten(self):
        app, key, record = self.app()
        record['archive_state'] = {'kb': True}
        with patch.object(bg, 'extract_documents', AsyncMock(return_value={'values': {}})):
            await bg.enrich(app, record['code'], 9)
        app.bot.edit_message_text.assert_not_awaited()

    async def test_action_lock_prevents_stale_edit(self):
        app, key, record = self.app()
        lock = bg.control_lock(*key)
        await lock.acquire()
        with patch.object(bg, 'extract_documents', AsyncMock(return_value={'values': {}})):
            task = asyncio.create_task(bg.enrich(app, record['code'], 9))
            await asyncio.sleep(.01)
            app.bot.edit_message_text.assert_not_awaited()
            app.bot_data['applications'].clear()
            lock.release()
            await task
        app.bot.edit_message_text.assert_not_awaited()

    async def test_persisted_pending_records_resume_once(self):
        app, key, record = self.app()
        app.bot_data['applications'][(-2002, 200)] = dict(record)
        with patch.object(bg, 'schedule_ocr') as schedule:
            await bg.resume_pending(N(application=app))
        schedule.assert_called_once_with(app, record['code'], 9)

    async def test_inference_uses_application_snapshot(self):
        app, key, record = self.app()
        with patch.object(bg, 'extract_documents', AsyncMock(return_value={'values': {}})) as extract:
            await bg.enrich(app, record['code'], 9)
        self.assertEqual(extract.await_args.args[1], {'passport_front': 'file'})
