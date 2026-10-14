// Runs app/code/validate.js (the exact n8n Code-node body) outside n8n. stdin: [{name,src,llm}] -> stdout: [result json]
const fs = require('fs'), path = require('path');
const code = fs.readFileSync(path.join(__dirname, '..', 'app', 'code', 'validate.js'), 'utf8');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = cases.map(c => {
  const pre = { json: { has_text: true, text: c.src, file_id: c.name, file_name: c.name, file_url: '' } };
  const $ = () => ({ all: () => [pre], item: pre });
  return new Function('$json', '$', '$itemIndex', code)({ text: c.llm }, $, 0).json;
});
process.stdout.write(JSON.stringify(out));
