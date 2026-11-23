"""
gold.py
-------
Gold and silver answer keys for whole statements (CHAT_HANDOFF item 3.4 C,
CLOUD_PLAN "Gold and silver sets").

A *second reader* (Claude, reading the PDF page images) writes down every row of a
statement independently of the parser. This module compares that reading with the
parser's output row by row, writes the disagreements for Harsh's review screen, and
builds the reference copies that the regression suite checks against.

    GOLD   ~15 statements. Every disagreement is resolved by Harsh in the review
           screen, so the copy is human-verified. Any difference later = FAILURE.
    SILVER as many statements as the credits allow. Rows where Claude and the parser
           agree, plus Claude's reading where they disagree. AI-verified only, so
           differences later = WARNING, never automatic truth.

Everything is compared in the statement's PRINTED units (e.g. ₹ '000 for SBI), exactly
as the parser returns it from one report, so the check does not depend on unit
conversion or on how years are merged across reports.

Files (all under tests/gold/; the format is documented in tests/gold/FORMAT.md):
    parser/<T>_<FY>_<kind>.json             parser snapshot at the time of the comparison
    reading/<T>_<FY>_<kind>.json            the second reader's independent reading
    disagreements_<T>_<FY>_<kind>.json      what Harsh resolves in the review screen (gold)
    resolutions_<T>_<FY>_<kind>.json        his answers (written by the review screen)
    gold_<T>_<FY>_<kind>.json               human-verified reference copy
    silver/<T>_<FY>_<kind>.json             AI-verified reference copy
    silver_findings.md                      silver mismatches grouped by pattern, for session A

Commands:
    python gold.py prepare SBIN 2026 [--kinds pl,bs,cf]   download PDF, snapshot parser, render page images
    python gold.py compare SBIN 2026 [--set gold|silver]  reading vs parser -> disagreements / silver copy
    python gold.py finalize SBIN 2026                     disagreements + resolutions -> gold copy
    python gold.py check [--set gold|silver|all]          re-run the parser and compare with the copies
    python gold.py status                                 what exists for each statement

kind is pl (Profit & Loss), bs (Balance Sheet) or cf (Cash Flow). Scope is consolidated.
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', "engine"))
import argparse
import difflib
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD_DIR = os.path.join(HERE, "tests", "gold")
CACHE_DIR = os.environ.get("DOCFETCHER_CACHE", os.path.join(os.path.expanduser("~"), "DocFetcherData"))
IMG_DIR = os.path.join(CACHE_DIR, "gold_pages")  # page images: never committed
KIND_NAMES = {"pl": "Profit & Loss", "bs": "Balance Sheet", "cf": "Cash Flow"}
FORMAT_DISAGREE = "docfetcher-gold-disagreements/1"
FORMAT_COPY = "docfetcher-gold-copy/1"


def stem(ticker, fy, kind):
    return f"{ticker.upper()}_{fy}_{kind}"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def pdf_path(ticker, fy):
    return os.path.join(CACHE_DIR, ticker.upper(), "AnnualReports", f"Annual Report {fy}.pdf")


# ── Label and value normalisation (independent of the parser's own helpers) ──────
RUPEE_GLYPHS = re.compile(r"(?<![A-Za-z])[`J](?![A-Za-z])|\(in\s+[`JH]\)|\bin\s+[`H]\b")


def norm(label):
    """Loose form of a label for matching: lower case, letters and digits only."""
    s = (label or "").replace("₹", " ").replace("&", " and ")
    s = RUPEE_GLYPHS.sub(" ", s)
    s = s.lower().replace("amortization", "amortisation").replace("amorization", "amortisation")
    s = re.sub(r"\b(refer\s+)?note\s*(no\.?)?\s*\d+[\w.()]*", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(w for w in s.split() if w not in {"the", "of", "and", "a", "an", "rs", "inr"})


FORMULA_REF = re.compile(r"\(\s*([ivxlcIVXLC]+|[A-Ha-h]|\d)(\s*[-+=–]?\s*([ivxlcIVXLC]+|[A-Ha-h]|\d))+\s*\)")
LEAD_SERIAL = re.compile(r"^\s*(\(?[ivxlcIVXLC]{1,5}\)|[ivxlcIVXLC]{1,5}\.|\(?[a-zA-Z]\)|\(?\d{1,2}\)|\d{1,2}\.)\s+")


def _soft(label):
    """Drops presentation-only parts: formula refs "(I+II)", leading serials "(1)", "a)"."""
    s = FORMULA_REF.sub(" ", label or "")
    return LEAD_SERIAL.sub("", s).strip()


def labels_equivalent(p, r):
    """
    Same line item, allowing for deliberate parser conventions:
    - an unlabelled sub-total ("") is named "Subtotal" by the parser
    - bank statements print a bare "TOTAL", which the parser names ("Total income", "Total assets")
    """
    np_, nr = norm(_soft(p)), norm(_soft(r))
    if np_ == nr:
        return True
    if nr == "" and np_ in ("subtotal", "sub total", "total"):
        return True
    if nr in ("total", "grand total") and np_.startswith("total"):
        return True
    return False


def label_sim(a, b):
    if labels_equivalent(a, b):
        return 1.0
    na, nb = norm(_soft(a)), norm(_soft(b))
    if na == nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def same_value(a, b):
    if a is None or b is None:
        return (a is None or a == 0) and (b is None or b == 0)  # "-" may be read as nil or 0
    return abs(a - b) <= max(0.0051, abs(b) * 1e-9)


def fmt(v):
    if v is None:
        return None
    return int(v) if float(v).is_integer() else v


def clean_rows(rows, ncols):
    out = []
    for r in rows:
        vals = [(float(v) if isinstance(v, (int, float)) else None) for v in (r.get("values") or [])]
        out.append({"label": str(r.get("label", "")).strip(),
                    "values": (vals + [None] * ncols)[:ncols]})
    return out


# ── prepare: PDF + parser snapshot + page images ─────────────────────────────────
def ensure_pdf(ticker, fy):
    p = pdf_path(ticker, fy)
    if os.path.exists(p) and os.path.getsize(p) > 10_000:
        return p, None
    import finxl
    _, _, reports = finxl.list_reports(ticker)
    item = next((r for r in reports if r["year"] == fy), None)
    if not item:
        raise RuntimeError(f"{ticker}: no FY{fy} annual report on Screener")
    p = finxl.download_report(item, os.path.dirname(p))
    if not p:
        raise RuntimeError(f"{ticker} FY{fy}: report link is not a PDF")
    return p, item["url"]


def report_url(ticker, fy):
    try:
        import finxl
        _, _, reports = finxl.list_reports(ticker)
        return next((r["url"] for r in reports if r["year"] == fy), None)
    except Exception:
        return None


def parser_statements(ticker, fy, kinds=("pl", "bs", "cf"), scope="consolidated"):
    """
    Runs the parser on one report. Returns {kind: snapshot}. Only uses the parser's
    public entry points (finxl.extract_report and ar_extract.locate_statements),
    so it keeps working while the parser internals change.
    """
    import fitz
    import ar_extract
    import finxl
    path = pdf_path(ticker, fy)
    res = finxl.extract_report(path, fy, [scope])
    doc = fitz.open(path)
    loc = ar_extract.locate_statements(doc)
    out = {}
    for kind in kinds:
        item = res.get((scope, kind)) or {}
        parsed = item.get("parsed")
        vps = loc.get((scope, kind)) or []
        pages = [{"page": vp[0], "name": ar_extract.vp_name(vp, doc),
                  "clip": [round(c, 1) for c in tuple(vp[1])]} for vp in vps]
        if parsed is None:
            out[kind] = {"ticker": ticker, "fy": fy, "scope": scope, "statement": kind, "pages": pages,
                         "check": item.get("check"), "unit": None, "years": [], "rows": []}
            continue
        ncols = len(parsed.get("years") or []) or parsed.get("ncols", 0)
        out[kind] = {"ticker": ticker, "fy": fy, "scope": scope, "statement": kind, "pages": pages,
                     "check": item.get("check"), "unit": parsed.get("unit"),
                     "years": list(parsed.get("years") or []),
                     "rows": clean_rows(parsed["rows"], ncols)}
    doc.close()
    return out


def render_pages(ticker, fy, kind, pages, extra_next=True, width=1500, strip_h=1100, overlap=120):
    """
    Page images for the second reader: each statement page (or spread half) at a
    width that keeps 10-digit Indian amounts legible, cut into overlapping strips.
    Also the page after the statement, in case the statement runs on.
    Returns the list of PNG paths.
    """
    import fitz
    doc = fitz.open(pdf_path(ticker, fy))
    out_dir = os.path.join(IMG_DIR, stem(ticker, fy, kind))
    os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, "*.png")):
        os.remove(f)
    todo = [(p["page"], fitz.Rect(p["clip"]), p["name"]) for p in pages]
    if extra_next and pages:
        last = pages[-1]
        nxt = last["page"] + 1
        if last["name"].endswith("L"):  # left half of a spread: next is the right half
            r = doc[last["page"]].rect
            todo.append((last["page"], fitz.Rect(r.x0 + r.width / 2, r.y0, r.x1, r.y1), last["name"][:-1] + "R-next"))
        elif nxt < len(doc):
            r = doc[nxt].rect
            if r.width > r.height * 1.2:
                r = fitz.Rect(r.x0, r.y0, r.x0 + r.width / 2, r.y1)
            todo.append((nxt, r, f"{nxt + 1}-next"))
    paths = []
    for pno, clip, name in todo:
        page = doc[pno]
        if page.rotation:
            page.remove_rotation()
        zoom = width / clip.width
        h = int(clip.height * zoom)
        y, i = 0, 1
        while True:
            y1 = min(h, y + strip_h)
            crop = fitz.Rect(clip.x0, clip.y0 + y / zoom, clip.x1, clip.y0 + y1 / zoom)
            sp = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=crop)
            fn = os.path.join(out_dir, f"p{name}_s{i}.png")
            sp.save(fn)
            paths.append(fn)
            if y1 >= h:
                break
            y, i = y1 - overlap, i + 1
    doc.close()
    return paths


def cmd_prepare(ticker, fy, kinds, scope="consolidated"):
    ticker = ticker.upper()
    _, url = ensure_pdf(ticker, fy)
    if scope == "auto":
        snaps = parser_statements(ticker, fy, kinds, "consolidated")
        if all(not sn["pages"] for sn in snaps.values()):
            scope = "standalone"  # the report has no consolidated statements
            snaps = parser_statements(ticker, fy, kinds, scope)
    else:
        snaps = parser_statements(ticker, fy, kinds, scope)
    url = url or report_url(ticker, fy)
    for kind, snap in snaps.items():
        snap["pdf"] = os.path.relpath(pdf_path(ticker, fy), CACHE_DIR)
        snap["pdf_url"] = url
        snap["parsed_at"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        _write(os.path.join(GOLD_DIR, "parser", stem(ticker, fy, kind) + ".json"), snap)
        imgs = render_pages(ticker, fy, kind, snap["pages"])
        print(f"{stem(ticker, fy, kind)}: pages {', '.join(p['name'] for p in snap['pages']) or '-'}, "
              f"{len(snap['rows'])} parser rows, unit {snap['unit']}, years {snap['years']}; "
              f"{len(imgs)} images in {os.path.dirname(imgs[0]) if imgs else '-'}")


# ── compare: reading vs parser ──────────────────────────────────────────────────
def _row_match_score(p, r):
    """How likely parser row p and reader row r are the same line item (0..1)."""
    s = label_sim(p["label"], r["label"])
    pv = [v for v in p["values"] if v not in (None, 0)]
    rv = [v for v in r["values"] if v not in (None, 0)]
    if pv and rv:
        hits = sum(1 for a in pv if any(same_value(a, b) for b in rv))
        vs = hits / max(len(pv), len(rv))
        s = max(s, 0.45 * s + 0.55 * vs)
    elif not pv and not rv:
        pass  # both headings: label only
    else:
        s *= 0.85
    return s


def align(prow, rrow):
    """
    Order-preserving alignment of parser rows and reader rows (Needleman-Wunsch on
    the match score). Returns a list of (i, j) with None for an unmatched side.
    """
    n, m = len(prow), len(rrow)
    GAP = 0.0
    THRESH = 0.55
    sc = [[_row_match_score(prow[i], rrow[j]) for j in range(m)] for i in range(n)]
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        bt[i][0] = 1
    for j in range(1, m + 1):
        bt[0][j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best, how = dp[i - 1][j] + GAP, 1
            if dp[i][j - 1] + GAP > best:
                best, how = dp[i][j - 1] + GAP, 2
            s = sc[i - 1][j - 1]
            if s >= THRESH and dp[i - 1][j - 1] + s > best:
                best, how = dp[i - 1][j - 1] + s, 0
            dp[i][j], bt[i][j] = best, how
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        how = bt[i][j]
        if how == 0:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif how == 1:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    return pairs[::-1]


def _label_differs(p, r, threshold):
    """
    A label is wrong if anything beyond case, spacing and punctuation differs, e.g. a
    note number left in it ("Provisions 471-472"), half of a wrapped label, or a
    rupee sign stored as a letter ("Basic (in `)"). threshold is kept for callers that
    want a looser test.
    """
    a = re.sub(r"\s+", " ", _soft(p)).strip().lower()
    b = re.sub(r"\s+", " ", _soft(r)).strip().lower()
    if a == b:
        return False
    strip = lambda x: re.sub(r"[^0-9a-z₹]+", "", x.replace("&", "and"))
    if strip(a) == strip(b):
        return False
    return threshold >= 1.0 or label_sim(p, r) < 1.0


def year_map(src_years, dst_years):
    """index in src -> index in dst for the same year."""
    return {i: dst_years.index(y) for i, y in enumerate(src_years) if y in dst_years}


def compare_rows(parser, reading, label_threshold=0.86):
    """
    Row-by-row comparison. Returns (items, stats). Each item is one aligned row:
      {"parser_index", "reader_index", "label_parser", "label_reader",
       "values_parser": {year: v}, "values_reader": {year: v}, "issues": [...]}
    issue kinds: missing_in_parser, extra_in_parser, label, value
    """
    years = reading.get("years") or parser.get("years") or []
    prow = clean_rows(parser.get("rows", []), len(parser.get("years") or []))
    rrow = clean_rows(reading.get("rows", []), len(reading.get("years") or []))
    pmap = year_map(parser.get("years") or [], years)
    rmap = year_map(reading.get("years") or [], years)

    def by_year(row, ymap):
        return {years[d]: row["values"][s] for s, d in ymap.items()}

    # compare in the reader's year layout; the parser's rows re-indexed onto it
    pr = [{"label": r["label"], "values": [by_year(r, pmap).get(y) for y in years]} for r in prow]
    rr = [{"label": r["label"], "values": [by_year(r, rmap).get(y) for y in years]} for r in rrow]
    items = []
    for i, j in align(pr, rr):
        it = {"parser_index": i, "reader_index": j,
              "label_parser": pr[i]["label"] if i is not None else None,
              "label_reader": rr[j]["label"] if j is not None else None,
              "values_parser": {y: fmt(pr[i]["values"][k]) for k, y in enumerate(years)} if i is not None else {},
              "values_reader": {y: fmt(rr[j]["values"][k]) for k, y in enumerate(years)} if j is not None else {},
              "issues": []}
        if i is None:
            it["issues"].append({"kind": "missing_in_parser"})
        elif j is None:
            it["issues"].append({"kind": "extra_in_parser"})
        else:
            if not labels_equivalent(pr[i]["label"], rr[j]["label"]) and \
                    _label_differs(pr[i]["label"], rr[j]["label"], label_threshold):
                it["issues"].append({"kind": "label"})
            for k, y in enumerate(years):
                a, b = pr[i]["values"][k], rr[j]["values"][k]
                if not same_value(a, b):
                    it["issues"].append({"kind": "value", "year": y})
        items.append(it)
    value_rows = [it for it in items if it["reader_index"] is not None
                  and any(v is not None for v in it["values_reader"].values())]
    stats = {
        "rows_parser": len(pr), "rows_reader": len(rr),
        "rows_aligned": sum(1 for it in items if it["parser_index"] is not None and it["reader_index"] is not None),
        "rows_agreed": sum(1 for it in items if not it["issues"]),
        "missing_in_parser": sum(1 for it in items if any(x["kind"] == "missing_in_parser" for x in it["issues"])),
        "extra_in_parser": sum(1 for it in items if any(x["kind"] == "extra_in_parser" for x in it["issues"])),
        "label_diffs": sum(1 for it in items if any(x["kind"] == "label" for x in it["issues"])),
        "value_diffs": sum(1 for it in items for x in it["issues"] if x["kind"] == "value"),
        "values_reader": sum(1 for it in value_rows for v in it["values_reader"].values() if v is not None),
        "years_parser": parser.get("years"), "years_reader": reading.get("years"),
        "unit_parser": parser.get("unit"), "unit_reader": reading.get("unit"),
    }
    return items, stats


def _search_text(v):
    """How the value is likely printed, for the review screen's highlight search."""
    if v is None:
        return None
    a = abs(v)
    s = f"{a:,.2f}" if not float(a).is_integer() else f"{int(a):,}"
    # Indian grouping: 1,23,45,678
    whole, _, dec = s.replace(",", "").partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
        whole = head + "," + tail
    return whole + ("." + dec if dec else "")


# ── Mismatch patterns (shared by the gold review and silver_findings.md) ────────
PATTERNS = {
    "note_ref_in_label": "Note number left in the label",
    "rupee_glyph": "Rupee sign stored as a letter (`, J, C, H, I, K, L)",
    "serial_in_label": "Serial marker left in the label ((1), B, a.)",
    "heading_merged": "Section heading glued onto the next line item",
    "wrapped_label_split": "Wrapped label split into two rows",
    "column_header_row": "Statement title / column heading / unit line kept as a row",
    "page_furniture": "Page furniture (navigation strip, page number) read as a row or value",
    "footnote_rows": "Footnote / memo table below the statement kept as rows",
    "marker_in_label": "Footnote / cross-reference marker left in the label (provisions1, (B), SOCE)",
    "statement_truncated": "Statement cut short: last lines missing from the parser output",
    "garbled_label": "Garbled label (undecoded font)",
    "row_missing": "Line item missing from the parser output",
    "row_extra": "Extra row in the parser output",
    "label_other": "Label differs",
    "value_wrong_year": "Value in the wrong year column",
    "value_sign": "Value has the wrong sign",
    "value_scale": "Value off by a power of 10 (unit / digits)",
    "value_missing": "Value missing in the parser output",
    "value_extra": "Parser has a value where the statement has none",
    "value_other": "Value differs",
    "unit_wrong": "Statement unit (crore / lakh / million / thousand) differs",
}
NOTE_TAIL = re.compile(r"^(.*?\S)\s+((\d{1,3}(\.\d{1,3}){0,3}[A-Za-z]?|\d{3}\s*-\s*\d{3})"
                       r"([\s,&]+(and\s*)?(\d{1,3}(\.\d{1,3}){0,3}[A-Za-z]?|\d{3}\s*-\s*\d{3}))*(\s*(and|&))?)$")
GLYPH = re.compile(r"(?<![A-Za-z])[`JCH](?![A-Za-z])")
HEADER_JUNK = re.compile(r"schedule\s+no|current\s+year|previous\s+year|^\W*[`₹JCH]?\W*[`₹JCH]\W*$|^note(s)?$"
                         r"|^(as\s+at|year\s+ended)\b|restated|\(?refer\s+note|^particulars$|crore|lakh|million|omitted"
                         r"|statement\s+of|for\s+the\s+(financial\s+)?year\s+ended|year\s+ended\s+(\S+\s+)?year\s+ended"
                         r"|^\d{1,2}(st|nd|rd|th)?\s+march|balance\s+sheet\s+as\s+at|\(contd|continued", re.I)


def classify(d, items=None):
    """Pattern tag for one disagreement record (see PATTERNS)."""
    k, lp, lr = d["kind"], d.get("label_parser") or "", d.get("label_reader") or ""
    if k == "label":
        m = NOTE_TAIL.match(lp)
        if m and norm(_soft(m.group(1))) == norm(_soft(lr)):
            return "note_ref_in_label"
        mid = re.sub(r"(?<=\s)\d{1,3}(\.\d{1,2})*(\s*-\s*\d{2,3})?(?=\s)", " ", lp)
        if mid != lp and norm(_soft(mid)) == norm(_soft(lr)):
            return "note_ref_in_label"
        if "₹" in lr:
            g = re.sub(r"(?<![A-Za-z])[`JCHIKL](?=\s?\d|\)|\s*$|\s+\d)|(?<![A-Za-z])[`JCHKL](?![A-Za-z])", "₹", lp)
            g = re.sub(r"(\s+₹)+\s*$", "", g) if not lr.rstrip().endswith("₹") else g
            if g != lp and norm(_soft(g)) == norm(_soft(lr)):
                return "rupee_glyph"
        tail = lp[len(lr):].strip() if lr and lp.lower().startswith(lr.lower()) else None
        if tail is not None and re.fullmatch(r"\d|[*#@^]+|\([A-Za-z]{1,3}\)|SOCE|\([A-Z]\)\s*[-+]\s*\([A-Z]\)", tail):
            return "marker_in_label"
        if tail and items is not None:
            nxt = _neighbour(items, d, +1)
            if nxt and nxt.get("parser_index") is None and (nxt.get("label_reader") or "").lower() == tail.lower():
                return "heading_merged"
        if re.search(r"[a-z][A-Z]{2,}[a-z]|[bcdfghjklmnpqrstvwxz]{5,}", lp) and not re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", lr):
            return "garbled_label"
        if norm(_soft(lp)) == norm(_soft(lr)) or re.sub(r"^\(?[A-Za-z0-9]{1,3}[.)]?\s+", "", lp) == lr:
            return "serial_in_label"
        if lr and lp.lower().endswith(lr.lower()) and len(lp) > len(lr) + 3:
            return "heading_merged"
        a, b = norm(_soft(lp)), norm(_soft(lr))
        if a and b and (b.startswith(a) or b.endswith(a) or a.startswith(b) or a.endswith(b)):
            return "wrapped_label_split"
        return "label_other"
    if k == "missing_in_parser":
        vals = [v for v in (d.get("values_reader") or {}).values() if v is not None]
        nxt = _neighbour(items, d, +1)
        if not vals and nxt and (nxt.get("label_parser") or "").lower().startswith(lr.lower()):
            return "heading_merged"
        prv = _neighbour(items, d, -1)
        if prv and lr and (prv.get("label_parser") or "").lower().endswith(" " + lr.lower()):
            return "heading_merged"  # this line's label (and values) went into the heading above
        if items is not None:
            idx = next((n for n, it in enumerate(items) if it["reader_index"] == d.get("reader_index")
                        and it["parser_index"] is None), None)
            last_p = max((n for n, it in enumerate(items) if it["parser_index"] is not None), default=-1)
            if idx is not None and idx > last_p:
                return "statement_truncated"
        return "row_missing"
    if k == "extra_in_parser":
        vals = [v for v in (d.get("values_parser") or {}).values() if v is not None]
        if not vals and HEADER_JUNK.search(lp):
            return "column_header_row"
        if re.search(r"company overview|statutory reports|financial statements|corporate overview|governance", lp, re.I) \
                or (vals and all(abs(v) < 1000 and float(v).is_integer() for v in vals) and len(vals) == 1
                    and re.fullmatch(r"(sub)?total", lp.strip(), re.I)):
            return "page_furniture"
        if _after_last_reader_row(items, d):
            return "footnote_rows"
        for off in (-1, +1):
            nb = _neighbour(items, d, off)
            lab = norm(_soft((nb or {}).get("label_reader") or ""))
            a = norm(_soft(lp))
            if a and lab and (lab.startswith(a) or lab.endswith(a) or a in lab):
                return "wrapped_label_split"
        return "row_extra"
    # value: a value lost to a merged / split label belongs to that label pattern
    if items is not None and d.get("label_parser") is not None and d.get("label_reader") is not None:
        lab = classify({**d, "kind": "label"}, items) if _label_differs(d["label_parser"], d["label_reader"], 0.86) \
            and not labels_equivalent(d["label_parser"], d["label_reader"]) else None
        if lab in ("heading_merged", "wrapped_label_split"):
            return lab
    vp, vr = d.get("value_parser"), d.get("value_reader")
    if vp is None:
        others = [v for y, v in (d.get("values_parser") or {}).items() if v is not None]
        return "value_missing" if not others else "value_wrong_year"
    if vr is None:
        return "value_extra"
    if any(same_value(vp, v) for y, v in (d.get("values_reader") or {}).items() if str(y) != str(d["year"])):
        return "value_wrong_year"
    if same_value(vp, -vr):
        return "value_sign"
    if vr and vp:
        r = abs(vp / vr)
        for e in range(1, 9):
            if abs(r - 10 ** e) / 10 ** e < 0.01 or abs(r - 10 ** -e) / 10 ** -e < 0.01:
                return "value_scale"
    return "value_other"


def _neighbour(items, d, off):
    if not items:
        return None
    idx = next((n for n, it in enumerate(items) if it["parser_index"] == d.get("parser_index")
                and it["reader_index"] == d.get("reader_index")), None)
    if idx is None or not 0 <= idx + off < len(items):
        return None
    return items[idx + off]


def _after_last_reader_row(items, d):
    if not items:
        return False
    last = max((n for n, it in enumerate(items) if it["reader_index"] is not None), default=-1)
    idx = next((n for n, it in enumerate(items) if it["parser_index"] == d.get("parser_index")
                and it["reader_index"] is None), None)
    return idx is not None and idx > last


def disagreements(parser, reading, items):
    out = []
    n = 0
    up, ur = parser.get("unit"), reading.get("unit")
    if "unit" in reading and up != ur:
        n += 1
        out.append({"id": f"d{n:03d}", "kind": "unit", "year": None, "parser_index": None, "reader_index": None,
                    "label_parser": None, "label_reader": None, "value_parser": up, "value_reader": ur,
                    "values_parser": {}, "values_reader": {}, "page": _row_page(reading, 0, parser),
                    "search": [], "pattern": "unit_wrong", "pattern_text": PATTERNS["unit_wrong"]})
    for it in items:
        for iss in it["issues"]:
            n += 1
            y = iss.get("year")
            vp = it["values_parser"].get(y) if y else None
            vr = it["values_reader"].get(y) if y else None
            d = {"id": f"d{n:03d}", "kind": iss["kind"], "year": y,
                 "parser_index": it["parser_index"], "reader_index": it["reader_index"],
                 "label_parser": it["label_parser"], "label_reader": it["label_reader"],
                 "value_parser": vp, "value_reader": vr,
                 "values_parser": it["values_parser"], "values_reader": it["values_reader"],
                 "page": _row_page(reading, it["reader_index"], parser),
                 "search": [s for s in (_search_text(vr), _search_text(vp)) if s] or
                           [s for v in list(it["values_reader"].values()) + list(it["values_parser"].values())
                            for s in [_search_text(v)] if s][:2]}
            d["pattern"] = classify(d, items)
            d["pattern_text"] = PATTERNS[d["pattern"]]
            out.append(d)
    return out


def _row_page(reading, j, parser):
    """PDF page index (0-based) the reader saw this row on, else the first statement page."""
    rows = reading.get("rows") or []
    if j is not None and j < len(rows) and rows[j].get("page") is not None:
        return rows[j]["page"]
    pages = parser.get("pages") or []
    return pages[0]["page"] if pages else None


def build_copy(parser, reading, items, level, resolutions=None):
    """
    Reference copy of the statement. silver: reader's row/value where they disagree
    (AI-verified). gold: Harsh's choice from the resolutions file.
    """
    years = reading.get("years") or parser.get("years")
    res = resolutions or {}
    by_key = {}
    for d in res.get("disagreements", []):
        by_key[(d.get("parser_index"), d.get("reader_index"), d.get("kind"), d.get("year"))] = d
    rows, unresolved = [], 0
    for it in items:
        label = it["label_reader"] if it["label_reader"] is not None else it["label_parser"]
        vals = dict(it["values_reader"] or it["values_parser"])
        keep = True
        source = "agreed" if not it["issues"] else "reader"
        for iss in it["issues"]:
            if iss["kind"] == "unit":
                continue
            if level != "gold":
                if iss["kind"] == "extra_in_parser":
                    keep = False  # silver trusts the reader: the row is not in the statement
                continue
            d = by_key.get((it["parser_index"], it["reader_index"], iss["kind"], iss.get("year")))
            choice = (d or {}).get("choice")
            if not choice:
                unresolved += 1
                continue
            source = "harsh"
            if iss["kind"] == "extra_in_parser":
                keep = choice == "parser"
                label = it["label_parser"]
                vals = dict(it["values_parser"])
            elif iss["kind"] == "missing_in_parser":
                keep = choice != "parser"  # parser right = the reader invented the row
                if choice == "neither":
                    label = d.get("label", label)
                    vals.update({int(k): v for k, v in (d.get("values") or {}).items()})
            elif iss["kind"] == "label":
                label = {"parser": it["label_parser"], "reader": it["label_reader"]}.get(choice, d.get("label", label))
            elif iss["kind"] == "value":
                y = iss["year"]
                vals[y] = {"parser": it["values_parser"].get(y), "reader": it["values_reader"].get(y)}.get(
                    choice, d.get("value"))
        if keep:
            rows.append({"label": label, "values": [vals.get(y) for y in years], "source": source})
    unit = reading.get("unit") or parser.get("unit")
    ud = next((d for d in res.get("disagreements", []) if d.get("kind") == "unit"), None)
    if level == "gold" and ud:
        if not ud.get("choice"):
            unresolved += 1
        else:
            unit = {"parser": parser.get("unit"), "reader": reading.get("unit")}.get(ud["choice"], ud.get("value"))
    return {"format": FORMAT_COPY, "level": level, "ticker": parser["ticker"], "fy": parser["fy"],
            "scope": parser.get("scope", "consolidated"), "statement": parser["statement"],
            "pages": parser.get("pages"), "pdf": parser.get("pdf"), "pdf_url": parser.get("pdf_url"),
            "unit": unit, "years": years,
            "unresolved": unresolved, "rows": rows,
            "built_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}


def cmd_compare(ticker, fy, kinds, level):
    ticker = ticker.upper()
    report = []
    for kind in kinds:
        s = stem(ticker, fy, kind)
        pf, rf = (os.path.join(GOLD_DIR, d, s + ".json") for d in ("parser", "reading"))
        if not (os.path.exists(pf) and os.path.exists(rf)):
            print(f"{s}: missing {'parser snapshot' if not os.path.exists(pf) else 'reading'}; skipped")
            continue
        parser, reading = _read(pf), _read(rf)
        items, stats = compare_rows(parser, reading)
        dis = disagreements(parser, reading, items)
        if level == "gold":
            _write(os.path.join(GOLD_DIR, f"disagreements_{s}.json"), {
                "format": FORMAT_DISAGREE, "ticker": ticker, "fy": fy, "scope": parser.get("scope"),
                "statement": kind, "statement_name": KIND_NAMES[kind],
                "pdf": parser.get("pdf"), "pdf_url": parser.get("pdf_url"), "pages": parser.get("pages"),
                "unit": reading.get("unit") or parser.get("unit"),
                "years": reading.get("years") or parser.get("years"),
                "reader": reading.get("reader", "claude"), "stats": stats,
                "disagreements": dis, "rows": items,
                "created_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())})
        else:
            copy = build_copy(parser, reading, items, "silver")
            copy["stats"] = stats
            copy["mismatches"] = dis
            _write(os.path.join(GOLD_DIR, "silver", s + ".json"), copy)
        print(f"{s}: parser {stats['rows_parser']} rows, reader {stats['rows_reader']} rows, "
              f"agreed {stats['rows_agreed']}; missing {stats['missing_in_parser']}, extra {stats['extra_in_parser']}, "
              f"label {stats['label_diffs']}, value {stats['value_diffs']}  -> {len(dis)} disagreements")
        report.append((s, stats, dis))
    return report


def cmd_finalize(ticker, fy, kinds):
    ticker = ticker.upper()
    for kind in kinds:
        s = stem(ticker, fy, kind)
        df = os.path.join(GOLD_DIR, f"disagreements_{s}.json")
        if not os.path.exists(df):
            print(f"{s}: no disagreements file; run compare first")
            continue
        dis = _read(df)
        rf = os.path.join(GOLD_DIR, f"resolutions_{s}.json")
        res = _read(rf) if os.path.exists(rf) else {}
        parser = _read(os.path.join(GOLD_DIR, "parser", s + ".json"))
        reading = _read(os.path.join(GOLD_DIR, "reading", s + ".json"))
        items, _ = compare_rows(parser, reading)
        copy = build_copy(parser, reading, items, "gold", _merge_resolutions(dis, res))
        if copy["unresolved"]:
            print(f"{s}: {copy['unresolved']} disagreement(s) not resolved yet; gold copy NOT written")
            continue
        _write(os.path.join(GOLD_DIR, f"gold_{s}.json"), copy)
        print(f"{s}: gold copy written ({len(copy['rows'])} rows)")


def _merge_resolutions(dis, res):
    """Attach Harsh's answers ({"answers": {id: {...}}}) to the disagreement records."""
    answers = res.get("answers", {})
    merged = []
    for d in dis.get("disagreements", []):
        a = answers.get(d["id"]) or {}
        merged.append({**d, **{k: a[k] for k in ("choice", "value", "label", "values") if k in a}})
    return {"disagreements": merged}


# ── check: compare fresh parser output with the gold / silver copies ────────────
def compare_with_copy(copy, snap):
    """
    Compares a parser snapshot (same shape as parser/<stem>.json) with a reference copy.
    Returns {"missing": [...], "extra": [...], "labels": [...], "values": [...], "rows": n}.
    """
    items, _ = compare_rows(snap, {"years": copy["years"], "unit": copy.get("unit"), "rows": copy["rows"]},
                            label_threshold=0.86)
    out = {"rows": len(copy["rows"]), "missing": [], "extra": [], "labels": [], "values": []}
    for it in items:
        for iss in it["issues"]:
            if iss["kind"] == "missing_in_parser":
                out["missing"].append(it["label_reader"])
            elif iss["kind"] == "extra_in_parser":
                out["extra"].append(it["label_parser"])
            elif iss["kind"] == "label":
                out["labels"].append(f"{it['label_parser']!r} should be {it['label_reader']!r}")
            else:
                y = iss["year"]
                out["values"].append(f"{it['label_reader']} FY{y}: {it['values_parser'].get(y)} "
                                     f"should be {it['values_reader'].get(y)}")
    if copy.get("unit") and snap.get("unit") and copy["unit"] != snap["unit"]:
        out["values"].insert(0, f"unit {snap['unit']} should be {copy['unit']}")
    return out


def reference_copies(level="all"):
    files = []
    if level in ("gold", "all"):
        files += [("gold", f) for f in sorted(glob.glob(os.path.join(GOLD_DIR, "gold_*.json")))]
    if level in ("silver", "all"):
        gold_stems = {os.path.basename(f)[5:-5] for _, f in files}
        files += [("silver", f) for f in sorted(glob.glob(os.path.join(GOLD_DIR, "silver", "*.json")))
                  if os.path.basename(f)[:-5] not in gold_stems]  # gold supersedes silver
    return files


def gold_check(level="all", tickers=None, snapshots=None, log=print):
    """
    Entry point for tests/regression.py. Re-runs the parser on each reference
    statement's report (or uses `snapshots` = {stem: parser snapshot} if given)
    and compares with the gold / silver copies.

    Returns {"failures": [...], "warnings": [...], "statements": n, "rows": n,
             "per_statement": {stem: {...}}}.
    A difference against GOLD is a failure; against SILVER a warning.
    """
    copies = reference_copies(level)
    if tickers:
        tick = {t.upper() for t in tickers}
        copies = [(lv, f) for lv, f in copies if os.path.basename(f).replace("gold_", "").split("_")[0] in tick]
    by_report = {}
    for lv, f in copies:
        c = _read(f)
        by_report.setdefault((c["ticker"], c["fy"]), []).append((lv, c))
    result = {"failures": [], "warnings": [], "statements": 0, "rows": 0, "per_statement": {}}
    for (ticker, fy), group in sorted(by_report.items()):
        kinds = tuple(c["statement"] for _, c in group)
        scope = group[0][1].get("scope", "consolidated")
        if snapshots is not None:
            snaps = {c["statement"]: snapshots.get(stem(ticker, fy, c["statement"])) for _, c in group}
        else:
            try:
                ensure_pdf(ticker, fy)
                snaps = parser_statements(ticker, fy, kinds, scope)
            except Exception as e:
                for lv, c in group:
                    msg = f"{stem(ticker, fy, c['statement'])}: could not run parser ({type(e).__name__}: {e})"
                    (result["failures"] if lv == "gold" else result["warnings"]).append(msg)
                continue
        for lv, c in group:
            s = stem(ticker, fy, c["statement"])
            snap = snaps.get(c["statement"])
            result["statements"] += 1
            result["rows"] += len(c["rows"])
            if not snap or not snap.get("rows"):
                d = {"rows": len(c["rows"]), "missing": [r["label"] for r in c["rows"]], "extra": [],
                     "labels": [], "values": []}
            else:
                d = compare_with_copy(c, snap)
            d["level"] = lv
            result["per_statement"][s] = d
            n = len(d["missing"]) + len(d["extra"]) + len(d["labels"]) + len(d["values"])
            if n:
                msg = (f"{s} ({lv}): {len(d['missing'])} missing, {len(d['extra'])} extra, "
                       f"{len(d['labels'])} wrong labels, {len(d['values'])} wrong values")
                (result["failures"] if lv == "gold" else result["warnings"]).append(msg)
    tot = {k: sum(len(d[k]) for d in result["per_statement"].values()) for k in ("missing", "extra", "labels", "values")}
    result["totals"] = tot
    log(f"Gold/silver check: {result['statements']} statements, {result['rows']} rows: "
        f"{tot['missing']} missing, {tot['extra']} extra, {tot['labels']} wrong labels, {tot['values']} wrong values  "
        f"({len(result['failures'])} gold failures, {len(result['warnings'])} silver warnings)")
    return result


def collect_mismatches():
    """All Claude-vs-parser mismatches: gold disagreements and silver mismatches."""
    out = []
    for f in sorted(glob.glob(os.path.join(GOLD_DIR, "disagreements_*.json"))):
        d = _read(f)
        sid = stem(d["ticker"], d["fy"], d["statement"])
        out += [{**x, "stmt": sid, "set": "gold", "unit": d.get("unit")} for x in d["disagreements"]]
    for f in sorted(glob.glob(os.path.join(GOLD_DIR, "silver", "*.json"))):
        d = _read(f)
        sid = stem(d["ticker"], d["fy"], d["statement"])
        out += [{**x, "stmt": sid, "set": "silver", "unit": d.get("unit")} for x in d.get("mismatches", [])]
    return out


def _example(x):
    if x["kind"] == "value":
        return (f"`{x['label_reader'] or x['label_parser']}` FY{x['year']}: parser **{x['value_parser']}**, "
                f"page **{x['value_reader']}**")
    if x["kind"] == "label":
        return f"parser `{x['label_parser']}` → page `{x['label_reader']}`"
    if x["kind"] == "unit":
        return f"unit: parser `{x['value_parser']}`, page `{x['value_reader']}`"
    if x["kind"] == "missing_in_parser":
        vals = ", ".join(str(v) for v in x["values_reader"].values() if v is not None)
        return f"not in parser: `{x['label_reader']}`" + (f" ({vals})" if vals else "")
    vals = ", ".join(str(v) for v in x["values_parser"].values() if v is not None)
    return f"extra parser row: `{x['label_parser']}`" + (f" ({vals})" if vals else "")


def cmd_findings(batch_note=None):
    """Writes tests/gold/silver_findings.md: mismatches grouped by pattern, most companies first."""
    ms = collect_mismatches()
    silver = [_read(f) for f in sorted(glob.glob(os.path.join(GOLD_DIR, "silver", "*.json")))]
    gold_d = [_read(f) for f in sorted(glob.glob(os.path.join(GOLD_DIR, "disagreements_*.json")))]
    rows_cmp = sum(d["stats"]["rows_reader"] for d in silver + gold_d)
    vals_cmp = sum(d["stats"]["values_reader"] for d in silver + gold_d)
    agreed = sum(d["stats"]["rows_agreed"] for d in silver + gold_d)
    by = {}
    for x in ms:
        by.setdefault(x["pattern"], []).append(x)
    order = sorted(by, key=lambda p: (-len({x["stmt"].split("_")[0] for x in by[p]}), -len(by[p])))
    L = ["# Silver findings: Claude vs parser mismatches, grouped by pattern", "",
         "*Generated by `python gold.py findings` (session C). Each mismatch is either a parser bug or a",
         "Claude misread; value mismatches were not human-checked. Gold rows are pending Harsh's review.*", "",
         f"- Statements compared: **{len(silver) + len(gold_d)}** ({len(gold_d)} gold, {len(silver)} silver), "
         f"companies: **{len({d['ticker'] for d in silver + gold_d})}**",
         f"- Rows on the page: **{rows_cmp}**, values: **{vals_cmp}**; rows where Claude and parser fully agree: "
         f"**{agreed}** ({100 * agreed / max(1, rows_cmp):.1f}%)",
         f"- Mismatches: **{len(ms)}**", "",
         "| # | Pattern | Companies | Statements | Mismatches |", "|---|---|---|---|---|"]
    for i, p in enumerate(order, 1):
        comps = sorted({x["stmt"].split("_")[0] for x in by[p]})
        L.append(f"| {i} | {PATTERNS[p]} (`{p}`) | {len(comps)} | {len({x['stmt'] for x in by[p]})} | {len(by[p])} |")
    for i, p in enumerate(order, 1):
        comps = sorted({x["stmt"].split("_")[0] for x in by[p]})
        L += ["", f"## {i}. {PATTERNS[p]} (`{p}`)", "",
              f"{len(by[p])} mismatches in {len(comps)} companies: {', '.join(comps)}", ""]
        shown = {}
        for x in by[p]:
            if shown.get(x["stmt"], 0) >= 3:
                continue
            shown[x["stmt"]] = shown.get(x["stmt"], 0) + 1
            L.append(f"- {x['stmt']} ({x['set']}, p.{(x['page'] or 0) + 1}): {_example(x)}")
            if len(shown) >= 12 and shown[x["stmt"]] == 1 and sum(shown.values()) >= 20:
                break
    L += ["", "## Per statement", "", "| Statement | Set | Scope | Rows (page) | Agreed | Missing | Extra | Labels | Values |",
          "|---|---|---|---|---|---|---|---|---|"]
    for d, lv in [(d, "gold") for d in gold_d] + [(d, "silver") for d in silver]:
        st = d["stats"]
        L.append(f"| {stem(d['ticker'], d['fy'], d['statement'])} | {lv} | {d.get('scope', '')} | {st['rows_reader']} | "
                 f"{st['rows_agreed']} | {st['missing_in_parser']} | {st['extra_in_parser']} | {st['label_diffs']} | "
                 f"{st['value_diffs']} |")
    log_f = os.path.join(GOLD_DIR, "silver_batches.json")
    log = _read(log_f) if os.path.exists(log_f) else []
    if batch_note:
        log.append({"at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "note": batch_note,
                    "statements": len(silver), "mismatches": len(ms)})
        _write(log_f, log)
    if log:
        L += ["", "## Batch log", ""] + [f"- {b['at']}: {b['note']} (silver statements so far: {b['statements']}, "
                                         f"mismatches: {b['mismatches']})" for b in log]
    with open(os.path.join(GOLD_DIR, "silver_findings.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"silver_findings.md: {len(ms)} mismatches in {len(order)} patterns")


def cmd_sample(n=30, seed=20261104):
    """
    tests/gold/silver_sample.json: a fixed random sample of silver values for Harsh to check
    against the PDF, to measure how often Claude itself misreads. Half are values where
    Claude and the parser agree, half are values where the silver copy took Claude's reading
    over the parser's (value or row mismatches). Same record shape as a disagreement, plus
    the statement's pdf / pages / unit on each record.
    """
    import random
    rng = random.Random(seed)
    agreed, overridden = [], []
    for f in sorted(glob.glob(os.path.join(GOLD_DIR, "silver", "*.json"))):
        d = _read(f)
        sid = stem(d["ticker"], d["fy"], d["statement"])
        ctx = {"stmt": sid, "pdf": d.get("pdf"), "pdf_url": d.get("pdf_url"), "pages": d.get("pages"),
               "unit": d.get("unit"), "scope": d.get("scope")}
        reading = _read(os.path.join(GOLD_DIR, "reading", sid + ".json"))
        rrows = reading.get("rows", [])
        mism = {(x.get("reader_index"), x.get("year")) for x in d.get("mismatches", []) if x["kind"] == "value"}
        for j, r in enumerate(rrows):
            for k, y in enumerate(reading.get("years", [])):
                v = (r.get("values") or [None] * 9)[k] if k < len(r.get("values") or []) else None
                if v is None:
                    continue
                rec = {**ctx, "kind": "value", "year": y, "label_reader": r.get("label"), "value_reader": v,
                       "reader_index": j, "page": r.get("page"), "search": [_search_text(v)]}
                (overridden if (j, y) in mism else agreed).append(rec)
    # rows the parser lacked entirely also carry Claude-only values
    for f in sorted(glob.glob(os.path.join(GOLD_DIR, "silver", "*.json"))):
        d = _read(f)
        sid = stem(d["ticker"], d["fy"], d["statement"])
        for x in d.get("mismatches", []):
            if x["kind"] == "missing_in_parser":
                for y, v in (x.get("values_reader") or {}).items():
                    if v is not None:
                        overridden.append({"stmt": sid, "pdf": d.get("pdf"), "pdf_url": d.get("pdf_url"),
                                           "pages": d.get("pages"), "unit": d.get("unit"), "kind": "value",
                                           "year": int(y), "label_reader": x["label_reader"], "value_reader": v,
                                           "reader_index": x["reader_index"], "page": x.get("page"),
                                           "search": [_search_text(v)]})
    k2 = min(len(overridden), n // 2)
    pick = rng.sample(overridden, k2) + rng.sample(agreed, min(len(agreed), n - k2))
    rng.shuffle(pick)
    for i, rec in enumerate(pick, 1):
        rec["id"] = f"s{i:03d}"
        rec["group"] = "claude_only" if rec in overridden else "agreed"
    _write(os.path.join(GOLD_DIR, "silver_sample.json"), {
        "format": "docfetcher-silver-sample/1", "seed": seed,
        "about": "Check each value against the PDF page: is Claude's reading right? "
                 "group 'agreed' = Claude and parser agree; 'claude_only' = silver uses Claude's value over the parser.",
        "population": {"agreed": len(agreed), "claude_only": len(overridden)},
        "items": pick, "created_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())})
    print(f"silver_sample.json: {len(pick)} values ({k2} Claude-only of {len(overridden)}, "
          f"{len(pick) - k2} agreed of {len(agreed)})")


def cmd_status():
    stems = set()
    for f in glob.glob(os.path.join(GOLD_DIR, "parser", "*.json")):
        stems.add(os.path.basename(f)[:-5])
    for s in sorted(stems):
        flags = []
        for label, path in (("reading", f"reading/{s}.json"), ("disagreements", f"disagreements_{s}.json"),
                            ("resolutions", f"resolutions_{s}.json"), ("GOLD", f"gold_{s}.json"),
                            ("silver", f"silver/{s}.json")):
            if os.path.exists(os.path.join(GOLD_DIR, path)):
                flags.append(label)
        print(f"{s:28} {' '.join(flags)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "compare", "finalize", "check", "status", "findings", "sample"])
    ap.add_argument("ticker", nargs="?")
    ap.add_argument("fy", nargs="?", type=int)
    ap.add_argument("--kinds", default="pl,bs,cf")
    ap.add_argument("--set", default=None, choices=["gold", "silver", "all"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--scope", default="consolidated", choices=["consolidated", "standalone", "auto"])
    ap.add_argument("--note", default=None, help="findings: batch note for the log")
    a = ap.parse_args()
    kinds = tuple(a.kinds.split(","))
    if a.cmd == "prepare":
        cmd_prepare(a.ticker, a.fy, kinds, a.scope)
    elif a.cmd == "compare":
        cmd_compare(a.ticker, a.fy, kinds, a.set or "gold")
    elif a.cmd == "finalize":
        cmd_finalize(a.ticker, a.fy, kinds)
    elif a.cmd == "check":
        res = gold_check(a.set or "all", [a.ticker] if a.ticker else None)
        if a.json:
            print(json.dumps(res, indent=1, default=str))
        else:
            for x in res["failures"]:
                print("  FAIL " + x)
            for x in res["warnings"]:
                print("  warn " + x)
        sys.exit(1 if res["failures"] else 0)
    elif a.cmd == "findings":
        cmd_findings(a.note)
    elif a.cmd == "sample":
        cmd_sample()
    else:
        cmd_status()


if __name__ == "__main__":
    main()
