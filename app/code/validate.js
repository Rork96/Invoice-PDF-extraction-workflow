// n8n Code node "Parse & Validate" — Mode: Run Once for Each Item
const MODEL = 'google-gemini';
const ALLOWED_CURRENCIES = ['USD', 'CAD', 'EUR'];           // extend as needed
const KEYS = ['vendor','invoice_number','issue_date','due_date','currency','subtotal','tax','total','line_items'];
const PLACEHOLDER = /^(n\/?a|null|none|unknown|undefined|-+|—)$/i;

const errors = [], warnings = [];
// LLM chain output has no usable item pairing -> match by position among items that had text
const pre = $('Preprocess Text').all().filter(x => x.json.has_text)[$itemIndex].json;
const meta = { id: pre.file_id, name: pre.file_name, webViewLink: pre.file_url };
const src  = String(pre.text || '');
const raw  = String($json.text ?? $json.output ?? '').trim();

// ---------- 1. parse ----------
let data = null;
try { data = JSON.parse(raw); } catch (e) {
  const a = raw.indexOf('{'), b = raw.lastIndexOf('}');
  if (a >= 0 && b > a) {
    try { data = JSON.parse(raw.slice(a, b + 1)); warnings.push('JSON_WRAPPED_IN_TEXT'); } catch (e2) {}
  }
}
if (!data || typeof data !== 'object' || Array.isArray(data)) { errors.push('JSON_PARSE_FAILED'); data = {}; }

const missingKeys = KEYS.filter(k => !(k in data));
if (missingKeys.length) errors.push('SCHEMA_KEYS_MISSING:' + missingKeys.join(','));
const extra = Object.keys(data).filter(k => !KEYS.includes(k));
if (extra.length) warnings.push('EXTRA_KEYS:' + extra.join(','));

// ---------- helpers ----------
const isStr = v => typeof v === 'string' && v.trim() !== '' && !PLACEHOLDER.test(v.trim());
const isNum = v => typeof v === 'number' && Number.isFinite(v);
const cents = v => Math.round(v * 100);
const validIso = s => {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(s + 'T00:00:00Z');
  return !isNaN(d) && d.toISOString().slice(0, 10) === s;
};
const esc = s => s.replace(/[.*+?^$\{}()|[\]\\]/g, '\\$&');
const numInSource = n => {                                   // number printed in any common format?
  const [i, d] = Math.abs(n).toFixed(2).split('.');
  const grp = sep => i.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
  const forms = new Set();
  for (const g of [grp(','), grp('.'), grp(' '), i]) for (const dec of ['.', ',']) forms.add(g + dec + d);
  return [...forms].some(f => new RegExp('(?<![\\d.,])' + esc(f) + '(?!\\d)').test(src));
};

// ---------- 2. required fields ----------
for (const k of ['vendor', 'invoice_number', 'issue_date', 'currency'])
  if (k in data && !isStr(data[k])) errors.push('MISSING_' + k.toUpperCase());
for (const k of ['subtotal', 'tax', 'total']) {
  if (!(k in data)) continue;
  if (data[k] === null || data[k] === undefined) errors.push('MISSING_' + k.toUpperCase());
  else if (!isNum(data[k])) errors.push('NOT_A_NUMBER_' + k.toUpperCase());
}
if (!Array.isArray(data.line_items) || data.line_items.length === 0) errors.push('NO_LINE_ITEMS');

// ---------- 3. formats ----------
if (isStr(data.issue_date) && !validIso(data.issue_date)) errors.push('BAD_ISSUE_DATE');
if (data.due_date == null) warnings.push('DUE_DATE_NULL');
else if (!validIso(data.due_date)) errors.push('BAD_DUE_DATE');
if (validIso(data.issue_date) && validIso(data.due_date) && data.due_date < data.issue_date) errors.push('DUE_BEFORE_ISSUE');
if (isStr(data.currency) && !/^[A-Z]{3}$/.test(data.currency)) errors.push('BAD_CURRENCY_FORMAT');
else if (isStr(data.currency) && !ALLOWED_CURRENCIES.includes(data.currency)) errors.push('CURRENCY_NOT_ALLOWED:' + data.currency);

// ---------- 4. arithmetic ----------
if (isNum(data.subtotal) && isNum(data.tax) && isNum(data.total)) {
  const calc = cents(data.subtotal) + cents(data.tax);
  if (Math.abs(calc - cents(data.total)) > 1)
    errors.push('TOTAL_MISMATCH(subtotal+tax=' + (calc / 100).toFixed(2) + ', total=' + data.total.toFixed(2) + ')');
}
if (Array.isArray(data.line_items)) {
  let sum = 0, allAmounts = true;
  data.line_items.forEach((li, i) => {
    const n = i + 1;
    if (!li || typeof li !== 'object') { errors.push('LINE_' + n + '_INVALID'); allAmounts = false; return; }
    for (const k of ['qty', 'unit_price', 'amount'])
      if (li[k] != null && !isNum(li[k])) errors.push('LINE_' + n + '_' + k.toUpperCase() + '_NOT_A_NUMBER');
    if (!isStr(li.description)) warnings.push('LINE_' + n + '_NO_DESCRIPTION');
    if (isNum(li.amount)) {
      sum += cents(li.amount);
      if (isNum(li.qty) && isNum(li.unit_price) &&
          Math.abs(Math.round(li.qty * li.unit_price * 100) - cents(li.amount)) > 1)
        errors.push('LINE_' + n + '_AMOUNT_NE_QTY_X_PRICE');
    } else allAmounts = false;
  });
  if (!allAmounts) warnings.push('LINE_AMOUNT_NULL');
  else if (isNum(data.subtotal) && Math.abs(sum - cents(data.subtotal)) > 1) errors.push('LINES_SUM_NE_SUBTOTAL');
}

// ---------- 5. grounding: extracted values must literally exist in the PDF text ----------
// catches hallucinated invoice numbers and the LLM "correcting" a wrong printed total
if (isStr(data.invoice_number) && !src.toLowerCase().replace(/\s+/g, '').includes(data.invoice_number.toLowerCase().replace(/\s+/g, '')))
  errors.push('NOT_IN_SOURCE_INVOICE_NUMBER');
for (const k of ['subtotal', 'total'])
  if (isNum(data[k]) && !numInSource(data[k])) errors.push('NOT_IN_SOURCE_' + k.toUpperCase());
if (isNum(data.tax) && data.tax !== 0 && !numInSource(data.tax)) errors.push('NOT_IN_SOURCE_TAX');
if (isStr(data.vendor) && !src.toLowerCase().replace(/\s+/g, ' ').includes(data.vendor.toLowerCase().replace(/\s+/g, ' ')))
  warnings.push('VENDOR_NOT_IN_SOURCE');

// ---------- output ----------
const items = Array.isArray(data.line_items) ? data.line_items : [];
const keyPart = s => String(s ?? '').toLowerCase().replace(/\s+/g, ' ').trim();
return { json: {
  ok: errors.length === 0, errors, warnings,
  failure_codes: errors.join('; '), warning_codes: warnings.join('; '),
  vendor: data.vendor ?? null, invoice_number: data.invoice_number ?? null,
  issue_date: data.issue_date ?? null, due_date: data.due_date ?? null, currency: data.currency ?? null,
  subtotal: data.subtotal ?? null, tax: data.tax ?? null, total: data.total ?? null,
  line_item_count: items.length, line_items_json: JSON.stringify(items),
  dedupe_key: keyPart(data.vendor) + '|' + keyPart(data.invoice_number),
  raw_llm_output: raw, model: MODEL,
  file_id: meta.id, file_name: meta.name, file_url: meta.webViewLink,
  processed_at: new Date().toISOString(),
} };
