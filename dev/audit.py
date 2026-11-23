"""
audit.py — sampling audit (CHAT_HANDOFF item 4)
-----------------------------------------------
Draws a fixed random sample of figures from the test companies' Excels so Harsh
can check each one against the PDF by eye (screen: audit_ui.py, opened from the
app), then turns his answers into an accuracy report.

The sample deliberately covers all three groups of the arithmetic check
(quality.py):
    confirmed   - part of a total that adds up in the report itself
    unchecked   - can't be checked (EPS, memo lines, ...; not part of any total)
    flagged     - a total that doesn't add up (yellow cell in the Excel)
Because the groups are over-/under-sampled on purpose, the overall accuracy is
reported both as the plain sample figure and re-weighted by each group's share
of all figures.

The group of each figure isn't stored in the Excel, so `sample` re-runs the
normal pipeline (finxl.run, unchanged, no AI) on each company with the same
settings as tests/regression.py: the Excel it writes is the regression Excel.
PDFs are cached, so the only network call is the Screener report list.

Usage:
    python audit.py sample                       all companies in tests/companies.json
    python audit.py sample TCS INFY --years 2024-2026    (testing)
    python audit.py sample --workers 4 --n 100 --seed 20261104
    python audit.py report                       writes tests/audit/report.md + report.json

Files (tests/audit/):
    sample.json    the drawn sample (fixed seed; re-drawing needs --force)
    progress.json  Harsh's answers, saved after every click
    report.md/json the accuracy report
Per-company figure lists are cached in test_output/audit_cells/ (not versioned).
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', "engine"))
import argparse
import datetime
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
# DOCFETCHER_AUDIT_DIR points the sample/progress/report elsewhere (used for test runs)
AUDIT_DIR = os.environ.get("DOCFETCHER_AUDIT_DIR") or os.path.join(ROOT, "tests", "audit")
SAMPLE_FILE = os.path.join(AUDIT_DIR, "sample.json")
PROGRESS_FILE = os.path.join(AUDIT_DIR, "progress.json")
REPORT_MD = os.path.join(AUDIT_DIR, "report.md")
REPORT_JSON = os.path.join(AUDIT_DIR, "report.json")
CELLS_DIR = os.path.join(ROOT, "test_output", "audit_cells")
OUT_DIR = os.path.join(ROOT, "test_output")

DEFAULT_SEED = 20261104
DEFAULT_YEARS = (2020, 2026)  # = tests/regression.py YEARS
GROUPS = ("confirmed", "unchecked", "flagged")
GROUP_NAMES = {"confirmed": "Confirmed by the report's totals",
               "unchecked": "Can't be checked (EPS, memo lines, ...)",
               "flagged": "Flagged (total doesn't add up)"}
# Share of the sample per group. Flagged figures are rare, so they're over-sampled
# to get a usable accuracy for them; any shortfall is filled from the other groups.
QUOTAS = {"confirmed": 0.5, "unchecked": 0.3, "flagged": 0.2}
VERDICTS = ("correct", "wrong", "cant_tell")
REASONS = ("wrong number", "wrong year column", "wrong sign", "wrong unit", "garbled label", "other")
KIND_NAMES = {"pl": "Profit & Loss", "bs": "Balance Sheet", "cf": "Cash Flow", "ra": "Revenue Account"}


# ── Collecting the figures of one company ─────────────────────────────────────
def collect_cells(ticker, years=DEFAULT_YEARS, use_cache=True):
    """Every figure in the company's Excel with its group, source report and pages."""
    cache = os.path.join(CELLS_DIR, f"{ticker}_{years[0]}-{years[1]}.json")
    if use_cache and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    import finxl
    import pdfview
    log = []
    path, merged, sources, yrs, _ = finxl.run(ticker, years[0], years[1], scope="both",
                                              out_dir=os.path.join(OUT_DIR, ticker), log=log.append)
    company = ticker
    try:
        from openpyxl import load_workbook
        title = load_workbook(path, read_only=True)["Summary"]["A1"].value or ""
        company = title.split(" (")[0] or ticker
    except Exception:
        pass
    src_map = {(s["fy"], s["scope"], s["statement"]): s for s in sources}
    cells = []
    for (scope, kind), rows in merged.items():
        sheet = finxl.SHEET_NAMES[(scope, kind)]
        for i, r in enumerate(rows):
            for y, v in r["values"].items():
                fy = r.get("src", {}).get(y)
                if v is None or fy is None or y not in yrs:
                    continue  # synthetic totals (no source report) or a year outside the Excel
                src = src_map.get((fy, scope, KIND_NAMES[kind])) or {}
                st = r.get("status", {}).get(y)
                pdf = pdfview.pdf_path(None, ticker, fy)
                cells.append({
                    "ticker": ticker, "company": company, "scope": scope, "kind": kind, "sheet": sheet,
                    "row": i + 3, "label": r["label"], "year": y, "value": v,
                    "group": "confirmed" if st == "ok" else "flagged" if st == "fail" else "unchecked",
                    "report_fy": fy, "pages": src.get("pages", ""), "url": src.get("url", ""),
                    "pdf": pdfview.rel_to_cache(pdf) if pdf else None,
                    "excel": os.path.relpath(path, ROOT).replace(os.sep, "/"),
                })
    os.makedirs(CELLS_DIR, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(cells, f)
    return cells


def _collect_worker(args):
    ticker, years, use_cache = args
    t0 = time.time()
    try:
        return ticker, collect_cells(ticker, years, use_cache), None, round(time.time() - t0)
    except Exception as e:
        return ticker, [], f"{type(e).__name__}: {e}", round(time.time() - t0)


# ── Drawing the sample ────────────────────────────────────────────────────────
def draw_sample(cells, n=100, seed=DEFAULT_SEED, quotas=QUOTAS):
    """
    Stratified sample: a quota per group, and within each group the figures are
    spread over companies (round robin), then statement type, scope and year
    (each pick prefers the least-used combination so far).
    """
    rng = random.Random(seed)
    by_group = {g: [c for c in cells if c["group"] == g] for g in GROUPS}
    want = {g: int(round(n * quotas[g])) for g in GROUPS}
    # move the shortfall of small groups to the others, largest first
    short = sum(max(0, want[g] - len(by_group[g])) for g in GROUPS)
    for g in GROUPS:
        want[g] = min(want[g], len(by_group[g]))
    for g in sorted(GROUPS, key=lambda g: -len(by_group[g])):
        extra = min(short, len(by_group[g]) - want[g])
        want[g] += extra
        short -= extra
    used = {"ticker": {}, "kind": {}, "scope": {}, "year": {}}
    picked = []
    for g in GROUPS:
        pool = list(by_group[g])
        rng.shuffle(pool)
        tickers = sorted({c["ticker"] for c in pool})
        rng.shuffle(tickers)
        per_t = {t: [c for c in pool if c["ticker"] == t] for t in tickers}
        while len([p for p in picked if p["group"] == g]) < want[g] and any(per_t.values()):
            live = [t for t in tickers if per_t[t]]
            # the company with the fewest picks so far (ties: shuffled order)
            t = min(live, key=lambda t: (used["ticker"].get(t, 0), tickers.index(t)))
            cands = per_t[t]

            def cost(c):
                return (used["kind"].get(c["kind"], 0) + used["scope"].get(c["scope"], 0)
                        + used["year"].get(c["year"], 0) + rng.random() * 0.5)
            c = min(cands, key=cost)
            cands.remove(c)
            picked.append(c)
            for dim in ("ticker", "kind", "scope", "year"):
                used[dim][c[dim]] = used[dim].get(c[dim], 0) + 1
    rng.shuffle(picked)  # mixed order on screen, so groups can't bias the reviewer
    for i, c in enumerate(picked, 1):
        c["id"] = f"a{i:03d}"
    return picked


def population(cells):
    out = {g: sum(1 for c in cells if c["group"] == g) for g in GROUPS}
    out["total"] = len(cells)
    return out


# ── Progress (saved after every click) ────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    """Write via a temp file so a crash mid-save can't corrupt earlier answers."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def load_sample():
    return load_json(SAMPLE_FILE, None)


def load_progress():
    return load_json(PROGRESS_FILE, {"answers": {}})


def record_answer(item_id, verdict, reason=None, note=""):
    assert verdict in VERDICTS
    prog = load_progress()
    prog.setdefault("answers", {})[item_id] = {
        "verdict": verdict, "reason": reason if verdict == "wrong" else None, "note": note or "",
        "at": datetime.datetime.now().isoformat(timespec="seconds")}
    prog["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    save_json(PROGRESS_FILE, prog)
    return prog


# ── Report ────────────────────────────────────────────────────────────────────
def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n (good for small n and p near 1)."""
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


def build_report(sample=None, progress=None):
    sample = sample or load_sample()
    progress = progress or load_progress()
    ans = progress.get("answers", {})
    items = sample["items"]
    rows = []
    for it in items:
        a = ans.get(it["id"])
        rows.append((it, a["verdict"] if a else None, a))
    rep = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
           "sample_size": len(items), "answered": sum(1 for _, v, _ in rows if v),
           "seed": sample.get("seed"), "groups": {}, "errors": [], "errors_by_reason": {}}

    def stats(sel):
        n_ok = sum(1 for _, v, _ in sel if v == "correct")
        n_bad = sum(1 for _, v, _ in sel if v == "wrong")
        n_ct = sum(1 for _, v, _ in sel if v == "cant_tell")
        n = n_ok + n_bad
        lo, hi = wilson(n_ok, n)
        return {"sampled": len(sel), "correct": n_ok, "wrong": n_bad, "cant_tell": n_ct,
                "unanswered": sum(1 for _, v, _ in sel if not v), "judged": n,
                "accuracy": n_ok / n if n else None, "ci95": [lo, hi]}

    rep["overall_sample"] = stats(rows)
    pop = sample.get("population", {})
    w_acc, w_var, w_tot = 0.0, 0.0, 0
    for g in GROUPS:
        s = stats([r for r in rows if r[0]["group"] == g])
        s["population"] = pop.get(g)
        rep["groups"][g] = s
        if s["judged"] and pop.get(g):
            p = s["accuracy"]
            w_acc += pop[g] * p
            w_var += pop[g] ** 2 * p * (1 - p) / s["judged"]
            w_tot += pop[g]
    if w_tot:
        acc = w_acc / w_tot
        se = math.sqrt(w_var) / w_tot
        # a stratum with 0 errors has zero variance; floor the half-width with the
        # overall Wilson interval so the range is never reported as exactly ±0
        lo_w, hi_w = rep["overall_sample"]["ci95"]
        half = max(1.96 * se, ((hi_w - lo_w) / 2) if lo_w is not None else 0)
        rep["overall_weighted"] = {"accuracy": acc, "ci95": [max(0.0, acc - half), min(1.0, acc + half)],
                                   "note": "each group weighted by its share of all figures"}
    for it, v, a in rows:
        if v == "wrong":
            reason = a.get("reason") or "other"
            rep["errors_by_reason"][reason] = rep["errors_by_reason"].get(reason, 0) + 1
            rep["errors"].append({k: it.get(k) for k in ("id", "ticker", "scope", "kind", "label", "year",
                                                          "value", "group", "report_fy", "pages")}
                                 | {"reason": reason, "note": a.get("note", "")})
    return rep


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def rng_txt(ci):
    return "–" if not ci or ci[0] is None else f"{pct(ci[0])} – {pct(ci[1])}"


def report_markdown(rep):
    o = rep["overall_sample"]
    L = [f"# Sampling audit report", "",
         f"Generated {rep['generated']}. Sample of {rep['sample_size']} figures (seed {rep['seed']}), "
         f"{rep['answered']} answered. 95% ranges are Wilson intervals; 'can't tell' answers are left out "
         "of the accuracy.", ""]
    if rep.get("overall_weighted"):
        w = rep["overall_weighted"]
        L.append(f"**Overall accuracy (weighted by group size): {pct(w['accuracy'])}** "
                 f"(95% range {rng_txt(w['ci95'])}). Groups with no judged figures yet are left out of the weighting.")
        L.append("")
    L.append(f"Plain sample accuracy: {pct(o['accuracy'])} ({o['correct']} of {o['judged']} judged; "
             f"95% range {rng_txt(o['ci95'])}); can't tell: {o['cant_tell']}, "
             f"unanswered: {o['unanswered']}.")
    L += ["", "| Group | Figures in all Excels | Sampled | Correct | Wrong | Can't tell | Accuracy | 95% range |",
          "|---|---:|---:|---:|---:|---:|---:|---|"]
    for g in GROUPS:
        s = rep["groups"][g]
        L.append(f"| {GROUP_NAMES[g]} | {s['population'] if s['population'] is not None else '?'} | {s['sampled']} | "
                 f"{s['correct']} | {s['wrong']} | {s['cant_tell']} | {pct(s['accuracy'])} | {rng_txt(s['ci95'])} |")
    L += ["", "## Errors by reason", ""]
    if rep["errors_by_reason"]:
        L += ["| Reason | Count |", "|---|---:|"]
        L += [f"| {r} | {n} |" for r, n in sorted(rep["errors_by_reason"].items(), key=lambda x: -x[1])]
        L += ["", "## Every error", "",
              "| # | Company | Statement | Year | Label | Our value (₹ cr) | Group | Report / pages | Reason | Note |",
              "|---|---|---|---|---|---:|---|---|---|---|"]
        for e in rep["errors"]:
            L.append(f"| {e['id']} | {e['ticker']} | {e['scope']} {KIND_NAMES.get(e['kind'], e['kind'])} | "
                     f"FY{e['year']} | {e['label']} | {e['value']} | {e['group']} | FY{e['report_fy']} p.{e['pages']} | "
                     f"{e['reason']} | {e['note']} |")
    else:
        L.append("No errors recorded.")
    return "\n".join(L) + "\n"


def write_report():
    rep = build_report()
    save_json(REPORT_JSON, rep)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report_markdown(rep))
    return rep


# ── CLI ───────────────────────────────────────────────────────────────────────
def cmd_sample(a):
    if os.path.exists(SAMPLE_FILE) and not a.force:
        sys.exit(f"{SAMPLE_FILE} already exists (the sample is fixed so it can be re-shown). "
                 "Use --force to draw a new one; this also needs a fresh progress.json.")
    if a.tickers:
        tickers = [t.upper() for t in a.tickers]
    else:
        with open(os.path.join(ROOT, "tests", "companies.json")) as f:
            tickers = [c["ticker"] for c in json.load(f)]
    s, _, e = a.years.partition("-")
    years = (int(s), int(e or s))
    print(f"Collecting figures for {len(tickers)} companies (FY{years[0]}-FY{years[1]}, both scopes) ...", flush=True)
    cells, failed = [], {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(_collect_worker, (t, years, not a.no_cache)) for t in tickers]
        for fut in as_completed(futs):
            t, cs, err, secs = fut.result()
            if err:
                failed[t] = err
                print(f"  {t:11} FAILED {err} ({secs}s)", flush=True)
            else:
                cells += cs
                pc = population(cs)
                print(f"  {t:11} {pc['total']:5} figures  confirmed {pc['confirmed']}  unchecked {pc['unchecked']}  "
                      f"flagged {pc['flagged']}  ({secs}s)", flush=True)
    cells.sort(key=lambda c: (c["ticker"], c["scope"], c["kind"], c["row"], c["year"]))  # seed-stable order
    items = draw_sample(cells, a.n, a.seed)
    sample = {"format": "docfetcher-audit-sample/1",
              "created": datetime.datetime.now().isoformat(timespec="seconds"),
              "seed": a.seed, "years": list(years), "companies": sorted({c["ticker"] for c in cells}),
              "failed_companies": failed, "population": population(cells), "quotas": QUOTAS, "items": items}
    save_json(SAMPLE_FILE, sample)
    if a.force and os.path.exists(PROGRESS_FILE):
        os.replace(PROGRESS_FILE, PROGRESS_FILE.replace(".json", time.strftime("_old_%Y%m%d_%H%M%S.json")))
    got = {g: sum(1 for i in items if i["group"] == g) for g in GROUPS}
    print(f"\nSample of {len(items)} saved to {SAMPLE_FILE}: " + ", ".join(f"{g} {n}" for g, n in got.items()))
    print(f"  companies {len({i['ticker'] for i in items})}, statements "
          + ", ".join(f"{k} {sum(1 for i in items if i['kind'] == k)}" for k in KIND_NAMES if any(i['kind'] == k for i in items))
          + f", consolidated {sum(1 for i in items if i['scope'] == 'consolidated')}"
          + f", standalone {sum(1 for i in items if i['scope'] == 'standalone')}")


def main():
    ap = argparse.ArgumentParser(description="Sampling audit: draw the sample / write the report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="re-run the pipeline on the test companies and draw the sample")
    s.add_argument("tickers", nargs="*")
    s.add_argument("--years", default=f"{DEFAULT_YEARS[0]}-{DEFAULT_YEARS[1]}")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=DEFAULT_SEED)
    s.add_argument("--workers", type=int, default=3)
    s.add_argument("--force", action="store_true", help="replace an existing sample")
    s.add_argument("--no-cache", action="store_true", help="re-run companies already collected")
    sub.add_parser("report", help="write tests/audit/report.md and report.json from progress.json")
    a = ap.parse_args()
    if a.cmd == "sample":
        cmd_sample(a)
    else:
        rep = write_report()
        print(report_markdown(rep))
        print(f"Saved {REPORT_MD} and {REPORT_JSON}")


if __name__ == "__main__":
    main()
