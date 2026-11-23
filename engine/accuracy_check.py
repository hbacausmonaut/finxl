"""
accuracy_check.py
-----------------
Cross-checks a finxl.py workbook against outside sources, year by year.

NSE-first (CHAT_HANDOFF item 5c):
  - NSE XBRL  MAIN check. The company's audited annual results as filed with NSE.
              An NSE filing states each year's figures AS ORIGINALLY REPORTED, so it is
              compared with our as-originally-reported figure for that year. When the
              workbook shows a later restated figure that differs, that year's own annual
              report is read again (only for those years) to get the original figure.
              Filings up to FY2024: "corporates-financial-results"; FY2025 on: SEBI's
              "Integrated Filing - Financials".
  - Screener  used ONLY where NSE has no figure, and reported separately. Screener shows
              the latest (restated) figures, so it is compared with the workbook value.
  - Yahoo     information only (never counts towards "verified"); needs yfinance, and is
              only fetched with --yahoo.

Metrics: Revenue, Net profit, Total assets, Cash from operations (₹ crore).
A figure is "verified" when the source used for it (NSE, else Screener) agrees within 0.5%.

Usage:
    python accuracy_check.py HCLTECH                 (latest workbook in HCLTECH/)
    python accuracy_check.py HCLTECH path/to/file.xlsx
    python accuracy_check.py HCLTECH --json          (machine-readable, for regression.py)
    python accuracy_check.py HCLTECH --yahoo         (also show Yahoo, for information)
"""

import glob
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

import fetchdocs
from finxl import CACHE_DIR, TO_CRORE, norm_label, pick_row

METRICS = ["Revenue", "Net profit", "Total assets", "Cash from operations"]

# our sheet suffix + label regex (on normalised labels) per metric
OURS = {
    "Revenue": ("P&L", r"^revenue from operations|^interest earned$|^total revenue from operations"),
    "Net profit": ("P&L", r"^(net )?profit (loss )?(year|period)$|^net profit$|^profit (loss )?after tax$"
                          r"|^(consolidated )?net profit (loss )?year( before minority interest)?$"),
    "Total assets": ("Balance Sheet", r"^total assets( [a-z]{1,5})?$|^total application funds$"),
    "Cash from operations": ("Cash Flow", r"^net cash.*operating"),
}
KIND_OF = {"Revenue": "pl", "Net profit": "pl", "Total assets": "bs", "Cash from operations": "cf"}
SCREENER_ROWS = {
    "Revenue": ("profit-loss", r"^(sales|revenue)$"),
    "Net profit": ("profit-loss", r"^net profit$"),
    "Total assets": ("balance-sheet", r"^total assets$"),
    "Cash from operations": ("cash-flow", r"^cash from operating activity$"),
}
NSE_TAGS = {
    "Revenue": ["RevenueFromOperations", "InterestEarned"],
    "Net profit": ["ProfitLossForPeriod", "ProfitLossForThePeriod"],
    "Total assets": ["Assets", "TotalAssets"],
    "Cash from operations": ["CashFlowsFromUsedInOperatingActivities", "NetCashFlowsFromUsedInOperatingActivities"],
}
YAHOO_ROWS = {
    "Revenue": ("income_stmt", ["Operating Revenue", "Total Revenue"]),
    "Net profit": ("income_stmt", ["Net Income Including Noncontrolling Interests", "Net Income"]),
    "Total assets": ("balance_sheet", ["Total Assets"]),
    "Cash from operations": ("cashflow", ["Operating Cash Flow"]),
}
CRORE = 1e7
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
# XBRL taxonomies: "in-bse-fin" (results up to FY2024), "in-capmkt" (Integrated Filing, FY2025 on)
NS = r"in-[a-z-]+"


# ── Sources ───────────────────────────────────────────────────────────────────
def screener_source(ticker):
    """{scope: {metric: {year: value}}} from screener.in."""
    out = {}
    for scope, consolidated in (("consolidated", True), ("standalone", False)):
        url = f"https://www.screener.in/company/{ticker}/" + ("consolidated/" if consolidated else "")
        try:
            html = requests.get(url, headers=fetchdocs.HEADERS, timeout=30).text
        except requests.RequestException:
            continue
        soup = BeautifulSoup(html, "html.parser")
        tables = {}
        for sec in ("profit-loss", "balance-sheet", "cash-flow"):
            node = soup.find("section", id=sec)
            table = node.find("table") if node else None
            if not table:
                continue
            heads = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]
            years = [int(m.group(1)) if (m := re.match(r"Mar (\d{4})", h)) else None for h in heads]
            rows = {}
            for tr in table.find("tbody").find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if not cells:
                    continue
                label = re.sub(r"[\s+ ]+$", "", cells[0]).strip().lower()
                vals = {}
                for y, c in zip(years[1:], cells[1:]):
                    c = c.replace(",", "").replace("%", "")
                    if y and re.fullmatch(r"-?\d+(\.\d+)?", c):
                        vals[y] = float(c)
                rows[label] = vals
            tables[sec] = rows
        out[scope] = {m: next((v for k, v in tables.get(sec, {}).items() if re.search(rx, k)), {})
                      for m, (sec, rx) in SCREENER_ROWS.items()}
    return out


def _xbrl_facts(xml):
    """{tag: value} for undimensioned full-year (or year-end instant) facts."""
    ctx = {}
    for cid, body in re.findall(r'<xbrli:context id="([^"]+)">(.*?)</xbrli:context>', xml, re.S):
        if "explicitMember" in body or "typedMember" in body:
            continue  # segment / component facts
        s = re.search(r"<xbrli:startDate>([^<]+)<", body)
        e = re.search(r"<xbrli:endDate>([^<]+)<", body)
        i = re.search(r"<xbrli:instant>([^<]+)<", body)
        ctx[cid] = (s.group(1) if s else None, e.group(1) if e else None, i.group(1) if i else None)
    end = re.search(rf"<{NS}:DateOfEndOfFinancialYear[^>]*>([^<]+)<", xml)
    start = re.search(rf"<{NS}:DateOfStartOfFinancialYear[^>]*>([^<]+)<", xml)
    if not end:
        return {}, None
    end, start = end.group(1).strip(), start.group(1).strip() if start else None
    defined = set(re.findall(r'<xbrli:context id="([^"]+)"', xml))
    # The filing states each main context's period as DateOfStart/EndOfReportingPeriod facts.
    # They win over the context definition: older filings (2018-2022) don't define the main
    # contexts at all, and 2023-2024 filings define the full-year context "FourD" with the
    # quarter's dates (so full-year revenue and profit were skipped before).
    rep = {}
    for which, cid, val in re.findall(rf'<{NS}:DateOf(Start|End)OfReportingPeriod [^>]*contextRef="([^"]+)"'
                                      r'[^>]*>([^<]+)<', xml):
        rep.setdefault(cid, {})[which] = val.strip()
    for cid, d in rep.items():
        if not d.get("End") or not (cid not in defined or cid in ctx):
            continue
        st = d.get("Start")
        if st is None and cid == "FourD" and d["End"] == end:
            st = start  # bank filings give only end dates; by NSE's layout "Four" = year to date
        ctx[cid] = (st, d["End"], None)
    facts = {}
    for tag, cid, val in re.findall(rf'<{NS}:(\w+) [^>]*contextRef="([^"]+)"[^>]*>([^<]*)<', xml):
        c = ctx.get(cid)
        if c is None and cid not in defined and re.fullmatch(r"\w*I", cid):
            c = (None, None, end)  # undefined instant context: balance sheet date
        if c is None and cid in defined:
            continue  # dimensioned context
        if not c or not re.fullmatch(r"-?\d+(\.\d+)?", val.strip()):
            continue
        full_year = c[1] == end and (start is None or c[0] == start)
        if full_year or c[2] == end:
            facts.setdefault(tag, float(val))
    return facts, int(end[:4])


def _nse_filings(s, ticker):
    """Annual results filings: [{"url", "scope", "fy"(or None)}], newest index first."""
    filings = []
    r = s.get("https://www.nseindia.com/api/corporates-financial-results",
              params={"index": "equities", "symbol": ticker, "period": "Annual"}, headers=NSE_HEADERS, timeout=30)
    for fl in r.json():
        url = fl.get("xbrl") or ""
        if url.endswith(".xml") and fl.get("audited") == "Audited":
            filings.append({"url": url, "scope": "consolidated" if fl.get("consolidated") == "Consolidated"
                            else "standalone", "fy": None})
    # FY2025 onwards: SEBI Integrated Filing (Financials). The March quarter filing carries the full year.
    r = s.get("https://www.nseindia.com/api/integrated-filing-results",
              params={"index": "equities", "symbol": ticker, "type": "Integrated Filing- Financials", "size": 200},
              headers=NSE_HEADERS, timeout=30)
    for fl in (r.json() or {}).get("data", []):
        url = fl.get("xbrl") or ""
        qe = fl.get("qe_Date") or ""
        if url.endswith(".xml") and qe.upper().startswith("31-MAR") and fl.get("audited") == "Audited":
            filings.append({"url": url, "scope": "consolidated" if fl.get("consolidated") == "Consolidated"
                            else "standalone", "fy": int(qe[-4:]), "revised": fl.get("type_Sub") == "Revision"})
    return filings


def nse_source(ticker):
    """Official audited annual results XBRL filed with NSE (cached on disk)."""
    cache = os.path.join(CACHE_DIR, ticker, "nse_xbrl")
    os.makedirs(cache, exist_ok=True)
    index_file = os.path.join(cache, "filings.json")
    s = requests.Session()
    try:
        s.get("https://www.nseindia.com/", headers=NSE_HEADERS, timeout=20)
        filings = _nse_filings(s, ticker)
        with open(index_file, "w") as f:
            json.dump(filings, f)
    except Exception:
        if not os.path.exists(index_file):
            return {}
        with open(index_file) as f:
            filings = json.load(f)
    out = {}
    # Original filings first: a revision doesn't change "as originally reported"
    for fl in sorted(filings, key=lambda f: bool(f.get("revised"))):
        url = fl["url"]
        path = os.path.join(cache, os.path.basename(url))
        if not os.path.exists(path):
            try:
                x = s.get(url, headers=NSE_HEADERS, timeout=30).text
            except requests.RequestException:
                continue
            if "<xbrli:" not in x:
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(x)
        with open(path, encoding="utf-8") as f:
            facts, fy = _xbrl_facts(f.read())
        if not fy:
            continue
        for m, tags in NSE_TAGS.items():
            v = next((facts[t] for t in tags if t in facts), None)
            if v is not None:
                out.setdefault(fl["scope"], {}).setdefault(m, {}).setdefault(fy, round(v / CRORE, 2))
    return out


def yahoo_source(ticker):
    """Yahoo Finance via yfinance: consolidated, ~4 latest years. Information only."""
    try:
        import yfinance as yf
        t = yf.Ticker(f"{ticker}.NS")
        frames = {"income_stmt": t.income_stmt, "balance_sheet": t.balance_sheet, "cashflow": t.cashflow}
    except Exception:
        return {}
    out = {}
    for m, (frame, rows) in YAHOO_ROWS.items():
        df = frames.get(frame)
        if df is None or df.empty:
            continue
        row = next((r for r in rows if r in df.index), None)
        if not row:
            continue
        for col, v in df.loc[row].items():
            if v == v and col.month == 3:  # skip NaN; March year-ends only
                out.setdefault("consolidated", {}).setdefault(m, {})[col.year] = round(float(v) / CRORE, 2)
    return out


SOURCES = {"NSE XBRL": nse_source, "Screener": screener_source}  # used for "verified"
INFO_SOURCES = {"Yahoo": yahoo_source}                          # shown, never counted


# ── Our workbook ──────────────────────────────────────────────────────────────
def our_rows(ws):
    years = {}
    for ci, cell in enumerate(next(ws.iter_rows(min_row=2, max_row=2, values_only=True))[1:], 2):
        m = re.match(r"[A-Z][a-z]{2} (\d{4})", str(cell or ""))  # "Mar 2025", "Dec 2022"
        if m:
            years[ci] = int(m.group(1))
    rows = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        if row[0]:
            rows.append((norm_label(str(row[0])), {years[ci]: row[ci - 1] for ci in years
                                                   if isinstance(row[ci - 1], (int, float))}))
    return rows


def our_values(wb):
    out = {}
    for scope, prefix in (("consolidated", "Consol"), ("standalone", "Standalone")):
        for m, (suffix, rx) in OURS.items():
            name = f"{prefix} {suffix}"
            if name not in wb.sheetnames:
                continue
            rows = our_rows(wb[name])
            covered = set().union(*(v.keys() for _, v in rows)) if rows else set()
            indexed = [(nl, i, v) for i, (nl, v) in enumerate(rows)]
            vals = {}
            for y in covered:
                pick = pick_row(m, indexed, y)  # same rule the Summary sheet uses
                vals[y] = pick[2][y] if pick else None
            out.setdefault(scope, {})[m] = vals
    return out


def workbook_is_restated(wb):
    """finxl writes the figures basis on the Summary sheet ("Figures" row)."""
    if "Summary" not in wb.sheetnames:
        return True
    for row in wb["Summary"].iter_rows(min_row=1, max_row=15, max_col=2, values_only=True):
        if row[0] == "Figures" and isinstance(row[1], str):
            return not row[1].lower().startswith("as originally")
    return True


class AsReported:
    """
    Our as-originally-reported figure for (scope, metric, year): the value in that year's
    own annual report. Reads the cached PDF lazily, once per (year, scope).
    """

    def __init__(self, ticker):
        self.ticker = ticker
        self.cache = {}

    def _pdf(self, fy):
        folder = os.path.join(CACHE_DIR, self.ticker, "AnnualReports")
        for p in [os.path.join(folder, f"Annual Report {fy}.pdf")] + glob.glob(os.path.join(folder, f"*{fy}*.pdf")):
            if os.path.exists(p) and os.path.getsize(p) > 10_000:
                return p
        return None

    def value(self, scope, metric, year):
        key = (year, scope)
        if key not in self.cache:
            self.cache[key] = None
            path = self._pdf(year)
            if path:
                try:
                    import finxl
                    self.cache[key] = finxl.extract_report(path, year, [scope])
                except Exception:
                    self.cache[key] = None
        res = self.cache[key]
        item = (res or {}).get((scope, KIND_OF[metric])) or {}
        parsed = item.get("parsed")
        if not parsed or year not in (parsed.get("years") or []):
            return None
        col = parsed["years"].index(year)
        factor = TO_CRORE.get(parsed.get("unit"), 1.0)
        rows = [(norm_label(r["label"]), i, {year: round(r["values"][col] * factor, 4)}
                 if col < len(r["values"]) and r["values"][col] is not None else {})
                for i, r in enumerate(parsed["rows"])]
        pick = pick_row(metric, rows, year)
        return pick[2][year] if pick else None


def close(a, b):
    return a is not None and b is not None and abs(a - b) <= max(1.5, abs(b) * 0.005)


def check(ticker, path=None, sources=None, info=False, as_reported=True):
    """
    Returns (path, results, per_source). One result per (scope, metric, year) that a
    counted source covers:
      {"scope", "metric", "year", "ours", "sources": {name: value}, "basis": "NSE XBRL"|"Screener",
       "status": "OK"|"DIFF"|"MISSING", "agree": [...], "ours_as_reported": value or None, "note": str}
    per_source: {"NSE XBRL": {checked, match}, "Screener (no NSE figure)": {checked, match},
                 "Screener (all, info)": {checked, match}, ...info sources...}
    """
    ticker = ticker.upper()
    if not path:
        files = sorted(glob.glob(os.path.join(ticker, f"{ticker}_Financials_*.xlsx")), key=os.path.getmtime)
        path = files[-1]
    wb = load_workbook(path)
    ours = our_values(wb)
    restated = workbook_is_restated(wb)
    names = [n for n in SOURCES if not sources or n in sources]
    src_data = {name: SOURCES[name](ticker) for name in names}
    info_data = {name: fn(ticker) for name, fn in INFO_SOURCES.items()} if info else {}
    orig = AsReported(ticker) if as_reported and restated else None
    results = []
    for scope, metrics in ours.items():
        for m, vals in metrics.items():
            for y, ov in sorted(vals.items()):
                theirs = {name: d.get(scope, {}).get(m, {}).get(y) for name, d in src_data.items()}
                theirs = {k: v for k, v in theirs.items() if v is not None}
                if not theirs:
                    continue
                r = {"scope": scope, "metric": m, "year": y, "ours": ov, "sources": theirs,
                     "agree": [k for k, v in theirs.items() if close(ov, v)], "ours_as_reported": None, "note": ""}
                if "NSE XBRL" in theirs:
                    r["basis"] = "NSE XBRL"
                    nse = theirs["NSE XBRL"]
                    if close(ov, nse):
                        r["status"] = "OK"
                    else:
                        o = orig.value(scope, m, y) if orig else None
                        r["ours_as_reported"] = o
                        if close(o, nse):
                            r["status"] = "OK"
                            r["agree"] = sorted(set(r["agree"]) | {"NSE XBRL"})
                            r["note"] = f"agrees as originally reported ({o}); the workbook shows the restated {ov}"
                        else:
                            r["status"] = "MISSING" if ov is None and o is None else "DIFF"
                else:
                    r["basis"] = "Screener"
                    r["status"] = "OK" if close(ov, theirs["Screener"]) else ("MISSING" if ov is None else "DIFF")
                for name, d in info_data.items():
                    v = d.get(scope, {}).get(m, {}).get(y)
                    if v is not None:
                        r.setdefault("info", {})[name] = v
                results.append(r)
    per_source = {}
    nse = [r for r in results if r["basis"] == "NSE XBRL"]
    scr = [r for r in results if r["basis"] == "Screener"]
    per_source["NSE XBRL"] = {"checked": len(nse), "match": sum(1 for r in nse if r["status"] == "OK"),
                              "restated_later": sum(1 for r in nse if r["note"])}
    per_source["Screener (no NSE figure)"] = {"checked": len(scr), "match": sum(1 for r in scr if r["status"] == "OK")}
    allscr = [r for r in results if "Screener" in r["sources"]]
    per_source["Screener (all, info)"] = {"checked": len(allscr),
                                          "match": sum(1 for r in allscr if "Screener" in r["agree"])}
    for name in info_data:
        rel = [r for r in results if name in r.get("info", {})]
        per_source[f"{name} (info)"] = {"checked": len(rel),
                                        "match": sum(1 for r in rel if close(r["ours"], r["info"][name]))}
    return path, results, per_source


def summary_lines(results, per_source):
    n = per_source["NSE XBRL"]
    s = per_source["Screener (no NSE figure)"]
    ok = sum(1 for r in results if r["status"] == "OK")
    pct = lambda a, b: 100 * a / max(1, b)
    lines = [f"  Agrees with NSE XBRL: {n['match']}/{n['checked']} ({pct(n['match'], n['checked']):.1f}%)"
             + (f", {n['restated_later']} of them as originally reported (restated later)" if n["restated_later"] else ""),
             f"  Screener, where NSE has no figure: {s['match']}/{s['checked']} ({pct(s['match'], s['checked']):.1f}%)"]
    for name, d in per_source.items():
        if name.endswith("(info)") and d["checked"]:
            lines.append(f"  {name}: agrees on {d['match']}/{d['checked']} ({pct(d['match'], d['checked']):.1f}%)")
    lines.append(f"  => {ok}/{len(results)} verified ({pct(ok, len(results)):.1f}%)")
    return lines


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ticker = args[0]
    path, results, per_source = check(ticker, args[1] if len(args) > 1 else None, info="--yahoo" in sys.argv)
    ok = sum(1 for r in results if r["status"] == "OK")
    if "--json" in sys.argv:
        print(json.dumps({"ticker": ticker.upper(), "file": os.path.basename(path), "verified": ok,
                          "checked": len(results), "per_source": per_source,
                          "issues": [r for r in results if r["status"] != "OK"],
                          "restated_later": [r for r in results if r["note"]]}, default=str))
        return
    print(f"{ticker.upper()}: {os.path.basename(path)}")
    for r in results:
        if r["status"] != "OK":
            src = "  ".join(f"{k}={v}" for k, v in r["sources"].items())
            orig = f"  as reported={r['ours_as_reported']}" if r["ours_as_reported"] is not None else ""
            print(f"  {r['status']:8} {r['scope']:12} {r['metric']:22} FY{r['year']}  [{r['basis']}]  "
                  f"ours={r['ours']}{orig}  {src}")
    for line in summary_lines(results, per_source):
        print(line)


if __name__ == "__main__":
    main()
