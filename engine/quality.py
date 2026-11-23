"""
quality.py
----------
Checks that make the extracted data prove itself, the way an analyst ticks a
printed statement:

1. Arithmetic ("footing"): every total must equal the lines it adds up, every
   profit line must follow from the one before it, closing cash = opening cash +
   net change. A number that is part of a total that adds up is *confirmed by the
   report itself*.
2. Labels: every line-item name must be made of real words (no "OVKRSFF").

check_statement(kind, parsed) adds to every row:
    "status": per value column, "ok" (confirmed) / "fail" (a total that doesn't
              add up) / None (not covered by any check, e.g. EPS)
    "label_ok": False if the name looks garbled
and sets parsed["quality"] = summary counts.
"""

import itertools
import os
import re

# Totals that must equal the sum of the lines above them
SUM_TARGET = re.compile(r"^(sub-?\s*total|total)\b", re.I)
CF_TARGET = re.compile(r"^(net\s+cash\b.*\b(activities|operations)\b|cash\s+generated|operating\s+(profit|cash\s+flows?)\s+before"
                       r"|net\s+(increase|decrease|change|\(decrease\)|\(increase\)).*\bcash\b"
                       r"|cash\s+and\s+cash\s+equivalents\s+(at|as\s+at)\s+the\s+(end|close))", re.I)
# Profit lines: follow from the previous profit/total line plus/minus the items in between
PL_TARGET = re.compile(r"^(net\s+)?(\(?profit\)?|\(?loss\)?)[\s/()a-z]*?\b(before|for|after)\b"
                       r"|^total\s+comprehensive|^other\s+comprehensive\s+income.*(net\s+of\s+tax|for\s+the\s+(year|period))",
                       re.I)
PL_NOT_TARGET = re.compile(r"share\s+of|on\s+sale|attributable|per\s+(equity\s+)?share|from\s+discontinued", re.I)
# "Total outstanding dues of micro enterprises ..." are line items under Trade payables
NOT_TOTAL = re.compile(r"^total\s+ou?tst?anding\s+dues", re.I)  # also the "oustanding" typo (VINATIORGA)
# "Profit attributable to: Owners / Non-controlling interest" - the split adds up to the line above
SPLIT_RE = re.compile(r"owners|equity\s+holders|shareholders\s+of|non[\s-]*controlling|minority", re.I)

MAX_SUM_ITEMS = 40   # lines a total can add up
MAX_SIGNED_ITEMS = 10  # items between two profit lines, e.g. an OCI block (2^9 sign combinations)


def _is_target(kind, label):
    if NOT_TOTAL.search(label):
        return None
    if label == "Subtotal":  # a bare number under a rule line: a sum, or a profit line
        return "either"
    if SUM_TARGET.search(label):
        return "sum"
    if kind == "cf" and CF_TARGET.search(label):
        return "sum"
    if kind in ("pl", "ra") and PL_TARGET.search(label) and not PL_NOT_TARGET.search(label):
        return "signed"
    return None


def _tolerance(n, integer, exact=False):
    """
    Printed figures are rounded, so a printed total can differ from the sum of its
    printed lines by a unit or two. exact=True for the pattern-based guesses
    (unlabelled subtotals, parent lines), where loose matching finds coincidences.
    """
    unit = 1.0 if integer else 0.01
    return unit * (0.5 if exact else 1.05 + 0.1 * n)


def _foot_column(kind, rows, c, integer):
    """
    Footing for one year column. Returns ({row index: "ok"/"fail"}, {row index: group}).
    A group says what a total was checked against: {"ok": bool, "members": [[row index, sign], ...]}.
    For a total that doesn't add up, "members" are the lines it could have covered (its section).
    The pattern-based guesses (unlabelled subtotals, parent lines) can match by
    coincidence among small figures (3 + 1 = 4) and then hide the real structure,
    so the column is footed with and without them and the better result is kept.
    """
    def score(res):
        vals = list(res[0].values())
        return (vals.count("fail"), -vals.count("ok"))
    return min((_foot(kind, rows, c, integer, h) for h in (True, False)), key=score)


def _foot(kind, rows, c, integer, heuristics):
    status = {}
    groups = {}  # row index -> {"ok", "members": [[row, sign]]}: what each total was checked against
    items = []  # (value, [row indices it stands for], row shown for it) - confirmed totals replace their lines
    last_target = [-1]  # the previous total: a failed total's candidates are the lines since then

    def mark(idx):
        for i in idx:
            if status.get(i) != "fail":
                status[i] = "ok"

    def find_sum(v, min_len=1, exact=False):
        s, cov = 0.0, []
        for L in range(1, min(len(items), MAX_SUM_ITEMS) + 1):
            s += items[-L][0]
            cov.extend(items[-L][1])
            if L >= min_len and abs(s - v) <= _tolerance(L, integer, exact):
                return L, cov, [[it[2], 1] for it in items[-L:]]
        return None

    def find_signed(v):
        for L in range(1, min(len(items), MAX_SIGNED_ITEMS) + 1):
            tail = items[-L:]
            for signs in itertools.product((1, -1), repeat=L - 1):
                s = tail[0][0] + sum(sg * it[0] for sg, it in zip(signs, tail[1:]))
                if abs(s - v) <= _tolerance(L, integer):
                    return L, [i for it in tail for i in it[1]], [[tail[0][2], 1]] + [[it[2], sg] for sg, it in zip(signs, tail[1:])]
        return None

    def val(j):
        return rows[j]["values"][c] if c < len(rows[j]["values"]) else None

    recent = []  # values of the last profit / total lines (for the owners / NCI split)
    i = 0
    while i < len(rows):
        r = rows[i]
        v = val(i)
        if v is None:
            i += 1
            continue
        if kind in ("pl", "ra") and SPLIT_RE.search(r["label"]) and recent:
            j, s = i, 0.0
            while j < len(rows) and SPLIT_RE.search(rows[j]["label"]) and val(j) is not None:
                s += val(j)
                j += 1
            if j - i >= 2 and any(abs(s - t) <= _tolerance(j - i, integer) for t in recent[-4:]):
                mark(range(i, j))  # a split is a memo: it doesn't feed later totals
                i = j
                continue
        kind_t = _is_target(kind, r["label"])
        if kind_t:
            recent.append(v)
        hit = None
        if kind_t == "sum":
            hit = find_sum(v)
        elif kind_t == "signed":
            hit = find_signed(v)
        elif kind_t == "either":
            hit = find_sum(v) or find_signed(v)
        if kind_t and hit:
            L, cov, members = hit
            mark(cov + [i])
            groups[i] = {"ok": True, "members": members}
            items[-L:] = [(v, cov + [i], i)]
            last_target[0] = i
            i += 1
            continue
        if kind_t == "either":
            # repeats a recent total (e.g. the sum of an owners / NCI split)
            if any(abs(v - t) <= _tolerance(1, integer, True) for t in recent[-4:]):
                mark([i])
                i += 1
                continue
            items.append((v, [i], i))  # unlabelled: no evidence it should add up
            i += 1
            continue
        if kind_t:
            status[i] = "fail"
            since = [[it[2], 1] for it in items if it[2] > last_target[0]][-MAX_SUM_ITEMS:]
            groups[i] = {"ok": False, "members": since or [[it[2], 1] for it in items[-10:]],
                         "signed": kind_t != "sum"}
            items.append((v, [i], i))
            last_target[0] = i
            i += 1
            continue
        if not heuristics:
            items.append((v, [i], i))
            i += 1
            continue
        # An unlabelled subtotal: equals the sum of 2+ lines just above it
        # (e.g. "Equity attributable to owners", a bare number under a rule line)
        hit = find_sum(v, min_len=2, exact=True)
        if hit:
            L, cov, members = hit
            mark(cov + [i])
            groups[i] = {"ok": True, "members": members}
            items[-L:] = [(v, cov + [i], i)]
            i += 1
            continue
        # A parent line whose figure is the sum of the 2+ sub-lines printed below it
        j, s, kids = i + 1, 0.0, []
        while j < len(rows) and len(kids) < 12:
            vj = rows[j]["values"][c] if c < len(rows[j]["values"]) else None
            if vj is None or _is_target(kind, rows[j]["label"]):
                break
            s += vj
            kids.append(j)
            if len(kids) >= 2 and abs(s - v) <= _tolerance(len(kids), integer, True):
                break
            j += 1
        if len(kids) >= 2 and abs(s - v) <= _tolerance(len(kids), integer, True):
            mark([i] + kids)
            groups[i] = {"ok": True, "members": [[k, 1] for k in kids]}
            items.append((v, [i] + kids, i))
            i = kids[-1] + 1
            continue
        items.append((v, [i], i))
        i += 1
    return status, groups


# ── Labels ────────────────────────────────────────────────────────────────────
_VOCAB = None
VOCAB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "label_words.txt")
# decoding leftovers: "=J=", "Q^", "$Total", "K&"; a spaced "=" is a formula label "(C) = (A - B)"
GARBAGE_CHARS = re.compile(r"\S=\S|[\^_|~\\]|[A-Za-z][$&`][A-Za-z]|^[$&`]\w|[$%&]{2}")


def vocab():
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = set()
        if os.path.exists(VOCAB_FILE):
            with open(VOCAB_FILE, encoding="utf-8") as f:
                _VOCAB = {w.strip() for w in f if w.strip() and not w.startswith("#")}
    return _VOCAB


def prose_words(doc, skip_pages=()):
    """
    Words of the report's own text outside the statement pages (notes, directors'
    report). A misread statement font can't put its garbage there, so a word found
    here is real even if it's rare across companies (e.g. a product name).
    """
    words = set()
    for i, page in enumerate(doc):
        if i not in skip_pages:
            words.update(w.lower() for w in re.findall(r"[A-Za-z]{4,}", page.get_text()))
    return words


def label_ok(label, extra=()):
    """False if a line-item name looks garbled (decoding leftovers, misread words)."""
    if GARBAGE_CHARS.search(label):
        return False
    words = vocab()
    if not words:
        return True
    def known(t):
        t = t.lower()
        forms = {t, t[:-1] if t.endswith("s") else t, t[:-2] if t.endswith("es") else t,
                 t[:-3] + "y" if t.endswith("ies") else t}
        return any(f in words or f in extra for f in forms)
    unknown = [t for t in re.findall(r"[A-Za-z]{4,}", label) if not known(t)]
    if not extra:
        # no report text to compare with: only nonsense capitals ("OVKRSFF") are certain
        return not any(t.isupper() and len(t) >= 5 for t in unknown)
    return not unknown


SENTENCE_RE = re.compile(r"in\s+accordance\s+with|is\s+prepared|has\s+been\s+prepared|refer\s+note\s+\d+\s+for"
                         r"|figures\s+(for|of)\s+the\s+previous|regrouped|the\s+accompanying\s+notes", re.I)


def is_sentence(row):
    """
    Footnote sentences under a statement kept as blank rows (no amounts): long or
    policy-like text, "*1 Cash and cash equivalents ... includes", or an amount written
    inside the text ("... balances with banks ₹ 1,141,050 thousand").
    """
    lab = row["label"]
    return not any(v is not None for v in row["values"]) and \
        bool(SENTENCE_RE.search(lab) or len(lab.split()) >= 14 or re.match(r"\*+\d*\s", lab)
             or re.search(r"[a-z]\s+[`₹]?\s*\d{1,3}(,\d{2,3})+(\.\d+)?\s+[a-z(]", lab, re.I))


# ── Junk rows ─────────────────────────────────────────────────────────────────
# Running page bands ("Company Overview Responsible Approach Governance Statutory Reports ...")
FURNITURE_WORDS = re.compile(r"company\s+overview|corporate\s+overview|statutory\s+reports?|financial\s+statements"
                             r"|governance|responsible\s+approach|integrated\s+(annual\s+)?report|annual\s+report"
                             r"|management\s+discussion|board'?s\s+report|strategic\s+review|value\s+creation", re.I)
REPEAT_RE = re.compile(r"\b([A-Za-z]{3,})\s+\1\b", re.I)


def junk_reason(row, prev_header=None):
    """
    Why a row is not a real line item (None if it is): a heading, a page strip,
    a symbol code or repeated words.
    """
    import ar_extract
    lab = row["label"].strip()
    has_val = any(v is not None for v in row["values"])
    if not lab:
        return None
    if len(FURNITURE_WORDS.findall(lab)) >= 2 or re.search(r"\|\s*\d{1,4}\s*$", lab):
        return "page strip"
    if ar_extract.is_symbol_row(lab) or ar_extract.rupee_glyphs(lab) != lab:
        return "symbol code"
    if not has_val and (ar_extract.TITLE_RE.search(lab) or any(rx.search(lab) for rx in ar_extract.HEADING_RE.values())
                        or ar_extract.is_column_header(lab)):
        return "heading"
    if REPEAT_RE.search(lab) and not re.search(r"\b(that|had|than)\s+\1", lab, re.I):
        return "repeated words"
    if not has_val and prev_header is not None and lab.lower() == prev_header.lower():
        return "repeated heading"
    return None


# ── Entry point ───────────────────────────────────────────────────────────────
def check_statement(kind, parsed, prose=()):
    if not parsed or not parsed.get("rows"):
        return parsed
    parsed["rows"] = [r for r in parsed["rows"] if not is_sentence(r)]
    rows = parsed["rows"]
    ncols = max((len(r["values"]) for r in rows), default=0)
    vals = [v for r in rows for v in r["values"] if v is not None]
    integer = bool(vals) and all(abs(v - round(v)) < 1e-9 for v in vals)
    for r in rows:
        r["status"] = [None] * len(r["values"])
        r["groups"] = [None] * len(r["values"])
    totals = failed = 0
    for c in range(ncols):
        st, grp = _foot_column(kind, rows, c, integer)
        for i, s in st.items():
            rows[i]["status"][c] = s
        for i, g in grp.items():
            if c < len(rows[i]["groups"]):
                rows[i]["groups"][c] = g
        for i, r in enumerate(rows):
            if c < len(r["values"]) and r["values"][c] is not None and _is_target(kind, r["label"]):
                totals += 1
                failed += st.get(i) == "fail"
    bad_labels = junk = 0
    prev_header = None
    for r in rows:
        r["label_ok"] = label_ok(r["label"], prose)
        bad_labels += not r["label_ok"]
        r["junk"] = junk_reason(r, prev_header)
        junk += r["junk"] is not None
        if r["is_header"]:
            prev_header = r["label"]
        elif any(v is not None for v in r["values"]):
            prev_header = None
    cells = sum(1 for r in rows for v in r["values"] if v is not None)
    confirmed = sum(1 for r in rows for v, s in zip(r["values"], r["status"]) if v is not None and s == "ok")
    parsed["quality"] = {"cells": cells, "confirmed": confirmed, "totals": totals,
                         "failed_totals": failed, "bad_labels": bad_labels, "junk_rows": junk}
    return parsed


def summary_text(q):
    if not q or not q.get("cells"):
        return "-"
    pct = 100.0 * q["confirmed"] / q["cells"]
    s = f"{q['confirmed']}/{q['cells']} figures confirmed by the report's totals ({pct:.0f}%)"
    if q["failed_totals"]:
        s += f"; {q['failed_totals']} total(s) don't add up"
    if q["bad_labels"]:
        s += f"; {q['bad_labels']} garbled label(s)"
    if q.get("junk_rows"):
        s += f"; {q['junk_rows']} junk row(s)"
    if q.get("eps_flags"):
        s += f"; {q['eps_flags']} EPS figure(s) off"
    return s
