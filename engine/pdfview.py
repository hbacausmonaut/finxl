"""
pdfview.py
----------
Shared helpers for the review screens (audit_ui.py, review_ui.py): find an
annual-report PDF in the cache, render one statement page as an image, and
highlight where a figure is printed on it.

Read-only: uses ar_extract's word reader (so shifted / coded fonts decode the
same way the parser sees them) but never changes extraction.
"""

import difflib
import io
import os
import re

import fitz  # PyMuPDF
from PIL import Image, ImageDraw

import ar_extract

CACHE_DIR = os.environ.get("DOCFETCHER_CACHE", os.path.join(os.path.expanduser("~"), "DocFetcherData"))

# Report unit -> factor to ₹ crore (same table as finxl.TO_CRORE)
TO_CRORE = {"crore": 1.0, "lakh": 0.01, "million": 0.1, "thousand": 0.0001, None: 1.0}

PAGE_RE = re.compile(r"^\s*(\d+)\s*([LR])?\s*$", re.I)


# ── Files and pages ───────────────────────────────────────────────────────────
def pdf_path(rel_or_abs, ticker=None, fy=None):
    """Resolve a PDF given relative to the cache (or absolute). Falls back to the
    standard cache name for ticker + fy. Returns None if not on disk."""
    cands = []
    if rel_or_abs:
        cands.append(rel_or_abs if os.path.isabs(rel_or_abs) else os.path.join(CACHE_DIR, rel_or_abs))
    if ticker and fy:
        folder = os.path.join(CACHE_DIR, ticker, "AnnualReports")
        cands.append(os.path.join(folder, f"Annual Report {fy}.pdf"))
        if os.path.isdir(folder):  # fetchdocs.py names files after the Screener label
            cands += [os.path.join(folder, f) for f in sorted(os.listdir(folder))
                      if f.lower().endswith(".pdf") and str(fy) in f]
    for p in cands:
        if p and os.path.exists(p):
            return p
    return None


def rel_to_cache(path):
    try:
        rel = os.path.relpath(path, CACHE_DIR)
        return path if rel.startswith("..") else rel.replace(os.sep, "/")
    except ValueError:  # different drive on Windows
        return path


def parse_pages(pages):
    """'212, 213L' or ['212', '213L'] -> ['212', '213L'] (valid names only)."""
    if isinstance(pages, str):
        pages = re.split(r"[,\s]+", pages)
    return [str(p).strip().upper() for p in pages or [] if PAGE_RE.match(str(p))]


def page_rect(doc, name):
    """Sources-sheet page name ('126', '126L', '126R') -> (page index, clip rect)."""
    m = PAGE_RE.match(name)
    pno = int(m.group(1)) - 1
    page = doc[pno]
    if page.rotation:  # same as ar_extract.virtual_pages: make rotated pages upright
        page.remove_rotation()
    r = page.rect
    half = (m.group(2) or "").upper()
    if half and r.width > r.height * 1.2:
        mid = r.x0 + r.width / 2
        r = fitz.Rect(r.x0, r.y0, mid, r.y1) if half == "L" else fitz.Rect(mid, r.y0, r.x1, r.y1)
    return pno, r


# ── Finding a figure on a page ────────────────────────────────────────────────
def _num_tokens(words):
    """Numeric tokens incl. ones split into pieces ('(1,234' ')' / '1,23,' '456')."""
    out = []
    lines = ar_extract.group_lines(list(words))
    for ln in lines:
        ln = sorted(ln, key=lambda w: w[0])
        for i, w in enumerate(ln):
            v = ar_extract.to_num(w[4])
            if v is not None:
                out.append((v, fitz.Rect(w[:4]), ln))
            if i + 1 < len(ln) and ln[i + 1][0] - w[2] < 3:  # glued fragment
                t = w[4] + ln[i + 1][4]
                v2 = ar_extract.to_num(t)
                if v2 is not None and v is None:
                    out.append((v2, fitz.Rect(w[:4]) | fitz.Rect(ln[i + 1][:4]), ln))
    return out


def _norm(s):
    return re.sub(r"[^a-z]+", " ", (s or "").lower()).strip()


def find_value(doc, page_names, value, label="", unit=None, in_crore=True):
    """
    Look for `value` on the given statement pages.
    in_crore=True: value is in ₹ crore (as in the Excel); every report unit is tried.
    in_crore=False: value is as printed in the report (unit ignored).
    Returns hits sorted best first: {"page", "rect", "line_rect", "sign_ok", "score", "printed"}.
    """
    if value is None:
        return []
    factors = sorted(set(TO_CRORE.values())) if in_crore else [1.0]
    if in_crore and unit in TO_CRORE:
        factors = [TO_CRORE[unit]] + [f for f in factors if f != TO_CRORE[unit]]
    want = _norm(label)
    hits = []
    for name in parse_pages(page_names):
        try:
            pno, rect = page_rect(doc, name)
        except (IndexError, AttributeError, ValueError):
            continue
        words = ar_extract.vp_words(doc, (pno, rect))
        for n, r, ln in _num_tokens(words):
            for f in factors:
                tol = (0.00006 + 1e-7 * abs(value)) if in_crore else max(0.006, abs(value) * 1e-6)
                if abs(n * f - value) <= tol:
                    sign_ok = True
                elif abs(n * f + value) <= tol and value != 0:
                    sign_ok = False
                else:
                    continue
                left = " ".join(w[4] for w in ln if w[2] <= r.x0 + 1)
                sim = difflib.SequenceMatcher(None, want, _norm(left)).ratio() if want else 0.0
                line_rect = fitz.Rect(rect.x0, min(w[1] for w in ln) - 1, rect.x1, max(w[3] for w in ln) + 1)
                hits.append({"page": name, "rect": r, "line_rect": line_rect, "sign_ok": sign_ok,
                             "score": sim + (0.3 if sign_ok else 0) + (0.05 if f == factors[0] else 0),
                             "printed": n})
                break
    hits.sort(key=lambda h: -h["score"])
    return hits


def find_label(doc, page_names, label):
    """Best line matching a label (for rows without a value). Returns hit dict or None."""
    want = _norm(label)
    if not want:
        return None
    best = None
    for name in parse_pages(page_names):
        try:
            pno, rect = page_rect(doc, name)
        except (IndexError, AttributeError, ValueError):
            continue
        for ln in ar_extract.group_lines(list(ar_extract.vp_words(doc, (pno, rect)))):
            text = _norm(" ".join(w[4] for w in sorted(ln, key=lambda w: w[0])))
            if not text:
                continue
            sim = difflib.SequenceMatcher(None, want, text[:len(want) + 20]).ratio()
            if not best or sim > best["score"]:
                lr = fitz.Rect(rect.x0, min(w[1] for w in ln) - 1, rect.x1, max(w[3] for w in ln) + 1)
                best = {"page": name, "rect": None, "line_rect": lr, "sign_ok": True, "score": sim}
    return best if best and best["score"] >= 0.6 else None


# ── Rendering ─────────────────────────────────────────────────────────────────
def render(doc, page_name, hits=(), dpi=120):
    """PNG bytes of one (virtual) page with the hits drawn on it: the best hit as a
    thick red box and a yellow band across its line, other hits as thin orange boxes."""
    pno, rect = page_rect(doc, page_name)
    pix = doc[pno].get_pixmap(dpi=dpi, clip=rect)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    s = dpi / 72.0

    def box(r):
        return [(r.x0 - rect.x0) * s, (r.y0 - rect.y0) * s, (r.x1 - rect.x0) * s, (r.y1 - rect.y0) * s]

    on_page = [h for h in hits if h["page"] == page_name]
    for k, h in enumerate(on_page):
        if k == 0:
            d.rectangle(box(h["line_rect"]), fill=(255, 235, 59, 70))
            if h.get("rect") is not None:
                r = h["rect"]
                d.rectangle(box(fitz.Rect(r.x0 - 3, r.y0 - 2, r.x1 + 3, r.y1 + 2)),
                            outline=(220, 0, 0, 255) if h["sign_ok"] else (128, 0, 200, 255), width=3)
        elif h.get("rect") is not None:
            d.rectangle(box(h["rect"]), outline=(255, 140, 0, 220), width=2)
    out = Image.alpha_composite(img, over).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def fmt_num(v):
    """Indian-style grouping, 2 decimals, negatives in brackets (as reports print them)."""
    if v is None:
        return "–"
    neg = v < 0
    s = f"{abs(v):.2f}"
    whole, dec = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1] if head else ""
        whole = f"{head},{tail}" if head else tail
    s = f"{whole}.{dec}"
    return f"({s})" if neg else s
