// Node "Build Needs-review row" — Run Once for Each Item. Inputs come from 4 failure sources.
const j = $json;
let meta;
if (j.file_id) meta = { id: j.file_id, name: j.file_name, webViewLink: j.file_url };
else { try { meta = $('Drive Trigger').item.json; } catch (e) { meta = $('Drive Trigger').first().json; } }
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
let codes;
if (Array.isArray(j.errors)) codes = j.errors;                                   // Valid? = false
else if (j.mimeType && j.mimeType !== 'application/pdf') codes = ['NOT_A_PDF:' + j.mimeType];
else if (j.has_text === false) codes = ['NO_TEXT_LAYER'];                        // scanned / image-only
else codes = ['LLM_CALL_FAILED:' + (j.error?.message || j.error || 'unknown')];  // LLM error output
const failure_codes = codes.join('; ');
return { json: {
  received_at: new Date().toISOString(),
  file_id: meta.id, file_name: meta.name, file_url: meta.webViewLink,
  failure_codes, warning_codes: j.warning_codes || '',
  vendor: j.vendor ?? '', invoice_number: j.invoice_number ?? '',
  issue_date: j.issue_date ?? '', currency: j.currency ?? '',
  subtotal: j.subtotal ?? '', tax: j.tax ?? '', total: j.total ?? '',
  raw_llm_output: String(j.raw_llm_output ?? '').slice(0, 5000),
  telegram_text: [
    '<b>Invoice needs review</b>',
    'File: ' + esc(meta.name),
    'Reason: ' + esc(failure_codes).slice(0, 700),
    'Vendor: ' + esc(j.vendor ?? '-') + ' | Inv#: ' + esc(j.invoice_number ?? '-') + ' | Total: ' + esc(j.total ?? '-'),
    meta.webViewLink || '',
  ].join('\n'),
} };
