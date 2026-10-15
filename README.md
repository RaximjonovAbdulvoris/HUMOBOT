# HUMOBOT

Telegram bot for WB HUMO taxi applications in Tashkent and Namangan.

## Features

- Regional driver, branding and Spectre application routing.
- Driver application albums: ten document/car photos, then selfie and licence.
- Administrator controls: Ready, Progress, Incomplete photos, Other park, Delete.
- Ready archives the application before deleting originals. The two review actions move the full application to their separate review
  groups and send a prepared applicant notice after source cleanup.
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
bypassed. Set `ARCHIVE_GROUP` in `.env.test` to enable Ready/archive actions. Test state is isolated in `.test-bot-state`.
This command alone is a foreground process, not a hosted deployment.

## Validation

```sh
venv/bin/python -m unittest discover -s tests -v
```

113 offline tests cover regional routing, operator actions, archive safety,
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
to the queue with only Ready, Delete and reversible Progress buttons. A new
source record is saved with confirmed destination photo/message IDs before
originals are deleted. The applicant is notified after the move is finished.
Checkpoints prevent repeating confirmed copies when deletion is retried.
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


## Review moves and supplied emoji sets

Configure the isolated test runner with the user-provided review groups:
`INCOMPLETE_GROUP` and `OTHER_PARK_GROUP` from the private `.env.test` file.
Group identifiers are deliberately excluded from public source code. Make the test bot an
administrator with message-deletion rights in both groups. An optional
`ARCHIVE_GROUP` in `.env.test` is used for both cities' archive destinations;
there is deliberately no guessed archive destination.

Both review groups show exactly Ready, Delete, and red/yellow Progress. Ready
archives from the current review group, then removes its photos and controls.
Delete removes only that review application's messages, without archiving.
Application references and the originally selected city survive every move.
The old operator group can no longer control a successfully moved application.

If deleting original messages fails, the destination remains registered and
original controls are kept for retry. Pressing the original move button or a
control in the destination resumes cleanup without copying confirmed media a
second time. Failure to flush persistence blocks source deletion. A queue
copy with incomplete/unknown destination IDs also cannot trigger deletion.
Source/archive cleanup keeps the control message until its photos are removed.

At startup, actual custom emoji IDs are fetched from `ApplicationEmoji`,
`FinanceEmoji`, `TONEmoji`, and `NewsEmoji`. IDs are chosen by matching symbols
and fall back to the requested set if no matching symbol is available. The
results are cached in bot persistence. Explicit `PREMIUM_ICON_*` values still
override automatic choices. Unavailable sets fall back to cached/standard emoji;
a Telegram rejection of custom icons retries with ordinary working controls.
These links identify custom emoji sets, not standalone sticker packs.

Server update for the existing test service:

```sh
cd /root/HUMOBOT
git pull --ff-only
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/run_test_bot.py --check
systemctl restart humobot-test
journalctl -u humobot-test -n 30 --no-pager
```

Set `ARCHIVE_GROUP` before testing Ready. Never run a second polling process
alongside the systemd service; `--check` only performs read-only checks.

### Document extraction and privacy

The OCR pipeline strips image metadata in memory, corrects EXIF rotation, improves contrast and retries missing fields using overlapping document crops. Output tokens are capped at 8192 per request. This can increase latency and API cost. Conflicting readings remain empty for operator review; never treat AI output as verified identity data. Set `DOCUMENT_AI_ENABLED=0` in the environment (or `.env.test` for the test runner) and restart to disable external document extraction.

State is encrypted using authenticated Fernet encryption. On startup, trusted legacy `bot_persistence.pkl` state is migrated in place; the sibling `bot_persistence.key` is generated with mode 0600. Preserve this key in a separate secure backup: losing it makes existing state unreadable. Do not restore an older unencrypted-only release onto encrypted state. Do not upload state or keys to Git. Encryption does not protect against root access or theft of both state and key. Telegram messages and existing backups are not encrypted by this feature.

CodeCraft forwards document content to the upstream provider; provider retention and possible error-log fragments still apply. Restrict operator/archive groups to authorized staff, enable Telegram 2FA and protected content, revoke unused invite links, and agree a document deletion schedule. Rotate any credentials previously shared in chat. No zero-leak guarantee is possible with external services.
