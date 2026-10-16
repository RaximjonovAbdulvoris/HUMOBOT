// ONE standalone or bound Apps Script web app routes both workbooks.
// Private Script properties: HUMO_SECRET, BRAND_SPREADSHEET_ID, SPECTRE_SPREADSHEET_ID.
const BRAND_HEADERS = ['Модель авто', 'Год выпуска', 'Цвет', 'ФИО водителя',
  'Номер авто', 'Контакт', 'Парк', 'Дата добавления', 'Комментарии от WB'];
const SPECTRE_HEADERS = ['KUN/OY/YIL', 'ISM FAMILYA', 'TELEFON NO`MER', 'MOSHINA', 'DAVLAT RAQAMI'];
function humoReply(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
function humoText(value) {
  return /^[=+@\-\t\r]/.test(value) ? "'" + value : value;
}
function humoHex(bytes) {
  return bytes.map(b => ('0' + ((b + 256) % 256).toString(16)).slice(-2)).join('');
}
function humoRoute(payload) {
  if (!['brand', 'spectre'].includes(payload.kind) || !['tashkent', 'namangan'].includes(payload.region))
    throw new Error('Unknown route');
  return payload.kind === 'brand'
    ? {property: 'BRAND_SPREADSHEET_ID', tab: payload.region === 'tashkent' ? 'Ташкент' : 'Наманган', width: 8}
    : {property: 'SPECTRE_SPREADSHEET_ID', tab: 'Лист1', width: 6};
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
    const signature = humoHex(Utilities.computeHmacSha256Signature(
      String(request.timestamp) + '.' + request.payload, secret, Utilities.Charset.UTF_8));
    let diff = signature.length ^ request.signature.length;
    for (let i = 0; i < signature.length; i++)
      diff |= signature.charCodeAt(i) ^ (request.signature.charCodeAt(i) || 0);
    if (diff !== 0) return humoReply({ok: false});
    const payload = JSON.parse(Utilities.newBlob(Utilities.base64Decode(request.payload)).getDataAsString('UTF-8'));
    const fields = payload.fields;
    if (!/^HM-\d{6,}$/.test(payload.code) || !fields ||
        ['name', 'phone', 'model', 'year', 'color', 'plate'].some(key =>
          typeof fields[key] !== 'string' || !fields[key].trim() || fields[key].length > 500) ||
        !/^\d{4}$/.test(fields.year) || !/^\d{4}-\d{2}-\d{2}T/.test(payload.created_at))
      return humoReply({ok: false});
    const date = new Date(payload.created_at);
    if (isNaN(date.getTime())) return humoReply({ok: false});
    const route = humoRoute(payload);
    const lock = LockService.getScriptLock();
    lock.waitLock(15000);
    try {
      const spreadsheet = SpreadsheetApp.openById(props.getProperty(route.property));
      const sheet = spreadsheet.getSheetByName(route.tab);
      if (!sheet) return humoReply({ok: false}); // Never create a guessed tab.
      const headers = payload.kind === 'brand'
        ? sheet.getRange(2, 1, 1, 9).getDisplayValues()[0]
        : sheet.getRange(1, 2, 1, 5).getDisplayValues()[0];
      const expected = payload.kind === 'brand' ? BRAND_HEADERS : SPECTRE_HEADERS;
      if (headers.some((value, index) => value.trim() !== expected[index]) || headers.length !== expected.length)
        return humoReply({ok: false});
      // Cell notes preserve idempotency without adding columns or using WB's comments.
      // Reserve before writing; a retry can safely finish an interrupted row.
      const marker = 'HUMOBOT:' + payload.kind + ':' + payload.region + ':' + payload.code;
      const fingerprint = humoHex(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,
        JSON.stringify(payload), Utilities.Charset.UTF_8));
      const notes = sheet.getRange(1, 1, sheet.getMaxRows(), 1).getNotes();
      let reserved = 0, noteEdge = 0, saved = null;
      for (let i = 0; i < notes.length; i++) {
        const text = notes[i][0];
        if (text && text.startsWith('HUMOBOT:')) {
          noteEdge = i + 1;
          const lines = text.split('\n');
          if (lines[0] === marker) { reserved = i + 1; saved = lines; }
        }
      }
      if (saved && saved[1] !== fingerprint) return humoReply({ok: false});
      if (saved && saved[2] === 'DONE') return humoReply({ok: true, code: payload.code, duplicate: true});
      const row = reserved || Math.max(sheet.getLastRow(), noteEdge, payload.kind === 'brand' ? 3 : 2) + 1;
      if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), row - sheet.getMaxRows());
      const phone = fields.phone.replace(/[^0-9]/g, '');
      const textValues = payload.kind === 'brand'
        ? [fields.model, fields.year, fields.color, fields.name, fields.plate, phone, 'HUMO', payload.created_at]
        : ['', payload.created_at, fields.name, phone, fields.model, fields.plate];
      const range = sheet.getRange(row, 1, 1, route.width);
      if (reserved) {
        // An interrupted reservation must never overwrite a human-edited row.
        const current = range.getValues()[0];
        const dateColumn = payload.kind === 'brand' ? 7 : 1;
        for (let i = 0; i < current.length; i++) {
          if (current[i] === '') continue;
          const value = current[i] instanceof Date ? current[i].getTime() : String(current[i]).replace(/^'/, '');
          const wanted = i === dateColumn ? date.getTime() : textValues[i];
          if (i === 0 && payload.kind === 'spectre') continue; // sequential counter
          if (value !== wanted) return humoReply({ok: false});
        }
      }
      const first = sheet.getRange(row, 1);
      first.setNote(marker + '\n' + fingerprint + '\nPENDING');
      SpreadsheetApp.flush();
      // Copy ONLY formatting, not personal sample values, formulas or chips.
      const template = payload.kind === 'brand' ? 3 : 2;
      sheet.getRange(template, 1, 1, route.width).copyTo(range, SpreadsheetApp.CopyPasteType.PASTE_FORMAT, false);
      range.setBackground('#ffffff').setFontColor('#000000').setFontWeight('normal');
      range.setNumberFormat('@');
      const values = textValues.map(humoText);
      if (payload.kind === 'brand') {
        values[1] = Number(fields.year);
        values[7] = date;
      } else {
        const prior = sheet.getRange(2, 1, Math.max(1, row - 2), 1).getValues();
        values[0] = prior.reduce((max, entry) => Math.max(max, Number(entry[0]) || 0), 0) + 1;
        values[1] = date;
      }
      range.setValues([values]);
      if (payload.kind === 'brand') {
        sheet.getRange(row, 2).setNumberFormat('0');
        sheet.getRange(row, 8).setNumberFormat('dd/MM/yyyy');
      } else {
        sheet.getRange(row, 1).setNumberFormat('0');
        sheet.getRange(row, 2).setNumberFormat('dd,MM,yyyy');
      }
      first.setNote(marker + '\n' + fingerprint + '\nDONE');
      SpreadsheetApp.flush();
      return humoReply({ok: true, code: payload.code, tab: route.tab});
    } finally { lock.releaseLock(); }
  } catch (error) { return humoReply({ok: false}); }
}
