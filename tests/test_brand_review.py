"""Operator decision and applicant notifications are bound to the original post."""
import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123:test')

from bot import brand_review, brand_sheets


class BrandReviewTests(unittest.IsolatedAsyncioTestCase):
    def setup_review(self, member='administrator'):
        bot = N(get_chat_member=AsyncMock(return_value=N(status=member)),
                edit_message_text=AsyncMock(), send_message=AsyncMock(),
                delete_message=AsyncMock())
        context = N(bot_data={}, bot=bot, application=None)
        review = brand_review.stage_review(context, {
            'b_name': 'Test', 'b_phone': '+998781138081', 'b_model': 'Cobalt',
            'b_year': '2020', 'b_color': 'Oq', 'b_plate': '01A123BC',
        }, 'HM-000001', 'tashkent', -1001, '<b>Ariza</b>', 2001)
        review['message_id'] = 10
        query = N(data='brand-review:approve:HM-000001',
                  message=N(message_id=10, sender_chat=None), answer=AsyncMock())
        update = N(callback_query=query, effective_chat=N(id=-1001, type='supergroup'),
                   effective_user=N(id=7))
        return context, review, update

    async def test_only_group_admin_can_approve_exact_post(self):
        context, review, update = self.setup_review(member='member')
        await brand_review.on_review(update, context)
        self.assertEqual(review['status'], 'pending')
        self.assertNotIn('brand_sheets_outbox', context.bot_data)
        context.bot.get_chat_member.return_value = N(status='administrator')
        update.callback_query.message.message_id = 11
        await brand_review.on_review(update, context)
        self.assertEqual(review['status'], 'pending')
        update.callback_query.message.message_id = 10
        await brand_review.on_review(update, context)
        self.assertEqual(review['status'], 'approved')
        self.assertTrue(context.bot_data['brand_sheets_outbox']['HM-000001']['approved'])
        context.bot.send_message.assert_awaited_once()
        self.assertEqual(context.bot.send_message.await_args.kwargs['chat_id'], 2001)
        await brand_review.on_review(update, context)
        self.assertEqual(context.bot.send_message.await_count, 1)

    async def test_rejection_deletes_post_and_never_exports(self):
        context, review, update = self.setup_review()
        update.callback_query.data = 'brand-review:reject:HM-000001'
        await brand_review.on_review(update, context)
        self.assertEqual(review['status'], 'rejected')
        self.assertFalse(context.bot_data.get('brand_sheets_outbox'))
        context.bot.delete_message.assert_awaited_once_with(chat_id=-1001, message_id=10)
        self.assertIn('tasdiqlanmadi', context.bot.send_message.await_args.kwargs['text'])

    async def test_sheet_success_updates_original_post(self):
        context, review, update = self.setup_review()
        await brand_review.on_review(update, context)
        with patch.object(brand_sheets, 'configuration', return_value=('url', 'secret')), \
             patch.object(brand_sheets, 'post_export', AsyncMock()):
            await brand_sheets.flush(context)
        self.assertEqual(review['status'], 'exported')
        self.assertIn('Google Sheetsga to‘ldirildi',
                      context.bot.edit_message_text.await_args.kwargs['text'])
        self.assertIsNone(context.bot.edit_message_text.await_args.kwargs['reply_markup'])

    async def test_namangan_approval_keeps_region_until_export(self):
        context, review, update = self.setup_review()
        review['region'] = 'namangan'
        review['group_id'] = '-2002'
        update.effective_chat.id = -2002
        await brand_review.on_review(update, context)
        queued = context.bot_data['brand_sheets_outbox']['HM-000001']['payload']
        self.assertEqual(queued['region'], 'namangan')
        with patch.object(brand_sheets, 'configuration', return_value=('url', 'secret')), \
             patch.object(brand_sheets, 'post_export', AsyncMock()) as send:
            await brand_sheets.flush(context)
        self.assertEqual(send.await_args.args[3]['region'], 'namangan')
        self.assertEqual(review['status'], 'exported')

    async def test_failed_persistence_does_not_leave_approved_export(self):
        context, review, update = self.setup_review()
        with patch.object(brand_review, 'checkpoint', AsyncMock(return_value=False)):
            await brand_review.on_review(update, context)
        self.assertEqual(review['status'], 'pending')
        self.assertNotIn('HM-000001', context.bot_data['brand_sheets_outbox'])
        context.bot.send_message.assert_not_awaited()

    async def test_export_waits_until_approval_is_saved(self):
        context, review, update = self.setup_review()
        from asyncio import Event, create_task
        saving = Event()
        resume = Event()
        async def delayed_checkpoint(context):
            saving.set()
            await resume.wait()
            return True
        with patch.object(brand_review, 'checkpoint', side_effect=delayed_checkpoint), \
             patch.object(brand_sheets, 'configuration', return_value=('url', 'secret')), \
             patch.object(brand_sheets, 'post_export', AsyncMock()) as post:
            decision = create_task(brand_review.on_review(update, context))
            await saving.wait()
            export = create_task(brand_sheets.flush(context))
            from asyncio import sleep
            await sleep(0)
            post.assert_not_awaited()
            resume.set()
            await decision
            await export
        post.assert_awaited_once()
