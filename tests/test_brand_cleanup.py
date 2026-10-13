import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.brand_cleanup import remove_legacy_brand_keyboards


class BrandCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_removes_old_brand_buttons_once_without_archiving_or_deletion(self):
        brand = {"kind": "brand", "group_chat_id": -101, "kb_msg_id": 10}
        spectre = {"kind": "spectre", "group_chat_id": -102, "kb_msg_id": 11}
        driver = {"kind": "driver", "group_chat_id": -103, "kb_msg_id": 12}
        app = SimpleNamespace(
            bot=SimpleNamespace(edit_message_reply_markup=AsyncMock()),
            bot_data={"applications": {1: brand, 2: spectre, 3: driver},
                      "app_messages": {1: brand}},
        )
        await remove_legacy_brand_keyboards(app)
        await remove_legacy_brand_keyboards(app)
        self.assertEqual(app.bot.edit_message_reply_markup.await_count, 2)
        app.bot.edit_message_reply_markup.assert_any_await(
            chat_id=-101, message_id=10, reply_markup=None,
        )
        app.bot.edit_message_reply_markup.assert_any_await(
            chat_id=-102, message_id=11, reply_markup=None,
        )
        self.assertEqual(len(app.bot_data["applications"]), 3)

    async def test_failed_cleanup_is_retried_and_keeps_application(self):
        record = {"kind": "brand", "group_chat_id": -101, "kb_msg_id": 10}
        app = SimpleNamespace(
            bot=SimpleNamespace(edit_message_reply_markup=AsyncMock(side_effect=RuntimeError)),
            bot_data={"applications": {1: record}},
        )
        await remove_legacy_brand_keyboards(app)
        self.assertNotIn("brand_buttons_removed", record)
        app.bot.edit_message_reply_markup.side_effect = None
        await remove_legacy_brand_keyboards(app)
        self.assertTrue(record["brand_buttons_removed"])