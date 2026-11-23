"""
finxl.py
--------
Step 2 of DocFetcher: Screener annual reports -> one clean, multi-year Excel.

1. Looks up the company on screener.in (reuses fetchdocs.py)
2. Downloads the annual report PDFs for the selected years (cached on disk)
3. Finds the Balance Sheet, P&L and Cash Flow inside each 300-page PDF and
   parses every line item (ar_extract.py, free, no API)
4. Optional AI fallback (Gemini free tier / local Ollama) for anything the
   parser can't read cleanly (llm_extract.py)
5. Lines up all years side by side and writes a formatted Excel workbook

Usage:
    python finxl.py HCLTECH 2021-2025
    python finxl.py PIDILITIND 2020-2025 --scope both --ai gemini
"""

import argparse
import difflib
import os
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor

import fitz
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

import ar_extract
import fetchdocs
import llm_extract
import quality
from ixbrl_to_excel import (NAVY, TEAL, LGREY, DGREY, _fill, _font, _border, hdr, col_hdr, is_total)

SCRIPT_VERSION = "v1"

# Downloaded PDFs are cached outside the (OneDrive-synced) project folder
CACHE_DIR = os.environ.get("DOCFETCHER_CACHE", os.path.join(os.path.expanduser("~"), "DocFetcherData"))

TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "thousand": 0.0001, None: 1.0}

SHEET_NAMES = {
    ("consolidated", "pl"): "Consol P&L",
    ("consolidated", "bs"): "Consol Balance Sheet",
    ("consolidated", "cf"): "Consol Cash Flow",
    ("standalone", "pl"): "Standalone P&L",
    ("standalone", "bs"): "Standalone Balance Sheet",
    ("standalone", "cf"): "Standalone Cash Flow",
    ("consolidated", "ra"): "Consol Revenue Account",
    ("standalone", "ra"): "Standalone Revenue Account",
}


def _noop(*_a, **_k):
    pass


# ── 1-2. Screener lookup + download ──────────────────────────────────────────
def list_reports(ticker):
    """Returns (screener_url, [{'year': 2025, 'label', 'url'}...]) newest first, one per year."""
    html, url = fetchdocs.fetch_screener_page(ticker)
    if not html:
        raise RuntimeError(f"Could not find '{ticker}' on screener.in. Check the ticker (e.g. RELIANCE, TCS).")
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for r in fetchdocs.parse_annual_reports(soup):
        if not r["year"].isdigit() or r["year"] in seen or not r["url"].startswith("http"):
            continue
        seen.add(r["year"])
        out.append({"year": int(r["year"]), "label": r["label"], "url": r["url"]})
    name_tag = soup.find("h1")
    company = name_tag.get_text(strip=True) if name_tag else ticker
    return url, company, sorted(out, key=lambda r: -r["year"])


def download_report(item, folder):
    """Download one annual report PDF (skips if already on disk). Returns path or None."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"Annual Report {item['year']}.pdf")
    legacy = os.path.join(folder, fetchdocs.safe_filename(item["label"]) + ".pdf")  # fetchdocs.py name
    for p in (path, legacy):
        if os.path.exists(p) and os.path.getsize(p) > 10_000:
            with open(p, "rb") as f:
                if f.read(4) == b"%PDF":
                    return p
    with requests.get(item["url"], headers=fetchdocs.HEADERS, timeout=300, stream=True) as r:
        r.raise_for_status()
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    with open(tmp, "rb") as f:
        head = f.read(4)
    if head != b"%PDF":
        os.remove(tmp)
        return None
    os.replace(tmp, path)
    return path


# ── 3-4. Extraction for one report ────────────────────────────────────────────
def extract_report(path, fy, scopes, ai=None, log=_noop):
    """
    Returns {(scope, kind): {"parsed", "pages", "method", "check"}} for one PDF.
    ai = {"backend": "gemini"|"ollama", "api_key", "model", "mode": "fallback"|"always"} or None
    """
    doc = fitz.open(path)
    loc = ar_extract.locate_statements(doc)
    out = {}
    # Insurers also have a Revenue Account (policyholders); only look for it when present
    kinds = ("pl", "bs", "cf") + (("ra",) if any(k[1] == "ra" for k in loc) else ())
    prose = quality.prose_words(doc, {vp[0] for pages in loc.values() for vp in pages})
    for scope in scopes:
        for kind in kinds:
            pages = loc.get((scope, kind))
            if not pages:
                if not any(k[0] == scope for k in loc):
                    # e.g. no subsidiaries -> the report has no consolidated statements at all
                    out[(scope, kind)] = {"parsed": None, "pages": "", "method": "-",
                                          "check": f"N/A: report has no {scope} statements"}
                    continue
                log(f"    FY{fy} {scope} {ar_extract.KINDS[kind]}: not found in PDF")
                out[(scope, kind)] = {"parsed": None, "pages": "", "method": "-",
                                      "check": "MISSING: statement not found in PDF"}
                continue
            page_names = ", ".join(ar_extract.vp_name(p, doc) for p in pages)
            parsed = ar_extract.name_bank_totals(kind, ar_extract.parse_statement(doc, pages))
            # footnote sentences are not line items (and would count as blank rows below)
            parsed["rows"] = [r for r in parsed["rows"] if not quality.is_sentence(r)]
            ok, msg = ar_extract.validate(kind, parsed)
            method = "parser"
            use_ai = ai and ai.get("backend") and (not ok or ai.get("mode") == "always")
            if use_ai:
                try:
                    text = ar_extract.statement_text(doc, pages)
                    images = [doc[p[0]].get_pixmap(dpi=130, clip=p[1]).tobytes("png") for p in pages]
                    log(f"    FY{fy} {scope} {ar_extract.KINDS[kind]}: asking {ai['backend']} ({msg or 'always mode'})")
                    llm = llm_extract.extract_with_llm(text, ar_extract.KINDS[kind], scope, fy,
                                                       ai["backend"], ai.get("api_key"), ai.get("model"),
                                                       images=images)
                    lok, lmsg = ar_extract.validate(kind, llm)
                    if lok or not ok:
                        parsed, ok, msg, method = llm, lok, lmsg, ai["backend"]
                except Exception as e:
                    log(f"    AI fallback failed: {e}")
            fix_years(parsed, fy)
            parsed["ok"] = ok
            parsed["_pages"] = pages
            quality.check_statement(kind, parsed, prose)  # footing + label checks on this report's own figures
            mark = "OK " if ok else "CHECK"
            log(f"    FY{fy} {scope} {ar_extract.KINDS[kind]}: {mark} pages {page_names}, "
                f"{len(parsed['rows'])} rows via {method} ({msg}); {quality.summary_text(parsed.get('quality'))}")
            out[(scope, kind)] = {"parsed": parsed, "pages": page_names, "method": method,
                                  "check": ("OK: " if ok else "CHECK: ") + msg, "quality": parsed.get("quality")}
    fill_missing_units(doc, out, log, fy)
    doc.close()
    return out


def fill_missing_units(doc, out, log=_noop, fy=None):
    """
    Some statement pages don't print their unit. Use the unit the report's other
    statements state; failing that, look at the pages right after the statements
    ("All amounts in ₹ million" usually heads the notes).
    """
    parsed = [it["parsed"] for it in out.values() if it.get("parsed")]
    known = [p["unit"] for p in parsed if p.get("unit")]
    unit = max(set(known), key=known.count) if known else None
    if unit is None and parsed:
        last = max(vp[0] for p in parsed for vp in p.get("_pages", []))
        for pno in range(last + 1, min(last + 6, len(doc))):
            unit = ar_extract.detect_unit(doc[pno].get_text())
            if unit:
                break
    filled = 0
    for p in parsed:
        if not p.get("unit") and unit:
            p["unit"] = unit
            filled += 1
        p.pop("_pages", None)
    if filled:
        log(f"    FY{fy}: unit not printed on {filled} statement page(s); using '{unit}' from elsewhere in the report")


def fix_years(parsed, fy):
    """Make sure the column years make sense for a report of fiscal year `fy`."""
    n = parsed["ncols"]
    ys = parsed.get("years") or []
    if len(ys) != n or fy not in ys or len(set(ys)) != len(ys):
        parsed["years"] = [fy - i for i in range(n)]  # current year first is the standard layout
        parsed["months"] = {}  # header unreadable, so its months are unknown too


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def col_label(y, months=None):
    """Column header for a year: 'Mar 2025', or 'Dec 2022' for December year-ends."""
    return f"{MONTH_NAMES[(months or {}).get(y, 3) - 1]} {y}"


def collect_months(per_key):
    """Period-end month per year, taken from the newest report that states it."""
    months = {}
    # balance-sheet headers ("As at 31 December 2022") are the clearest, so they go first
    for key in sorted(per_key, key=lambda k: k[1] != "bs"):
        by_fy = per_key[key]
        for fy in sorted(by_fy, reverse=True):
            for y, mm in (by_fy[fy].get("months") or {}).items():
                months.setdefault(y, mm)
    return months


# ── 5. Multi-year merge ───────────────────────────────────────────────────────
def norm_label(s):
    s = s.lower()
    s = re.sub(r"\(?refer\s+note[^)]*\)?|\[[a-z+\s]*\]|note\s*\d+[\w.()]*", " ", s)
    # cross-references like "(IX - X)", "(I+II)", "(A+B+C)", "(VII - VIII)"
    s = re.sub(r"\(\s*([ivxlc]+|[a-h])(\s*[-+–=]\s*([ivxlc]+|[a-h]))+\s*\)|\(\s*[ivxlc]+\s*\)\s*$", " ", s)
    s = s.replace("&", "and").replace("amorization", "amortisation").replace("amortization", "amortisation")
    s = re.sub(r"[^a-z]+", " ", s)
    return " ".join(w for w in s.split() if w not in STOPWORDS)


STOPWORDS = {"for", "the", "of", "and", "in", "on", "to", "a", "an"}

GAP_TOTAL_RE = re.compile(r"^total\b|^net cash|^(net )?profit (loss )?(year|period|after tax|before tax)")

PER_SHARE_RE = re.compile(r"\bper (equity |ordinary )?shares?\b|\beps\b|^(basic|diluted)\b|\bface value\b"
                          r"|\bnumber (of )?(equity |ordinary )?shares\b|\bweighted average (number|shares)")
PER_SHARE_HEAD_RE = re.compile(r"^earnings? per|\bper (equity |ordinary )?shares?\b|\beps\b")


def is_per_share(nl, head=""):
    """Per-share lines (EPS, DPS, face value) and share counts: no ₹-unit conversion."""
    if PER_SHARE_RE.search(nl):
        return True
    # "Basic", "Diluted", "Continuing operations" under an "Earnings per equity share" heading
    return bool(head and PER_SHARE_HEAD_RE.search(head) and not re.search(r"\btotal\b|\bprofit\b", nl))


def merge_years(per_year, restated=True):
    """
    per_year: {fy: parsed} for one (scope, kind).
    Returns ordered list of {"label","level","is_header","values":{year: v}}.
    restated=True:  each year's number comes from the NEWEST report that shows it
                    (restated comparatives, best for year-on-year comparison; matches Screener)
    restated=False: each year's number comes from that year's own report (as originally reported)
    Years with no report of their own are always filled from the next report's comparative column.
    """
    master, order = {}, []
    # One source report per year column: the column must add up as one report printed it.
    # Mixing a newer report's restated comparatives with lines that only an older report
    # has (reclassified items) double-counts or splits figures (SBI FY2025 investing).
    source = {}
    for fy, parsed in per_year.items():
        filled = [r for r in parsed["rows"] if any(v is not None for v in r["values"])]
        for ci, y in enumerate(parsed["years"]):
            # a column read only in part (a page with other columns) can't be the sole source
            if filled and sum(1 for r in filled if ci < len(r["values"]) and r["values"][ci] is not None) < 0.8 * len(filled):
                continue
            prio = (-fy if restated else (0 if y == fy else 1)) + (0 if parsed.get("ok", True) else 10 ** 6)
            if y not in source or prio < source[y][0]:
                source[y] = (prio, fy)
    for fy in sorted(per_year, reverse=True):
        parsed = per_year[fy]
        unit_factor = TO_CRORE.get(parsed.get("unit"), 1.0)
        heads, seen, last_pos, used = ["", ""], {}, -1, set()
        for r in parsed["rows"]:
            nl = norm_label(r["label"])
            if not nl:
                continue
            if r["is_header"]:
                heads = [heads[-1], nl]
            # EPS, dividend per share, face value, share counts are never in ₹ crore
            factor = 1.0 if is_per_share(nl, heads[-1]) else unit_factor
            context = ">".join(heads)
            base = f"{context}|{nl}"
            seen[base] = seen.get(base, 0) + 1
            key = f"{base}#{seen[base]}"
            if key in used:
                key = None
            if key in master and not r["is_header"] and value_conflict(r, parsed["years"], fy, factor, master[key]):
                key = match_by_value(r, parsed["years"], fy, factor, master, order, used, last_pos) or key
            if key not in master and not r["is_header"]:
                key = match_by_value(r, parsed["years"], fy, factor, master, order, used, last_pos) \
                    or match_by_position(nl, master, order, used, last_pos) or key
            if key not in master:
                # tolerate small wording changes between years
                cands = [k for k in master if k.split("|")[0] == context
                         and k.endswith(f"#{seen[base]}") and k not in used]
                cands = [k for k in cands if not opposed(nl, k.split("|")[-1].split("#")[0])]
                best = difflib.get_close_matches(f"{base}#{seen[base]}", cands, n=1, cutoff=0.92)
                key = best[0] if best else f"{base}#{seen[base]}"
            if key in used:  # never map two lines of one report onto one row
                key = f"{base}#{seen[base]}~{fy}"
            used.add(key)
            if key not in master:
                master[key] = {"label": r["label"], "level": r.get("level", 0),
                               "is_header": r["is_header"], "values": {}, "prio": {},
                               "status": {}, "src": {}, "label_ok": r.get("label_ok", True),
                               "junk": r.get("junk")}
                order.insert(last_pos + 1, key)
                last_pos += 1
            else:
                last_pos = max(last_pos, order.index(key))
            m = master[key]
            status = r.get("status") or [None] * len(r["values"])
            for v, y, st in zip(r["values"], parsed["years"], status):
                if v is None:
                    continue
                if y in source and source[y][1] != fy and not (
                        y not in m["values"] and GAP_TOTAL_RE.search(nl)):  # a total the newer report lost
                    continue
                    continue
                prio = -fy if restated else (0 if y == fy else 1)
                if not parsed.get("ok", True):
                    prio += 10 ** 6  # a statement that failed its checks only fills gaps
                if y not in m["values"] or prio < m["prio"][y]:
                    m["values"][y] = round(v * factor, 4)
                    m["prio"][y] = prio
                    m["status"][y] = st  # footing result, from the report the figure came from
                    m["src"][y] = fy
                    m["is_header"] = False
                    if prio == min(m["prio"].values()):
                        m["label_ok"] = r.get("label_ok", True)
    rows = [master[k] for k in order]
    add_revenue_total(rows)
    # Drop empty section rows that just repeat a neighbouring line item's name
    def dup_header(i):
        r = rows[i]
        if r["values"]:
            return False
        nl = norm_label(r["label"])
        for j in range(max(0, i - 3), min(len(rows), i + 4)):
            if j == i:
                continue
            other = norm_label(rows[j]["label"])
            if other == nl and (rows[j]["values"] or j < i):
                return True  # same name as a neighbour (or a repeated empty header)
            if rows[j]["values"] and len(nl) > 20 and other.startswith(nl):
                return True  # first line of a label that wrapped differently in another year
        return False
    rows = [r for i, r in enumerate(rows) if not dup_header(i)]
    return merge_split_rows(rows)


def merge_split_rows(rows):
    """
    One line item landing on two half-empty rows because its wording changed
    between reports ("(Profit)/Loss on sale of ..." vs "Loss on sale of ...",
    "Basic (in H)" vs "Basic (in ₹)"): rows next to each other with near-identical
    names and no year in common become one row. A line printed as nil in every
    year next to such a twin is dropped.
    """
    def similar(a, b):
        na, nb = norm_label(a["label"]), norm_label(b["label"])
        if not na or not nb or opposed(na, nb):
            return False
        # two rows with figures need near-identical names; a nil-only twin can differ more
        cut = 0.92 if a["values"] and b["values"] else 0.85
        return na == nb or difflib.SequenceMatcher(None, na, nb).ratio() >= cut
    out = []
    for r in rows:
        merged = False
        if not r["is_header"]:
            for p in out[-2:][::-1]:
                if p["is_header"] or not similar(p, r):
                    continue
                if not r["values"] or not p["values"] or not set(p["values"]) & set(r["values"]):
                    for k in ("values", "prio", "status", "src"):
                        for y, v in r.get(k, {}).items():
                            p.setdefault(k, {})[y] = v
                    if r["values"] and not p.get("label_ok", True):
                        p["label"], p["label_ok"] = r["label"], r.get("label_ok", True)
                    merged = True
                    break
        if not merged:
            out.append(r)
    return out


def add_revenue_total(rows):
    """
    Some companies (e.g. Asian Paints) print 'Revenue from operations' only as a
    heading over its parts. Fill the heading with the sum of the parts so the
    total exists, and say so in the label.
    """
    for i, r in enumerate(rows):
        if r["values"] or norm_label(r["label"]) != "revenue from operations":
            continue
        parts = []
        for nxt in rows[i + 1:]:
            if not nxt["values"] or not re.match(r"revenue from|sale|other operating", norm_label(nxt["label"])):
                break
            parts.append(nxt)
        if len(parts) >= 2:
            years = set().union(*(p["values"] for p in parts))
            r["values"] = {y: round(sum(p["values"].get(y) or 0 for p in parts), 2) for y in years}
            r["label"] = "Revenue from operations (total of the lines below)"
            r["is_header"] = False
        return


def value_conflict(row, years, fy, factor, m):
    """True if this report's current-year figure disagrees with the comparative already stored."""
    if fy not in years or fy not in m["values"]:
        return False
    v = row["values"][years.index(fy)]
    if v is None:
        return True
    return abs(v * factor - m["values"][fy]) > max(0.011, abs(v * factor) * 1e-4)


OPPOSED = [({"purchase", "purchases", "acquisition", "investment", "investments"}, {"sale", "sales", "proceeds", "disposal"}),
           ({"issue", "proceeds"}, {"redemption", "repayment", "repayments", "buyback", "buy"}),
           ({"receipt", "receipts", "received"}, {"payment", "payments", "paid"}),
           ({"profit"}, {"loss"}), ({"increase"}, {"decrease"}), ({"income"}, {"expense", "expenses"}),
           ({"basic"}, {"diluted"}), ({"current"}, {"non"})]


def opposed(a, b):
    """True if two normalised labels name opposite items ("Purchase of ..." vs "Sale of ...")."""
    ta, tb = set(a.split()), set(b.split())
    for x, y in OPPOSED:
        if (ta & x and tb & y and not ta & y and not tb & x) or (ta & y and tb & x and not ta & x and not tb & y):
            return True
    return False


def match_by_position(nl, master, order, used, last_pos, window=10):
    """
    Restated figures don't match by value and section headings may have been
    reworded, so fall back to the same (or nearly the same) label sitting at
    about the same place in the statement.
    """
    best, best_score = None, 0.0
    for k in order[max(0, last_pos + 1 - window):last_pos + 1 + window]:
        if k in used or master[k]["is_header"]:
            continue
        other = norm_label(master[k]["label"])
        if opposed(nl, other):
            continue
        score = difflib.SequenceMatcher(None, nl, other).ratio()
        if score > best_score:
            best, best_score = k, score
    return best if best_score >= 0.85 else None


def match_by_value(row, years, fy, factor, master, order, used, last_pos):
    """
    A line renamed between reports is still the same line if this report's
    current-year figure equals the figure the newer report printed as its
    comparative. Pick the nearest such row (by position) not yet used.
    """
    if fy not in years:
        return None
    v = row["values"][years.index(fy)]
    if v is None or abs(v) < 0.01:
        return None
    v = round(v * factor, 4)
    hits = [k for k in master if k not in used and not master[k]["is_header"]
            and master[k]["values"].get(fy) is not None
            and abs(master[k]["values"][fy] - v) <= max(0.011, abs(v) * 1e-4)]
    if not hits:
        return None
    # Prefer the most similar label (e.g. "Profit before tax" over "Profit before
    # exceptional items and tax" when both carry the same number), then the nearest row
    nl = norm_label(row["label"])
    return max(hits, key=lambda k: (round(difflib.SequenceMatcher(None, nl, norm_label(master[k]["label"])).ratio(), 1),
                                    -abs(order.index(k) - (last_pos + 1))))


# ── Per-share sanity ──────────────────────────────────────────────────────────
EPS_RX = re.compile(r"^(basic|basic and diluted|basic diluted)\b|^earnings per (equity )?share\b.*\bbasic\b")
OWNERS_RX = re.compile(r"^(profit|net profit|profit loss)?\s*(year|period)?\s*attributable (to )?(owners|equity holders"
                       r"|shareholders)|^owners (parent|company|holding)|^equity (holders|shareholders) (parent|company)"
                       r"|^shareholders company|^net profit (loss )?group$|^profit (loss )?attributable group$")
CAPITAL_RX = re.compile(r"^(equity )?share capital$|^capital$|^equity share capital")
FACE_RX = re.compile(r"face value (of )?(each )?(equity )?(share )?(of )?(₹|rs\.?|inr)?\s*(\d+(\.\d+)?)", re.I)
STANDARD_FV = (1, 2, 5, 10)


def eps_check(merged, scope, years):
    """
    EPS ≈ net profit attributable to owners ÷ number of shares, where shares =
    equity share capital ÷ face value. A unit slip (EPS divided by 10,000, a
    lakh/crore mix-up) shows as a factor of 10 or more. Marks flagged EPS cells
    (row["eps_flag"]) and returns {year: "ok" | "flag" | None}.
    """
    pl, bs = merged.get((scope, "pl")), merged.get((scope, "bs"))
    if not pl or not bs:
        return {}, None
    eps = next((r for r in pl if not r["is_header"] and r["values"] and is_per_share(norm_label(r["label"]))
                and EPS_RX.search(norm_label(r["label"]))), None)
    cap = next((r for r in bs if not r["is_header"] and CAPITAL_RX.search(norm_label(r["label"]))), None)
    if not eps or not cap:
        return {}, None
    fv = None
    for r in pl:
        m = FACE_RX.search(r["label"])
        if m:
            fv = float(m.group(7))
            break
    rows = [(norm_label(r["label"]), i, r["values"]) for i, r in enumerate(pl)]
    out = {}
    for y in years:
        e, c = eps["values"].get(y), cap["values"].get(y)
        owners = None
        np_row = pick_row("Net profit", rows, y)
        start = np_row[1] if np_row else 0
        oci = next((i for nl, i, _ in rows if i > start and OCI_START.search(nl)), len(rows))
        for nl, i, vals in rows:
            if vals.get(y) is not None and OWNERS_RX.search(nl) and (i > start or nl.startswith(("net profit", "profit"))) \
                    and i < oci:
                owners = vals[y]
                break
        if owners is None and np_row:
            owners = np_row[2].get(y)
        if None in (e, c, owners) or e == 0 or abs(owners) < 1 or c <= 0:
            out[y] = None
            continue
        implied_fv = c * abs(e) / abs(owners)  # = face value if EPS = profit / (capital / face value)
        if fv:
            ratio = implied_fv / fv
        else:
            ratio = min((implied_fv / f for f in STANDARD_FV), key=lambda x: abs(math.log(x)))
        if ratio >= 5 or ratio <= 0.2:
            shares = c * 1e7 / (fv or min(STANDARD_FV, key=lambda f: abs(math.log(implied_fv / f))))
            expect = owners * 1e7 / shares
            out[y] = "flag"
            eps.setdefault("eps_flag", {})[y] = (
                f"EPS {e:,.4g} does not fit the profit and share capital: profit attributable to owners "
                f"₹{owners:,.0f} crore ÷ about {shares / 1e7:,.1f} crore shares ≈ ₹{expect:,.2f} per share "
                f"(off by a factor of {max(ratio, 1 / ratio):,.0f}). Check the unit and the PDF.")
        else:
            out[y] = "ok"
    return out, eps


# ── 6. Excel ──────────────────────────────────────────────────────────────────
NUM_FMT = '#,##0.00;(#,##0.00);"-"'
FLAG_FAIL = "FFF2A8"   # yellow: a total that doesn't add up
FLAG_LABEL = "FCD5B4"  # orange: a line-item name that looks garbled
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def xl_text(s):
    """Excel rejects control characters that broken PDF fonts can leave behind."""
    return _ILLEGAL.sub("", s) if isinstance(s, str) else s


def write_statement_sheet(wb, name, title, rows, years, months=None):
    ws = wb.create_sheet(name)
    ncols = 1 + len(years)
    hdr(ws, 1, ncols, title)
    col_hdr(ws, 2, ["Particulars (₹ Crore)"] + [col_label(y, months) for y in years])
    ws.column_dimensions["A"].width = 60
    for i in range(len(years)):
        ws.column_dimensions[get_column_letter(i + 2)].width = 14
    rownum = []  # (normalised label, sheet row, values) for the Summary formulas
    for i, r in enumerate(rows, 3):
        sec, tot = r["is_header"], (not r["is_header"] and is_total(r["label"]))
        c = ws.cell(row=i, column=1, value=xl_text(r["label"]))
        c.border = _border()
        c.alignment = Alignment(indent=min(r["level"], 3) + (0 if sec or tot else 1), vertical="center")
        c.font = _font(bold=sec or tot, color=NAVY if sec or tot else "000000")
        if sec:
            c.fill = _fill(LGREY)
        elif tot:
            c.fill = _fill(DGREY)
        if r.get("junk"):
            c.fill = _fill(FLAG_LABEL)
            c.comment = Comment(f"This row looks like page text, not a line item ({r['junk']}). "
                                "Check it against the annual report.", "DocFetcher")
        elif not r.get("label_ok", True):
            c.fill = _fill(FLAG_LABEL)
            c.comment = Comment("This name may be garbled (the PDF uses an unusual font). "
                                "Check the wording in the annual report.", "DocFetcher")
        for j, y in enumerate(years, 2):
            v = r["values"].get(y)
            vc = ws.cell(row=i, column=j, value=v)
            vc.border = _border()
            vc.number_format = NUM_FMT
            vc.alignment = Alignment(horizontal="right")
            if sec:
                vc.fill = _fill(LGREY)
            elif tot:
                vc.fill = _fill(DGREY)
                vc.font = _font(bold=True, color=NAVY)
            if v is not None and (r.get("eps_flag") or {}).get(y):
                vc.fill = _fill(FLAG_FAIL)
                vc.comment = Comment(r["eps_flag"][y], "DocFetcher")
            elif v is not None and r.get("status", {}).get(y) == "fail":
                vc.fill = _fill(FLAG_FAIL)
                vc.comment = Comment(f"This total does not equal the lines above it in the FY{r['src'][y]} "
                                     "annual report as read. A figure here or above may be misread: "
                                     "check against the PDF (pages on the Sources sheet).", "DocFetcher")
        rownum.append((norm_label(r["label"]), i, r["values"]))
    ws.freeze_panes = "B3"
    ws.sheet_view.showGridLines = False
    return ws, rownum


# Key metrics: (label, statement, regex on normalised label)
METRIC_ROWS = [
    ("Revenue from operations", "pl", r"^revenue from operations|^interest earned$"),
    ("Total income", "pl", r"^total income$|^total revenue$"),
    ("Total expenses", "pl", r"^total expenses$"),
    ("Finance costs", "pl", r"^finance costs?$"),
    ("Depreciation & amortisation", "pl", r"^depreciation"),
    ("Profit before tax", "pl", r"^profit (loss )?before tax$"),
    ("Net profit", "pl", r"^(net )?profit (loss )?(year|period)$|^net profit$|^profit (loss )?after tax$"
                         r"|^(consolidated )?net profit (loss )?year( before minority interest)?$"),
    ("Basic EPS (₹)", "pl", r"^basic"),
    ("Total equity", "bs", r"^total equity$"),
    ("Total assets", "bs", r"^total assets( [a-z]{1,5})?$|^total application funds$"),
    ("Cash from operations", "cf", r"^net cash.*operat(ing|ions)"),
    ("Cash from investing", "cf", r"^net cash.*investing"),
    ("Cash from financing", "cf", r"^net cash.*financing"),
]


NP_RX = re.compile(r"^(consolidated )?(net )?(profit (loss )?|loss (profit )?)((year|period)\b|after tax)")
NP_EXCLUDE = re.compile(r"before (share|regulatory|tax|exceptional)|continuing|discontinued|comprehensive"
                        r"|brought forward|carried|appropriation|per share")
NCI = re.compile(r"non controlling|minority")
OWNERS = re.compile(r"attributable (owners|equity holders|shareholders)|attributable non controlling")
OCI_START = re.compile(r"other comprehensive|items (that )?will (not )?be reclassified|items may be reclassified")


def pick_row(metric, rows, y):
    """
    Choose which statement line gives a headline metric for year y.
    rows: ordered list of (normalised label, row id, {year: value}).
    Net profit = the total profit line: after tax, associates and discontinued
    operations, but before the owners / non-controlling split and OCI.
    Operating cash flow = the last 'net cash ... operating' line before investing.
    """
    if metric == "Net profit":
        oci = next((i for i, (nl, _, _) in enumerate(rows) if OCI_START.search(nl)), len(rows))
        for allow_owner in (False, True):
            cands = []
            for i, (nl, rid, vals) in enumerate(rows):
                if vals.get(y) is None or not NP_RX.search(nl) or NP_EXCLUDE.search(nl):
                    continue
                if not allow_owner:
                    if OWNERS.search(nl) or (NCI.search(nl) and "before" not in nl):
                        continue
                    # "Profit for the year" printed right after the NCI line is the owners' share
                    if any(NCI.search(rows[j][0]) and "before" not in rows[j][0] for j in range(max(0, i - 2), i)):
                        continue
                cands.append(i)
            before = [i for i in cands if i < oci]
            pick = before[-1] if before else (cands[-1] if cands else None)
            if pick is not None:
                return rows[pick]
        return None
    if metric == "Cash from operations":
        inv = next((i for i, (nl, _, _) in enumerate(rows)
                    if re.search(r"^(net )?cash flows? (from|used|generated)?.{0,20}investing", nl)), len(rows))
        cands = [(i, r) for i, r in enumerate(rows) if re.search(r"^net cash.*operating", r[0])
                 and r[2].get(y) is not None]
        if not cands:  # KAJARIACER, MOTHERSON: "Net cash generated from operations"
            cands = [(i, r) for i, r in enumerate(rows) if re.search(r"^net cash.*operations", r[0])
                     and not re.search(r"continu", r[0]) and r[2].get(y) is not None]
        if not cands:  # e.g. TTK Prestige ends the section with "Cash generated from / (used in) operations"
            cands = [(i, r) for i, r in enumerate(rows)
                     if re.search(r"^cash generated (from )?used operations$", r[0]) and r[2].get(y) is not None]
        before = [r for i, r in cands if i < inv]
        return before[-1] if before else (cands[0][1] if cands else None)
    rx = {"Revenue": r"^revenue from operations|^interest earned$|^total revenue from operations",
          "Total assets": r"^total assets( [a-z]{1,5})?$|^total application funds$"}.get(metric)
    return next((r for r in rows if rx and re.search(rx, r[0]) and r[2].get(y) is not None), None)


def write_metrics(ws, start_row, scope, sheets, years, months=None):
    """Key figures pulled by formula from the statement sheets, plus ratios."""
    hdr(ws, start_row, 1 + len(years), f"Key metrics — {scope.title()} (₹ Crore)")
    col_hdr(ws, start_row + 1, ["Metric"] + [col_label(y, months) for y in years])
    r = start_row + 2
    where = {}
    for label, kind, rx in METRIC_ROWS:
        sh = sheets.get((scope, kind))
        if not sh:
            continue
        ws_name, rownum = sh
        smart = {"Revenue from operations": "Revenue", "Net profit": "Net profit",
                 "Total assets": "Total assets", "Cash from operations": "Cash from operations"}.get(label)
        if smart:
            picks = {y: pick_row(smart, rownum, y) for y in years}
            if not any(picks.values()):
                continue
        else:
            matches = [(rn, vals) for nl, rn, vals in rownum if re.search(rx, nl)]
            if not matches:
                continue
        ws.cell(row=r, column=1, value=label).font = _font(bold=True, color=NAVY)
        for j, y in enumerate(years):
            col = get_column_letter(j + 2)
            # a line can sit in different rows over the years if the layout changed
            if smart:
                src = picks[y][1] if picks[y] else None
            else:
                src = next((rn for rn, vals in matches if vals.get(y) is not None), None)
            c = ws.cell(row=r, column=j + 2, value=f"='{ws_name}'!{col}{src}" if src else None)
            c.number_format = NUM_FMT
            c.border = _border()
        ws.cell(row=r, column=1).border = _border()
        where[label] = r
        r += 1

    ratios = [
        ("Revenue growth %", "Revenue from operations", None, "growth"),
        ("Net profit margin %", "Net profit", "Revenue from operations", "ratio"),
        ("Return on equity %", "Net profit", "Total equity", "ratio"),
        ("Return on assets %", "Net profit", "Total assets", "ratio"),
        ("CFO / Net profit %", "Cash from operations", "Net profit", "ratio"),
    ]
    for label, num, den, typ in ratios:
        if num not in where or (den and den not in where):
            continue
        ws.cell(row=r, column=1, value=label).font = _font(bold=True, color=TEAL)
        ws.cell(row=r, column=1).border = _border()
        for j in range(len(years)):
            col = get_column_letter(j + 2)
            if typ == "growth":
                if j == 0:
                    continue
                prev = get_column_letter(j + 1)
                f = f"=IFERROR({col}{where[num]}/{prev}{where[num]}-1,\"\")"
            else:
                f = f"=IFERROR({col}{where[num]}/{col}{where[den]},\"\")"
            c = ws.cell(row=r, column=j + 2, value=f)
            c.number_format = "0.0%"
            c.border = _border()
        r += 1
    return r + 1


def write_workbook(out_path, company, ticker, screener_url, years, merged, sources, scopes, restated=True,
                   months=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 32
    for i in range(len(years)):
        ws.column_dimensions[get_column_letter(i + 2)].width = 14
    hdr(ws, 1, 1 + len(years), f"{company} ({ticker}) — Financial statements from annual reports")
    meta = [("Screener page", screener_url),
            ("Years", f"FY{years[0]} – FY{years[-1]}" if years else "-"),
            ("Units", "₹ Crore (converted from report units)"),
            ("Figures", "Latest restated (newest report showing each year)" if restated
             else "As originally reported in each year's report"),
            ("Quality", quality_line(sources)),
            ("Generated", time.strftime("%Y-%m-%d %H:%M")),
            ("Tool", f"DocFetcher finxl.py {SCRIPT_VERSION}")]
    for i, (k, v) in enumerate(meta, 2):
        ws.cell(row=i, column=1, value=k).font = _font(bold=True, color=NAVY)
        ws.cell(row=i, column=2, value=v)

    sheets = {}
    for key, rows in merged.items():
        if not rows:
            continue
        scope, kind = key
        name = SHEET_NAMES[key]
        _, rownum = write_statement_sheet(wb, name, f"{company} — {scope.title()} {ar_extract.KINDS[kind]}",
                                          rows, years, months)
        sheets[key] = (name, rownum)

    r = len(meta) + 3
    for scope in scopes:
        if any(k[0] == scope for k in sheets):
            r = write_metrics(ws, r, scope, sheets, years, months)

    # Sources / audit trail
    src = wb.create_sheet("Sources")
    hdr(src, 1, 7, "Where every number came from")
    col_hdr(src, 2, ["FY", "Statement", "Scope", "PDF pages", "Method", "Check", "Report URL"])
    for i, s in enumerate(sources, 3):
        for j, v in enumerate([s["fy"], s["statement"], s["scope"], s["pages"], s["method"], s["check"], s["url"]], 1):
            c = src.cell(row=i, column=j, value=xl_text(v))
            c.border = _border()
            if j == 6 and str(v).startswith(("CHECK", "MISSING")):
                c.font = _font(bold=True, color="C00000")
    for col, w in zip("ABCDEFG", (8, 16, 14, 12, 10, 50, 70)):
        src.column_dimensions[col].width = w
    src.freeze_panes = "A3"
    write_quality_sheet(wb, sources)
    wb.save(out_path)
    return out_path


def quality_line(sources):
    t = quality_totals(sources)
    if not t["cells"]:
        return "-"
    s = f"{100.0 * t['confirmed'] / t['cells']:.1f}% of figures confirmed by the reports' own totals"
    if t["failed_totals"] or t["bad_labels"] or t["junk_rows"] or t["eps_flags"]:
        s += (f"; {t['failed_totals']} total(s) to check (yellow), {t['bad_labels']} label(s) and "
              f"{t['junk_rows']} junk row(s) to check (orange), {t['eps_flags']} EPS figure(s) off (yellow)")
    return s + " (see Quality sheet)"


def quality_totals(sources):
    qs = [s["quality"] for s in sources if s.get("quality")]
    return {k: sum(q.get(k, 0) for q in qs) for k in ("cells", "confirmed", "totals", "failed_totals", "bad_labels",
                                                      "junk_rows", "eps_checked", "eps_flags")}


def write_quality_sheet(wb, sources):
    """How much of each statement the report's own arithmetic confirms."""
    ws = wb.create_sheet("Quality")
    ws.sheet_view.showGridLines = False
    hdr(ws, 1, 8, "Quality checks: do the figures add up in the annual report itself?")
    t = quality_totals(sources)
    pct = 100.0 * t["confirmed"] / t["cells"] if t["cells"] else 0.0
    notes = [
        f"Figures confirmed by the report's own totals: {t['confirmed']:,} of {t['cells']:,} ({pct:.1f}%)",
        f"Totals that don't add up: {t['failed_totals']} of {t['totals']} (yellow cells on the statement sheets)",
        f"Line-item names that look garbled: {t['bad_labels']} (orange cells)",
        f"Junk rows (headings, page strips, symbol codes, repeated words): {t['junk_rows']} (orange cells)",
        f"EPS checked against profit ÷ shares: {t['eps_checked']} figures, {t['eps_flags']} off by a factor of 5 or "
        "more (yellow cells)",
        "A figure is confirmed when it is part of a total (or profit line) that adds up exactly as printed. "
        "Unconfirmed is not wrong: lines like EPS are not part of any total (EPS has its own check above).",
    ]
    for i, n in enumerate(notes, 2):
        ws.cell(row=i, column=1, value=n).font = _font(bold=i < 7, color=NAVY)
    head = 2 + len(notes) + 1
    col_hdr(ws, head, ["FY", "Statement", "Scope", "Figures", "Confirmed", "% confirmed",
                       "Totals not adding up", "Garbled labels", "Junk rows", "EPS off"])
    r = head + 1
    for s in sources:
        q = s.get("quality")
        if not q:
            continue
        p = q["confirmed"] / q["cells"] if q["cells"] else None
        vals = [s["fy"], s["statement"], s["scope"], q["cells"], q["confirmed"], p, q["failed_totals"], q["bad_labels"],
                q.get("junk_rows", 0), q.get("eps_flags", 0)]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.border = _border()
            if j == 6:
                c.number_format = "0%"
            if j >= 7 and v:
                c.fill = _fill(FLAG_FAIL if j in (7, 10) else FLAG_LABEL)
        r += 1
    for col, w in zip("ABCDEFGHIJ", (8, 16, 14, 10, 11, 12, 20, 15, 11, 9)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = ws.cell(row=head + 1, column=1).coordinate


# ── One-click pipeline ────────────────────────────────────────────────────────
def run(ticker, start_year, end_year, scope="consolidated", ai=None, out_dir=None,
        log=print, progress=_noop, restated=True):
    """Everything in one call. Returns (excel_path, merged, sources)."""
    ticker = ticker.upper().strip()
    scopes = ["consolidated", "standalone"] if scope == "both" else [scope]
    out_dir = out_dir or os.path.join(os.getcwd(), ticker)
    pdf_dir = os.path.join(CACHE_DIR, ticker, "AnnualReports")

    log(f"Looking up {ticker} on screener.in ...")
    screener_url, company, reports = list_reports(ticker)
    reports = [r for r in reports if start_year <= r["year"] <= end_year]
    if not reports:
        raise RuntimeError(f"No annual reports between {start_year} and {end_year} on Screener for {ticker}.")
    log(f"{company}: {len(reports)} annual report(s): {', '.join(str(r['year']) for r in reports)}")
    progress(0.05)

    log("Downloading PDFs (cached after the first run) ...")
    paths = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {r["year"]: ex.submit(download_report, r, pdf_dir) for r in reports}
        for i, (y, f) in enumerate(futs.items(), 1):
            try:
                p = f.result()
                if p:
                    paths[y] = p
                    log(f"  FY{y}: {os.path.basename(p)} ({os.path.getsize(p) / 1e6:.1f} MB)")
                else:
                    log(f"  FY{y}: link is not a PDF, skipped")
            except Exception as e:
                log(f"  FY{y}: download failed ({e})")
            progress(0.05 + 0.25 * i / len(futs))

    log("Reading financial statements from each report ...")
    per_key, sources = {}, []
    urls = {r["year"]: r["url"] for r in reports}
    for i, fy in enumerate(sorted(paths, reverse=True), 1):
        log(f"  FY{fy}:")
        try:
            res = extract_report(paths[fy], fy, scopes, ai=ai, log=log)
        except Exception as e:
            log(f"    failed to read PDF ({e})")
            res = {}
        for key, item in res.items():
            if item["parsed"] is not None:
                per_key.setdefault(key, {})[fy] = item["parsed"]
            sources.append({"fy": fy, "statement": ar_extract.KINDS[key[1]], "scope": key[0],
                            "pages": item["pages"], "method": item["method"], "check": item["check"],
                            "url": urls[fy], "quality": item.get("quality")})
        progress(0.30 + 0.6 * i / len(paths))

    merged = {}
    all_years = set()
    for scope_ in scopes:
        for kind in ("pl", "bs", "cf", "ra"):
            key = (scope_, kind)
            if key in per_key:
                merged[key] = merge_years(per_key[key], restated)
                for r in merged[key]:
                    all_years.update(r["values"])
    # Comparative columns can reach one year before the first report
    years = sorted(y for y in all_years if start_year - 1 <= y <= end_year)
    if not merged:
        raise RuntimeError("No financial statements could be extracted. See the log above.")
    months = collect_months(per_key)
    for scope_ in scopes:
        res, eps_row = eps_check(merged, scope_, years)
        for y, st in res.items():
            src = next((s for s in sources if s["fy"] == eps_row["src"].get(y) and s["scope"] == scope_
                        and s["statement"] == ar_extract.KINDS["pl"] and s.get("quality")), None)
            if st is None or not src:
                continue
            src["quality"]["eps_checked"] = src["quality"].get("eps_checked", 0) + 1
            src["quality"]["eps_flags"] = src["quality"].get("eps_flags", 0) + (st == "flag")
            if st == "flag":
                log(f"  {scope_} FY{y}: EPS check: {eps_row['eps_flag'][y]}")

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{ticker}_Financials_FY{years[0]}-FY{years[-1]}.xlsx")
    try:
        write_workbook(out_path, company, ticker, screener_url, years, merged, sources, scopes, restated, months)
    except PermissionError:  # file is open in Excel
        out_path = out_path.replace(".xlsx", time.strftime("_%H%M%S.xlsx"))
        log("  (previous file is open in Excel - saving under a new name)")
        write_workbook(out_path, company, ticker, screener_url, years, merged, sources, scopes, restated, months)
    progress(1.0)
    log(f"Saved: {out_path}")
    return out_path, merged, sources, years, months


def main():
    ap = argparse.ArgumentParser(description="Annual reports from Screener -> multi-year Excel")
    ap.add_argument("ticker")
    ap.add_argument("years", help="e.g. 2021-2025")
    ap.add_argument("--scope", choices=["consolidated", "standalone", "both"], default="consolidated")
    ap.add_argument("--ai", choices=["gemini", "ollama"], help="AI fallback for statements the parser can't read")
    ap.add_argument("--model", help="AI model (default gemini-flash-latest with backups / gemma3:12b)")
    ap.add_argument("--as-reported", action="store_true",
                    help="use each year's originally reported numbers instead of the latest restated ones")
    a = ap.parse_args()
    s, _, e = a.years.partition("-")
    ai = None
    if a.ai:
        ai = {"backend": a.ai, "api_key": os.environ.get("GEMINI_API_KEY"), "model": a.model, "mode": "fallback"}
    print(f"[finxl.py {SCRIPT_VERSION}]")
    run(a.ticker, int(s), int(e or s), a.scope, ai, restated=not a.as_reported)


if __name__ == "__main__":
    main()
