"""
tests/regression.py
-------------------
Runs the whole pipeline on every test company and compares against the saved
baseline, so a parser change that fixes one company can't silently break another.

For each company: statements OK / CHECK / MISSING (from the run), and figures
verified by NSE XBRL / Screener / Yahoo (from accuracy_check.py).

Usage (from the project folder):
    python tests/regression.py                      all companies in tests/companies.json
    python tests/regression.py TCS INFY             just these
    python tests/regression.py --round 2            only round-2 companies
    python tests/regression.py --update-baseline    accept current results as the new baseline
    python tests/regression.py --workers 4          parallel processes (default 3)
    python tests/regression.py --no-gold            skip the gold / silver comparison

Results: tests/results/latest.json (+ a dated copy), tests/results/gold_latest.json
and a summary table on screen.
A company REGRESSES if its OK statements or verified figures drop below baseline.
Any difference from a GOLD copy (human-verified) also counts as a regression;
a difference from a SILVER copy (AI-verified) is only a warning.
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', "engine"))
import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

YEARS = (2020, 2026)
OUT_DIR = os.path.join(ROOT, "test_output")
RESULTS_DIR = os.path.join(HERE, "results")
BASELINE = os.path.join(HERE, "baseline.json")


def run_one(ticker):
    import finxl
    import accuracy_check
    lines = []
    t0 = time.time()
    try:
        path, merged, sources, years, months = finxl.run(ticker, *YEARS, scope="both",
                                                 out_dir=os.path.join(OUT_DIR, ticker), log=lines.append)
    except Exception as e:
        return {"ticker": ticker, "error": f"{type(e).__name__}: {e}", "log": lines[-20:],
                "trace": traceback.format_exc()[-1500:], "seconds": round(time.time() - t0)}
    ok = [s for s in sources if s["check"].startswith("OK")]
    bad = [s for s in sources if s["check"].startswith(("CHECK", "MISSING"))]
    res = {
        "ticker": ticker,
        "reports": sorted({s["fy"] for s in sources}),
        "not_applicable": sum(1 for s in sources if s["check"].startswith("N/A")),
        "ok": len(ok), "check": sum(1 for s in bad if s["check"].startswith("CHECK")),
        "missing": sum(1 for s in bad if s["check"].startswith("MISSING")),
        "problems": [f"FY{s['fy']} {s['scope']} {s['statement']}: {s['check']}" for s in bad],
        "ai_used": sum(1 for s in sources if s["method"] not in ("parser", "-")),
    }
    # "Matches the report": figures confirmed by the report's own totals (quality.py)
    res.update({f"q_{k}": v for k, v in finxl.quality_totals(sources).items()})
    # headline EPS per scope and year, to compare runs (per-share unit bug, #80)
    res["eps"] = {}
    for (sc, kind), rows in merged.items():
        if kind == "pl":
            r = next((r for r in rows if not r["is_header"] and r["values"]
                      and finxl.EPS_RX.search(finxl.norm_label(r["label"]))), None)
            if r:
                res["eps"][sc] = {str(y): v for y, v in r["values"].items()}
    res["q_issues"] = [f"FY{s['fy']} {s['scope']} {s['statement']}: {finxl.quality.summary_text(s['quality'])}"
                       for s in sources if s.get("quality") and (s["quality"]["failed_totals"] or s["quality"]["bad_labels"])]
    try:
        _, results, per_source = accuracy_check.check(ticker, path)
        res["verified"] = sum(1 for r in results if r["status"] == "OK")
        res["compared"] = len(results)
        res["per_source"] = per_source
        res["accuracy_issues"] = [f"{r['status']} {r['scope']} {r['metric']} FY{r['year']}: ours={r['ours']} "
                                  + " ".join(f"{k}={v}" for k, v in r["sources"].items())
                                  for r in results if r["status"] != "OK"]
    except Exception as e:
        res["accuracy_error"] = f"{type(e).__name__}: {e}"
    res["seconds"] = round(time.time() - t0)
    return res


def main():
    args = sys.argv[1:]
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 3
    rnd = int(args[args.index("--round") + 1]) if "--round" in args else None
    with open(os.path.join(HERE, "companies.json")) as f:
        companies = json.load(f)
    named = [a.upper() for a in args if not a.startswith("--") and not a.isdigit()]
    todo = [c for c in companies if (not named or c["ticker"] in named) and (rnd is None or c["round"] == rnd)]
    todo += [{"ticker": t, "sector": "?", "round": 0} for t in named if t not in {c["ticker"] for c in companies}]

    baseline = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as f:
            baseline = json.load(f)

    print(f"Running {len(todo)} companies with {workers} workers ...", flush=True)
    results = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_one, c["ticker"]): c for c in todo}
        for fut in as_completed(futs):
            r = fut.result()
            results[r["ticker"]] = r
            if "error" in r:
                print(f"  {r['ticker']:11} ERROR {r['error']}", flush=True)
            else:
                print(f"  {r['ticker']:11} OK {r['ok']:3}  CHECK {r['check']:2}  MISSING {r['missing']:2}  "
                      f"verified {r.get('verified', '?')}/{r.get('compared', '?')}  "
                      f"report-confirmed {r.get('q_confirmed', 0)}/{r.get('q_cells', 0)}  "
                      f"bad totals {r.get('q_failed_totals', 0)}  bad labels {r.get('q_bad_labels', 0)}  "
                      f"junk {r.get('q_junk_rows', 0)}  EPS off {r.get('q_eps_flags', 0)}  ({r['seconds']}s)",
                      flush=True)

    # Compare with baseline
    regressions = []
    for t, r in results.items():
        b = baseline.get(t)
        if not b or "error" in r:
            continue
        if r["ok"] < b.get("ok", 0):
            regressions.append(f"{t}: OK statements {b['ok']} -> {r['ok']}")
        if r.get("verified", 0) < b.get("verified", 0):
            regressions.append(f"{t}: verified figures {b['verified']} -> {r.get('verified')}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M")
    for name in ("latest.json", f"run_{stamp}.json"):
        with open(os.path.join(RESULTS_DIR, name), "w") as f:
            json.dump(results, f, indent=1, default=str)

    # Gold / silver: plain file comparison of whole statements, no AI calls
    gold_result = None
    if "--no-gold" not in args:
        import gold
        print("\nComparing with the gold and silver copies ...", flush=True)
        tickers = [c["ticker"] for c in todo] if (named or rnd is not None) else None
        gold_result = gold.gold_check("all", tickers=tickers)
        regressions += [f"GOLD {x}" for x in gold_result["failures"]]
        with open(os.path.join(RESULTS_DIR, "gold_latest.json"), "w") as f:
            json.dump(gold_result, f, indent=1, default=str)

    tot = {k: sum(r.get(k, 0) for r in results.values() if "error" not in r)
           for k in ("ok", "check", "missing", "verified", "compared",
                     "q_cells", "q_confirmed", "q_totals", "q_failed_totals", "q_bad_labels",
                     "q_junk_rows", "q_eps_checked", "q_eps_flags")}
    print(f"\nTOTAL statements OK {tot['ok']}  CHECK {tot['check']}  MISSING {tot['missing']}  |  "
          f"figures verified {tot['verified']}/{tot['compared']}")
    if tot["q_cells"]:
        print(f"MATCHES THE REPORT: {tot['q_confirmed']}/{tot['q_cells']} figures confirmed by the report's own totals "
              f"({100 * tot['q_confirmed'] / tot['q_cells']:.1f}%)  |  totals not adding up "
              f"{tot['q_failed_totals']}/{tot['q_totals']}  |  garbled labels {tot['q_bad_labels']}  |  "
              f"junk rows {tot['q_junk_rows']}  |  EPS off {tot['q_eps_flags']}/{tot['q_eps_checked']}")
    if gold_result and gold_result["warnings"]:
        print(f"\nSilver differences (warnings, not regressions): {len(gold_result['warnings'])} statements; "
              "details in tests/results/gold_latest.json")
    if regressions:
        print("\nREGRESSIONS vs baseline:")
        for x in regressions:
            print("  " + x)
    elif baseline:
        print("\nNo regressions vs baseline.")

    if "--update-baseline" in args:
        baseline.update({t: {k: r.get(k) for k in ("ok", "check", "missing", "verified", "compared")}
                         for t, r in results.items() if "error" not in r})
        with open(BASELINE, "w") as f:
            json.dump(baseline, f, indent=1, sort_keys=True)
        print(f"Baseline updated for {len(results)} companies.")
    sys.exit(1 if regressions else 0)


if __name__ == "__main__":
    main()
