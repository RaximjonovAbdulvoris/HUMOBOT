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
