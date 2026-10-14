PY ?= python3
.PHONY: setup demo eval test showcase video

setup:            ## check toolchain (no keys needed)
	@which node pdftotext $(PY) >/dev/null || (echo "need: node, poppler-utils (pdftotext), python3" && exit 1)
	@node --version && $(PY) --version && echo ok

demo:             ## MOCK mode, zero keys: replay recorded LLM outputs through the real validator, compare to ground truth
	$(PY) eval/run_extraction.py --pdf-dir data/invoices --out-dir out --replay data/recorded/llm
	$(PY) eval/compare.py --expected data/invoices/expected.csv --invoices out/Invoices.csv --review out/Needs_review.csv \
	  --json-out eval/eval.json --source "mock-replay: recorded LLM outputs -> app/code/validate.js"

eval: demo        ## + compare the committed live n8n run export (8 passing files) to ground truth
	$(PY) -c "import csv;r=list(csv.DictReader(open('data/invoices/expected.csv')));l={x['file_name'] for x in csv.DictReader(open('data/live_run/Invoices.csv'))};w=csv.DictWriter(open('out/expected_live.csv','w',newline=''),r[0].keys());w.writeheader();w.writerows(x for x in r if x['file'] in l)"
	$(PY) eval/compare.py --expected out/expected_live.csv --invoices data/live_run/Invoices.csv \
	  --json-out eval/eval_live.json --source "live n8n run (Gemini), Invoices sheet export"

test:             ## validator tests -> eval/tests.json
	$(PY) eval/run_tests.py

showcase: eval test  ## render docs/showcase/results.md + README results block from eval.json / tests.json
	$(PY) eval/showcase.py

video:            ## the explainer is an HTML animation; nothing is rendered here
	@echo "open docs/showcase/explainer.html in a browser (add ?t=40 for the final frame)"

live:             ## real LLM run (needs ANTHROPIC_API_KEY)
	$(PY) eval/run_extraction.py --pdf-dir data/invoices --out-dir out_live
