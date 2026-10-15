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

## Operator refresh

Every new driver, brand and Spectre application has a persistent sequential
`HM-000001` reference. Keep `application_numbers.sqlite3` in the durable
`PERSIST_DIR` alongside the bot state; do not delete it during updates.

Driver identity/contact details and copyable AI fields are now in one operator
card. Album captions only identify the application and album part. Progress
can be toggled between red and yellow; a failed keyboard edit does not alter
the stored state.

Set `INCOMPLETE_GROUP` and `OTHER_PARK_GROUP` to separate negative Telegram chat
IDs. City-specific overrides (`TASHKENT_INCOMPLETE_GROUP`, etc.) are supported.
On a button press, the full application albums and information card are copied
to the queue without active operator buttons; the applicant is notified only
after the copy is confirmed. The source application remains in the operator
group. Checkpoints prevent repeating confirmed copies on notification retry.
Missing routes block the operation with an actionable operator message.

`python scripts/run_test_bot.py` loads these global queue IDs and premium asset
IDs from `.env.test`. It continues to use only the fixed test application groups.

`Pillow` generates 12 consistent navy/teal/gold instruction cards at startup in
`PERSIST_DIR/visual_templates`. These are abstract guides, with no personal
photos, passport replicas, numbers, faces or signatures. Install updated
requirements before restarting. Generation failure falls back to text prompts.

For optional branded welcome/success stickers, set `WELCOME_STICKER_ID` and
`SUCCESS_STICKER_ID`. Reply to a sticker with `/asset_id` in the bot's private
chat to obtain its file ID. The same command returns custom emoji IDs from an
emoji message. Premium icon IDs are opt-in; according to Telegram, the bot owner
must have Premium (or the bot must have an eligible purchased username). Without
IDs, the interface uses colored Telegram-native buttons and standard emoji.
A sticker send failure does not interrupt a form.

Vehicle-certificate OCR normalizes spacing/separators and Cyrillic lookalikes
before comparing front/back readings, while still flagging conflicting values.
Provider HTTP status is logged without document text or credentials. Vision
requests have a 60-second read timeout and 150-second overall bound; the user
gets a waiting message. Real-world reading accuracy still needs a test on the
server with clear certificate photos; normalized values must be checked.
