#!/usr/bin/env python3
"""Offline replica of nodes 4-9: PDF text -> Anthropic API (same prompt files, same model) -> same validator code ->
writes Invoices.csv / Needs_review.csv in the sheet's column layout, ready for compare.py.
Needs: ANTHROPIC_API_KEY in env, node, and pdftotext (poppler) or pypdf.
Usage: ANTHROPIC_API_KEY=... python3 run_extraction.py --pdf-dir data/invoices --out-dir out
       python3 run_extraction.py --pdf-dir data/invoices --out-dir out --replay data/recorded/llm   (MOCK, zero keys)
Note: n8n's Extract From File uses pdf.js; pdftotext output differs slightly. Final proof is the real workflow run."""
import argparse, csv, glob, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
INV_COLS = ["processed_at","file_name","file_id","file_url","vendor","invoice_number","issue_date","due_date","currency",
            "subtotal","tax","total","line_item_count","line_items_json","dedupe_key","warnings","model"]
REV_COLS = ["received_at","file_name","file_id","file_url","failure_codes","warnings","vendor","invoice_number","issue_date",
            "currency","subtotal","tax","total","raw_llm_output","status","resolved_by","resolution_note"]

def pdf_text(path):
    try: return subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)

def preprocess(t):  # same as code/preprocess.js
    t = re.sub(r"[ \t]+", " ", t.replace("\r", "")); t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t[:30000], len(t) >= 50

def call_llm(model, system, user, key):
    body = json.dumps({"model": model, "max_tokens": 4096, "temperature": 0, "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    last = None
    for attempt in range(3):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", body,
              {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return "".join(b.get("text", "") for b in json.load(r)["content"] if b.get("type") == "text")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e; time.sleep(5)
    raise RuntimeError(f"LLM_CALL_FAILED: {last}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-dir", required=True); ap.add_argument("--out-dir", default="out")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--system", default=os.path.join(ROOT, "app", "prompt", "system.txt"))
    ap.add_argument("--user", default=os.path.join(ROOT, "app", "prompt", "user.txt"))
    ap.add_argument("--replay", help="MOCK mode: dir of recorded LLM outputs (<invoice>.json). No API key needed.")
    a = ap.parse_args()
    key = None if a.replay else (os.environ.get("ANTHROPIC_API_KEY") or sys.exit("ANTHROPIC_API_KEY not set (or use --replay DIR)"))
    system = open(a.system, encoding="utf-8").read().strip(); user_t = open(a.user, encoding="utf-8").read().strip()
    os.makedirs(a.out_dir, exist_ok=True)
    cases, pre = [], []
    for p in sorted(glob.glob(os.path.join(a.pdf_dir, "invoice_*.pdf"))):
        name = os.path.basename(p); text, has = preprocess(pdf_text(p))
        if not has: pre.append({"name": name, "codes": "NO_TEXT_LAYER", "raw": ""}); continue
        if a.replay:
            rp = os.path.join(a.replay, name.replace(".pdf", ".json"))
            raw = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
            cases.append({"name": name, "src": text, "llm": raw}); continue
        try: raw = call_llm(a.model, system, user_t.replace("{{ $json.text }}", text), key)
        except RuntimeError as e: pre.append({"name": name, "codes": str(e), "raw": ""}); continue
        cases.append({"name": name, "src": text, "llm": raw})
    res = json.loads(subprocess.run(["node", os.path.join(HERE, "run_validator.js")], input=json.dumps(cases),
                                    capture_output=True, text=True, check=True).stdout) if cases else []
    now = datetime.now(timezone.utc).isoformat()
    inv, rev = [], []
    for r in res:
        if r["ok"]:
            inv.append({**{k: r.get(k) if r.get(k) is not None else "" for k in INV_COLS},
                        "processed_at": now, "warnings": r["warning_codes"]})
        else:
            rev.append({"received_at": now, "file_name": r["file_name"], "file_id": r["file_id"], "file_url": "",
                        "failure_codes": r["failure_codes"], "warnings": r["warning_codes"], "vendor": r["vendor"] or "",
                        "invoice_number": r["invoice_number"] or "", "issue_date": r["issue_date"] or "",
                        "currency": r["currency"] or "", "subtotal": "" if r["subtotal"] is None else r["subtotal"],
                        "tax": "" if r["tax"] is None else r["tax"], "total": "" if r["total"] is None else r["total"],
                        "raw_llm_output": r["raw_llm_output"][:5000], "status": "OPEN", "resolved_by": "", "resolution_note": ""})
    for x in pre:
        rev.append({c: "" for c in REV_COLS} | {"received_at": now, "file_name": x["name"], "failure_codes": x["codes"], "status": "OPEN"})
    for fn, cols, data in (("Invoices.csv", INV_COLS, inv), ("Needs_review.csv", REV_COLS, rev)):
        with open(os.path.join(a.out_dir, fn), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(data)
    print(f"{len(inv)} -> Invoices.csv, {len(rev)} -> Needs_review.csv in {a.out_dir}")

main()
