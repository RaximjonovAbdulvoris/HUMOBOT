"""Shared subscription gate for all application flows."""

import logging
import os
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

REQUIRED_CHANNEL = os.environ.get("SUBSCRIPTION_CHANNEL_ID", os.environ.get("CHANNEL", "@WB_HUMO_TAXI")).strip()
if not re.fullmatch(r"(?:-[1-9][0-9]*|@[A-Za-z0-9_]+)", REQUIRED_CHANNEL):
    raise ValueError("SUBSCRIPTION_CHANNEL_ID uchun kanal ID yoki @username kiriting, taklif havolasi emas.")
CHANNEL_URL = "https://t.me/+knRCQZnC9UphNjky"
NAMANGAN_GROUP = "@wbhumo_namangan"
NAMANGAN_GROUP_URL = "https://t.me/wbhumo_namangan"

DEFAULT_REQUIRED_CHATS = (
    (REQUIRED_CHANNEL, CHANNEL_URL, "Kanalga obuna bo‘lish"),
)
NAMANGAN_REQUIRED_CHATS = (
    *DEFAULT_REQUIRED_CHATS,
    (NAMANGAN_GROUP, NAMANGAN_GROUP_URL, "Namangan guruhiga qo‘shilish"),
)


def subscription_keyboard(
    callback_data: str,
    required_chats=DEFAULT_REQUIRED_CHATS,
) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, url=url)]
        for _, url, label in required_chats
    ]
    buttons.append([
        InlineKeyboardButton("✅ Tekshirish", callback_data=callback_data)
    ])
    return InlineKeyboardMarkup(buttons)


def required_chats_for_region(region: str | None):
    if region == "namangan":
        return NAMANGAN_REQUIRED_CHATS
    return DEFAULT_REQUIRED_CHATS


async def is_subscribed(
    bot, user_id: int, chat_id: str = REQUIRED_CHANNEL
) -> bool | None:
    """Return True/False, or None when Telegram could not check membership."""
    try:
        member = await bot.get_chat_member(
            chat_id=chat_id, user_id=user_id
        )
    except TelegramError:
        logger.warning("Required chat membership check failed: %s", chat_id)
        return None
    return member.status in ("creator", "administrator", "member") or (
        member.status == "restricted" and member.is_member
    )


async def are_subscribed(bot, user_id: int, required_chats) -> bool | None:
    """Return True only when the user belongs to every required chat."""
    for chat_id, _, _ in required_chats:
        joined = await is_subscribed(bot, user_id, chat_id)
        if joined is None:
            return None
        if not joined:
            return False
    return True


async def require_subscription(
    update,
    context,
    *,
    callback_data: str,
    error_contact: str = "@WB_HUMO_TAXI",
) -> bool:
    """Gate a form on the shared WB HUMO channel.

    This function never changes user data.  Callers can therefore safely use
    it before collecting the first answer and decide which conversation state
    to return when it is not yet satisfied.
    """
    user = update.effective_user
    required_chats = required_chats_for_region(
        context.user_data.get("region")
    )
    joined = await are_subscribed(context.bot, user.id, required_chats)
    keyboard = subscription_keyboard(callback_data, required_chats)
    message = update.effective_message
    required_label = (
        "WB HUMO kanaliga va Namangan guruhiga"
        if len(required_chats) > 1
        else "WB HUMO kanaliga"
    )

    if joined is None:
        if update.callback_query:
            await update.callback_query.answer()
        await message.reply_text(
            "A’zolikni hozir tekshirib bo‘lmadi. Iltimos, birozdan keyin "
            "«✅ Tekshirish» tugmasini qayta bosing. Muammo davom etsa, "
            f"{error_contact} orqali bog‘laning.",
            reply_markup=keyboard,
        )
        return False

    if not joined:
        query = update.callback_query
        if query:
            await query.answer(
                f"Iltimos, avval {required_label} obuna bo‘ling.",
                show_alert=True,
            )
        else:
            await message.reply_text(
                f"📢 <b>Ariza yuborish uchun avval {required_label} "
                "obuna bo‘ling.</b>\n\n"
                "1️⃣ Yuqoridagi obuna tugmalarini bosing.\n"
                "2️⃣ Botga qaytib, «✅ Tekshirish»ni bosing.",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        return False

    if query := update.callback_query:
        await query.answer()
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            logger.debug("Could not remove subscription keyboard", exc_info=True)
    return True
