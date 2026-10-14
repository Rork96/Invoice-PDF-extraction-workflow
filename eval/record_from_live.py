#!/usr/bin/env python3
"""One-off provenance script: turns the raw Google Sheet exports of the live n8n run (Gemini) into
(a) data/live_run/*.csv  - sanitized: Drive file_id/file_url blanked, decimal commas -> dots
(b) data/recorded/llm/*.json - the LLM output per invoice, used by MOCK mode.
Passing rows: LLM JSON reconstructed from the sheet row. Review rows: raw_llm_output copied verbatim.
Usage: python3 eval/record_from_live.py Invoices.tsv [Needs_review.tsv]"""
import csv, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p): return list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter="\t"))
def dec(v): return v.replace(",", ".") if v and v.count(",") == 1 and "." not in v else v
inv = rd(sys.argv[1]); rev = rd(sys.argv[2]) if len(sys.argv) > 2 else []
os.makedirs(f"{ROOT}/data/live_run", exist_ok=True); os.makedirs(f"{ROOT}/data/recorded/llm", exist_ok=True)
for name, rows in (("Invoices", inv),) + ((("Needs_review", rev),) if rev else ()):
    cols = [c for c in rows[0].keys() if c]
    with open(f"{ROOT}/data/live_run/{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in rows:
            r = {c: r[c] for c in cols}
            for c in ("subtotal", "tax", "total"): r[c] = dec(r.get(c, ""))
            r["file_id"] = r["file_url"] = ""
            w.writerow(r)
for r in inv:
    d = {"vendor": r["vendor"], "invoice_number": r["invoice_number"], "issue_date": r["issue_date"], "due_date": r["due_date"],
         "currency": r["currency"], "subtotal": float(dec(r["subtotal"])), "tax": float(dec(r["tax"])), "total": float(dec(r["total"])),
         "line_items": json.loads(r["line_items_json"])}
    open(f"{ROOT}/data/recorded/llm/{r['file_name'].replace('.pdf', '.json')}", "w").write(json.dumps(d, indent=1))
for r in rev:
    open(f"{ROOT}/data/recorded/llm/{r['file_name'].replace('.pdf', '.json')}", "w").write(r["raw_llm_output"])
json.dump({r["file_name"]: "live" for r in inv} | {r["file_name"]: "live" for r in rev}, open(f"{ROOT}/data/recorded/manifest.json", "w"), indent=1)
print(len(inv), "passing +", len(rev), "review")
