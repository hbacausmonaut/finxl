"""
second_reading.py
-----------------
When a printed total doesn't add up, re-read the report page and look for the
one figure that explains it. No AI: the numbers printed on each candidate line
are read again from the PDF's words, and a candidate is proposed only when
exactly one single-figure change makes the total tie.

Cases covered:
  - an item misread (a digit, or the figure taken from the wrong column);
  - the total itself misread.
Every proposal is a number actually printed on that line of the page. Nothing is
proposed when the fix is ambiguous or no printed number explains it: some annual
reports print totals that don't add up, and those stay flagged for the reader.

for_run(engine_json) -> [{"scope", "kind", "row", "year", "value", "printed",
                          "note", "reportFy", "page"}]  (row = merged row index)
"""

import os
import re

import fitz  # PyMuPDF

import ar_extract
import pdfview

TOL = 0.011  # ₹ crore: figures are rounded to two decimals


def _num(text):
    """'(1,234.50)' -> -1234.5 ; '1,234' -> 1234.0 ; None if not a number."""
    t = text.strip().replace(",", "")
    neg = t.startswith("(") and t.endswith(")") or t.startswith(("-", "–", "−"))
    t = t.strip("()-–−")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _line_numbers(doc, pages, label):
    """Numbers printed on the line that best matches `label`, left to right, as printed."""
    hit = pdfview.find_label(doc, pages, label)
    if not hit:
        return None, []
    pno, rect = pdfview.page_rect(doc, hit["page"])
    page = doc[pno]
    lr = hit["line_rect"]
    words = [w for w in page.get_text("words", clip=rect)
             if w[1] < lr.y1 - 1 and w[3] > lr.y0 + 1]
    words.sort(key=lambda w: w[0])
    nums = [(_num(w[4]), w[4]) for w in words]
    return hit["page"], [(v, t) for v, t in nums if v is not None and re.search(r"\d", t)]


def _candidates(nums, factor, current):
    """Values on the line that could be this figure, in ₹ crore, excluding the one already used."""
    out = []
    for v, text in nums:
        for f in sorted({factor, 1.0, 0.01, 0.1, 0.0001}):
            c = round(v * f, 4)
            if abs(c - current) > TOL and abs(c) > 0:
                out.append((c, text))
    return out


def _report_factor(rows_vals, printed):
    """Guess the unit factor from a figure we know: crore value ÷ printed number."""
    for v, text in printed:
        for f in (1.0, 0.01, 0.1, 0.0001):
            if abs(v * f - rows_vals) <= TOL:
                return f
    return 1.0


def _try_fix(total, members, values):
    """
    total: printed total. members: [(row, sign)]. values: {row: value}.
    Returns the single change that makes the sum tie, as (row, new_value) or None.
    """
    s = sum(sign * values[r] for r, sign in members)
    gap = total - s
    if abs(gap) <= TOL:
        return None
    return gap


def for_statement(doc, pages, rows, year, total_row, group):
    """Second readings for one failing total in one year. rows: merged rows (crore)."""
    members = [(r, sign) for r, sign in group["members"] if rows[r]["values"].get(year) is not None]
    if not members:
        return []
    values = {r: rows[r]["values"][year] for r, _ in members}
    total = rows[total_row]["values"][year]
    gap = _try_fix(total, members, values)
    if gap is None:
        return []

    proposals = []
    # 1. one item misread: its line on the page shows another number that closes the gap
    for r, sign in members:
        want = round(values[r] + sign * gap, 4)
        page, nums = _line_numbers(doc, pages, rows[r]["label"])
        if not nums:
            continue
        factor = _report_factor(values[r], nums)
        for c, text in _candidates(nums, factor, values[r]):
            if abs(c - want) <= TOL * 2:
                proposals.append({"row": r, "value": round(want, 2), "printed": text, "page": page,
                                  "note": f"The page also shows {text} on this line; with it the total adds up."})
                break
        # No "flip the sign" guess without the page showing it: annual reports themselves
        # sometimes print totals that don't add up (PIDILITIND FY2021 OCI), and a guess
        # would contradict the page. Every proposal must be a number printed on the line.
    # 2. the total itself misread: its line shows the sum of its items
    page, nums = _line_numbers(doc, pages, rows[total_row]["label"])
    if nums:
        s = total - gap
        factor = _report_factor(total, nums)
        for c, text in _candidates(nums, factor, total):
            if abs(c - s) <= TOL * 2:
                proposals.append({"row": total_row, "value": round(s, 2), "printed": text, "page": page,
                                  "note": f"The total's line also shows {text}, which equals the sum of its items."})
                break
    # Only an unambiguous fix is worth showing.
    return proposals if len(proposals) == 1 else []


def for_run(eng, log=lambda m: None):
    """Second readings for every failing total in a run's engine result (engine.json shape)."""
    from_cache = {}
    out = []
    sources = eng["sources"]
    merged = eng["merged"]
    for key, rows in merged.items():
        scope, kind = key.split("|")
        for ti, row in enumerate(rows):
            for y, st in (row.get("status") or {}).items():
                if st != "fail":
                    continue
                g = (row.get("group") or {}).get(y) or (row.get("group") or {}).get(str(y))
                fy = (row.get("src") or {}).get(y) or (row.get("src") or {}).get(str(y))
                if not g or not fy:
                    continue
                year = int(y)
                src = next((s for s in sources if s["fy"] == fy and s["scope"] == scope
                            and ar_extract.KINDS.get(kind) == s["statement"]), None)
                pages = pdfview.parse_pages((src or {}).get("pages", "").split(",")) if src else []
                path = pdfview.pdf_path(None, eng["ticker"], fy)
                if not pages or not path:
                    continue
                if path not in from_cache:
                    from_cache[path] = fitz.open(path)
                doc = from_cache[path]
                rows_y = [{"label": r["label"], "values": {int(k): v for k, v in r["values"].items()}} for r in rows]
                try:
                    found = for_statement(doc, pages, rows_y, year, ti, g)
                except Exception as e:  # a bad page shouldn't stop the others
                    log(f"  second reading: {kind} FY{year}: {e}")
                    continue
                for p in found:
                    out.append({"scope": scope, "kind": kind, "year": year, "reportFy": fy, "totalRow": ti, **p})
                    log(f"  second reading: {scope} {kind} FY{year} '{rows[p['row']]['label'][:40]}' → {p['value']:,.2f}")
    for doc in from_cache.values():
        ar_extract.forget_doc(doc)
        doc.close()
    return out
