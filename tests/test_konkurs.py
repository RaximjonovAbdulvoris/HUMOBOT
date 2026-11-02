"""Contest approval remains separate from existing application exports."""
import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

os.environ.setdefault('TELEGRAM_BOT_TOKEN', '123:test')
os.environ.setdefault('DRIVER_GROUP_1', '-1001')
os.environ.setdefault('DRIVER_GROUP_2', '-1002')
os.environ.setdefault('BRAND_GROUP', '-1003')

from bot import brand_review, brand_sheets
from bot.handlers import konkurs


class KonkursTests(unittest.IsolatedAsyncioTestCase):
    async def test_city_and_order_buttons_only_accept_offered_values(self):
        context = N(user_data={})
        message = N(text='Fargona', reply_text=AsyncMock())
        self.assertEqual(await konkurs.city(N(message=message), context), konkurs.CITY)
        for city in konkurs.CITY_CHOICES:
            message.text = city
            self.assertEqual(await konkurs.city(N(message=message), context), konkurs.NAME)
            self.assertEqual(context.user_data['k_city'], city)
        message.text = '150'
        self.assertEqual(await konkurs.orders(N(message=message), context), konkurs.ORDERS)
        for number in konkurs.ORDER_CHOICES:
            message.text = number
            self.assertEqual(await konkurs.orders(N(message=message), context), konkurs.DAY)
            self.assertEqual(context.user_data['k_orders'], number)

    def test_contest_menu_immediately_follows_driver(self):
        from bot.handlers.start import main_keyboard, MENU_KONKURS
        keyboard = main_keyboard('tashkent').keyboard
        self.assertEqual(keyboard[1][0].text, MENU_KONKURS)

    def test_entry_accepts_premium_cleaned_and_original_button(self):
        from bot.premium_emoji import _button_text
        handler = konkurs.build_konkurs_conversation().entry_points[0]
        for label in (konkurs.MENU_KONKURS, _button_text(konkurs.MENU_KONKURS)):
            from telegram import Update
            update = Update.de_json({'update_id': 1, 'message': {'message_id': 1,
                'date': 0, 'chat': {'id': 42, 'type': 'private'}, 'text': label}}, None)
            self.assertTrue(handler.filters.check_update(update))

    async def test_admin_approval_enqueues_only_contest_fields(self):
        data = {'k_city': 'Farg‘ona', 'k_name': 'Ali Valiyev',
                'k_phone': '998901234567', 'k_orders': '42', 'k_date': '01.11.2026'}
        bot = N(get_chat_member=AsyncMock(return_value=N(status='administrator')),
                edit_message_text=AsyncMock(), send_message=AsyncMock())
        context = N(bot_data={}, bot=bot, application=None)
        review = brand_review.stage_review(context, data, 'HM-123456', 'konkurs',
                                           -1007, '<b>Konkurs</b>', 42, kind='konkurs')
        review['message_id'] = 17
        query = N(data='brand-review:approve:HM-123456', message=N(message_id=17, sender_chat=None),
                  answer=AsyncMock())
        update = N(callback_query=query, effective_chat=N(id=-1007, type='supergroup'),
                   effective_user=N(id=8))
        with patch.object(brand_sheets, 'post_export', AsyncMock()) as post, \
             patch.object(brand_sheets, 'configuration', return_value=('url', 'secret')):
            await brand_sheets.flush(context)
            post.assert_not_awaited()
            await brand_review.on_review(update, context)
            payload = context.bot_data['brand_sheets_outbox']['HM-123456']['payload']
            self.assertEqual(payload['kind'], 'konkurs')
            self.assertEqual(payload['region'], 'konkurs')
            self.assertEqual(payload['fields'], dict(city='Farg‘ona', name='Ali Valiyev',
                phone='998901234567', orders='42', date='01.11.2026'))
            await brand_sheets.flush(context)
            post.assert_awaited_once()
        self.assertEqual(review['status'], 'exported')

    async def test_rejected_contest_never_exports(self):
        bot = N(get_chat_member=AsyncMock(return_value=N(status='administrator')),
                edit_message_text=AsyncMock(), send_message=AsyncMock(), delete_message=AsyncMock())
        context = N(bot_data={}, bot=bot, application=None)
        review = brand_review.stage_review(context, {}, 'HM-123456', 'konkurs',
                                           -1007, 'Konkurs', 42, kind='konkurs')
        review['message_id'] = 17
        update = N(callback_query=N(data='brand-review:reject:HM-123456',
            message=N(message_id=17, sender_chat=None), answer=AsyncMock()),
            effective_chat=N(id=-1007, type='supergroup'), effective_user=N(id=8))
        await brand_review.on_review(update, context)
        self.assertEqual(review['status'], 'rejected')
        self.assertFalse(context.bot_data.get('brand_sheets_outbox'))
        self.assertIn('konkurs', bot.send_message.await_args.kwargs['text'].lower())

    async def test_invalid_order_count_keeps_form_state(self):
        message = N(text='0', reply_text=AsyncMock())
        self.assertEqual(await konkurs.orders(N(message=message), N(user_data={})), konkurs.ORDERS)
        message.reply_text.assert_awaited_once()

    async def test_lost_telegram_response_does_not_duplicate_post(self):
        data = dict(k_city='Toshkent', k_name='Test Driver', k_phone='998901234567', k_orders='42')
        context = N(user_data=data, bot_data={}, application=None,
                    bot=N(send_message=AsyncMock(side_effect=TimeoutError)))
        update = N(message=N(text='01.01.2026', reply_text=AsyncMock()),
                   effective_user=N(id=42, full_name='Test Driver'))
        with patch.object(konkurs, 'destination', return_value='-5302408605'), \
             patch.object(konkurs, 'application_code', return_value='HM-123456'):
            await konkurs.day(update, context)
            await konkurs.day(update, context)
        context.bot.send_message.assert_awaited_once()
