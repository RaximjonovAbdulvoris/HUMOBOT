# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

GitHub destination: https://github.com/RaximjonovAbdulvoris/HUMOBOT (`main`).
The user replaced the former HUMO-NAMANGAN destination with NAMANTOSH.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally
- `python -m bot.main` — run the WB TAXI HUMO Telegram bot locally

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

## WB TAXI HUMO Telegram Bot

Located in `bot/`. Long-polling Python Telegram bot built with `python-telegram-bot` 21.

- `bot/main.py` — entry point, registers conversation handlers
- `bot/config.py` — loads `TELEGRAM_BOT_TOKEN`, 2× `DRIVER_GROUP_*`, `BRAND_GROUP`, and optional `ARCHIVE_GROUP` from env
- `bot/handlers/start.py` — region selection, explicit confirmation and regional menus. Both city menus have driver, brand, Spectre Energy, contact, and office entries. Tashkent contact and office details are configured separately in this file.
- `bot/handlers/driver.py` — driver registration: name → phone → document photos → car photos → plate. Sends albums to one operator group, rotating within the selected region.
- `bot/handlers/brand.py` — branding application: eligibility warning → name → phone → model → year → color → plate. Spectre Energy in both cities asks the same fields without assuming branding eligibility restrictions.
- Brand applications and Spectre applications in both cities are plain messages: no operator buttons, comment relay, or archiving. Startup removes old stored brand/Spectre keyboards without deleting their messages. Operator controls are only for driver applications.
- For an old Spectre/Brand message absent from persistence, an identifiable group administrator can reply to that bot-authored application with `/tugmasiz`. This edits only its buttons; it never deletes or archives the application. Clicking a stale operator button on an identifiable Spectre/Brand form also disables it even without a stored record. GitHub pushes do not update the separately hosted server process: pull and restart there.
- New driver applications preserve photo file IDs and captions for explicit album reconstruction in the archive (maximum 10 photos per album, normally main 10 + selfie/license 2). Legacy records without these file IDs retain batch-copy compatibility; existing archived photos are not retroactively regrouped. Sources are deleted only after all albums and the information message are confirmed.
- `bot/subscription.py` — common membership gate for all application types, using @WB_HUMO_TAXI.
- `bot/regions.py` — regional destinations. DRIVER_GROUP_1–2, BRAND_GROUP and ARCHIVE_GROUP are Namangan settings; DRIVER_GROUP_3–4 are no longer used. Never reuse Namangan destinations as a fallback for missing Tashkent destinations.
- User-facing city menu and contact/office text must use city wording and must not use “filial” wording.
- `bot/handlers/operator.py` — records are isolated by source chat/message; operator replies and archive destinations follow the application's region, not the applicant's current menu.
- `bot/templates/` — optional template images (`passport_front.jpg`, etc.) shown to the user when each photo is requested. See `bot/templates/README.md`.

Workflow: `Telegram Bot` (console output, command `python -m bot.main`).

### Tashkent destination setup

Provide numeric Telegram chat IDs (typically starting with `-100`) in:

- `TASHKENT_DRIVER_GROUP_1` — driver applications; optional `TASHKENT_DRIVER_GROUP_2` enables rotation between two groups.
- `TASHKENT_BRAND_GROUP` — brand applications.
- `TASHKENT_SPECTRE_GROUP` — Spectre Energy applications.
- `TASHKENT_ARCHIVE_GROUP` — completed Tashkent applications.

Several application types may intentionally use the same Tashkent group ID.

### Configure Tashkent from Windows CMD / Linux terminal

Run in the project folder on **the same machine/container running the bot**:

```sh
python -m bot.configure tashkent
```

This prompts for both driver group IDs, brand, Spectre Energy, and archive.
Enter keeps an existing value; `none` disables the optional second driver group.
It works without a bot token for configuration (the token remains environment-only).
For noninteractive setup, replace the example IDs with real negative group IDs:

```sh
python -m bot.configure tashkent --driver1=-1001111111111 --driver2=-1002222222222 --brand=-1003333333333 --spectre=-1004444444444 --archive=-1005555555555
python -m bot.configure show
python -m bot.configure check
```

### Configure Namangan Spectre Energy

`NAMANGAN_SPECTRE_GROUP` is optional and independent of the existing Namangan
destinations. Configure its local override interactively with the single Spectre
group ID prompt:

```sh
python3 -m bot.configure namangan
```

Or configure it noninteractively (replace the example with the real negative ID):

```sh
python3 -m bot.configure namangan --spectre=-1006666666666
```

The existing `python -m bot.configure check` checks Tashkent only, so a missing
Namangan Spectre destination does not break that check. Select a scope explicitly:

```sh
python3 -m bot.configure check --scope namangan
python3 -m bot.configure check --scope tashkent
python3 -m bot.configure check --scope all
```

Re-running the command updates IDs. Local overrides take precedence over environment
variables; absent keys still use environment variables. Changes are read for new
applications without a restart. Pending applications retain their stored destinations.
Settings live in `bot_routes.json` under `PERSIST_DIR`, or the project root by default.
Keep that directory on durable storage. The file is ignored by Git; configuring your
PC does not configure a bot running on a different server.
`check` makes read-only Telegram requests to check bot authentication, destination
access, administrator/deletion permissions, and subscription-channel administration.
It does not send test applications or start a second polling process.

The bot needs permission to send messages/photos in destination groups and to
delete originals in operator groups. It must be an admin of the shared
subscription channel to reliably check membership. Missing destinations block
the affected form before collection. Missing/unavailable archives do not delete
the original application.

One combined conversation handles both forms; `/start` and “Hududni almashtirish”
discard incomplete form data and require a new region confirmation. `/cancel`
returns to the confirmed region's menu. Preserve `bot_persistence.pkl` on durable
storage (`PERSIST_DIR`) across restarts to retain pending applications and relay
metadata. Do not commit persistence data or credentials.

Offline checks: `python -m unittest discover -s tests -v`. Tests use mocked
Telegram calls and do not send real applications.

### CodeCraft document extraction (local integration)

Set `CODECRAFT_API_KEY` in the server environment; optionally set
`CODECRAFT_VISION_MODEL` (default `gpt-5.6-luna`, advertised with vision by
CodeCraft). No key is committed. `deploy.sh` loads `.env` with systemd.
Direct `python -m bot.main` requires environment variables to be exported first.

At submission, `bot/document_ocr.py` reads the six passport/licence/vehicle
registration photos via Telegram, and sends their bytes to CodeCraft's fixed
`https://codecraftapi.com/v1/chat/completions` endpoint. No selfie or car photos
are sent to AI. Telegram download URLs and bot tokens are never sent to CodeCraft.
The six requested fields appear as escaped, copyable code text in the operator
control message, which follows the existing archive and delete lifecycle.
Missing, invalid or conflicting values are labelled for manual checking; AI
results always require comparison with the original documents. API failure does
not prevent submission of the original photos. Extraction is cached per form
for retries, requests are bounded, and document bytes/responses are not logged.
A missing key leaves extraction unavailable rather than fabricating values.

Local mocked tests verify the integration. Live authentication/model/OCR accuracy
was not verified: the CodeCraft endpoint returned Cloudflare 403 (1010) from the
review environment. Check from the actual bot server before enabling in production.

Operator controls now have Ready, Progress, Incomplete photos, Other park, Delete.
The two review actions move the application to their configured review groups; a
successfully sent notice is not repeated for the same application and notice type.
Delete removes only stored source photo/control IDs, and retains the control
message if a photo cannot be removed. All actions require a group administrator.
Stored driver keyboards are refreshed on startup; untracked old applications
cannot be reconstructed from Telegram message history. The old comment button
is retired; already pending conversations retain compatibility.

### Isolated test run

`python scripts/run_test_bot.py` loads ignored `.env.test`, verifies the exact
`@testthumo_bot` identity and administrator/deletion access to the four provided
test groups, and uses isolated `.test-bot-state` persistence. Both city menus
route only to those test groups. Subscription checks are bypassed only by this
test runner; Ready/archive stays disabled until ARCHIVE_GROUP is provided in .env.test.
`--check` performs read-only preflight and exits. Do not run a second instance
while this token is already polling. This is a temporary test process, not a
24/7 deployment. The normal production entry point remains `python -m bot.main`.

Review queue moves now preserve confirmed destination IDs and expose Ready/Delete/Progress. The test runner uses the two user-provided review IDs and accepts ARCHIVE_GROUP. Emoji icons resolve from the four user-selected sets at startup. See README.md for recovery and setup.
