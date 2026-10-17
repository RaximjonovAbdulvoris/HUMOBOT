"""Offline checks for premium rendering and a safe Telegram rejection path."""
import os
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace as N

for key in ('TELEGRAM_BOT_TOKEN', 'DRIVER_GROUP_1', 'DRIVER_GROUP_2', 'BRAND_GROUP'):
    os.environ.setdefault(key, '123:test' if key == 'TELEGRAM_BOT_TOKEN' else '-1001')

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import BadRequest
from telegram.ext import ExtBot

from bot import presentation
from bot.premium_emoji import PremiumEmojiBot, premium_html, premium_keyboard


class PremiumEmojiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        presentation._PACK_EMOJIS.clear()
        presentation._PACK_EMOJIS.update({'✅': '12345', '📄': '23456'})
        self.addCleanup(presentation._PACK_EMOJIS.clear)
        presentation._PACK_ICONS.clear()
        self.addCleanup(presentation._PACK_ICONS.clear)

    def bot(self):
        with patch.dict(os.environ, {'ALL_PROXY': '', 'HTTPS_PROXY': '',
                                     'HTTP_PROXY': '', 'all_proxy': '', 'https_proxy': ''}):
            return PremiumEmojiBot('123:test')

    def test_html_keeps_markup_and_premium_emoji(self):
        result = premium_html('✅ <b>Tayyor</b> <code>📄</code>', 'HTML')
        self.assertIn('<tg-emoji emoji-id="12345">✅</tg-emoji>', result)
        self.assertIn('<b>Tayyor</b>', result)
        self.assertIn('<code>📄</code>', result)

    def test_markdown_keeps_bold_and_unmapped_emoji_if_sets_fail(self):
        result = premium_html('✅ *Tayyor* 📝', 'Markdown')
        self.assertIn('<b>Tayyor</b>', result)
        self.assertIn('📝', result)
        self.assertIn('emoji-id="12345"', result)

    def test_unrelated_logo_never_replaces_location_or_document_text(self):
        presentation._PACK_ICONS.update({'DRIVER': '34567', 'CONTACT': '45678'})
        self.assertNotIn('tg-emoji', premium_html('📍 Toshkent · 📝 Ulanish', 'HTML'))
        self.assertEqual(premium_html('1️⃣ Old • 2️⃣ Orqa'), '1. Old • 2. Orqa')
        from bot.handlers.start import MENU_DRIVER, main_keyboard
        keyboard = main_keyboard('tashkent')
        self.assertEqual(keyboard.keyboard[0][0].text, MENU_DRIVER)
        self.assertEqual(keyboard.keyboard[0][0].api_kwargs['icon_custom_emoji_id'], '34567')

    def test_missing_location_icon_remains_visible_in_keyboard(self):
        from bot.handlers.start import main_keyboard
        button = main_keyboard('tashkent').keyboard[2][1]
        self.assertEqual(button.text, '📍 Ofis manzili')
        self.assertNotIn('icon_custom_emoji_id', button.api_kwargs)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('📍 Xaritada ochish', url='https://example.org')]])
        self.assertIsNone(premium_keyboard(markup))

    async def test_location_is_exact_and_driver_uses_only_logo_pack(self):
        packs = {
            'NewsEmoji': [N(emoji='🅱️', custom_emoji_id='111')],
            'IslomjonAnimeEmoji': [N(emoji='📍', custom_emoji_id='222')],
            'logowbtg': [N(emoji='🚕', custom_emoji_id='333')],
        }
        async def get_set(name):
            return N(stickers=packs.get(name, []))
        app = N(bot=N(get_sticker_set=get_set),
                bot_data={'premium_pack_icons': {'LOCATION': '111'}})
        await presentation.load_emoji_packs(app)
        self.assertEqual(presentation.premium_id('📍'), '222')
        self.assertEqual(presentation._PACK_ICONS['LOCATION'], '222')
        self.assertEqual(presentation._PACK_ICONS['DRIVER'], '333')
        self.assertIn('emoji-id="222"', premium_html('📍 Toshkent shahri', 'HTML'))
        self.assertEqual(presentation.premium_id('📝'), None)

    def test_button_click_data_survives_premium_render(self):
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Tayyor', callback_data='op:ready:5')]])
        changed = premium_keyboard(markup)
        self.assertEqual(changed['inline_keyboard'][0][0]['text'], 'Tayyor')
        self.assertEqual(changed['inline_keyboard'][0][0]['icon_custom_emoji_id'], '12345')
        self.assertEqual(changed['inline_keyboard'][0][0]['callback_data'], 'op:ready:5')

    async def test_rejected_icon_retries_original_message(self):
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Tayyor', callback_data='x')]])
        sender = AsyncMock(side_effect=[BadRequest('custom emoji not allowed'), {'ok': True}])
        bot = self.bot()
        with patch.object(ExtBot, '_post', sender):
            await bot._post('sendMessage', {'chat_id': 5, 'text': '✅ *Tayyor*',
                                            'parse_mode': 'Markdown', 'reply_markup': markup})
        self.assertEqual(sender.await_count, 2)
        self.assertEqual(sender.await_args_list[0].args[1]['parse_mode'], 'HTML')
        self.assertEqual(sender.await_args_list[1].args[1]['parse_mode'], 'Markdown')
        self.assertIs(sender.await_args_list[1].args[1]['reply_markup'], markup)

    async def test_album_captions_keep_photo_and_style(self):
        sender = AsyncMock(return_value=[])
        bot = self.bot()
        album = [InputMediaPhoto('file-id', caption='📄 *Hujjatlar*', parse_mode='Markdown')]
        with patch.object(ExtBot, '_post', sender):
            await bot._post('sendMediaGroup', {'chat_id': 5, 'media': album})
        media = sender.await_args.args[1]['media'][0]
        self.assertEqual(media.media, 'file-id')
        self.assertEqual(media.parse_mode, 'HTML')
        self.assertIn('<tg-emoji', media.caption)

    async def test_real_send_path_preserves_button_action(self):
        bot = self.bot()
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('✅ Tayyor', callback_data='op:ready:5')]])
        response = {'message_id': 1, 'date': 0, 'chat': {'id': 5, 'type': 'private'}, 'text': 'Tayyor'}
        with patch.object(PremiumEmojiBot, '_do_post', AsyncMock(return_value=response)) as sent:
            await bot.send_message(5, '✅ *Tayyor*', parse_mode='Markdown', reply_markup=markup)
        payload = sent.await_args.kwargs['data']
        self.assertIn('<tg-emoji emoji-id="12345">✅</tg-emoji>', payload['text'])
        self.assertIn('<b>Tayyor</b>', payload['text'])
        self.assertEqual(payload['reply_markup']['inline_keyboard'][0][0]['callback_data'], 'op:ready:5')
