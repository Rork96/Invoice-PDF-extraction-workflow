const meta = $('Drive Trigger').item.json;
const text = String($json.text ?? '').replace(/\r/g, '').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
return { json: {
  text: text.slice(0, 30000), has_text: text.length >= 50, truncated: text.length > 30000,
  file_id: meta.id, file_name: meta.name, file_url: meta.webViewLink,
} };
