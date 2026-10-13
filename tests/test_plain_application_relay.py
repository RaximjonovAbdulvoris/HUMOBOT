import os
import unittest
from types import SimpleNamespace as N
from unittest.mock import AsyncMock

for key in ("TELEGRAM_BOT_TOKEN", "DRIVER_GROUP_1", "DRIVER_GROUP_2", "BRAND_GROUP"):
    os.environ.setdefault(key, "123:offline" if key == "TELEGRAM_BOT_TOKEN" else "-100")

from bot.handlers import operator


class PlainApplicationRelayTests(unittest.IsolatedAsyncioTestCase):
    def context(self, kind):
        record = {
            "kind": kind, "group_chat_id": -100, "kb_msg_id": 20,
            "applicant_id": 9, "region": "tashkent",
        }
        return N(bot=N(send_message=AsyncMock()), bot_data={
            "applications": {(-100, 20): record},
            "pending_comments": {(-100, 77): (-100, 20)},
            "pending_prompts": {(-100, 77): 21},
            "pending_user_replies": {9: (-100, 20)},
        })

    async def test_old_pending_comments_do_not_relay(self):
        for kind in ("brand", "spectre"):
            ctx = self.context(kind)
            msg = N(text="old comment", reply_text=AsyncMock())
            update = N(message=msg, effective_chat=N(id=-100), effective_user=N(id=77))
            await operator.on_operator_text_in_group(update, ctx)
            ctx.bot.send_message.assert_not_awaited()
            self.assertFalse(ctx.bot_data["pending_comments"])
            self.assertFalse(ctx.bot_data["pending_prompts"])

    async def test_old_user_reply_button_does_not_open_relay(self):
        for kind in ("brand", "spectre"):
            ctx = self.context(kind)
            query = N(
                data="user:reply:-100:20", message=N(reply_text=AsyncMock()),
                answer=AsyncMock(), edit_message_reply_markup=AsyncMock(),
            )
            await operator.on_user_reply_button(N(callback_query=query, effective_user=N(id=9)), ctx)
            self.assertFalse(ctx.bot_data["pending_user_replies"])
            query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
            ctx.bot.send_message.assert_not_awaited()

    async def test_old_pending_user_text_does_not_relay(self):
        for kind in ("brand", "spectre"):
            ctx = self.context(kind)
            msg = N(text="old reply", reply_text=AsyncMock())
            await operator.on_user_reply_message(N(message=msg, effective_user=N(id=9)), ctx)
            ctx.bot.send_message.assert_not_awaited()
            self.assertFalse(ctx.bot_data["pending_user_replies"])