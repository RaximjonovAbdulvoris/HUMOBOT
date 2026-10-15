"""Telegram-native visual styling; premium assets are opt-in and never required."""
import logging
import os
import re
from telegram import InlineKeyboardButton, KeyboardButton

logger = logging.getLogger(__name__)


def button(label, *, action=None, url=None, style='primary', icon=None):
    extra = {'style': style}
    emoji_id = os.environ.get(f'PREMIUM_ICON_{icon or ""}', '')
    if re.fullmatch(r'[0-9]+', emoji_id):
        extra['icon_custom_emoji_id'] = emoji_id
    return InlineKeyboardButton(label, callback_data=action, url=url, api_kwargs=extra)


def menu_button(label, style='primary'):
    return KeyboardButton(label, api_kwargs={'style': style})


async def send_brand_sticker(message, event):
    sticker = os.environ.get(f'{event.upper()}_STICKER_ID', '').strip()
    if not sticker:
        return
    try:
        await message.reply_sticker(sticker=sticker)
    except Exception:
        # Branding must never block an application. Do not log asset credentials/URLs.
        logger.warning('Optional %s sticker could not be sent', event)


async def with_keyboard_fallback(call, **kwargs):
    """A rejected premium icon must not prevent sending operator controls."""
    from telegram import InlineKeyboardMarkup
    from telegram.error import BadRequest
    try:
        return await call(**kwargs)
    except BadRequest:
        markup = kwargs.get('reply_markup')
        if not isinstance(markup, InlineKeyboardMarkup) or not any(
            b.api_kwargs.get('icon_custom_emoji_id')
            for row in markup.inline_keyboard for b in row
        ):
            raise
        kwargs['reply_markup'] = InlineKeyboardMarkup([
            [InlineKeyboardButton(b.text, callback_data=b.callback_data, url=b.url)
             for b in row] for row in markup.inline_keyboard
        ])
        return await call(**kwargs)
