"""
The engine's result as JSON: engine.json (enough to re-write the Excel later)
and run.json (what the app draws). Years are object keys, so they become strings
in JSON; load_engine() turns them back into ints.
"""

import ar_extract
import finxl
import quality

KIND_OF = {v: k for k, v in ar_extract.KINDS.items()}
YEAR_MAPS = ("values", "prio", "status", "src", "group", "own", "newest", "newest_src", "eps_flag", "eps_expect")


def _is_total(kind, label):
    return bool(quality._is_target(kind, label)) or finxl.is_total(label)


def engine_payload(ticker, company, url, req, out):
    path, merged, sources, years, months = out
    return {
        "ticker": ticker, "company": company, "url": url,
        "years": years, "months": {str(k): v for k, v in (months or {}).items()},
        "scopes": sorted({k[0] for k in merged}, key=lambda s: s != "consolidated"),
        "restated": req["figures"] == "restated",
        "merged": {f"{s}|{k}": rows for (s, k), rows in merged.items()},
        "sources": sources,
    }


def load_engine(data):
    """engine.json back to the shapes finxl uses (int years, tuple keys)."""
    merged = {}
    for key, rows in data["merged"].items():
        s, k = key.split("|")
        for r in rows:
            for m in YEAR_MAPS:
                if isinstance(r.get(m), dict):
                    r[m] = {int(y): v for y, v in r[m].items()}
        merged[(s, k)] = rows
    months = {int(k): v for k, v in (data.get("months") or {}).items()} or None
    return merged, months


def _row(kind, r):
    out = {
        "label": r["label"], "level": r.get("level", 0), "header": bool(r["is_header"]),
        "total": (not r["is_header"]) and _is_total(kind, r["label"]),
        "values": r.get("values", {}), "status": r.get("status", {}), "src": r.get("src", {}),
        "group": r.get("group", {}), "labelOk": r.get("label_ok", True),
    }
    if r.get("junk"):
        out["junk"] = r["junk"]
    # A restatement: the year's own report printed a different figure than the newest report.
    own, newest = r.get("own", {}), r.get("newest", {})
    alt = {y: {"own": own[y], "newest": newest[y], "newestFy": r["newest_src"][y]}
           for y in own if y in newest and abs(own[y] - newest[y]) > 0.011}
    if alt:
        out["restated"] = alt
    if r.get("eps_flag"):
        out["epsFlag"] = r["eps_flag"]
        out["epsExpect"] = r.get("eps_expect", {})
    return out


def run_payload(run, eng, reports):
    merged, months = load_engine(eng)
    years = eng["years"]
    books = {}
    for scope in eng["scopes"]:
        stmts = {}
        for (s, kind), rows in merged.items():
            if s == scope and rows:
                stmts[kind] = {"title": ar_extract.KINDS[kind], "rows": [_row(kind, r) for r in rows]}
        books[scope] = {"statements": stmts, "summary": finxl.summary_values(merged, scope, years)}
    sources = []
    for s in eng["sources"]:
        sources.append({
            "fy": s["fy"], "scope": s["scope"], "kind": KIND_OF.get(s["statement"], s["statement"]),
            "pages": [p.strip() for p in str(s.get("pages") or "").split(",") if p.strip()],
            "method": s.get("method"), "check": s.get("check"), "url": s.get("url"),
            "quality": s.get("quality"),
        })
    q = finxl.quality_totals(eng["sources"])
    return {
        "id": run["id"],
        "request": {"symbol": run["symbol"], "from": run["from_fy"], "to": run["to_fy"], "scope": run["scope"],
                    "figures": run["figures"], "ai": run["ai"]},
        "company": {"symbol": eng["ticker"], "name": eng["company"], "url": eng["url"]},
        "years": years,
        "columns": {str(y): finxl.col_label(y, months) for y in years},
        "scopes": eng["scopes"],
        "books": books,
        "sources": sources,
        "reports": reports,
        "quality": q,
        "secondReadings": [],
        "createdAt": run["created_at"],
    }


def headline(eng):
    """Confirmed % and number of things to review, for the library list."""
    q = finxl.quality_totals(eng["sources"])
    pct = round(100.0 * q["confirmed"] / q["cells"], 1) if q["cells"] else None
    return pct, q["failed_totals"] + q["eps_flags"] + q["bad_labels"]
