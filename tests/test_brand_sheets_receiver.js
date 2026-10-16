// Test the actual Apps Script receiver with in-memory Google service doubles.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const vm = require('node:vm');
const secret = 'synthetic-test-secret-not-real-123456';
let rows = [];
let frozen = 0;
const sheet = {
  getLastRow: () => rows.length,
  setFrozenRows: value => { frozen = value; },
  getRange: (row, col, height, width) => ({
    setValues: values => { rows[row - 1] = [...values[0]]; },
    getDisplayValues: () => [rows[row - 1] || []],
    setNumberFormat: () => {},
    createTextFinder: code => ({matchEntireCell: () => ({
      findNext: () => rows.slice(row - 1, row - 1 + height).some(r => r[0] === code) ? {} : null
    })})
  })
};
const context = {
  ContentService: {MimeType: {JSON: 'application/json'},
    createTextOutput: text => ({setMimeType: () => JSON.parse(text)})},
  PropertiesService: {getScriptProperties: () => ({getProperty: key => ({
    HUMO_SECRET: secret, SPREADSHEET_ID: 'synthetic-sheet-id', SHEET_NAME: 'Brend'
  })[key]})},
  Utilities: {
    Charset: {UTF_8: 'utf8'},
    computeHmacSha256Signature: (value, key) => [...crypto.createHmac('sha256', key).update(value).digest()],
    base64Decode: value => Buffer.from(value, 'base64'),
    newBlob: value => ({getDataAsString: () => value.toString('utf8')})
  },
  LockService: {getScriptLock: () => ({waitLock: () => {}, releaseLock: () => {}})},
  SpreadsheetApp: {openById: () => ({getSheetByName: () => sheet}), flush: () => {}}
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('integrations/brand_sheets.gs', 'utf8'), context);
function request(code = 'HM-000001', age = 0) {
  const row = [code, '2026-01-01', 'Test', '=1+1', '+998000000000', 'Test',
    '2020', 'Oq', '01A123BC', '@test', '123'];
  const payload = Buffer.from(JSON.stringify({code, row})).toString('base64');
  const timestamp = String(Math.floor(Date.now() / 1000) - age);
  const signature = crypto.createHmac('sha256', secret).update(timestamp + '.' + payload).digest('hex');
  const contents = JSON.stringify({timestamp, payload, signature});
  return {postData: {contents, length: contents.length}};
}
let response = context.doPost(request());
assert.equal(response.ok, true);
assert.equal(rows.length, 2);
assert.equal(frozen, 1);
assert.equal(rows[1][3], "'=1+1");
assert.equal(rows[1][4], "'+998000000000");
response = context.doPost(request());
assert.equal(response.duplicate, true);
assert.equal(rows.length, 2);
assert.equal(context.doPost(request('HM-000002', 600)).ok, false);
const tampered = request('HM-000002');
const body = JSON.parse(tampered.postData.contents);
body.signature = '0'.repeat(64);
tampered.postData.contents = JSON.stringify(body);
assert.equal(context.doPost(tampered).ok, false);
rows[0][0] = 'Existing incompatible header';
assert.equal(context.doPost(request('HM-000002')).ok, false);
assert.equal(rows.length, 2);
console.log('Apps Script receiver: signature, duplicate, expiry, formula and existing-header checks passed.');
