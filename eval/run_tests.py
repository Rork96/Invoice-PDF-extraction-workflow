#!/usr/bin/env python3
"""make test: runs app/code/validate.js (exact n8n Code-node body) on recorded LLM outputs + mutations. Writes eval/tests.json. Exit 1 on any failure."""
import csv, json, os, subprocess, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def pdf(n): return subprocess.run(["pdftotext", f"{R}/data/invoices/{n}", "-"], capture_output=True, text=True, check=True).stdout
def validate(cases): return json.loads(subprocess.run(["node", f"{R}/eval/run_validator.js"], input=json.dumps(cases), capture_output=True, text=True, check=True).stdout)
rec = lambda n: open(f"{R}/data/recorded/llm/{n.replace('.pdf', '.json')}").read()
exp = {e["file"]: e for e in csv.DictReader(open(f"{R}/data/invoices/expected.csv"))}
tests = []
files = sorted(exp)
res = validate([{"name": n, "src": pdf(n), "llm": rec(n)} for n in files])
for n, r in zip(files, res):
    want = exp[n]["problem"].upper()
    ok = (not r["ok"] and r["failure_codes"].startswith(want)) if want else r["ok"]
    tests.append({"name": f"recorded:{n}", "expect": want or "PASS", "got": r["failure_codes"] or "PASS", "passed": bool(ok)})
base = json.loads(rec("invoice_01.pdf")); src = pdf("invoice_01.pdf")
def mut(label, fn, code):
    d = json.loads(json.dumps(base)); fn(d)
    r = validate([{"name": "invoice_01.pdf", "src": src, "llm": json.dumps(d)}])[0]
    tests.append({"name": f"mutation:{label}", "expect": code, "got": r["failure_codes"] or "PASS", "passed": code in r["failure_codes"]})
mut("hallucinated_invoice_number", lambda d: d.update(invoice_number="ZZZ-999999"), "NOT_IN_SOURCE_INVOICE_NUMBER")
mut("total_off_by_one_euro", lambda d: d.update(total=d["total"] + 1), "TOTAL_MISMATCH")
mut("currency_not_allowed", lambda d: d.update(currency="XYZ"), "CURRENCY")
mut("bad_date", lambda d: d.update(issue_date="12/01/2026"), "DATE")
mut("line_amount_wrong", lambda d: d["line_items"][0].update(amount=1.0), "LINE")
mut("missing_key", lambda d: d.pop("tax"), "SCHEMA_KEYS_MISSING")
out = {"total": len(tests), "passed": sum(t["passed"] for t in tests), "tests": tests}
json.dump(out, open(f"{R}/eval/tests.json", "w"), indent=2)
for t in tests: print(("PASS " if t["passed"] else "FAIL ") + t["name"], "| expect", t["expect"], "| got", t["got"])
print(f"{out['passed']}/{out['total']} passed"); sys.exit(0 if out["passed"] == out["total"] else 1)
