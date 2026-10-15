"""Telegram-native visual styling; premium assets are opt-in and never required."""
import logging
import os
import re
from telegram import InlineKeyboardButton, KeyboardButton

logger = logging.getLogger(__name__)


def button(label, *, action=None, url=None, style='primary', icon=None):
    extra = {'style': style}
    emoji_id = os.environ.get(f'PREMIUM_ICON_{icon or ""}', '') or _PACK_ICONS.get(icon, '')
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


PACK_NAMES = ('ApplicationEmoji', 'FinanceEmoji', 'TONEmoji', 'NewsEmoji')
_PACK_ICONS = {}


async def load_emoji_packs(application):
    """Resolve actual Telegram IDs from the four user-selected custom emoji sets."""
    import asyncio
    cached = application.bot_data.setdefault('premium_pack_icons', {})
    _PACK_ICONS.clear()
    _PACK_ICONS.update(cached)
    packs = {}
    async def load(name):
        try:
            result = await application.bot.get_sticker_set(name)
            packs[name] = [s for s in result.stickers if s.custom_emoji_id]
        except Exception:
            logger.warning('Optional emoji set %s unavailable; fallback icons retained.', name)
    try:
        await asyncio.wait_for(asyncio.gather(*(load(name) for name in PACK_NAMES)), timeout=25)
    except asyncio.TimeoutError:
        logger.warning('Emoji-set lookup timed out; available/cache icons retained.')
    preferred = {
        'READY': ('✅', '☑', '✔'), 'PROGRESS': ('⏳', '🔄', '🕒'),
        'INCOMPLETE': ('📄', '📷', '⚠'), 'OTHERPARK': ('🚕', '🚗', '🔁'),
        'DELETE': ('🗑', '❌', '✖'),
    }
    all_stickers = [s for name in PACK_NAMES for s in packs.get(name, [])]
    for action, options in preferred.items():
        selected = next((s for emoji in options for s in all_stickers
                         if (s.emoji or '').replace('\ufe0f', '') == emoji), None)
        if selected is None and all_stickers:
            fallback_pack = {'READY': 'ApplicationEmoji', 'PROGRESS': 'TONEmoji',
                             'INCOMPLETE': 'NewsEmoji', 'OTHERPARK': 'FinanceEmoji',
                             'DELETE': 'ApplicationEmoji'}[action]
            candidates = packs.get(fallback_pack) or all_stickers
            selected = candidates[0]
        if selected:
            cached[action] = selected.custom_emoji_id
    _PACK_ICONS.update(cached)
