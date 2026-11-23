"""
tests/summary.py
----------------
Prints the latest regression results as Markdown rows for TEST_LOG.md, and
optionally saves them as the new baseline.

    python tests/summary.py                  print table
    python tests/summary.py --save-baseline  also accept results as baseline
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', "engine"))
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "results", "latest.json")) as f:
    results = json.load(f)
with open(os.path.join(HERE, "companies.json")) as f:
    companies = json.load(f)

KEYS = ("ok", "check", "missing", "verified", "compared", "q_cells", "q_confirmed", "q_failed_totals", "q_bad_labels")


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "-"


print("| Ticker | Sector | Round | Statements OK | Verified | Matches the report | Totals not adding up | Garbled labels |")
print("|---|---|---|---|---|---|---|---|")
for c in companies:
    r = results.get(c["ticker"])
    if not r or "error" in r:
        print(f"| {c['ticker']} | {c['sector']} | {c['round']} | ERROR | | | | |")
        continue
    applicable = r["ok"] + r["check"] + r["missing"]
    print(f"| {c['ticker']} | {c['sector']} | {c['round']} | {r['ok']}/{applicable} | "
          f"{r.get('verified')}/{r.get('compared')} | {pct(r.get('q_confirmed', 0), r.get('q_cells', 0))} | "
          f"{r.get('q_failed_totals', '-')} | {r.get('q_bad_labels', '-')} |")

print()
for rnd in sorted({c["round"] for c in companies}):
    ts = [c["ticker"] for c in companies if c["round"] == rnd and "error" not in results.get(c["ticker"], {"error": 1})]
    tot = {k: sum(results[t].get(k, 0) or 0 for t in ts) for k in KEYS}
    app = tot["ok"] + tot["check"] + tot["missing"]
    print(f"Round {rnd}: {len(ts)} companies | statements OK {tot['ok']}/{app} ({pct(tot['ok'], app)}) "
          f"CHECK {tot['check']} MISSING {tot['missing']} | verified {tot['verified']}/{tot['compared']} "
          f"({pct(tot['verified'], tot['compared'])}) | matches the report {tot['q_confirmed']}/{tot['q_cells']} "
          f"({pct(tot['q_confirmed'], tot['q_cells'])}) | totals not adding up {tot['q_failed_totals']} "
          f"| garbled labels {tot['q_bad_labels']}")

if "--save-baseline" in sys.argv:
    base = {t: {k: r.get(k) for k in KEYS}
            for t, r in results.items() if "error" not in r}
    with open(os.path.join(HERE, "baseline.json"), "w") as f:
        json.dump(base, f, indent=1, sort_keys=True)
    print(f"\nBaseline saved for {len(base)} companies.")
