#!/usr/bin/env python3
"""Generates the two importable n8n workflow JSON files from prompt/ and code/.
Run: python3 build_workflows.py   (writes workflow/*.json)
Every credential id and resource id is a REPLACE_* placeholder."""
import json, pathlib, uuid

R = pathlib.Path(__file__).parent
rd = lambda p: (R / p).read_text(encoding="utf-8")

SYSTEM = rd("prompt/system.txt").strip()
USER = rd("prompt/user.txt").strip()
# LangChain treats { } in system messages as template variables -> keep system free of braces.
assert "{" not in SYSTEM and "}" not in SYSTEM, "system prompt must not contain braces"
assert "{{" not in USER.replace("{{ $json.text }}", ""), "stray double braces in user prompt"

def nid(name): return str(uuid.uuid5(uuid.NAMESPACE_DNS, "invoice-intake/" + name))
def cred(key, label): return {key: {"id": "REPLACE_CREDENTIAL_ID", "name": "REPLACE: " + label}}
def rl(mode, value): return {"__rl": True, "mode": mode, "value": value}

def node(name, type_, ver, pos, params, **extra):
    n = {"parameters": params, "id": nid(name), "name": name, "type": type_, "typeVersion": ver, "position": pos}
    n.update(extra); return n

def if_node(name, pos, left, op):
    return node(name, "n8n-nodes-base.if", 2.3, pos, {
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                       "conditions": [{"id": nid(name + "/c"), "leftValue": left, **op}], "combinator": "and"},
        "options": {}})

def sheet_cols(pairs):
    return {"mappingMode": "defineBelow", "value": dict(pairs), "matchingColumns": [],
            "schema": [{"id": k, "displayName": k, "required": False, "defaultMatch": False, "display": True,
                        "type": "string", "canBeUsedToMatch": True} for k, _ in pairs],
            "attemptToConvertTypes": False, "convertFieldsToString": False}

def sheet_node(name, pos, tab, pairs):
    return node(name, "n8n-nodes-base.googleSheets", 4.7, pos, {
        "authentication": "oAuth2", "resource": "sheet", "operation": "append",
        "documentId": rl("id", "REPLACE_SPREADSHEET_ID"),
        "sheetName": rl("name", tab),
        "columns": sheet_cols(pairs),
        "options": {"cellFormat": "RAW"}},
        credentials=cred("googleSheetsOAuth2Api", "Google Sheets OAuth2"))

def move_node(name, pos, file_expr, folder_id, label):
    return node(name, "n8n-nodes-base.googleDrive", 3, pos, {
        "authentication": "oAuth2", "resource": "file", "operation": "move",
        "fileId": rl("id", file_expr),
        "driveId": rl("list", "My Drive"),
        "folderId": rl("id", folder_id)},
        credentials=cred("googleDriveOAuth2Api", "Google Drive OAuth2"))

def code_node(name, pos, js):
    return node(name, "n8n-nodes-base.code", 2, pos, {"mode": "runOnceForEachItem", "jsCode": js})

V = "$json."
BV = "$('Build Needs-review row').item.json."
INV_PAIRS = [(k, "={{ " + e + " }}") for k, e in [
    ("processed_at", V + "processed_at"), ("file_name", V + "file_name"), ("file_id", V + "file_id"),
    ("file_url", V + "file_url"), ("vendor", V + "vendor"), ("invoice_number", V + "invoice_number"),
    ("issue_date", V + "issue_date"), ("due_date", V + "due_date ?? ''"),
    ("currency", V + "currency"), ("subtotal", V + "subtotal"), ("tax", V + "tax"), ("total", V + "total"),
    ("line_item_count", V + "line_item_count"), ("line_items_json", V + "line_items_json"),
    ("dedupe_key", V + "dedupe_key"), ("warnings", V + "warning_codes"), ("model", V + "model")]]
REV_PAIRS = [(k, "={{ " + BV + src + " }}") for k, src in [
    ("received_at", "received_at"), ("file_name", "file_name"), ("file_id", "file_id"), ("file_url", "file_url"),
    ("failure_codes", "failure_codes"), ("warnings", "warning_codes"), ("vendor", "vendor"),
    ("invoice_number", "invoice_number"), ("issue_date", "issue_date"), ("currency", "currency"),
    ("subtotal", "subtotal"), ("tax", "tax"), ("total", "total"), ("raw_llm_output", "raw_llm_output")]]
REV_PAIRS += [("status", "OPEN"), ("resolved_by", ""), ("resolution_note", "")]

TRUE = {"operator": {"type": "boolean", "operation": "true", "singleValue": True}, "rightValue": ""}

nodes = [
    node("Setup notes", "n8n-nodes-base.stickyNote", 1, [-260, -220], {
        "content": "## Setup\nReplace every REPLACE_* value:\n- credentials: Google Drive OAuth2, Google Sheets OAuth2, Anthropic API, Telegram\n- Drive Trigger: Inbox folder ID\n- Move to Processed / Move to Needs review: folder IDs\n- Both Sheets nodes: spreadsheet ID (tabs `Invoices`, `Needs_review`, headers in row 1)\n- Telegram Alert: chat ID\n- Settings > Error workflow: select 'Invoice Intake - Error Alert'\nThen run the tests in design/invoice-workflow-design.md section 7.",
        "height": 260, "width": 460}),
    node("Drive Trigger", "n8n-nodes-base.googleDriveTrigger", 1, [0, 200], {
        "pollTimes": {"item": [{"mode": "everyMinute"}]}, "authentication": "oAuth2",
        "triggerOn": "specificFolder", "folderToWatch": rl("id", "REPLACE_INBOX_FOLDER_ID"),
        "event": "fileCreated", "options": {}},
        credentials=cred("googleDriveOAuth2Api", "Google Drive OAuth2")),
    if_node("Is PDF?", [220, 200], "={{ $json.mimeType }}",
            {"operator": {"type": "string", "operation": "equals"}, "rightValue": "application/pdf"}),
    node("Download PDF", "n8n-nodes-base.googleDrive", 3, [440, 100], {
        "authentication": "oAuth2", "resource": "file", "operation": "download",
        "fileId": rl("id", "={{ $json.id }}"), "options": {"binaryPropertyName": "data"}},
        credentials=cred("googleDriveOAuth2Api", "Google Drive OAuth2"),
        retryOnFail=True, maxTries=3, waitBetweenTries=5000),
    node("Extract PDF Text", "n8n-nodes-base.extractFromFile", 1.1, [660, 100],
         {"operation": "pdf", "binaryPropertyName": "data", "options": {"joinPages": True}}),
    code_node("Preprocess Text", [880, 100], rd("code/preprocess.js")),
    if_node("Has text?", [1100, 100], "={{ $json.has_text }}", TRUE),
    node("LLM Extract", "@n8n/n8n-nodes-langchain.chainLlm", 1.9, [1320, 0], {
        "promptType": "define", "text": "=" + USER, "hasOutputParser": False,
        "messages": {"messageValues": [{"type": "SystemMessagePromptTemplate", "message": SYSTEM}]}},
        retryOnFail=True, maxTries=3, waitBetweenTries=5000, onError="continueErrorOutput"),
    node("Anthropic Chat Model", "@n8n/n8n-nodes-langchain.lmChatAnthropic", 1.5, [1320, -180], {
        "model": rl("id", "claude-haiku-5-5"),
        "options": {"maxTokensToSample": 4096, "temperature": 0}},
        credentials=cred("anthropicApi", "Anthropic API")),
    code_node("Parse & Validate", [1600, 0], rd("code/validate.js")),
    if_node("Valid?", [1820, 0], "={{ $json.ok }}", TRUE),
    sheet_node("Append Invoice row", [2040, -100], "Invoices", INV_PAIRS),
    move_node("Move to Processed", [2260, -100], "={{ $('Parse & Validate').item.json.file_id }}",
              "REPLACE_PROCESSED_FOLDER_ID", "Processed"),
    code_node("Build Needs-review row", [2040, 340], rd("code/build_review.js")),
    node("Telegram Alert", "n8n-nodes-base.telegram", 1.2, [2260, 340], {
        "resource": "message", "operation": "sendMessage", "chatId": "REPLACE_TELEGRAM_CHAT_ID",
        "text": "={{ $json.telegram_text }}",
        "additionalFields": {"parse_mode": "HTML", "appendAttribution": False}},
        credentials=cred("telegramApi", "Telegram Bot"), onError="continueRegularOutput"),
    sheet_node("Append Needs_review row", [2480, 340], "Needs_review", REV_PAIRS),
    move_node("Move to Needs review", [2700, 340], "={{ $('Build Needs-review row').item.json.file_id }}",
              "REPLACE_NEEDS_REVIEW_FOLDER_ID", "Needs review"),
]

def link(*targets):  # one output port -> list of targets
    return [{"node": t, "type": "main", "index": 0} for t in targets]

conn = {
    "Drive Trigger": {"main": [link("Is PDF?")]},
    "Is PDF?": {"main": [link("Download PDF"), link("Build Needs-review row")]},
    "Download PDF": {"main": [link("Extract PDF Text")]},
    "Extract PDF Text": {"main": [link("Preprocess Text")]},
    "Preprocess Text": {"main": [link("Has text?")]},
    "Has text?": {"main": [link("LLM Extract"), link("Build Needs-review row")]},
    "LLM Extract": {"main": [link("Parse & Validate"), link("Build Needs-review row")]},
    "Anthropic Chat Model": {"ai_languageModel": [[{"node": "LLM Extract", "type": "ai_languageModel", "index": 0}]]},
    "Parse & Validate": {"main": [link("Valid?")]},
    "Valid?": {"main": [link("Append Invoice row"), link("Build Needs-review row")]},
    "Append Invoice row": {"main": [link("Move to Processed")]},
    "Build Needs-review row": {"main": [link("Telegram Alert")]},
    "Telegram Alert": {"main": [link("Append Needs_review row")]},
    "Append Needs_review row": {"main": [link("Move to Needs review")]},
}
main_wf = {"name": "Invoice Intake - Drive to Sheet", "nodes": nodes, "connections": conn,
           "settings": {"executionOrder": "v1"}, "active": False, "pinData": {}, "tags": []}

# ---- error workflow ----
esc = ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')"
err_text = ("=<b>WORKFLOW ERROR</b>\n"
            "{{ String($json.workflow.name)" + esc + " }}\n"
            "Node: {{ String($json.execution.lastNodeExecuted)" + esc + " }}\n"
            "Error: {{ String($json.execution.error.message)" + esc + " }}\n"
            "{{ $json.execution.url }}")
err_wf = {"name": "Invoice Intake - Error Alert", "settings": {"executionOrder": "v1"}, "active": False,
          "pinData": {}, "tags": [],
          "nodes": [node("Error Trigger", "n8n-nodes-base.errorTrigger", 1, [0, 0], {}),
                    node("Telegram Error Alert", "n8n-nodes-base.telegram", 1.2, [240, 0], {
                        "resource": "message", "operation": "sendMessage", "chatId": "REPLACE_TELEGRAM_CHAT_ID",
                        "text": err_text, "additionalFields": {"parse_mode": "HTML", "appendAttribution": False}},
                        credentials=cred("telegramApi", "Telegram Bot"))],
          "connections": {"Error Trigger": {"main": [link("Telegram Error Alert")]}}}

out = R / "workflow"; out.mkdir(exist_ok=True)
(out / "invoice-intake.workflow.json").write_text(json.dumps(main_wf, indent=2, ensure_ascii=False), encoding="utf-8")
(out / "invoice-intake-error.workflow.json").write_text(json.dumps(err_wf, indent=2, ensure_ascii=False), encoding="utf-8")
print("written", len(nodes), "nodes +", len(err_wf["nodes"]), "error-wf nodes")
