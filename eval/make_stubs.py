#!/usr/bin/env python3
"""Adds STUB LLM outputs for invoices with no recorded live output (problem files 05, 08), built from data/invoices/expected.csv
(the printed values, i.e. what a correct extractor returns). Marks them 'stub' in data/recorded/manifest.json. Not live data."""
import csv, json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
man = json.load(open(f"{R}/data/recorded/manifest.json"))
for e in csv.DictReader(open(f"{R}/data/invoices/expected.csv")):
    name = e["file"]
    if name in man: continue
    d = {"vendor": e["vendor_name"], "invoice_number": e["invoice_number"] or None, "issue_date": e["invoice_date"], "due_date": e["due_date"],
         "currency": e["currency"], "subtotal": float(e["subtotal"]), "tax": float(e["tax_amount"]), "total": float(e["printed_total"]),
         "line_items": [{"description": f"line {i+1}", "qty": 1, "unit_price": 0, "amount": None} for i in range(int(e["line_item_count"]))]}
    open(f"{R}/data/recorded/llm/{name.replace('.pdf', '.json')}", "w").write(json.dumps(d, indent=1)); man[name] = "stub"
json.dump(man, open(f"{R}/data/recorded/manifest.json", "w"), indent=1, sort_keys=True); print(man)
