"""Remove obsolete brand/Spectre controls without archiving or deleting messages."""
import logging

from telegram.error import BadRequest, TelegramError
from telegram.ext import ApplicationHandlerStop

logger = logging.getLogger(__name__)


def is_plain_application_message(message, bot_id) -> bool:
    """Identify an old bot-authored form even when its persistence record is gone."""
    sender = getattr(message, "from_user", None)
    if not bot_id or getattr(sender, "id", None) != bot_id:
        return False
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    heading = text.split("\n", 1)[0].upper()
    return "ARIZA" in heading and ("SPECTRE" in heading or "BREND" in heading)


async def remove_message_buttons(bot, chat_id, message_id) -> None:
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=None,
        )
    except BadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise


async def remove_buttons_command(update, context) -> None:
    """An authenticated group admin can target an old form by replying /tugmasiz."""
    try:
        await _remove_buttons_command(update, context)
    finally:
        # Do not relay this administrative command as a pending operator comment.
        raise ApplicationHandlerStop


async def _remove_buttons_command(update, context) -> None:
    message, chat, user = update.message, update.effective_chat, update.effective_user
    if not message or not chat or chat.type not in ("group", "supergroup"):
        return
    if not user:
        return
    # Require an identifiable administrator; anonymous sender_chat posts cannot
    # be tied to a verified person.
    if getattr(message, "sender_chat", None):
        await message.reply_text("Buyruqni shaxsiy administrator profilingizdan yuboring.")
        return
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
    except TelegramError:
        await message.reply_text("Administrator huquqini tekshirib bo‘lmadi. Xabar o‘zgartirilmadi.")
        return
    if member.status not in ("administrator", "creator"):
        await message.reply_text("Bu buyruq faqat guruh administratorlari uchun.")
        return
    target = getattr(message, "reply_to_message", None)
    if not target or not is_plain_application_message(target, context.bot.id):
        await message.reply_text(
            "Bot yuborgan Spectre yoki Brend arizasiga Reply/Javob qilib /tugmasiz yuboring."
        )
        return
    try:
        await remove_message_buttons(context.bot, chat.id, target.message_id)
    except TelegramError:
        await message.reply_text("Tugmalar olib tashlanmadi. Botning xabarni tahrirlash imkonini tekshiring.")
        return
    await message.reply_text("Tugmalar olib tashlandi. Ariza o‘z joyida qoldi; arxivlanmadi.")


async def remove_legacy_brand_keyboards(application) -> None:
    seen = set()
    for store_name in ("applications", "app_messages"):
        for record in list(application.bot_data.get(store_name, {}).values()):
            if not isinstance(record, dict) or record.get("kind") not in ("brand", "spectre"):
                continue
            if record.get("brand_buttons_removed"):
                continue
            chat_id, message_id = record.get("group_chat_id"), record.get("kb_msg_id")
            if not chat_id or not message_id or (chat_id, message_id) in seen:
                continue
            seen.add((chat_id, message_id))
            try:
                await remove_message_buttons(application.bot, chat_id, message_id)
                record["brand_buttons_removed"] = True
            except Exception:
                # Keep the record for a future startup retry. Old callbacks are
                # independently blocked, so failure cannot enable archiving.
                logger.warning("Old brand/Spectre keyboard could not be removed; will retry on restart.")