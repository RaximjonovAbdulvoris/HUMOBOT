# Brend → Google Sheets

This optional integration exports ONLY brand applications: application code, timestamp (Asia/Tashkent), region, name, phone, vehicle model/year/color/plate, Telegram username and ID. It does not export passport images, PINFL, OCR results or Spectre applications. Google will process the exported brand data; keep the destination spreadsheet private. The bot retains pending rows in its encrypted persistence and retries every 30 seconds. Confirmed rows lose their local payload; a receipt keyed by application code remains. A failed spreadsheet export does not block Telegram submission.

## Connect your existing spreadsheet

1. Supply the exact destination spreadsheet URL and tab layout before connecting. Prefer a separate empty `Brend` tab. The supplied receiver refuses to overwrite incompatible headers.
2. In that spreadsheet, open **Extensions → Apps Script**. Paste the code from `integrations/brand_sheets.gs`.
3. In Apps Script **Project Settings → Script properties**, set:
   - `SPREADSHEET_ID`: your spreadsheet's verified ID.
   - `SHEET_NAME`: `Brend` (or an agreed empty tab name).
   - `HUMO_SECRET`: a random secret at least 32 characters long. Generate on your own server using `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`. Store it privately; do not paste it into chat/GitHub.
4. **Deploy → New deployment → Web app**, execute as **Me**, access **Anyone** (if allowed by your Google Workspace policy), and authorize the script. The endpoint is public, but accepts only timestamped HMAC-signed requests. This does not make the spreadsheet public. Use the deployment URL ending in `/exec`, not `/dev`.
5. Put the deployment URL and same secret in the server's private `.env.test`:
   ```dotenv
   BRAND_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
   BRAND_SHEETS_SECRET=YOUR_PRIVATE_RANDOM_SECRET
   ```
   Keep `.env.test` mode 0600. The test runner reads these two settings; standard deployment reads environment variables.
6. Restart `humobot-test` after saving. Send one authorized test brand application and verify its code appears exactly once in the intended tab. This repository's tests do not prove live Google permissions or successful deployment.

The receiver serializes requests with ScriptLock and checks the application-code column before appending, so retries after an ambiguous response cannot duplicate rows. All incoming cells are treated as text; formula-leading characters are escaped. Only HTTPS Apps Script deployment URLs are accepted, and the client follows only the Google ContentService result redirect with a body-free GET. No bot/API secrets are sent to Google. Do not log request payloads or change the receiver to return spreadsheet contents.

Rows queued before configuration are exported once configuration is added. Repeated transport failures keep a row pending; inspect service logs and the destination. No historical reconstruction of applications submitted before this feature is included. Keep the persistence key backup safe. If Apps Script source changes, update its deployment version as well.

Offline validation:

```bash
venv/bin/python -m unittest discover -s tests -q
node tests/test_brand_sheets_receiver.js
```
