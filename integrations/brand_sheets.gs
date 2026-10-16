// Install in YOUR Google Sheet's Apps Script project.
// Script properties: SPREADSHEET_ID, SHEET_NAME, HUMO_SECRET (32+ random characters).
const HUMO_HEADERS = ['Ariza kodi', 'Sana', 'Hudud', 'F.I.Sh.', 'Telefon', 'Model',
  'Yili', 'Rangi', 'Davlat raqami', 'Telegram username', 'Telegram ID'];

function humoReply(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
function doPost(e) {
  try {
    const props = PropertiesService.getScriptProperties();
    const secret = props.getProperty('HUMO_SECRET');
    if (!secret || secret.length < 32 || !e.postData || e.postData.length > 12000)
      return humoReply({ok: false});
    const request = JSON.parse(e.postData.contents);
    if (!/^\d{10,11}$/.test(String(request.timestamp)) ||
        Math.abs(Date.now() / 1000 - Number(request.timestamp)) > 300 ||
        typeof request.payload !== 'string' || typeof request.signature !== 'string')
      return humoReply({ok: false});
    const bytes = Utilities.computeHmacSha256Signature(
      String(request.timestamp) + '.' + request.payload, secret, Utilities.Charset.UTF_8);
    const signature = bytes.map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
    let diff = signature.length ^ request.signature.length;
    for (let i = 0; i < signature.length; i++)
      diff |= signature.charCodeAt(i) ^ (request.signature.charCodeAt(i) || 0);
    if (diff !== 0) return humoReply({ok: false});
    const payload = JSON.parse(Utilities.newBlob(Utilities.base64Decode(request.payload))
      .getDataAsString('UTF-8'));
    if (!/^HM-\d{6,}$/.test(payload.code) || !Array.isArray(payload.row) ||
        payload.row.length !== HUMO_HEADERS.length || payload.row[0] !== payload.code ||
        payload.row.some(value => typeof value !== 'string' || value.length > 500))
      return humoReply({ok: false});
    const lock = LockService.getScriptLock();
    lock.waitLock(15000);
    try {
      const spreadsheet = SpreadsheetApp.openById(props.getProperty('SPREADSHEET_ID'));
      const name = props.getProperty('SHEET_NAME') || 'Brend';
      const sheet = spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
      if (sheet.getLastRow() === 0) {
        sheet.getRange(1, 1, 1, HUMO_HEADERS.length).setValues([HUMO_HEADERS]);
        sheet.setFrozenRows(1);
      }
      const headers = sheet.getRange(1, 1, 1, HUMO_HEADERS.length).getDisplayValues()[0];
      if (headers.some((header, index) => header !== HUMO_HEADERS[index]))
        return humoReply({ok: false}); // Do not overwrite an existing incompatible sheet.
      const count = sheet.getLastRow();
      if (count > 1 && sheet.getRange(2, 1, count - 1, 1).createTextFinder(payload.code)
          .matchEntireCell(true).findNext())
        return humoReply({ok: true, code: payload.code, duplicate: true});
      // Force text; apostrophe additionally prevents spreadsheet formula injection.
      const row = payload.row.map(value => /^[=+@\-\t\r]/.test(value) ? "'" + value : value);
      const range = sheet.getRange(count + 1, 1, 1, HUMO_HEADERS.length);
      range.setNumberFormat('@');
      range.setValues([row]);
      SpreadsheetApp.flush();
      return humoReply({ok: true, code: payload.code});
    } finally {
      lock.releaseLock();
    }
  } catch (error) {
    // No payload, applicant data, or secrets in logs/responses.
    return humoReply({ok: false});
  }
}
