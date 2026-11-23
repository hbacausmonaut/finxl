"""
ar_extract.py
-------------
Finds the financial statements inside a (300-page) annual report PDF and
parses them into structured rows using PyMuPDF word positions. No API needed.

    locate_statements(doc)        -> where each statement lives (page numbers)
    parse_statement(doc, pages)   -> {"unit", "years", "rows": [...]}

Each row is {"label", "level", "values": [v_col0, v_col1, ...], "is_header"}.
Column 0 is normally the current year, column 1 the previous year.
"""

import re
import fitz  # PyMuPDF

# ── Statement headings ────────────────────────────────────────────────────────
KINDS = {
    "pl": "Profit & Loss",
    "bs": "Balance Sheet",
    "cf": "Cash Flow",
    "ra": "Revenue Account",  # insurers (IRDAI format): policyholders' account
}

# Matched at the START of a short line, so sentences that merely mention
# "the Statement of Profit and Loss" are ignored.
_SCOPE = r"^\s*(?:(?:audited\s+)?(?:consolidated|standalone)\s+)?(?:ind\s*as\s+)?"
HEADING_RE = {
    "bs": re.compile(_SCOPE + r"(?:statements?\s+of\s+)?balance\s+sheet\b", re.I),
    "pl": re.compile(_SCOPE + r"(?:statements?\s+of\s+(?:the\s+)?(?:consolidated\s+|standalone\s+)?profit\s+(?:and|&)\s+loss"
                     r"|profit\s+(?:and|&)\s+loss\s+(?:statement|account))(?![a-z])", re.I),  # "Account1" footnote ok
    "cf": re.compile(_SCOPE + r"(?:statements?\s+of\s+(?:consolidated\s+|standalone\s+)?cash\s+flows?|cash\s+flows?\s+statement"
                     r"|receipts\s+(?:and|&)\s+payments\s+account)\b", re.I),
    "ra": re.compile(_SCOPE + r"revenue\s+account\b", re.I),
}
SOCE_RE = re.compile(_SCOPE + r"statements?\s+of\s+changes\s+in\s+equity", re.I)

# A statement page must also contain words that only appear in that statement
BODY_RE = {
    "bs": re.compile(r"total\s+assets|equity\s+(and|&)\s+liabilities|capital\s+(and|&)\s+liabilities"
                     r"|liabilities\s+(and|&)\s+equity|sources\s+of\s+funds|application\s+of\s+funds"
                     r"|non-financial\s+liabilities", re.I),
    "pl": re.compile(r"revenue\s+from\s+operations|total\s+income|profit\s+(before|for)|interest\s+earned"
                     r"|policyholders", re.I),
    "cf": re.compile(r"operating\s+activities", re.I),
    "ra": re.compile(r"premiums?\s+earned|premium", re.I),
}

# Content signatures, used when a PDF has no heading text at all
SIGNATURE_RE = {
    "bs": [re.compile(r"total\s+assets", re.I),
           re.compile(r"total\s+equity\s+(and|&)\s+liabilities", re.I)],
    "pl": [re.compile(r"revenue\s+from\s+operations", re.I),
           re.compile(r"total\s+expenses", re.I),
           re.compile(r"earnings\s+per\s+(equity\s+)?share", re.I)],
    "cf": [re.compile(r"operating\s+activities", re.I),
           re.compile(r"adjustments?\s+(for|to)", re.I)],
}
NCI_RE = re.compile(r"non[\s-]*controlling\s+interest|minority\s+interest", re.I)

# Headings that mean "the previous statement has ended"
STOP_RE = re.compile(r"statements?\s+of\s+changes\s+in\s+equity|notes\s+(to|forming)"
                     r"|independent\s+auditor|^\s*schedule\s*[-–:]?\s*\d+|schedules?\s+(forming|to\s+the)", re.I)

FOOTER_RE = re.compile(r"as\s+per\s+our\s+report|for\s+and\s+on\s+behalf|in\s+terms\s+of\s+our\s+report"
                       r"|schedules\s+referred\s+to\s+(above|herein)\s+form|notes\s+referred\s+to\s+above\s+form"
                       r"|the\s+accompanying\s+notes|see\s+accompanying\s+notes"
                       r"|significant\s+accounting\s+policies\s+and\s+notes"
                       r"|the\s+above\s+(consolidated\s+|standalone\s+)?(statements?\s+of\s+)?cash\s+flows?"
                       r"|the\s+above\s+.{0,30}receipts\s*(&|and)\s*payments\s+account"  # insurers (ICICIGI)
                       r"|has\s+been\s+prepared\s+under\s+the\s+.?indirect"
                       r"|changes?\s+in\s+liabilit(y|ies)\s+arising\s+from\s+financing"
                       # signature blocks (SBI: auditors' membership numbers read as amounts)
                       # (not "...reported using the indirect method": INFY prints that policy
                       # note at the top of its cash flow page)
                       r"|chartered\s+accountants|firm\s+reg(n|istration)\.?\s+no|membership\s+no", re.I)

UNIT_RE = re.compile(r"(?:₹|rs\.?|inr|`|₹)\s*(?:in\s+)?(crores?|lakhs?|lacs?|millions?|thousands?|['‘’]000)"
                     r"|(?:in|amount\s+in)\s+(?:₹|rs\.?|inr|`)?\s*(crores?|lakhs?|lacs?|millions?|thousands?|['‘’]000)", re.I)

NUM_RE = re.compile(r"^\(?-?[\d,]*\d(\.\d+)?\)?\*{0,2}$")
NIL_TOKENS = {"-", "–", "—", "--", "nil", "Nil"}
NOTE_RE = re.compile(r"^\d{1,2}(\.\d{1,2})?([A-Za-z]|\([a-zA-Z]+\))?[,&]?$")
YEAR_RE = re.compile(r"(?:20|19)\d{2}")
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_LINE_RE = re.compile(r"\b\d{1,2}(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*(19|20)\d{2}"
                          r"|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s*(19|20)\d{2}", re.I)
ENUM_RE = re.compile(r"^(\(?[ivxlcIVXLC]+\)|[ivxlcIVXLC]+\.|\(?[a-zA-Z]\)|[a-zA-Z]\.|\d+\.|\d+\))\s+")


# ── Virtual pages ─────────────────────────────────────────────────────────────
# Many Indian reports are published as 2-up landscape spreads (two A4 pages on
# one sheet). We split those into left/right halves and treat each as a page.
def virtual_pages(doc):
    vps = []
    for i, page in enumerate(doc):
        # Pages stored rotated (NTPC FY2024: /Rotate 270) report word positions in the
        # unrotated frame, so text reads sideways. Make them upright in memory first.
        if page.rotation:
            page.remove_rotation()
        r = page.rect
        if r.width > r.height * 1.2:
            mid = r.x0 + r.width / 2
            vps.append((i, fitz.Rect(r.x0, r.y0, mid, r.y1)))
            vps.append((i, fitz.Rect(mid, r.y0, r.x1, r.y1)))
        else:
            vps.append((i, r))
    return vps


def join_glyph_digits(words):
    """After de-duplicating fake bold, text comes out one glyph per word ("5" "9" "5" "," ...): re-join."""
    words = sorted(words, key=lambda w: (round((w[1] + w[3]) / 2), w[0]))
    out = []
    for w in words:
        if out:
            p = out[-1]
            num = re.fullmatch(r"[\d,.()-]+", p[4]) and re.fullmatch(r"[\d,.()-]+", w[4])
            if abs((p[1] + p[3]) / 2 - (w[1] + w[3]) / 2) < 2 and 0 <= w[0] - p[2] < (1.5 if num else 0.8):
                out[-1] = (p[0], min(p[1], w[1]), w[2], max(p[3], w[3]), p[4] + w[4]) + tuple(p[5:])
                continue
        out.append(w)
    return out


RUPEE_GLUED_RE = re.compile(r"^[`HJDK](\(?-?\d[\d,]*[.,]\d+\)?)$")


def vp_words(doc, vp):
    page = doc[vp[0]]
    # PyMuPDF's word splitter silently drops control characters, so check raw text
    if CTRL_RE.search(page.get_text("text", clip=vp[1])):
        words = decoded_words(page, vp[1])
    else:
        words = page.get_text("words", clip=vp[1])
    # Skip rotated text (side bands like "ANNUAL REPORT 2024-25"). A tall-and-narrow box
    # is only a hint (some fonts have very tall boxes); confirm with the line direction.
    tall = [w for w in words if len(w[4]) > 2 and (w[3] - w[1]) > (w[2] - w[0]) * 1.2]
    if tall:
        rotated = [fitz.Rect(ln["bbox"]) for b in page.get_text("dict", clip=vp[1])["blocks"]
                   for ln in b.get("lines", []) if abs(ln["dir"][1]) > 0.5]
        if rotated:
            def is_rot(w):
                c = fitz.Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
                return any(c in r for r in rotated)
            words = [w for w in words if not (w in tall and is_rot(w))]
    # symbol-font glyphs in Unicode's private-use area glued to amounts ("80,97,57" in SBI)
    words = [w[:4] + (PUA_RE.sub("", w[4]),) + tuple(w[5:]) for w in words]
    words = [w for w in words if w[4]]
    # fake bold: the same glyph printed several times on the same spot (CUMMINSIND)
    seen, dedup = {}, []
    for w in words:
        pos = seen.setdefault(w[4], [])
        if not any(abs(w[0] - x) < 1.5 and abs(w[1] - y) < 1.5 for x, y in pos):
            pos.append((w[0], w[1]))
            dedup.append(w)
    if len(dedup) < len(words) * 0.9:
        words = join_glyph_digits(dedup)
    # rupee sign drawn in a symbol font extracts as a letter glued to the amount: "H86.91" (SBI EPS)
    words = [w[:4] + (RUPEE_GLUED_RE.sub(r"\1", w[4]),) + tuple(w[5:]) for w in words]
    words = fix_shifted_font(words)
    if any(UP_TRIGGER_RE.search(w[4]) for w in words):
        vocab = doc_vocab(doc)
        words = [w[:4] + (decode_up_token(w[4], vocab),) + w[5:] if UP_TRIGGER_RE.search(w[4]) else w
                 for w in words]
    return decode_up_words(words, doc)


def decode_up_words(words, doc):
    """
    Capitals shifted up into lowercase, as separate words ("molcfq clo qeb YEAR" =
    "PROFIT FOR THE YEAR", SUNPHARMA FY2022). A word is decoded only if it is not a
    real word but its decoded form is, and the page shows this at least 3 times.
    """
    cands = [i for i, w in enumerate(words) if re.fullmatch(r"[$&]*\(?[a-zA-Z][a-zA-Z-]+\)?", w[4])
             and re.search(r"[a-z]{2}", w[4])]
    if len(cands) < 3:
        return words
    import quality
    vocab = doc_vocab(doc) | quality.vocab()

    def real(s):
        parts = re.findall(r"[a-z]+", s.lower())
        return bool(parts) and all(p in vocab for p in parts)

    hits = {}
    for i in cands:
        t = words[i][4].lstrip("$&")
        if real(t):
            continue
        # lowercase = coded capitals; real capitals kept ("klk-Clkqoliifkd" = "NON-CONTROLLING"),
        # or every letter coded ("molcfqLEilppF" = "PROFIT/(LOSS)")
        for d in ("".join(_down(c) if c.islower() else c for c in t), "".join(_down(c) for c in t)):
            if real(d) and not re.search(r"[a-z]", d):
                hits[i] = d
                break
    if len(hits) < 3:
        return words
    return [w[:4] + (hits[i],) + tuple(w[5:]) if i in hits else w for i, w in enumerate(words)]


# ── Fonts that extract capitals/digits/spaces +29 shifted (lowercase intact) ──
# "$ket=mrofit=_efore=qax" = "Net Profit Before Tax", "lqebo=`ljmobebkpfsb" = "OTHER COMPREHENSIVE".
# Lowercase letters are ambiguous (genuine, or a shifted capital), so each word is
# decoded the way that produces a real word from the report's own vocabulary.
UP_TRIGGER_RE = re.compile(r"\w[=^_`]\w|^[=^_`]\w{2,}|^[M-V]{2,3}[\^_`]$|^E?[fsu]{1,5}[KF]=?[&$]*$")  # "ufK&" = "XI."
BASE_VOCAB = set("""income tax expense expenses profit loss other comprehensive earnings before interest
depreciation amortisation amortization net total revenue operations statement of and the for on in to as at
per items that will not be reclassified fair value gain investments equity instruments through defined benefit
plans remeasurement debt share year cash flow activities finance costs assets liabilities current non
exceptional employee benefits balance sheet sale products services operating opening closing increase decrease
equivalents ebitda oci""".split())
_vocab_cache = {}


def doc_vocab(doc):
    key = id(doc)
    if key not in _vocab_cache:
        vocab = set(BASE_VOCAB)
        for page in doc:
            # Title Case words can't come from the shifted font (it has no genuine capitals)
            vocab.update(w.lower() for w in re.findall(r"\b[A-Z][a-z]{2,}\b", page.get_text()))
        _vocab_cache[key] = vocab
    return _vocab_cache[key]


def _down(c):
    return chr(ord(c) - SHIFT) if 0x3d <= ord(c) <= 0x7a else c


def decode_up_token(token, vocab):
    # pure shifted roman-numeral serials: "fK&" = "I.&", "ufK&" = "XI.&", "EfF&" = "(I)&"
    if re.fullmatch(r"E?[fsu]{1,5}[KF]?=?[&$]*", token):
        return "".join(_down(c) for c in token)
    out = []
    for sub in token.split("="):
        if not sub:
            out.append("")
            continue
        a = "".join(c if c.islower() else _down(c) for c in sub)            # only non-lowercase shifted
        b = "".join(_down(c) for c in sub)                                    # everything shifted
        i = next((k for k, c in enumerate(sub) if c.islower()), None)
        c_ = a if i is None else a[:i] + _down(sub[i]) + a[i + 1:]            # + first letter (Title Case)
        def ok(s):
            if re.search(r"[A-Z]{2}[a-z]|[a-z][A-Z]", s):
                return False  # "CASe", "fkCljb" are not real words
            parts = re.findall(r"[a-z]+", s.lower())
            return bool(parts) and all(p in vocab or len(p) == 1 for p in parts)
        pick = next((s for s in (a, c_, b) if ok(s)), None)
        if pick is None:
            # real words never have a capital right after a lowercase letter
            pick = b if re.search(r"[a-z][A-Z]", a) else a
        out.append(pick)
    return " ".join(out).strip()


CTRL_RE = re.compile(r"[\x03-\x08\x0b\x0c\x0e-\x1f]")
PUA_RE = re.compile(r"[-]")


def decoded_words(page, clip):
    """
    Rebuild words character by character, un-shifting every span whose font
    produces control characters (even spaces come out as \\x03 in such fonts).

    The decision is made per font, from the whole page: a coded font has control
    characters in nearly all its spans (HCLTECH ArialMT 640/649), while a normal font
    may carry the odd stray bullet or footnote mark (VBL GothamBook 11/799). Judging
    span by span shifted genuine note numbers and dashes in VBL ("4A" -> "Q^", "-" -> "=J=").
    """
    rd = page.get_text("rawdict", clip=clip)

    def looks_coded(t):
        # coded text: control characters (its spaces and digits), never lowercase, and
        # more than a stray bullet ("\x07\t" in SUNPHARMA, "\x07Total ..." in VBL)
        return bool(CTRL_RE.search(t)) and not re.search(r"[a-z]", t) and len(t.strip()) >= 3

    counts = {}
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                t = "".join(c["c"] for c in s["chars"])
                if t.strip():
                    n, k = counts.get(s["font"], (0, 0))
                    counts[s["font"]] = (n + 1, k + looks_coded(t))
    coded = {f for f, (n, k) in counts.items() if k >= n * 0.5}

    def is_shifted(span):
        t = "".join(c["c"] for c in span["chars"])
        if re.search(r"[a-z]", t):
            return False  # lowercase never comes out of the coded range
        if CTRL_RE.search(t):
            # whole font coded (HCLTECH), or a font name used for both coded and normal
            # text (BANKBARODA headings): judge the span itself
            return span["font"] in coded or looks_coded(t)
        if span["font"] not in coded or NUM_RE.match(t.strip()):
            return False
        # a coded font can also carry genuine capitals/numbers ("EQUITY", "77" in HCLTECH
        # FY2020): shift only text with a coded capital ($..= range) in it
        return all(0x03 <= ord(c) <= 0x5d or c in SHIFT_LIGATURES for c in t) and \
            any(0x24 <= ord(c) <= 0x3d or c in SHIFT_LIGATURES for c in t)

    words = []
    for bi, b in enumerate(rd["blocks"]):
        for li, ln in enumerate(b.get("lines", [])):
            text, box = [], None
            def flush():
                nonlocal text, box
                if text:
                    words.append((box[0], box[1], box[2], box[3], "".join(text), bi, li, len(words)))
                text, box = [], None
            for s in ln["spans"]:
                shifted = is_shifted(s)
                for ch in s["chars"]:
                    c = ch["c"]
                    if shifted:
                        if c in SHIFT_LIGATURES:
                            c = SHIFT_LIGATURES[c]
                        elif 0x03 <= ord(c) <= 0x5d and c != " ":  # a real space is a space (BPCL)
                            c = chr(ord(c) + SHIFT)
                    elif CTRL_RE.match(c):
                        continue  # stray bullet / footnote mark in a normal font
                    if c.isspace():
                        flush()
                        continue
                    x0, y0, x1, y1 = ch["bbox"]
                    box = [x0, y0, x1, y1] if box is None else \
                        [min(box[0], x0), min(box[1], y0), max(box[2], x1), max(box[3], y1)]
                    text.append(c)
            flush()
    return words


# Some PDFs embed fonts whose text extracts shifted by 29 code points
# ("6WDQGDORQH 6WDWHPHQW RI 3UR¿W DQG /RVV" = "Standalone Statement of Profit and Loss").
SHIFT = 29
SHIFT_MARKERS = {"WKH", "RI", "DQG", "IRU", "LQ", "WR", "DV", "DW"}  # the of and for in to as at
SHIFT_LIGATURES = {"¿": "fi", "À": "fl", "Ë": "ffi"}


def _unshift(t):
    out = []
    for ch in t:
        if ch in SHIFT_LIGATURES:
            out.append(SHIFT_LIGATURES[ch])
        elif 0x03 <= ord(ch) <= 0x5d:
            out.append(chr(ord(ch) + SHIFT))
        else:
            return None
    return "".join(out)


def segment_words(s, vocab, maxlen=20):
    """Split run-together lowercase text into vocabulary words ("cashequivalents" -> "cash equivalents")."""
    best = [None] * (len(s) + 1)
    best[0] = []
    for i in range(1, len(s) + 1):
        for j in range(max(0, i - maxlen), i):
            if best[j] is not None and s[j:i] in vocab and (best[i] is None or len(best[j]) + 1 < len(best[i])):
                best[i] = best[j] + [s[j:i]]
    return best[len(s)]


SMALL_WORDS = {"a", "of", "in", "to", "on", "and", "the", "for", "from", "at", "by", "or", "as", "net"}


def decode_glued(token):
    """
    A +29 coded word whose spaces were lost ("1HWLQFUHDVHGHFUHDVHLQFDVK" = "Net increase
    decrease in cash"): decode only if the result splits cleanly into real words.
    """
    if len(token) < 6 or not re.fullmatch(r"[\x21-\x5d]+", token) or not re.search(r"[A-Z]{4}", token):
        return None
    u = _unshift(token)
    if not u:
        return None
    m = re.fullmatch(r"([A-Za-z][a-z]+)([^a-z]*)", u)  # tail like "ABC" in "cashequivalentsABC"
    if not m:
        return None
    import quality
    vocab = quality.vocab() | BASE_VOCAB | SMALL_WORDS
    parts = segment_words(m.group(1).lower(), vocab)
    if not parts or len(parts) < 2 or sum(len(p) >= 4 for p in parts) < 1:
        return None
    text = " ".join(parts)
    if m.group(1)[0].isupper():
        text = text[0].upper() + text[1:]
    return text + (" " + m.group(2) if m.group(2) else "")


def fix_shifted_font(words):
    if sum(1 for w in words if w[4] in SHIFT_MARKERS) < 2:
        glued = [decode_glued(w[4]) for w in words]
        if any(glued):
            return [w[:4] + (g,) + tuple(w[5:]) if g else w for w, g in zip(words, glued)]
        return words
    fixed = []
    for w in words:
        t = w[4]
        if not NUM_RE.match(t) and t not in NIL_TOKENS:
            u = _unshift(t)
            if u and re.search(r"[a-z]", u):
                w = w[:4] + (u,) + w[5:]
        fixed.append(w)
    return fixed


def vp_text(doc, vp):
    return doc[vp[0]].get_text("text", clip=vp[1])


def vp_name(vp, doc):
    """Human page number, e.g. '126' or '126L'/'126R' for a spread half."""
    pno, rect = vp
    page = doc[pno].rect
    if rect.width < page.width * 0.9:
        return f"{pno + 1}{'L' if rect.x0 < page.x0 + 1 else 'R'}"
    return str(pno + 1)


def norm_text(t):
    """Undo ligatures that extract as 'ﬁ ' / 'ﬂ ' (e.g. 'Cash ﬂ ows'), 'Á' (= fl) and 'fl' for fi ('Proflt')."""
    t = re.sub(r"ﬁ\s?(?=[a-z])", "fi", t).replace("ﬁ", "fi")
    t = re.sub(r"ﬂ\s?(?=[a-z])", "fl", t).replace("ﬂ", "fl")
    t = re.sub(r"Á(?=[a-z])", "fl", t)  # "Cash Áow"
    t = t.replace("ႇ", "ff")  # HCLTECH's "ff" ligature extracts as U+1087 ("Eႇect", "diႇerences")
    return re.sub(r"(?<=[A-Za-z])fl(?=[nctxsrd])|\bfl(?=[nr][a-z])", "fi", t)  # "Proflt", "flnancial"


def top_lines(words, rect, frac=0.4):
    limit = rect.y0 + rect.height * frac
    out = []
    for ln in group_lines([w for w in words if w[1] < limit]):
        t = norm_text(" ".join(w[4] for w in ln))
        # "fake bold" headings draw each word several times: "Balance Balance Balance Sheet Sheet"
        # (words of 3+ letters only: letter-spaced "S H E E T" must keep its double E)
        t = re.sub(r"\b(\w{3,})(?:\s+\w?\1\b)+", r"\1", t)
        out.append(t)
    return out


COMPACT_HEADING_RE = {
    "ra": re.compile(r"^(consolidated|standalone|standlone)?revenueaccount"),
    "bs": re.compile(r"^(consolidated|standalone|standlone)?balancesheet"),
    "pl": re.compile(r"^(consolidated|standalone|standlone)?(statementof)?profit(and|&)loss(account|statement)?"),
    "cf": re.compile(r"^(consolidated|standalone|standlone)?(cashflowstatement|statementofcashflows?)"),
}


def unshift_up(t):
    """Fonts that extract +29 shifted: '`lkplifa^qba=pq^qbjbkq' -> 'CONSOLIDATED STATEMENT'."""
    return "".join(chr(ord(c) - SHIFT) if 0x3d <= ord(c) <= 0x7a else c for c in t)


def heading_kind(lines):
    """(kind, line) for the first statement heading among the given lines."""
    lines = [u for t in lines for u in ((t, unshift_up(t)) if t.count("=") >= 2 else (t,))]
    lines = [re.sub(r"^\d{1,4}\s+(?=[A-Za-z])", "", t) for t in lines]  # "278 STANDALONE STATEMENT OF..."
    # headings broken over two lines: "CONSOLIDATED STATEMENT OF" / "PROFIT AND LOSS"
    joined = [a + " " + b for a, b in zip(lines, lines[1:])
              if len(a) < 45 and re.search(r"\b(of|and|&|statement)$", a.strip(), re.I)]
    for t in lines + joined:
        if len(t) > 140 or "|" in t:
            continue  # "Balance Sheet | Statement of Profit and Loss" is a breadcrumb, not a heading
        if re.search(r"balance\s+sheet\s*(&|and)\s*(statements?\s+of\s+)?profit", t, re.I):
            continue  # section title "Balance Sheet & Profit and Loss Account"
        for kind, rx in HEADING_RE.items():
            m = rx.search(t)
            # what follows the heading must be a date phrase / bracket / nothing,
            # not a sentence ("Statement of cash flows comprises ...")
            if m and not re.match(r"\s*[a-z]+", t[m.end():]) or \
                    m and re.match(r"\s*(for|as|at|on|contd|continued|the\s+(year|period))\b", t[m.end():], re.I):
                return kind, t
        # letter-spaced headings: "S TA N D A L O N E B A L A N C E S H E E T"
        toks = t.split()
        if len(toks) >= 6 and sum(len(x) <= 2 for x in toks) >= len(toks) * 0.6:
            compact = re.sub(r"\s+", "", t).lower()
            for kind, rx in COMPACT_HEADING_RE.items():
                if rx.search(compact):
                    return kind, compact
    return None, None


def multi_year_summary(lines):
    """True for highlight tables with many year columns (statements show 2-3 years)."""
    years = set()
    for t in lines[:15]:
        if DATE_LINE_RE.search(t) and len(YEAR_RE.findall(t)) <= 2:
            continue
        years.update(re.findall(r"\b(?:FY\s?)?((?:19|20)\d{2})(?:-\d{2})?\b", t))
    return len(years) >= 4


def numeric_count(words):
    return sum(1 for w in words if NUM_RE.match(w[4]) and len(w[4]) >= 3)


def locate_statements(doc):
    """
    Returns {("consolidated"|"standalone", kind): [vpage, ...]}.
    A statement starts at a page whose top has the heading and whose body has
    statement-specific words and lots of numbers; continuation pages follow.
    """
    vps = virtual_pages(doc)
    cache = {}

    def info(k):
        if k not in cache:
            words = vp_words(doc, vps[k])
            lines = top_lines(words, vps[k][1])
            cache[k] = (words, lines, heading_kind(lines))
        return cache[k]

    def follow(i, kind):
        """Statement start page + its continuation pages (cash flow often runs over 2)."""
        pages = [vps[i]]
        for j in range(i + 1, min(i + 4, len(vps))):
            nwords, nlines, (nkind, _) = info(j)
            if (nkind and nkind != kind) or any(SOCE_RE.search(t) or STOP_RE.search(t) for t in nlines[:6]):
                break
            if numeric_count(nwords) < 15:
                break
            prev_text = " ".join(w[4] for w in info(j - 1)[0])
            if FOOTER_RE.search(prev_text) and nkind != kind:
                break  # previous page already ended with the signature block
            if nkind is None and any(sig_kind(j, with_next=False) == k for k in KINDS if k != kind):
                break  # next statement starts here (heading not in text)
            pages.append(vps[j])
        return pages

    def sig_kind(k, with_next=True):
        # a statement's tell-tale lines can be spread over its two pages
        nxt = info(k + 1)[0] if with_next and k + 1 < len(vps) else []
        body = norm_text(" ".join(w[4] for w in list(info(k)[0]) + list(nxt)))
        if numeric_count(info(k)[0]) < 25:
            return None
        # Real balance sheets / P&Ls have a "Note" column; MD&A summary tables don't.
        # (Cash flow statements usually have no Note column, but do have "Adjustments for".)
        has_note = any(re.search(r"\bnotes?\b", t, re.I) for t in info(k)[1])
        own = norm_text(" ".join(w[4] for w in info(k)[0]))
        for kind, sigs in SIGNATURE_RE.items():
            # the first tell-tale line must be on this page itself, the rest may follow on the next
            if sigs[0].search(own) and all(s.search(body) for s in sigs) and (has_note or kind == "cf"):
                return kind
        return None

    found = {}
    cands = {}  # (scope, kind) -> [vpage index, ...]
    raw = []    # (vpage index, kind, scope or None when the heading doesn't say)
    for i in range(len(vps)):
        words, lines, (kind, head) = info(i)
        if not kind:
            continue
        top = " ".join(lines)
        weak = None
        if re.search(r"consolidated", head, re.I):
            scope = "consolidated"
        elif re.search(r"standalone|standlone", head, re.I):
            scope = "standalone"
        else:
            scope = None
            # "consolidated" in a page header is only a weak hint: navigation bands
            # list every section, and the header may sit on the other half of a spread
            sheet_top = top + " " + " ".join(t for k in (i - 1, i + 1)
                                             if 0 <= k < len(vps) and vps[k][0] == vps[i][0]
                                             for t in info(k)[1][:5])
            if re.search(r"consolidated", sheet_top, re.I):
                weak = "consolidated"
        # the statement's tell-tale lines ("Total assets") may only appear on its next page
        nxt = info(i + 1)[0] if i + 1 < len(vps) else []
        body = norm_text(" ".join(w[4] for w in list(words) + list(nxt)))
        if not BODY_RE[kind].search(body) or numeric_count(words) < 20:
            continue
        if multi_year_summary(lines):
            continue  # "10-year financial highlights" pages are not the statement
        if any(re.search(r"notes\s+(to|forming)", t, re.I) for t in lines[:4]):
            continue  # a "Notes to the financial statements" page mentioning a statement
        if re.search(r"review\s+of\s+subsidiar|financial\s+(position|highlights)\s*[–-]", top, re.I):
            continue  # a subsidiary's statements reproduced in the report / highlight pages
        raw.append((i, kind, scope, weak))

    # Headings without "standalone"/"consolidated": decide by proximity to the labeled
    # ones. Some reports label only the consolidated set (standalone = plain "Balance
    # Sheet"), some only the standalone set; standalone usually comes first.
    anchor = {s: [i for i, _, sc, _ in raw if sc == s] for s in ("standalone", "consolidated")}
    for i, kind, scope, weak in raw:
        if scope is None and weak and not anchor["standalone"] and not anchor["consolidated"]:
            scope = weak
        if scope is None:
            sa, ca = anchor["standalone"], anchor["consolidated"]
            ds = min((abs(i - a) for a in sa), default=None)
            dc = min((abs(i - a) for a in ca), default=None)
            if ds is not None and dc is not None:
                scope = "standalone" if ds <= dc else "consolidated"
            elif dc is not None:
                scope = "consolidated" if dc <= 4 else "standalone"
            elif ds is not None:
                scope = "standalone" if ds <= 4 or i < min(sa) else "consolidated"
            else:
                first = min(j for j, k, s, _ in raw if k == kind and s is None)
                scope = "standalone" if i - first <= 3 else "consolidated"
        cands.setdefault((scope, kind), []).append(i)

    # The three statements of one scope sit together (BS, P&L, cash flow within a few
    # pages). Highlights pages and MD&A tables elsewhere can carry the same headings,
    # so pick the candidates that cluster together, not simply the first match.
    # A heading repeated on the next page ("Balance Sheet (contd.)") is a continuation,
    # not a new candidate.
    for key, c in cands.items():
        cands[key] = [x for x in c if not any(0 < x - y <= 2 for y in c)]
    for scope in ("standalone", "consolidated"):
        bs, pl, cf = (cands.get((scope, k), []) for k in ("bs", "pl", "cf"))
        anchors = bs or pl or cf
        if not anchors:
            continue
        others = [c for c in (pl, cf) if c] if bs else [c for c in (cf,) if c]

        def spread(a):
            return sum(min(abs(x - a) for x in c) for c in others)

        # first tight cluster wins: a company's own statements precede any subsidiary's
        # statements reproduced later in the report
        tight = [a for a in sorted(anchors) if others and spread(a) <= 4 * len(others)]
        anchor = tight[0] if tight else min(anchors, key=lambda a: (spread(a), a))
        ra = cands.get((scope, "ra"), [])
        for kind, c in (("bs", bs), ("pl", pl), ("cf", cf), ("ra", ra)):
            if c:
                i = min(c, key=lambda x: (abs(x - anchor), x))
                found[(scope, kind)] = follow(i, kind)

    # Fallback: some PDFs draw the headings as images/curves, so there is no
    # heading text. Recognise statement pages by their content instead.
    # Standalone statements come before consolidated ones in Indian reports.
    used = {(vp[0], vp[1].x0) for pages in found.values() for vp in pages}
    for kind in SIGNATURE_RE:
        missing = [s for s in ("standalone", "consolidated") if (s, kind) not in found]
        if not missing:
            continue
        hits = []
        for i in range(len(vps)):
            if (vps[i][0], vps[i][1].x0) in used or sig_kind(i) != kind:
                continue
            if hits and i <= hits[-1][1]:
                continue  # continuation of the previous hit
            pages = follow(i, kind)
            hits.append((i, i + len(pages) - 1, pages))
        if not hits:
            continue
        def has_nci(h):
            return any(NCI_RE.search(" ".join(w[4] for w in info(k)[0])) for k in range(h[0], h[1] + 1))
        if len(hits) >= 2:
            assign = {"standalone": hits[0], "consolidated": hits[1]}
        else:
            assign = {"consolidated" if has_nci(hits[0]) else "standalone": hits[0]}
        for s in missing:
            if s in assign:
                found[(s, kind)] = assign[s][2]
    return found


# ── Number helpers ────────────────────────────────────────────────────────────
def to_num(s):
    s = s.strip().replace(",", "").rstrip("*")
    if s in NIL_TOKENS or not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


UNIT_EXTRA = [
    ("thousand", re.compile(r"000['’]?s?\s+omitted|\(\s*['‘’]?000['’]?s?\s*\)|in\s+thousands|\bin\s+['‘’]?000['’]?s?\b", re.I)),
    # "\S{1,2}" allows a rupee sign rendered as an odd glyph ("in I million")
    ("million", re.compile(r"(rupees|inr|₹|rs\.?|`)\s*(in\s+)?mil(lion)?s?\b|\bin\s+(\S{1,2}\s+)?mil(lion)?s?\b"
                           r"|millions?\s+of\s+(indian\s+)?rupees", re.I)),
    ("crore", re.compile(r"(rupees|inr)\s*(in\s+)?crores?|\bin\s+(\S{1,2}\s+)?crores?\b"
                         r"|\bcrores?\s+of\s+(indian\s+)?rupees|\(\s*cr\.?\s*\)", re.I)),
    ("lakh", re.compile(r"(rupees|inr)\s*(in\s+)?la(kh|c)s?|(?:^|\s)[`₹f]\s*la(kh|c)s\b|\bin\s+(\S{1,2}\s+)?la(kh|c)s?\b", re.I)),
]


def detect_unit(text):
    m = UNIT_RE.search(text)
    if not m:
        hits = [(mm.start(), unit) for unit, rx in UNIT_EXTRA for mm in [rx.search(text)] if mm]
        return min(hits)[1] if hits else None
    u = (m.group(1) or m.group(2)).lower()
    if u.startswith("crore"):
        return "crore"
    if u.startswith(("lakh", "lac")):
        return "lakh"
    if u.startswith("million"):
        return "million"
    if u.startswith("thousand") or u.endswith("000"):
        return "thousand"
    return None


# ── Page parsing ──────────────────────────────────────────────────────────────
def group_lines(words, tol=3.0):
    """Group words into visual lines by vertical centre."""
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines, cur, cur_y = [], [], None
    for w in words:
        yc = (w[1] + w[3]) / 2
        if cur and abs(yc - cur_y) > tol:
            lines.append(sorted(cur, key=lambda w: w[0]))
            cur = []
        if not cur:
            cur_y = yc
        cur.append(w)
    if cur:
        lines.append(sorted(cur, key=lambda w: w[0]))
    return lines


def cluster(xs, tol):
    """1-D clustering; returns list of (centre, count)."""
    out = []
    for x in sorted(xs):
        if out and x - out[-1][-1] <= tol:
            out[-1].append(x)
        else:
            out.append([x])
    return [(sum(c) / len(c), len(c)) for c in out]


def is_value_token(t):
    return (NUM_RE.match(t) and ("," in t or "." in t or len(t.strip("()-")) >= 3)) or t in NIL_TOKENS


def find_value_columns(lines, rect):
    """Right edges of the numeric columns (amounts are right-aligned)."""
    toks = [w for ln in lines for w in ln
            if is_value_token(w[4]) and w[4] not in NIL_TOKENS and not YEAR_RE.fullmatch(w[4])
            and not NOTE_RE.match(w[4]) and w[0] > rect.x0 + rect.width * 0.35]
    # right edges of column-header dates ("31/03/2025", "2024-25", "2025"): a column
    # sitting exactly under one is real even if it holds a single total on this page
    hints = [w[2] for ln in lines[:25] for w in ln
             if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-](19|20)\d{2}|(19|20)\d{2}(-\d{2})?", w[4])]
    cols, plain = [], []
    for c, cnt in cluster([w[2] for w in toks], 14):
        members = [w[4] for w in toks if abs(w[2] - c) <= 14]
        formatted = all(re.search(r"\d,\d{3}|\.\d{2}\)?$", t) for t in members)
        # sparse outer "total" columns hold only a few, but clearly formatted, amounts
        if cnt >= 4 or (cnt >= 2 and formatted) or any(abs(c - h) <= 8 for h in hints):
            cols.append(c)
            plain.append(all(re.fullmatch(r"\d{2,4}", t) for t in members))
    # A column of bare 2-4 digit integers next to formatted amount columns is a
    # "Page No." / note cross-reference column, not amounts
    if any(plain) and not all(plain):
        cols = [c for c, p in zip(cols, plain) if not p]
    # numbers inside long labels ("... refer note 12 ...") have words right after them; amounts don't
    def embedded(c):
        hits = tot = 0
        for ln in lines:
            for i, w in enumerate(ln):
                if abs(w[2] - c) <= 14 and w in toks:
                    tot += 1
                    nxt = ln[i + 1] if i + 1 < len(ln) else None
                    if nxt and re.search(r"[A-Za-z]{2}", nxt[4]) and nxt[0] - w[2] < 30:
                        hits += 1
        return tot and hits * 2 > tot
    return [c for c in cols if not embedded(c)]


def join_number_fragments(ln):
    """PDF kerning can split '14,969.40' into '14' + ',969.40' (or '(' + '1,234)'): re-join them."""
    out = []
    for w in ln:
        if out:
            p = out[-1]
            gap = w[0] - p[2]
            if gap < 4 and ((re.fullmatch(r"\(?-?\d{1,3}", p[4]) and re.match(r"[,.]\d", w[4]))
                            or (p[4] in ("(", "-") and re.match(r"\d", w[4]))):
                out[-1] = (p[0], min(p[1], w[1]), w[2], max(p[3], w[3]), p[4] + w[4]) + tuple(p[5:])
                continue
        out.append(w)
    return out


def is_page_furniture(ln, rect):
    """
    Running header / footer: a line in the top or bottom band of the page whose only
    number is a bare page number ("Company Overview ... Financial Statements 265",
    a lone "357" under the last row). Amounts in a statement carry separators.
    """
    yc = (ln[0][1] + ln[0][3]) / 2
    band = rect.height * 0.08
    if rect.y0 + band < yc < rect.y1 - band:
        return False
    nums = [w[4] for w in ln if NUM_RE.match(w[4])]
    return len(nums) == 1 and re.fullmatch(r"\d{1,4}", nums[0]) is not None


def page_lines(doc, vp):
    words = vp_words(doc, vp)
    lines = [join_number_fragments(ln) for ln in group_lines(words)]
    lines = [ln for ln in lines if not is_page_furniture(ln, vp[1])]
    # Cut signatures / footnote tables first so their columns don't confuse detection
    amounts_seen = 0
    for li, ln in enumerate(lines):
        lt = " ".join(w[4] for w in ln)
        if li > 3 and FOOTER_RE.search(lt):
            lines = lines[:li]
            break
        # a second "Particulars" header after the body has started = a new table (e.g. a
        # reconciliation of financing liabilities under the cash flow)
        if amounts_seen >= 8 and re.match(r"\s*particulars\b", lt, re.I):
            lines = lines[:li]
            break
        amounts_seen += sum(1 for w in ln if NUM_RE.match(w[4]) and ("," in w[4] or "." in w[4]))
    return words, lines


def parse_page(doc, vp, force_cols=None):
    rect = vp[1]
    words, lines = page_lines(doc, vp)
    if not words:
        return None
    cols = force_cols if force_cols is not None else find_value_columns(lines, rect)
    if not cols:
        return None
    first_col_left = min(cols) - 75  # widest amounts are ~70pt wide

    # Note-reference column: small ints/'2.1' sitting between labels and amounts
    note_xs = [(w[0] + w[2]) / 2 for ln in lines for w in ln
               if NOTE_RE.match(w[4]) and rect.x0 + rect.width * 0.3 < w[0] < min(cols) - 20]
    note_cols = [c for c, cnt in cluster(note_xs, 10) if cnt >= 3]

    def col_of(w):
        for ci, cx in enumerate(cols):
            if abs(w[2] - cx) <= 14:
                return ci
        return None

    # Header (years) and body start: first line carrying ≥2 amounts
    body_start = None
    for li, ln in enumerate(lines):
        if DATE_LINE_RE.search(" ".join(w[4] for w in ln)):
            continue  # "...for the year ended 31 March 2021": the 31 is not an amount
        if sum(1 for w in ln if col_of(w) is not None and NUM_RE.match(w[4])
               and not YEAR_RE.fullmatch(w[4])) >= 1 and \
           any(not NUM_RE.match(w[4]) for w in ln):
            body_start = li
            break
    if body_start is None:
        return None

    # Year for each column from header lines above the body
    years = [None] * len(cols)
    # nearest header line first; skip page titles like "Integrated Annual Report 2019-20"
    for ln in reversed(lines[max(0, body_start - 8):body_start]):
        lt = " ".join(w[4] for w in ln)
        if re.search(r"annual\s+report|integrated|limited", lt, re.I):
            continue
        if re.search(r"balance\s+sheet|profit\s+(and|&)\s+loss|cash\s+flow|statement\s+of", lt, re.I):
            continue  # title "... for the year ended March 31, 2020": its year is not a column header
        for wi, w in enumerate(ln):
            # "Current Year" / "Previous Year" headers: placeholders -1 / -2 (current, previous)
            if w[4].lower() in ("current", "previous") and wi + 1 < len(ln) and \
                    ln[wi + 1][4].lower().startswith("year"):
                xc = ln[wi + 1][2]
                best = min(range(len(cols)), key=lambda c: abs(cols[c] - xc))
                if abs(cols[best] - xc) < 60 and years[best] is None:
                    years[best] = -1 if w[4].lower() == "current" else -2
                continue
            t = w[4].strip("=")
            if re.fullmatch(r"[J-V]{4,10}", t) and re.search(r"[M-V]{4}", t):
                # dates in a +29 shifted font: "OMOMJON" = "2020-21", "PNKMPKOMOQ" = "31.03.2024"
                t = "".join(chr(ord(c) - SHIFT) for c in t)
            m = re.search(r"((?:20|19)\d{2})(?:-(\d{2}))?", t)
            if not m:
                continue
            y = int(m.group(1)) + (1 if m.group(2) else 0)
            xc = w[2]
            best = min(range(len(cols)), key=lambda c: abs(cols[c] - xc))
            if abs(cols[best] - xc) < 60 and years[best] is None:
                years[best] = y

    # Period-end month per column ("31st December, 2022", "31/12/2022"): most Indian
    # companies close in March, but some (e.g. Nestlé until 2023) close in December
    month_marks = []
    for ln in lines[max(0, body_start - 8):body_start]:
        lt = " ".join(w[4] for w in ln)
        if re.search(r"balance\s+sheet|profit\s+(and|&)\s+loss|cash\s+flow|statement\s+of", lt, re.I):
            continue
        for w in ln:
            dm = re.fullmatch(r"\d{1,2}[/.-](\d{1,2})[/.-](?:19|20)\d{2}", w[4])
            mm = MONTHS.get(w[4].lower().strip(".,")[:3]) if not dm else int(dm.group(1))
            if mm and 1 <= mm <= 12:
                month_marks.append((w[2], mm))
    months = [None] * len(cols)
    for ci, cx in enumerate(cols):
        near = [(abs(x - cx), mm) for x, mm in month_marks if abs(x - cx) < 110]
        if near:
            months[ci] = min(near)[1]

    # Section headers just above the first amount line (e.g. "ASSETS",
    # "Non-current assets") belong to the body too.
    header_text = " ".join(w[4] for ln in lines[:body_start] for w in ln)
    start = body_start
    while start > 0:
        prev = lines[start - 1]
        txt = " ".join(w[4] for w in prev)
        if re.search(r"particulars|note|as at|year ended|crore|lakh|million|\d{4}", txt, re.I) \
                or HEADING_RE["bs"].search(txt) or HEADING_RE["pl"].search(txt) or HEADING_RE["cf"].search(txt):
            break
        start -= 1

    rows = []
    min_label_x = None
    for ln in lines[start:]:
        text = " ".join(w[4] for w in ln)
        if FOOTER_RE.search(text):
            break
        label_words, vals = [], [None] * len(cols)
        has_val = False
        for wi, w in enumerate(ln):
            ci = col_of(w)
            nxt = ln[wi + 1] if wi + 1 < len(ln) else None
            prv = ln[wi - 1] if wi else None
            if NUM_RE.match(w[4]) and (
                    # "(Refer note 14)", "₹ 404.03)", "(31 December": brackets that don't pair up
                    (w[4].rstrip("*").endswith(")") != w[4].startswith("("))
                    # "₹ 2,369.65 million)": a number followed by words is part of a sentence
                    or (nxt and nxt[0] - w[2] < 30 and re.search(r"[A-Za-z]{2}", nxt[4]))
                    # "... lease liabilities ₹ 30.50": amounts in a column carry no currency sign
                    or (prv and w[0] - prv[2] < 8 and re.fullmatch(r"[`₹]|rs\.?|inr", prv[4], re.I))):
                label_words.append(w)  # keep it as text of the label
                continue
            if ci is not None and (NUM_RE.match(w[4]) or w[4] in NIL_TOKENS):
                v = to_num(w[4])
                if vals[ci] is None:
                    vals[ci] = v
                has_val = True
                continue
            if w[2] > first_col_left and NUM_RE.match(w[4]):
                continue  # stray number in amount area
            if note_cols and NOTE_RE.match(w[4]) and \
                    any(abs((w[0] + w[2]) / 2 - nc) <= 12 for nc in note_cols):
                continue  # note reference
            if LEGACY_GLYPHS.search(w[4]):
                continue  # bilingual reports: Hindi in a legacy font extracts as Latin-1 garbage
            label_words.append(w)
        label = " ".join(w[4] for w in label_words).strip()
        if not label and not has_val:
            continue
        if label and re.fullmatch(r"[\d\s]+", label) and not has_val:
            continue  # page number
        x0 = label_words[0][0] if label_words else None
        if x0 is not None:
            min_label_x = x0 if min_label_x is None else min(min_label_x, x0)
        rows.append({"label": label, "x0": x0, "values": vals, "has_val": has_val})

    rows = merge_wrapped(rows)
    # Drop footers / page furniture after the last amount line
    while rows and not rows[-1]["has_val"]:
        rows.pop()
    for r in rows:
        r["level"] = 0 if r["x0"] is None or min_label_x is None else min(3, int((r["x0"] - min_label_x) // 8))
        r["is_header"] = not r["has_val"]
        r["label"] = clean_label(r["label"])
        if not r["label"] and r["has_val"]:
            r["label"] = "Subtotal"  # some reports print totals as bare numbers under a rule line
    rows = strip_heading_rows(rows)
    rows = [r for r in rows if r["label"]
            # page header "Integrated Annual Report 2023-24 | 471" (its page number read as an amount),
            # also with doubled text: "Maruti Maruti Suzuki Suzuki ... Annual Annual Integrated Integ..."
            and not re.search(r"\bannual\b.*\b(report|integrated)|\bintegrated\b.*\breport\b", r["label"], re.I)
            # column-header lines read as rows: "Particulars Year ended 31st March, 2024 ..." (its
            # year read as an amount), page bands "Consolidated Consolidated Consolidated" (CERA)
            and not re.match(r"particulars\b", r["label"], re.I)
            and not re.fullmatch(r"(\w+)(\s+\1){2,}", r["label"], re.I)
            and not re.fullmatch(r"(consolidated|standalone)?\s*financial\s+statements", r["label"], re.I)
            and not (r["is_header"] and JUNK_HEADER_RE.fullmatch(r["label"]))]

    return {
        "unit": detect_unit(" ".join(w[4] for w in words)),
        "cols": cols,
        "years": years,  # raw: one entry per column, None where no header was read
        "months": months,  # period-end month per column when the header says (else None)
        "rows": rows,
        "header_text": header_text,
    }


# Column-header lines kept as rows: "Schedule No. (Current Year) (Previous Year)",
# "As at 31.03.2025 As at 31.03.2024", "(000s omitted)", "Year ended Year ended", "J J"
COLUMN_HEAD_WORDS = {"as", "at", "year", "years", "ended", "ending", "schedule", "schedules", "no", "nos", "current",
                     "previous", "particulars", "note", "notes", "in", "rs", "inr", "crore", "crores", "lakh", "lakhs",
                     "lacs", "million", "millions", "thousand", "thousands", "000", "000s", "omitted", "for", "the",
                     "period", "months", "month", "audited", "unaudited", "amount", "amounts", "rupees", "of", "on",
                     "st", "nd", "rd", "th", "s", "ref", "refer", "restated", "to", "and", "all", "are", "otherwise", "unless", "stated"}
TITLE_RE = re.compile(r"(profit\s+(and|&)\s+loss|balance\s+sheet|cash\s+flows?|revenue\s+account|income\s+statement)"
                      r".*\b(year|period|ended|as\s+at|for\s+the)\b", re.I)


def is_column_header(label):
    toks = re.findall(r"[A-Za-z]+|\d+", label.lower())
    rest = [t for t in toks if t not in COLUMN_HEAD_WORDS and t not in MONTHS
            and not (t[:3] in MONTHS and len(t) <= 9) and not t.isdigit()]
    return bool(toks) and not rest


def is_symbol_row(label):
    """'J J', 'K K', '` `', '₹ ₹': currency marks over the columns."""
    return bool(label) and re.fullmatch(r"(?:[`₹HJDK]|rs\.?)(?:\s+(?:[`₹HJDK]|rs\.?))*", label.strip(), re.I) is not None


def strip_heading_rows(rows):
    """
    Drop page headings kept as rows: company name and statement title above the
    first line item, column-header lines and currency-mark rows anywhere.
    """
    first_val = next((i for i, r in enumerate(rows) if r["has_val"]), len(rows))
    title = max((i for i in range(first_val) if TITLE_RE.search(rows[i]["label"])
                 or any(rx.search(rows[i]["label"]) for rx in HEADING_RE.values())), default=-1)
    out = []
    for i, r in enumerate(rows):
        if i <= title:
            continue  # company name, "Consolidated Profit and Loss Account for the year ended ..."
        if not r["has_val"] and (is_column_header(r["label"]) or is_symbol_row(r["label"])):
            continue
        out.append(r)
    return out


def resolve_columns(part, prev=None):
    """
    Give every column a year, then collapse columns of the same year into one.
    - Continuation pages without headers inherit years from the previous page
      of the statement by column position (pages share a layout).
    - Indented layouts put sub-items in an inner column left of the year's total
      column: an un-headed column belongs to the next headed one on its right.
    """
    cols, years = part["cols"], list(part["years"])
    if not any(years) and prev:
        for ci, cx in enumerate(cols):
            near = min(range(len(prev["cols"])), key=lambda j: abs(prev["cols"][j] - cx))
            if abs(prev["cols"][near] - cx) <= 25:
                years[ci] = prev["col_years"][near]
    if any(years) and None in years:
        # Evidence first: a line has at most one figure per year, so an un-headed column
        # belongs to the year whose columns it never shares a row with.
        headed = [(ci, y) for ci, y in enumerate(years) if y is not None]
        rows_v = [r["values"] for r in part["rows"]]
        for ci in range(len(years)):
            if years[ci] is not None:
                continue
            cooc = {}
            for _, y in headed:
                cols_y = [cj for cj, yy in headed if yy == y]
                cooc[y] = sum(1 for v in rows_v if v[ci] is not None and any(v[cj] is not None for cj in cols_y))
            if len(set(cooc.values())) > 1:
                best = min(cooc.values())
                winners = [y for y, n in cooc.items() if n == best]
                if len(winners) == 1 and best <= max(1, 0.1 * max(cooc.values())):
                    years[ci] = winners[0]
    known = []
    for y in years:
        if y is not None and y not in known:
            known.append(y)
    if None in years and len(known) >= 2 and len(cols) % len(known) == 0:
        # e.g. 4 columns, 2 years: each year owns a contiguous block (inner + outer),
        # whether its header sits over the inner column, the outer one, or between
        size = len(cols) // len(known)
        blocks = [known[ci // size] for ci in range(len(cols))]
        if all(y is None or y == b for y, b in zip(years, blocks)):  # must agree with what's known
            years = blocks
    if any(years) and None in years:
        for ci in range(len(years)):
            if years[ci] is None:
                right = [y for y in years[ci + 1:] if y is not None]
                left = [y for y in years[:ci] if y is not None]
                years[ci] = right[0] if right else left[-1]
    elif not any(years):
        if len(cols) > 2:
            # Last resort: split into current/previous blocks at the widest gap
            gaps = [cols[i + 1] - cols[i] for i in range(len(cols) - 1)]
            cut = gaps.index(max(gaps)) + 1
            years = [-1] * cut + [-2] * (len(cols) - cut)
        else:
            years = [-1 - i for i in range(len(cols))]  # positional: current, previous
    part["col_years"] = years
    uniq = sorted(set(years), reverse=True)
    raw_months = part.get("months") or [None] * len(years)
    part["year_months"] = {}
    for y, mm in zip(years, raw_months):
        if y and y > 0 and mm and y not in part["year_months"]:
            part["year_months"][y] = mm
    for r in part["rows"]:
        merged = [None] * len(uniq)
        for v, y in zip(r["values"], years):
            k = uniq.index(y)
            if merged[k] is None:
                merged[k] = v
        r["values"] = merged
    part["years"] = [y if y > 0 else None for y in uniq]  # placeholders -> unknown (positional)
    part["ncols"] = len(uniq)
    return part


def merge_wrapped(rows):
    """Join labels that wrapped onto two lines."""
    out = []
    for r in rows:
        if out:
            p = out[-1]
            plab = strip_note_refs(p["label"])  # test the wording without "... Through Other 14.3"
            cont = (r["label"][:1].islower() or r["label"][:1] == "&") and not ENUM_RE.match(r["label"])
            # values on this line, label started on the previous line
            heading_list = re.search(r"attributable\s+to\s*:?$|:$", plab, re.I)
            if not p["has_val"] and r["has_val"] and p["label"] and not heading_list and \
                    (cont or re.match(r"\((refer|see|net|including|excluding|of|on|in|for)\b", r["label"], re.I)
                     or re.search(r"\b(and|of|for|on|in|to|through|other|than|or|by|from|with|&)$|[,/-]$", plab)):
                r = dict(r, label=p["label"] + " " + r["label"], x0=p["x0"])
                out[-1] = r
                continue
            # label continues on a line without values (incl. an unclosed bracket:
            # "Interest paid (inclusive of ... ₹ 509.22" / "(31 December 2024: ₹ 404.03))")
            unclosed = p["label"].count("(") > p["label"].count(")") and not re.match(r"notes?\b", r["label"], re.I)
            # "(before adjustment for ...)" under "Net Profit for the year"; a slash list
            # cut in the middle: "... Subsidiaries / Joint" + "Ventures / Associates"
            paren = re.match(r"\((?!\s*[ivxIVX]+\))[a-z]", r["label"]) is not None
            slash = re.search(r"/\s*[A-Za-z]+$", plab) and re.match(r"[A-Za-z]+\s*/", r["label"])
            if p["has_val"] and not r["has_val"] and r["label"] and \
                    (cont or unclosed or paren or slash
                     or re.search(r"\b(and|of|&|for|on|in|to|than|or|by|from|with|other|through)$|[,/]$", plab)
                     or (len(plab.split()) >= 3 and re.search(r"\s(other|through)$", plab, re.I))):
                p["label"] += " " + r["label"]
                continue
            # line holding only values (label wrapped above)
            if not r["label"] and r["has_val"] and not p["has_val"]:
                p["values"], p["has_val"] = r["values"], True
                continue
        out.append(r)
    return out


LEGACY_GLYPHS = re.compile(r"[\u0080-ßà-èê-ɏ]")  # keeps é (Nestlé)

# Column-header leftovers: shifted years "OMOQJOR OMOPJOQ", "(Restated)**", "2024-25"
JUNK_HEADER_RE = re.compile(r"(([M-V]{4}(J[M-V]{2})?|(19|20)\d{2}(-\d{2})?|\(restated\)\**|restated)\s*)+", re.I)


# Bare roman numerals / serials, including ones mangled by shifted fonts (",9" = "IV")
LEAD_RE = re.compile(r"^(?:[IVX]{1,4}|[ivx]{1,4}|\d{1,2}[A-Z]?|[,$%&^]\S{0,2}|[A-Z]\^[A-Z])\s+(?=[A-Z(])")


def rupee_glyphs(label):
    """
    The rupee sign drawn in a symbol font extracts as "`", "J", "H", "D" or "K":
    "Basic (in H)", "Face value J 1 per share", "(in `)". Put the ₹ back.
    """
    label = re.sub(r"\(\s*in\s+[`HJDKC]\s*\)", "(in ₹)", label)
    # "Basic (C)", "Basic and Diluted earnings per share (I)": a bare letter in brackets on an EPS line
    if re.search(r"per\s+(equity\s+)?share|^(basic|diluted)\b|\beps\b", label, re.I):
        label = re.sub(r"\(\s*[`HJDKCI]\s*\)", "(₹)", label)
    # "Face value J 1", "(of I 5 each)", "per share C 1)", "face value of H2/- each"
    label = re.sub(r"(?<![A-Za-z])[`HJDKCI]\s?(?=\d+(\.\d+)?(/-)?(\s+(per|each)\b|\s*\)|\s+each|$|\s*/-))", "₹ ", label)
    return label.replace("`", "₹")


def unshift_lower_caps(label):
    """Capitals in a +29-shifted font stored as lowercase: "TOTAL bnrfqv AND LIABILITIES" (= EQUITY)."""
    import quality
    vocab = quality.vocab()
    def fix(m):
        t = m.group(0)
        if t.lower() in vocab:
            return t
        u = "".join(chr(ord(c) - SHIFT) for c in t)
        return u if u.isalpha() and u.isupper() and u.lower() in vocab else t
    if not re.search(r"\b[A-Z]{3,}\b", label):
        return label  # only inside all-caps labels
    return re.sub(r"\b[a-z]{3,}\b", fix, label)


def clean_label(label):
    label = re.sub(r"\s+", " ", norm_text(label)).strip(" :-–")
    label = rupee_glyphs(label)
    label = unshift_lower_caps(label)
    # bilingual reports: Hindi in legacy fonts extracts as Latin-1 garbage ("ˆºÅ¥¸") - drop those words
    label = " ".join(t for t in label.split() if sum(ord(c) > 127 and c not in "₹é" for c in t) * 2 <= len(t))
    label = re.sub(r"\b(?:[A-Z] ){2,}[A-Z]\b", lambda m: m.group(0).replace(" ", ""), label)  # "T O T A L"
    label = re.sub(r"^((J[&=]|[&$•])\s*)+", "", label)  # bullet glyphs ("J&" = shifted "-")
    label = re.sub(r"^[A-H]\s+(?=[A-Z]{4,}(\s+[A-Z&/()-]+)+$)", "", label)  # "B CASH FLOW FROM INVESTING ..."
    label = re.sub(r"^(total)\s*[–-]\s*", r"\1 ", label, flags=re.I)  # "TOTAL – ASSETS"
    label = re.sub(r"^\(?[IVX]{1,5}[.)]\s*[&$]*\s*", "", label)  # decoded "XI.&" / "(I)&" serials
    label = re.sub(r"\)=\(", ") (", label)  # shifted space between serials: "(A)=(i) Items ..."
    # formula references "(G= D+E+F)", "(D = A+B+C)" (sometimes in an undecodable font: "(' $+%+&)")
    label = re.sub(r"\s*\((?=[^()a-z]*[=+])[^()a-z]{1,20}\)", "", label)
    prev = None
    while prev != label:
        prev = label
        label = ENUM_RE.sub("", label).strip()
        label = LEAD_RE.sub("", label).strip()
    label = strip_note_refs(label)
    return re.sub(r"\s+(\d{1,2}\.\d{1,2}(\([a-z]\))?|\d{1,2}[A-Z])$", "", label)  # trailing note ref "3.27", "22A"


_REF = r"\d{1,3}(?:\.\d{1,2}){0,2}(?:\([a-z]\)|[a-zA-Z])?"
NOTE_TAIL_RE = re.compile(rf"(?<![₹/])\s*[:]?\s+{_REF}(?:\s*(?:,|&|and|-|–)\s*{_REF})*(?:\s*(?:,|and|&))?$")
KEEP_NUMBER_BEFORE = re.compile(r"(\bas|section|sec\.?|rule|schedule|₹|rs\.?|value|of|notes?|year|fy|level|tier|phase"
                                r"|series|ind|regulation|article|clause|act|chapter|part|item|unit|days?|months?|ii?i?)$", re.I)


def strip_note_refs(label):
    """
    Note / page references the column split left in the label: "Goodwill 2.4.1 and",
    "Property, plant and equipment 457-459", "Deferred Tax Assets (Net) 17.1&17.2",
    "Earnings per equity share: 38", "Changes in inventories of finished goods, 476-477 work-in-progress".
    Numbers that belong to the name ("Ind AS 116", "Face value ₹ 1", "Section 135") stay.
    """
    m = NOTE_TAIL_RE.search(label)
    if m and m.start() > 0:
        head = label[:m.start()].rstrip()
        tail = label[m.start():]
        if head and re.search(r"[A-Za-z)]$", head) and not KEEP_NUMBER_BEFORE.search(head) \
                and (re.search(r"\d\.\d|\d\s*[-–,&]|\band$|:", tail) or re.search(r"\d{3}$", tail)
                     or re.search(r"\s\d{1,2}(\([a-z]\))?$", tail)):
            label = head
    label = re.sub(r"(?<=[a-z,])\s+\d{3}\s*[-–]\s*\d{3}(?=\s+[a-z])", "", label)  # page range mid-label
    return re.sub(r"\s+\d{1,2}\.\d{1,2}\.\d{1,2}(?=\s)", "", label)  # "2.4.1" anywhere


def parse_statement(doc, pages):
    """Parse all pages of one statement and stitch them together (aligned by year)."""
    # Columns are detected over all pages of the statement together: a sparse
    # outer "total" column may hold just one number on a given page.
    page_cols = [find_value_columns(page_lines(doc, p)[1], p[1]) for p in pages]
    parts, prev = [], None
    for p, own in zip(pages, page_cols):
        cols = list(own)
        for other, q in zip(page_cols, pages):
            if q is p or q[1].x0 != p[1].x0 or not own or not other:
                continue  # other half of a spread has different x positions
            # odd/even pages have different margins: find the shift that best aligns them
            best_d, best_n = 0.0, 0
            for d in {a - b for a in own for b in other}:
                n = sum(1 for b in other if any(abs(b + d - a) <= 6 for a in own))
                if n > best_n or (n == best_n and abs(d) < abs(best_d)):
                    best_d, best_n = d, n
            if best_n < min(2, len(other)):
                continue
            for c in other:
                if all(abs(c + best_d - x) > 14 for x in cols):
                    cols.append(c + best_d)
        part = parse_page(doc, p, sorted(cols) if cols else None)
        if part:
            prev = resolve_columns(part, prev)
            first = parts[0]["years"][0] if parts and parts[0]["years"] and parts[0]["years"][0] else None
            if first and any(part["years"]) and first not in part["years"]:
                continue  # continuation page holding a different table (e.g. prior-year cash breakup)
            parts.append(part)
    unit = next((p["unit"] for p in parts if p["unit"]), None)
    known = sorted({y for p in parts for y in p["years"] if y}, reverse=True)
    ncols = len(known) or max((p["ncols"] for p in parts), default=0)
    rows = []
    for p in parts:
        for r in p["rows"]:
            if known and all(p["years"]):
                vals = [None] * ncols
                for v, y in zip(r["values"], p["years"]):
                    vals[known.index(y)] = v
            else:
                vals = (r["values"] + [None] * ncols)[:ncols]
            r["values"] = vals
            rows.append(r)
    months = {}
    for p in parts:
        for y, mm in p.get("year_months", {}).items():
            months.setdefault(y, mm)
    return {"unit": unit, "years": known, "ncols": ncols, "rows": rows, "months": months}


# ── Quality checks ────────────────────────────────────────────────────────────
def find_row(rows, pattern):
    rx = re.compile(pattern, re.I)
    for r in rows:
        if rx.search(r["label"]) and r["values"] and r["values"][0] is not None:
            return r
    return None


def validate(kind, parsed):
    """Returns (ok, message). Used to decide whether to call the AI fallback."""
    rows = [r for r in parsed["rows"] if not r["is_header"]]
    if parsed["ncols"] == 0 or len(rows) < 8:
        return False, f"only {len(rows)} value rows parsed"
    missing = sum(1 for r in rows if r["values"][0] is None)
    if missing > len(rows) * 0.3:
        return False, f"{missing} of {len(rows)} rows have no current-year value (unreadable font?)"
    if kind == "bs":
        rx_a = re.compile(r"^total\s+assets|^total\s+application\s+of\s+funds", re.I)
        rx_e = re.compile(r"^total\s+(equity\s+(and|&)\s+liab\w*|liab\w*\s+(and|&)\s+equity"
                          r"|capital\s+(and|&)\s+liabilities|sources\s+of\s+funds)", re.I)
        tas = [r["values"][0] for r in rows if rx_a.search(r["label"]) and r["values"][0] is not None]
        tes = [r["values"][0] for r in rows if rx_e.search(r["label"]) and r["values"][0] is not None]
        if not tas or not tes:
            return False, "could not find Total assets / Total equity and liabilities"
        # any tying pair: utilities print "Total assets before regulatory deferral" first
        if not any(abs(a - b) <= max(1.0, abs(a) * 0.005) for a in tas for b in tes):
            return False, f"balance sheet does not tie ({tas[-1]:,.2f} vs {tes[-1]:,.2f})"
        return True, "balance sheet ties"
    if kind == "pl":
        if not find_row(rows, r"revenue\s+from\s+operations|total\s+income|interest\s+earned"
                              r"|transferred\s+from.*(policyholders|revenue\s+account)|income\s+from\s+investments"
                              r"|operating\s+profit|interest,\s+dividend"):
            return False, "revenue row not found"
        if not find_row(rows, r"(profit|loss).*\b(year|period)\b|net\s+(profit|loss)"
                              r"|(profit|loss)\s*(/\s*\(?(loss|profit)\)?\s*)?after\s+tax"):
            return False, "net profit row not found"
        return True, "revenue and profit rows found"
    if kind == "cf":
        if not find_row(rows, r"net\s+cash.*operat(ing|ions)|cash\s+generated\s+from\s*/\s*\(used\s+in\)\s+operations"):
            return False, "operating cash flow row not found"
        return True, "operating cash flow row found"
    if kind == "ra":
        if not find_row(rows, r"premium"):
            return False, "premium row not found"
        return True, "premium rows found"
    return True, ""


def name_bank_totals(kind, parsed):
    """
    Bank/insurer formats print bare "Total" lines. Name them so they can be
    checked and lined up: BS -> "Total capital and liabilities" / "Total assets",
    P&L -> "Total income" / "Total expenditure".
    """
    if kind == "bs" and not any(re.match(r"total\s+assets", r["label"], re.I) for r in parsed["rows"]):
        # unlabelled totals: the largest figure printed twice is assets = equity + liabilities
        subs = [r for r in parsed["rows"] if r["label"] == "Subtotal" and r["values"] and r["values"][0]]
        counts = {}
        for r in subs:
            counts[r["values"][0]] = counts.get(r["values"][0], 0) + 1
        twice = [v for v, n in counts.items() if n >= 2]
        if twice:
            top = max(twice)
            hits = [r for r in subs if r["values"][0] == top]
            hits[0]["label"], hits[1]["label"] = "Total assets", "Total equity and liabilities"
    names = {"bs": {"capital and liabilities": "Total capital and liabilities", "assets": "Total assets",
                    "liabilities and equity": "Total liabilities and equity",
                    "equity and liabilities": "Total equity and liabilities",
                    "sources of funds": "Total sources of funds", "application of funds": "Total application of funds"},
             "pl": {"income": "Total income", "expenditure": "Total expenditure"}}.get(kind)
    if not names:
        return parsed
    section = None
    for r in parsed["rows"]:
        low = re.sub(r"\s*&\s*", " and ", r["label"].lower())
        if r["is_header"]:
            for key in names:
                if re.fullmatch(rf"{key}", low):
                    section = key
        elif low == "total" and section:
            r["label"] = names[section]
            section = None
    if kind == "bs":
        # a bare "TOTAL" equal to Total assets is the liabilities side (its header sat above the table)
        ta = next((r for r in parsed["rows"] if r["label"].lower() == "total assets" and r["values"][0]), None)
        for r in parsed["rows"]:
            if ta and r["label"].lower() == "total" and r["values"][0] == ta["values"][0]:
                r["label"] = "Total capital and liabilities"
    return parsed


def statement_text(doc, pages):
    """Plain line-by-line text of the statement pages, for the AI fallback."""
    out = []
    for p in pages:
        for ln in group_lines(vp_words(doc, p)):
            out.append("  ".join(w[4] for w in ln))
        out.append("---- page break ----")
    return "\n".join(out)
