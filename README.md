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

### Local document OCR and privacy

The default backend is now **fast local Tesseract OCR** (`DOCUMENT_OCR_BACKEND=fast`). Install on the test VPS with `bash scripts/setup_fast_ocr.sh`. This installs system language packages, runs a real synthetic recognition check, preserves bot/Sheets settings, stops the Ollama service installed for this test, configures fast mode and restarts only `humobot-test`. No GPU, AI key or external inference is used. Document buffers pass to Tesseract via stdin/stdout in RAM, child processes do not inherit bot credentials, and no raw OCR text is logged. A batch has a 60-second work budget (plus engine preflight and cancellation cleanup); finished fields are kept, unknown/conflicting fields remain for manual review. Two OCR processes with one thread each limit CPU use. Supported rules target licence fields 3/4b/4d/5, complete PINFL tokens, labelled passport dates and upper-right registration serials. This is not a general document-understanding guarantee.

Measured in this workspace: a synthetic five-field licence was read correctly in 0.28s; the user's phone-screen licence example took 2.22s for three orientations and yielded PINFL and birth date, while the marked certificate example took 1.84s and its serial was not recovered. No private values/images are committed. These measurements are not VPS speed guarantees and do not establish complete real-document accuracy.

The following is the **optional slow legacy mode** (`DOCUMENT_OCR_BACKEND=ollama`), not the default. Its inference uses only `http://127.0.0.1:11434` with Ollama. The CodeCraft API route and cloud fallback have been removed. Even an old CodeCraft key left in the environment is not used. Approved local model tags are `qwen2.5vl:3b` and `qwen2.5vl:7b`; the setup installs 3b. Only passport, driving licence and registration certificate images are processed. Front/back images are read together, nearly white outer margins are trimmed with padding and images are capped at 1280 pixels on the long side to reduce CPU image encoding. Original Telegram photos are untouched. Metadata is stripped in RAM, conflicting readings remain empty, and operators must verify against the originals. Selfies and car photographs are not sent to the AI engine.

Only if deliberately selecting legacy Ollama mode, update code and dependencies, then run:

```bash
bash scripts/setup_local_ocr.sh
```

The root-only setup checks free RAM/disk, installs Ollama from the official installer if absent, downloads the public 3b model (~3.2GB), binds its API to loopback, disables cloud features and adds systemd network restrictions allowing only localhost after downloading. It limits parallelism to one, CPU to three cores and memory to 7GiB. No applicant data is used in installation. It runs a synthetic-image reading check before modifying `.env.test`, removes old CodeCraft settings without displaying them, checks the Telegram bot and restarts `humobot-test`. If it stops, read the error; do not manually enable a cloud fallback. Updating/replacing models later requires temporarily reviewing the network restriction. Never expose port 11434 through a reverse proxy, tunnel or public firewall rule. These settings affect this server's Ollama service, not other Telegram bot services.

Minimum setup guard: 6GiB available RAM and 10GiB free disk. These are starting checks, not a speed/accuracy guarantee. CPU-only inference can take minutes. Test real document accuracy and load before using this in production; a small local model can be less accurate than a large hosted model. The bot serializes inference and keeps partial results when one document group fails. Application albums and the operator control card are sent before OCR starts. The applicant receives their application code after Telegram delivery, without waiting for inference. A background task enriches the same control card later, using an application-owned snapshot. Controls stay available; edits share a lock with operator actions. Moves preserve OCR state and follow the confirmed destination. Deleted/archived applications are not recreated; deleting the last active record cancels its queued task. Pending snapshots are persisted and scheduled again after restart. OCR latency is still minutes on a CPU-only server and is not an admission delay. Requests have a 360-second read timeout and extraction has a 1140-second overall budget; timed-out fields stay empty. Set `DOCUMENT_AI_ENABLED=0` to disable all inference, then restart the bot. Cached OCR values from previous engines are not reused for a new submission retry.

State is encrypted using authenticated Fernet encryption. Trusted legacy `bot_persistence.pkl` state is migrated in place; the sibling `bot_persistence.key` is generated with mode 0600. Preserve this key in a separate secure backup: losing it makes existing state unreadable. Do not restore an unencrypted-only release onto encrypted state. Do not upload state or keys to Git. Encryption does not protect against root access or theft of both state and key. Telegram messages and existing backups are not encrypted by this feature.

Images and raw OCR text are not intentionally written to disk by our OCR code, but operating-system swap, core dumps, backups and administrative access remain separate risks. The Ollama service disables core dumps. Keep the server and dependencies patched; restrict operator/archive groups, enable Telegram 2FA and protected content, revoke unused invites, agree a document deletion schedule and rotate credentials shared in chat. Telegram still carries applicant documents. Local AI removes the external AI-provider path; it is not a guarantee of no data leakage anywhere.

CPU tuning: JSON schema constrains the output to requested fields, output budget is 384 tokens, three CPU threads are requested, and the model stays loaded for up to two minutes between requests. This retains its process/RAM for that interval; it does not write our document buffers to disk. A synthetic PINFL sample previously took 196.8s on the deployment VPS before this tuning. Re-measure with `venv/bin/python scripts/check_local_ocr.py --smoke` after updating. Smaller images can lose fine text: neither latency improvement nor real-document accuracy is guaranteed by the synthetic test. Do not run the setup/restart until the new check passes.

### Brand spreadsheet export

Optional signed Apps Script receiver and encrypted pending outbox are included for Brend and Spectre. Toshkent/Namangan Brend map to their existing city tabs; both Spectre flows map to the separate workbook’s existing `Лист1` tab. Setup and privacy details: [BRAND_SHEETS_SETUP.md](BRAND_SHEETS_SETUP.md). Supply and verify the actual spreadsheet/tab before enabling; this feature has not yet been connected to a live user spreadsheet.


### Optional local neural OCR

The Tesseract-only path can time out on textured document photos. On the test
server run `bash scripts/setup_neural_ocr.sh` to install the optional bundled
RapidOCR ONNX models and select `DOCUMENT_OCR_BACKEND=rapid`. The script smoke
tests generated text before changing configuration and preserves existing
Telegram/Sheets settings. Models run in a separate process with no inherited
bot credentials; document bytes use pipes, with no document files or raw-text logs.

The worker prioritizes licence front and registration reverse, uses two CPU
threads, and stops after 10 seconds, preserving complete per-image results
already emitted. Telegram downloads have a separate six-second timeout; the
entire Telegram-to-card operation is **not guaranteed to take 10 seconds**.
No external AI fallback is enabled. On two private example photos, this build
recovered PINFL, licence number, expiry and registration serial in approximately
three seconds including worker startup. Birth date/place remained unread; two
photos are not a representative accuracy benchmark. Operators must verify values.
The alternate model is focused on Latin/digits; Cyrillic birthplace support is
limited. Original fast/ollama modes remain explicitly selectable.
