#!/usr/bin/env python3
"""Compare Google Sheet exports against expected.csv. Prints per-field accuracy.
Usage: python3 compare.py --expected expected.csv --invoices Invoices.csv --review Needs_review.csv
Export each sheet tab as CSV (File > Download > CSV). Exit code 1 if any field < --threshold or routing < 100%."""
import argparse, csv, json, sys
from collections import OrderedDict

FIELDS = ["invoice_number", "vendor", "issue_date", "due_date", "currency", "subtotal", "tax", "total", "line_item_count"]
NUM = {"subtotal", "tax", "total"}

def rows(path):
    if not path: return []
    with open(path, newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))

def num(v):
    if v is None: return None
    s = str(v).strip().replace(",", "").replace("$", "").replace("€", "").replace("CA", "").replace("CAD", "").strip()
    if s == "": return None
    try: return float(s)
    except ValueError: return "BAD"

def date(v):
    s = ("" if v is None else str(v)).strip()
    if not s: return None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-": return s[:10]
    p = s.split("/")                       # Sheets may re-format ISO dates as M/D/YYYY
    if len(p) == 3 and len(p[2]) == 4: return f"{p[2]}-{int(p[0]):02d}-{int(p[1]):02d}"
    return s

def text(v, fold=False):
    s = ("" if v is None else str(v)).strip()
    if s == "": return None
    return s.casefold() if fold else s

def from_raw(raw):
    """Needs_review rows keep the whole extraction in raw_llm_output; use it for due_date/line_item_count."""
    try:
        a, b = raw.index("{"), raw.rindex("}")
        d = json.loads(raw[a:b + 1])
    except Exception:
        return {}
    if isinstance(d.get("line_items"), list): d["line_item_count"] = len(d["line_items"])
    return d

def actual_values(row, tab):
    a = {f: row.get(f) for f in FIELDS}
    if tab == "review":
        raw = from_raw(row.get("raw_llm_output", "") or "")
        for f in FIELDS:
            if f in raw: a[f] = raw[f]
    return a

def expected_values(e):
    return {"invoice_number": e["invoice_number"], "vendor": e["vendor_name"], "issue_date": e["invoice_date"],
            "due_date": e["due_date"], "currency": e["currency"], "subtotal": e["subtotal"], "tax": e["tax_amount"],
            "total": e["printed_total"],            # extraction must copy the PRINTED total, even when wrong
            "line_item_count": e["line_item_count"]}

def same(f, exp, act):
    if f in NUM:
        x, y = num(exp), num(act)
        return x is not None and y not in (None, "BAD") and abs(x - y) <= 0.005 if x is not None else y is None
    if f == "line_item_count":
        try: return int(float(exp)) == int(float(act))
        except (TypeError, ValueError): return False
    if f in ("issue_date", "due_date"): return date(exp) == date(act)
    if f == "vendor": return text(exp, True) == text(act, True)
    return text(exp) == text(act)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected", required=True); ap.add_argument("--invoices", required=True)
    ap.add_argument("--review"); ap.add_argument("--json-out"); ap.add_argument("--source", default=""); ap.add_argument("--threshold", type=float, default=95.0)
    a = ap.parse_args()
    exp = rows(a.expected)
    inv = {r["file_name"].strip(): r for r in rows(a.invoices)}
    rev = {r["file_name"].strip(): r for r in rows(a.review)}
    hit = OrderedDict((f, 0) for f in FIELDS); miss = []
    route_ok = code_ok = 0
    for e in exp:
        fn = e["file"]; want = "review" if e["problem"] else "invoices"
        where = [t for t, d in (("invoices", inv), ("review", rev)) if fn in d]
        got = where[0] if len(where) == 1 else None
        route_ok += got == want
        if got != want: miss.append((fn, "routing", want, ",".join(where) or "nowhere"))
        if e["problem"]:
            codes = (rev.get(fn) or {}).get("failure_codes", "")
            ok = got == "review" and codes.replace(" ", "").startswith(e["problem"].upper().replace("_MISMATCH", "_MISMATCH")) \
                 and ";" not in codes
            code_ok += ok
            if not ok: miss.append((fn, "failure_code", e["problem"], codes or "-"))
        row = inv.get(fn) if got == "invoices" else rev.get(fn) if got == "review" else None
        av = actual_values(row, got) if row else {}
        ev = expected_values(e)
        for f in FIELDS:
            if row and same(f, ev[f], av.get(f)): hit[f] += 1
            else: miss.append((fn, f, ev[f] or "(null)", (av.get(f) if av.get(f) not in (None, "") else "(null)") if row else "(no row)"))
    n = len(exp); nprob = sum(1 for e in exp if e["problem"])
    print(f"{'field':<18}{'correct':>8}{'of':>4}{'accuracy':>10}  status")
    worst = 100.0
    for f in FIELDS:
        pct = 100 * hit[f] / n; worst = min(worst, pct)
        print(f"{f:<18}{hit[f]:>8}{n:>4}{pct:>9.1f}%  {'OK' if pct >= a.threshold else 'BELOW ' + str(a.threshold)}")
    print(f"{'routing':<18}{route_ok:>8}{n:>4}{100 * route_ok / n:>9.1f}%  {'OK' if route_ok == n else 'FAIL'}")
    print(f"{'failure_code':<18}{code_ok:>8}{nprob:>4}{(100 * code_ok / nprob if nprob else 100):>9.1f}%  {'OK' if code_ok == nprob else 'FAIL'}")
    tot = sum(hit.values()); print(f"{'ALL FIELDS':<18}{tot:>8}{n * len(FIELDS):>4}{100 * tot / (n * len(FIELDS)):>9.1f}%")
    if a.json_out:
        json.dump({"source": a.source, "files": n, "fields": {f: {"correct": hit[f], "of": n, "accuracy_pct": round(100 * hit[f] / n, 1)} for f in FIELDS},
                   "routing": {"correct": route_ok, "of": n}, "failure_code": {"correct": code_ok, "of": nprob},
                   "all_fields": {"correct": tot, "of": n * len(FIELDS)}, "mismatches": [list(map(str, m)) for m in miss]},
                  open(a.json_out, "w"), indent=2)
    if miss:
        print("\nMISMATCHES"); [print(f"  {m[0]:<16}{m[1]:<16}expected={m[2]!s:<28}actual={m[3]}") for m in miss]
    sys.exit(0 if worst >= a.threshold and route_ok == n and code_ok == nprob else 1)

main()
