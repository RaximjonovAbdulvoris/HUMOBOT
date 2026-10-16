"""Isolated @testthumo_bot runner; never uses production routes or state."""
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATE = ROOT / '.test-bot-state'


def configure():
    envfile = ROOT / '.env.test'
    values = {}
    if envfile.exists():
        for line in envfile.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip().strip('\"\'')
    token = values.get('TELEGRAM_BOT_TOKEN', '')
    if token.split(':')[0] != '8845908442':
        raise ValueError('Only the authorized test bot token is accepted in .env.test')
    os.environ.update({
        'TELEGRAM_BOT_TOKEN': token,
        'DOCUMENT_AI_ENABLED': values.get('DOCUMENT_AI_ENABLED', '1'),
        'DOCUMENT_OCR_BACKEND': values.get('DOCUMENT_OCR_BACKEND', 'fast'),
        'LOCAL_OCR_MODEL': values.get('LOCAL_OCR_MODEL', 'qwen2.5vl:3b'),
        'DRIVER_GROUP_1': '-5258426588', 'DRIVER_GROUP_2': '-5468071353',
        'BRAND_GROUP': '-5422883968', 'ARCHIVE_GROUP': values.get('ARCHIVE_GROUP', ''),
        'TASHKENT_DRIVER_GROUP_1': '-5258426588', 'TASHKENT_DRIVER_GROUP_2': '-5468071353',
        'TASHKENT_BRAND_GROUP': '-5422883968', 'TASHKENT_SPECTRE_GROUP': '-5243428930',
        'NAMANGAN_SPECTRE_GROUP': '-5243428930', 'TASHKENT_ARCHIVE_GROUP': values.get('ARCHIVE_GROUP', ''),
        'PERSIST_DIR': str(STATE), 'SUBSCRIPTION_CHANNEL_ID': '@WB_HUMO_TAXI',
    })
    for key in ("INCOMPLETE_GROUP", "OTHER_PARK_GROUP", "WELCOME_STICKER_ID", "SUCCESS_STICKER_ID"):
        os.environ[key] = values.get(key, "")
    for key in ("BRAND_SHEETS_WEBHOOK_URL", "BRAND_SHEETS_SECRET"):
        os.environ[key] = values.get(key, "")
    for action in ("READY", "PROGRESS", "INCOMPLETE", "OTHERPARK", "DELETE"):
        key = f"PREMIUM_ICON_{action}"
        os.environ[key] = values.get(key, "")
    STATE.mkdir(mode=0o700, exist_ok=True)
    # Local routing overrides take precedence, so explicitly isolate these too.
    routes = {key: os.environ[key] for key in (
        'TASHKENT_DRIVER_GROUP_1', 'TASHKENT_DRIVER_GROUP_2', 'TASHKENT_BRAND_GROUP',
        'TASHKENT_SPECTRE_GROUP', 'NAMANGAN_SPECTRE_GROUP')}
    (STATE / 'bot_routes.json').write_text(json.dumps(routes))


async def preflight():
    from bot.document_ocr import enabled, local_client, local_model, check_local_engine, ocr_backend
    if enabled():
        if ocr_backend() == 'rapid':
            from bot.neural_ocr import engine_info
            await engine_info()
            print('Local neural OCR verified; external AI is disabled.', flush=True)
        elif ocr_backend() == 'fast':
            from bot.fast_ocr import engine_info
            await engine_info()
            print('Fast local OCR verified; no Ollama or external AI needed.', flush=True)
        else:
            async with local_client() as client:
                await check_local_engine(client, local_model())
            print('Local OCR model verified; external AI is disabled.', flush=True)
    from telegram import Bot
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connect_timeout=30, read_timeout=30, write_timeout=30, connection_pool_size=8)
    async with Bot(os.environ['TELEGRAM_BOT_TOKEN'], request=request) as bot:
        me = bot.bot
        if me.username.lower() != 'testthumo_bot':
            raise ValueError('Unexpected test bot identity')
        chats = (-5258426588, -5468071353, -5422883968, -5243428930)
        members = await asyncio.gather(*(bot.get_chat_member(chat, me.id) for chat in chats))
        for chat, member in zip(chats, members):
            if member.status != 'administrator' or not member.can_delete_messages:
                raise ValueError(f'Test bot needs admin/delete rights in {chat}')
        optional = {os.environ.get(name, '') for name in ('INCOMPLETE_GROUP', 'OTHER_PARK_GROUP', 'ARCHIVE_GROUP')}
        for chat in sorted(optional - {''}):
            if not chat.startswith('-') or not chat[1:].isdigit():
                raise ValueError('Invalid review/archive group ID')
            member = await bot.get_chat_member(int(chat), me.id)
            if member.status != 'administrator' or not member.can_delete_messages:
                raise ValueError(f'Test bot needs admin/delete rights in {chat}')
        webhook = await bot.get_webhook_info()
        if webhook.url:
            raise ValueError('Test bot has an existing webhook; stop that instance first')
        print('Test bot identity and four groups verified.', flush=True)


def main():
    logging.getLogger('httpx').setLevel(logging.WARNING)
    try:
        configure()
        asyncio.run(asyncio.wait_for(preflight(), timeout=90))
    except Exception as error:
        # Never print Telegram exceptions/URLs containing the bot token.
        print(f'Test bot preflight failed: {type(error).__name__}. Check local OCR, token, network and group permissions.', flush=True)
        return 1
    if '--check' in sys.argv:
        return 0
    # Subscription checks are disabled only in this identity-checked test runner.
    # This allows testing without adding the test bot to production channels.
    import bot.subscription as subscription
    subscription.DEFAULT_REQUIRED_CHATS = ()
    subscription.NAMANGAN_REQUIRED_CHATS = ()
    import bot.main as application
    print('TEST MODE: fixed application groups, configured review/archive groups; no subscription gate.', flush=True)
    asyncio.set_event_loop(asyncio.new_event_loop())
    application.main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
