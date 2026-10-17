# Brend va Spectre → mavjud Google jadvallari

ONE signed Apps Script web app routes the two user-selected workbooks. Spreadsheet IDs are private Script properties, never embedded in source. The Apps Script owner must have edit access to both files. The workbook/tab metadata and header cells were inspected before this mapping was implemented.

| Bot flow | Workbook property | Exact tab | Written columns |
| --- | --- | --- | --- |
| Toshkent Brend | `BRAND_SPREADSHEET_ID` | `Ташкент` | A:H |
| Namangan Brend | `BRAND_SPREADSHEET_ID` | `Наманган` | A:H |
| Toshkent Spectre | `SPECTRE_SPREADSHEET_ID` | `Лист1` | A:F |
| Namangan Spectre | `SPECTRE_SPREADSHEET_ID` | `Лист1` | A:F |

Brand row 2 headers are checked before every write. Values are written as: model, year, color, driver name, vehicle plate, phone, HUMO, submission date. Column I (`Комментарии от WB`) is not written. Headers and example row 3 are retained. Spectre row 1 headers B:F are checked; values are sequential number, submission date, driver name, phone, vehicle model, plate. The H:I color/status legend is not written. Other existing tabs, data, formulas and comments are preserved. New rows receive neutral formatting copied without sample values. Year/date values are native numbers/dates; phone and plate are text.

The receiver does NOT create tabs or choose a fallback region. A changed header or missing tab blocks that export. Only the explicitly configured files are writable; request payloads cannot supply arbitrary spreadsheet IDs or ranges.

## Enable

1. Open **script.google.com → New project** and create a SEPARATE Apps Script project. Paste the complete `integrations/brand_sheets.gs` source there. Do not overwrite any existing workbook automation project or an existing `doPost` handler.
2. **Project Settings → Script properties**:
   - `BRAND_SPREADSHEET_ID`: ID from the user's BRAND workbook URL.
   - `SPECTRE_SPREADSHEET_ID`: ID from the user's SPECTRE workbook URL.
   - `HUMO_SECRET`: a random secret at least 32 characters long. Generate privately on the VPS with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`. Do not send this secret in chat or commit it.
3. **Deploy → New deployment → Web app**, execute as **Me**, access **Anyone** (if the account policy permits), and authorize access to both workbooks. The URL ends in `/exec`. A public endpoint does not make the spreadsheets public: unsigned/expired requests are rejected and the receiver never returns sheet contents.
4. Put that URL and the SAME secret in `/root/HUMOBOT/.env.test` (mode 0600):
   ```dotenv
   BRAND_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
   BRAND_SHEETS_SECRET=YOUR_PRIVATE_RANDOM_SECRET
   ```
5. Update bot code, then restart `humobot-test`. Send one authorized real test application per flow and verify the intended destination. No fabricated test rows have been inserted by ChatGPT. Offline tests do not prove live Google deployment/permissions.

If an older receiver was already deployed, replace its source, replace obsolete `SPREADSHEET_ID`/`SHEET_NAME` properties with the two properties above, and update the deployment's version. The webhook URL can stay the same. The server migrates old pending brand payloads using their saved region. New Spectre exports are queued too. Applications submitted before export support are not reconstructed automatically.

## Reliability and privacy

Pending payloads are stored inside the bot's encrypted persistence. A periodic worker retries every 30 seconds without blocking Telegram delivery. A failing row does not prevent later rows for other regions from being tried. Confirmed rows lose their local payload; an application-code receipt remains.

ScriptLock serializes requests. An application-code marker and payload fingerprint are stored as a note on the first cell of each new row, preserving the visible column layout. A PENDING reservation is flushed before values are written, and retries finish the same row instead of adding duplicates, including after an ambiguous response. Human edits conflicting with an interrupted row are not overwritten. Do not remove bot notes while exports may be retried.

Only name, phone, model, year, color, plate, submission time, region, flow and code are sent to the authenticated Google receiver. Passport photos, PINFL, OCR results and Telegram profile identifiers are not exported. Both the bot and the receiver avoid logging request contents. Formula-leading user input is escaped. The bot accepts only HTTPS Apps Script deployment endpoints and follows only Google's response redirect with a body-free GET. Use `venv/bin/python scripts/configure_brand_sheets.py` on the VPS to enter the deployment URL and shared secret without placing the secret in shell history.

Keep spreadsheet sharing restricted; Google processes these exported application details.

Offline validation:

```bash
venv/bin/python -m unittest discover -s tests -q
node tests/test_brand_sheets_receiver.js
```
# Operator approval

Brend arizasi avval hududdagi operator guruhiga yuboriladi. Guruh administratori
**Tasdiqlansin** tugmasini bosgandan keyingina ariza Google Sheets navbatiga
qo‘shiladi. Muvaffaqiyatli yozilgach guruh postida «Tasdiqlandi va Google
Sheetsga to‘ldirildi» ko‘rinadi. **To‘g‘ri kelmadi** bosilsa ariza Sheetsga
yuborilmaydi, arizachiga xabar boradi va guruh posti o‘chiriladi. Spectre
arizalarining avvalgi avtomatik yuborish tartibi saqlanadi.

Ilgari navbatda qolgan, operator tomonidan tasdiqlanmagan Brend arizalari
avtomatik eksport qilinmaydi. Botni yangilash uchun VPSda `git pull --ff-only`
va `systemctl restart humobot-test` buyrug‘ini bajaring; botga operator guruhidagi
xabarlarni o‘chirish huquqi kerak.
