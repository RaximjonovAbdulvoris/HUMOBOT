# HUMOBOT

Telegram bot for WB HUMO taxi applications in Tashkent and Namangan.

## Features

- Regional driver, branding and Spectre application routing.
- Driver application albums: ten document/car photos, then selfie and licence.
- Administrator controls: Ready, Progress, Incomplete photos, Other park, Delete.
- Ready archives the application before deleting originals. The two notices send
  prepared applicant messages and keep the application in its operator group.
- CodeCraft vision extraction of PINFL, birth date/place, driving licence number
  and expiry, vehicle registration certificate serial/number. Extracted values
  are copyable and require verification against the original documents.
- Persistent form state and resumable submission of confirmed album stages.

## Setup

Python 3.11 or later:

```sh
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with real Telegram credentials and destination IDs. Never commit it.
Set `CODECRAFT_API_KEY` to enable OCR; without it, original photos still arrive,
and extracted fields are marked unavailable. The default vision model is
`gpt-5.6-luna`; choose a CodeCraft vision-capable model if necessary.

The bot reads environment variables. For an interactive run, export variables
from `.env` in your shell before `venv/bin/python -m bot.main`. On a Linux server,
`sudo bash deploy.sh` loads `.env` using a separate `humobot.service`, enables
startup on boot and automatic process restart. Stop any prior instance of the
same Telegram token first to avoid polling conflicts.

Namangan uses `DRIVER_GROUP_1`, `DRIVER_GROUP_2`, `BRAND_GROUP`, `ARCHIVE_GROUP`.
Configure additional destinations on the bot server:

```sh
venv/bin/python -m bot.configure tashkent
venv/bin/python -m bot.configure namangan
venv/bin/python -m bot.configure check --scope all
```

For private subscription channels, use the numeric chat ID in
`SUBSCRIPTION_CHANNEL_ID`, not an invite URL. The bot needs administrator rights
in the subscription channel and configured operator groups, including permission
to delete messages. Keep `PERSIST_DIR` on durable storage.

## Isolated test bot

`scripts/run_test_bot.py` is restricted to the authorized `@testthumo_bot` and
four test groups. Put its credentials in ignored `.env.test`:

```dotenv
TELEGRAM_BOT_TOKEN=
CODECRAFT_API_KEY=
CODECRAFT_VISION_MODEL=gpt-5.6-luna
```

Run `venv/bin/python scripts/run_test_bot.py`. Add `--check` for read-only
preflight. Both regions route only to the test groups; subscription gates are
bypassed and archives are disabled. Test state is isolated in `.test-bot-state`.
This command alone is a foreground process, not a hosted deployment.

## Validation

```sh
venv/bin/python -m unittest discover -s tests -v
```

86 offline tests cover regional routing, operator actions, archive safety,
submission retries and mocked OCR requests. Live CodeCraft authentication and
OCR accuracy remain unverified: its endpoint blocked the review environment.

## Optional template images

Personal document/selfie sample images are excluded from this repository.
The bot falls back to text instructions and text office addresses. You can
place your own approved images in `bot/templates` on the server; do not
commit personal documents or selfies. See `bot/templates/README.md` for names.
