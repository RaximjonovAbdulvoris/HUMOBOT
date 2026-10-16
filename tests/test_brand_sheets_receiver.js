const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');
const secret = 'synthetic-test-secret-not-real-123456';
const brandHeaders = ['Модель авто', 'Год выпуска', 'Цвет', 'ФИО водителя', 'Номер авто',
  'Контакт', 'Парк', 'Дата добавления', 'Комментарии от WB'];
let failAfterValues = false;
function sheet(rows) {
  const result = {rows, notes: [], maxRows: 30};
  result.getLastRow = () => result.rows.length;
  result.getMaxRows = () => result.maxRows;
  result.insertRowsAfter = (row, count) => { result.maxRows += count; };
  result.getRange = (row, col, height = 1, width = 1) => {
    const range = {};
    range.getValues = () => Array.from({length: height}, (_, r) => Array.from({length: width}, (_, c) =>
      result.rows[row - 1 + r]?.[col - 1 + c] ?? ''));
    range.getDisplayValues = () => range.getValues().map(r => r.map(value => String(value)));
    range.getNotes = () => Array.from({length: height}, (_, r) => [result.notes[row - 1 + r] || '']);
    range.setNote = value => { result.notes[row - 1] = value; return range; };
    range.setValues = values => {
      for (let r = 0; r < height; r++) {
        result.rows[row - 1 + r] ||= [];
        for (let c = 0; c < width; c++) result.rows[row - 1 + r][col - 1 + c] = values[r][c];
      }
      if (failAfterValues) { failAfterValues = false; throw Error('simulated lost acknowledgment'); }
      return range;
    };
    for (const name of ['setBackground', 'setFontColor', 'setFontWeight', 'setNumberFormat', 'copyTo'])
      range[name] = () => range;
    return range;
  };
  return result;
}
const tashkent = sheet([[], [...brandHeaders], ['EXAMPLE', 2026, 'White', 'EXAMPLE', '01A000AA', '998000000000', 'HUMO', '', 'EXAMPLE COMMENT']]);
const namangan = sheet([[], [...brandHeaders], [...tashkent.rows[2]]]);
const spectre = sheet([
  [' ', 'KUN/OY/YIL', 'ISM FAMILYA', 'TELEFON NO`MER', 'MOSHINA', 'DAVLAT RAQAMI'],
  [1, '', 'EXAMPLE', '998000000000', 'EXAMPLE', '01A000AA'],
  ['', '', '', '', '', '', '', 'Rang', 'Tavsif']
]);
const context = {
  ContentService: {MimeType: {JSON: 'application/json'}, createTextOutput: text => ({setMimeType: () => JSON.parse(text)})},
  PropertiesService: {getScriptProperties: () => ({getProperty: key => ({HUMO_SECRET: secret,
    BRAND_SPREADSHEET_ID: 'brand-book', SPECTRE_SPREADSHEET_ID: 'spectre-book'})[key]})},
  Utilities: {Charset: {UTF_8: 'utf8'}, DigestAlgorithm: {SHA_256: 'sha256'},
    computeHmacSha256Signature: (value, key) => [...crypto.createHmac('sha256', key).update(value).digest()],
    computeDigest: (algorithm, value) => [...crypto.createHash('sha256').update(value).digest()],
    base64Decode: value => Buffer.from(value, 'base64'), newBlob: value => ({getDataAsString: () => value.toString('utf8')})},
  LockService: {getScriptLock: () => ({waitLock: () => {}, releaseLock: () => {}})},
  SpreadsheetApp: {CopyPasteType: {PASTE_FORMAT: 'format'}, openById: id => ({getSheetByName: tab =>
    id === 'brand-book' ? ({'Ташкент': tashkent, 'Наманган': namangan})[tab]
      : id === 'spectre-book' && tab === 'Лист1' ? spectre : null}), flush: () => {}}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('integrations/brand_sheets.gs', 'utf8'), context);
function request(code = 'HM-000001', kind = 'brand', region = 'tashkent', age = 0) {
  const fields = {name: '=1+1', phone: '+998000000000', model: 'TEST', year: '2020', color: 'White', plate: '01A123BC'};
  const payload = Buffer.from(JSON.stringify({code, kind, region, created_at: '2026-01-01T10:00:00+05:00', fields})).toString('base64');
  const timestamp = String(Math.floor(Date.now() / 1000) - age);
  const signature = crypto.createHmac('sha256', secret).update(timestamp + '.' + payload).digest('hex');
  const contents = JSON.stringify({timestamp, payload, signature});
  return {postData: {contents, length: contents.length}};
}
assert.equal(context.doPost(request()).ok, true);
assert.equal(tashkent.rows.length, 4);
assert.equal(namangan.rows.length, 3);
assert.equal(tashkent.rows[3][0], 'TEST');
assert.equal(tashkent.rows[3][1], 2020);
assert.equal(tashkent.rows[3][3], "'=1+1");
assert.equal(tashkent.rows[3][5], '998000000000');
assert.equal(tashkent.rows[3][6], 'HUMO');
assert.equal(tashkent.rows[3][8], undefined);
assert.equal(tashkent.rows[2][8], 'EXAMPLE COMMENT');
assert.equal(context.doPost(request()).duplicate, true);
assert.equal(tashkent.rows.length, 4);
assert.equal(context.doPost(request('HM-000002', 'brand', 'namangan')).ok, true);
assert.equal(namangan.rows.length, 4);
assert.equal(context.doPost(request('HM-000003', 'spectre', 'tashkent')).ok, true);
assert.equal(context.doPost(request('HM-000004', 'spectre', 'namangan')).ok, true);
assert.equal(spectre.rows[3][0], 2);
assert.equal(spectre.rows[4][0], 3);
assert.equal(spectre.rows[2][7], 'Rang');
assert.equal(context.doPost(request('HM-000005', 'brand', 'unknown')).ok, false);
assert.equal(context.doPost(request('HM-000005', 'brand', 'tashkent', 600)).ok, false);
const tampered = request('HM-000005');
const body = JSON.parse(tampered.postData.contents); body.signature = '0'.repeat(64);
tampered.postData.contents = JSON.stringify(body);
assert.equal(context.doPost(tampered).ok, false);
// Lost response after committing values: same reserved row must be recovered.
failAfterValues = true;
assert.equal(context.doPost(request('HM-000006')).ok, false);
const count = tashkent.rows.length;
assert.equal(context.doPost(request('HM-000006')).ok, true);
assert.equal(tashkent.rows.length, count);
assert.equal(context.doPost(request('HM-000006')).duplicate, true);
tashkent.rows[1][0] = 'Changed existing header';
assert.equal(context.doPost(request('HM-000007')).ok, false);
console.log('Receiver passed: regional routes, Spectre columns/counter, preserved comments/legend, signatures, duplicate/recovery checks.');
