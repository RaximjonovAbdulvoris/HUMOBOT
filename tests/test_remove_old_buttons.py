import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock

for key in ("TELEGRAM_BOT_TOKEN", "DRIVER_GROUP_1", "DRIVER_GROUP_2", "BRAND_GROUP"):
    os.environ.setdefault(key, "123:offline" if key == "TELEGRAM_BOT_TOKEN" else "-100")

from telegram.error import BadRequest, Forbidden
from telegram.ext import ApplicationHandlerStop
from bot.brand_cleanup import remove_buttons_command
from bot.handlers.operator import on_operator_button


class RemoveOldButtonsTests(unittest.IsolatedAsyncioTestCase):
    def setup_context(self, status="administrator"):
        target = N(
            from_user=N(id=500), message_id=42,
            text="⚡ WB HUMO Toshkent — YANGI SPECTRE ENERGY ARIZA\nFIO: test",
        )
        message = N(
            reply_to_message=target, sender_chat=None, reply_text=AsyncMock(),
        )
        update = N(message=message, effective_chat=N(id=-100, type="supergroup"),
                   effective_user=N(id=10, full_name="Admin"))
        context = N(bot=N(
            id=500, get_chat_member=AsyncMock(return_value=N(status=status)),
            edit_message_reply_markup=AsyncMock(),
            send_message=AsyncMock(), delete_message=AsyncMock(),
            copy_message=AsyncMock(),
        ), bot_data={})
        return update, context

    async def command(self, update, context):
        with self.assertRaises(ApplicationHandlerStop):
            await remove_buttons_command(update, context)

    async def test_admin_removes_untracked_form_buttons_without_moving_message(self):
        update, context = self.setup_context()
        await self.command(update, context)
        context.bot.edit_message_reply_markup.assert_awaited_once_with(
            chat_id=-100, message_id=42, reply_markup=None,
        )
        context.bot.send_message.assert_not_awaited()
        context.bot.copy_message.assert_not_awaited()
        context.bot.delete_message.assert_not_awaited()
        self.assertFalse(context.bot_data)

    async def test_non_admin_cannot_modify_buttons(self):
        update, context = self.setup_context(status="member")
        await self.command(update, context)
        context.bot.edit_message_reply_markup.assert_not_awaited()

    async def test_foreign_bot_and_driver_messages_are_rejected(self):
        for sender, heading in (
            (501, "YANGI SPECTRE ENERGY ARIZA"),
            (500, "WB HUMO NAMANGAN — YANGI ARIZA"),
        ):
            update, context = self.setup_context()
            update.message.reply_to_message.from_user.id = sender
            update.message.reply_to_message.text = heading
            await self.command(update, context)
            context.bot.edit_message_reply_markup.assert_not_awaited()

    async def test_admin_lookup_failure_fails_closed(self):
        update, context = self.setup_context()
        context.bot.get_chat_member.side_effect = Forbidden("not allowed")
        await self.command(update, context)
        context.bot.edit_message_reply_markup.assert_not_awaited()

    async def test_already_removed_buttons_are_successful(self):
        update, context = self.setup_context()
        context.bot.edit_message_reply_markup.side_effect = BadRequest("Message is not modified")
        await self.command(update, context)
        self.assertIn("olib tashlandi", update.message.reply_text.call_args.args[0])

    async def test_untracked_spectre_callback_cannot_archive_or_comment(self):
        for action in ("ready", "progress", "comment"):
            update, context = self.setup_context()
            target = update.message.reply_to_message
            target.reply_text = AsyncMock()
            update.callback_query = N(
                data=f"op:{action}:99", message=target, answer=AsyncMock(),
                edit_message_reply_markup=AsyncMock(),
            )
            await on_operator_button(update, context)
            update.callback_query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
            context.bot.send_message.assert_not_awaited()
            context.bot.copy_message.assert_not_awaited()
            context.bot.delete_message.assert_not_awaited()
            self.assertFalse(context.bot_data)