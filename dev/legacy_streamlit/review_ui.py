"""
review_ui.py — gold-set review screen (CHAT_HANDOFF item 3.4 C)
---------------------------------------------------------------
Session C compares its own reading of each gold statement (the "second
reader", Claude) with the parser's, and writes only the disagreements to
tests/gold/disagreements_<TICKER>_<FY>_<kind>.json. This screen shows each
disagreement next to the PDF page so Harsh can pick: parser / second reader /
neither (and type the right value). His answers go to
tests/gold/resolutions_<same id>.json after every click; then
`python gold.py finalize <TICKER> <FY>` builds the gold copies.

File formats: tests/gold/FORMAT.md (written by session C, gold.py).

Opened from app.py ("Gold review" page), or on its own:
    python -m streamlit run review_ui.py
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', "engine"))
import datetime
import glob
import json
import os

import fitz
import pandas as pd
import streamlit as st

import pdfview

ROOT = os.path.dirname(os.path.abspath(__file__))
GOLD_DIR = os.environ.get("DOCFETCHER_GOLD_DIR") or os.path.join(ROOT, "tests", "gold")
KIND_NAMES = {"pl": "Profit & Loss", "bs": "Balance Sheet", "cf": "Cash Flow"}
DIS_KINDS = {"value": "Different value", "label": "Different label",
             "missing_in_parser": "Row only the second reader has",
             "extra_in_parser": "Row only the parser has",
             "unit": "Different unit for the whole statement"}
# What each choice means, per kind (shown under the buttons)
CHOICE_HINTS = {
    "extra_in_parser": {"parser": "the row is in the statement, keep it", "reader": "not a line item, drop it"},
    "missing_in_parser": {"parser": "no such row, leave it out", "reader": "the row is there, add it"},
}


# ── Files ─────────────────────────────────────────────────────────────────────
def list_files(gold_dir=None):
    return sorted(glob.glob(os.path.join(gold_dir or GOLD_DIR, "disagreements_*.json")))


def stmt_id(dis_path):
    return os.path.basename(dis_path)[len("disagreements_"):-len(".json")]


def resolutions_path(dis_path):
    return os.path.join(os.path.dirname(dis_path), f"resolutions_{stmt_id(dis_path)}.json")


def load_disagreements(path):
    """Read a disagreements file; add page names (Sources-sheet style, e.g. '235L') for display."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    names, by_index = [], {}
    for p in d.get("pages") or []:
        if isinstance(p, dict):
            name = str(p.get("name") or (p["page"] + 1)).upper()
            by_index.setdefault(p.get("page"), name)
        else:  # plain names ("126L")
            name = str(p).upper()
        if pdfview.PAGE_RE.match(name):
            names.append(name)
    d["_page_names"] = names
    for x in d.get("disagreements", []):
        pg = x.get("page")
        x["_page"] = by_index.get(pg) or (str(pg + 1) if isinstance(pg, int) else None)
    return d


def load_resolutions(dis_path, d=None):
    try:
        with open(resolutions_path(dis_path), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        d = d or {}
        return {"format": "docfetcher-gold-resolutions/1", "ticker": d.get("ticker"), "fy": d.get("fy"),
                "statement": d.get("statement"), "resolved_by": "Harsh", "answers": {}}


def save_answers(dis_path, d, entries):
    """entries: {id: {"choice": ..., "value"/"label"/"values": ..., "note": ...}}. Saved immediately."""
    res = load_resolutions(dis_path, d)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for k, e in entries.items():
        res.setdefault("answers", {})[k] = {**e, "at": now}
    res.update({"ticker": d.get("ticker"), "fy": d.get("fy"), "statement": d.get("statement"),
                "resolved_by": "Harsh", "resolved_at": now})
    path = resolutions_path(dis_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    return res


def _num(text):
    text = (text or "").strip().replace(" ", "")
    if not text:
        return None, None
    v = pdfview.ar_extract.to_num(text)
    if v is None:
        return None, f"'{text}' isn't a number. Use e.g. 1,234.56, or (1,234.56) for a negative figure."
    return v, None


def parse_neither(kind, typed, years):
    """What Harsh typed for 'neither' -> (fields for the resolutions file, error)."""
    typed = (typed or "").strip()
    if kind == "value":
        v, err = _num(typed)
        return ({"value": v}, err)
    if kind == "label":
        return ({"label": typed}, None if typed else "Type the label as printed.")
    if kind == "unit":
        u = typed.lower().rstrip("s")
        ok = {"crore", "lakh", "million", "thousand", "", "rupee"}
        if u not in ok:
            return None, "Type one of: crore, lakh, million, thousand (empty = plain rupees)."
        return ({"value": u if u not in ("", "rupee") else None}, None)
    # a row: "label | value | value", one value per year column
    parts = [p.strip() for p in typed.split("|")]
    if not parts[0]:
        return None, "Type the row as: label | value | value (one value per year)."
    vals = {}
    for y, t in zip(years, parts[1:]):
        v, err = _num(t)
        if err:
            return None, err
        vals[str(y)] = v
    return {"label": parts[0], "values": vals}, None


# ── Display helpers ───────────────────────────────────────────────────────────
def _fmt(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return pdfview.fmt_num(v)
    return "–" if v is None else str(v)


def side_text(x, side):
    """Markdown for the parser's or the reader's version of a disagreement."""
    label, value, values = x.get(f"label_{side}"), x.get(f"value_{side}"), x.get(f"values_{side}") or {}
    if x.get("kind") == "value":
        return f"**{_fmt(value)}**"
    if x.get("kind") == "unit":
        return f"**₹ {value}**" if value else "**rupees** (no unit printed)"
    if label is None:
        return "*(no such row)*"
    lab = f"**{label}**" if label else "*(no label: a bare sub-total)*"
    vals = "  ·  ".join(f"FY{y}: {_fmt(v)}" for y, v in values.items())
    return lab + (f"  \n{vals}" if vals else "")


def _numbers(x):
    out = []
    for side in ("reader", "parser"):
        if x.get("kind") == "value":
            v = x.get(f"value_{side}")
            out += [(side, v)] if isinstance(v, (int, float)) and v else []
        else:
            out += [(side, v) for v in (x.get(f"values_{side}") or {}).values()
                    if isinstance(v, (int, float)) and v]
    return out


def context_rows(d, x, around=3):
    rows = d.get("rows") or []
    pi, ri = x.get("parser_index"), x.get("reader_index")
    hit = [k for k, r in enumerate(rows) if (pi is not None and r.get("parser_index") == pi)
           or (ri is not None and r.get("reader_index") == ri)]
    if not hit:
        return None
    lo, hi = max(0, min(hit) - around), min(len(rows), max(hit) + around + 1)
    years = [str(y) for y in d.get("years", [])]
    out = []
    for k in range(lo, hi):
        r = rows[k]
        row = {"": "👉" if k in hit else "", "Parser label": r.get("label_parser"),
               "Second reader label": r.get("label_reader")}
        for y in years:
            row[f"Parser FY{y}"] = _fmt((r.get("values_parser") or {}).get(y))
            row[f"Reader FY{y}"] = _fmt((r.get("values_reader") or {}).get(y))
        out.append(row)
    return pd.DataFrame(out)


@st.cache_data(show_spinner=False, max_entries=64)
def page_view(pdf, ticker, fy, pages, item_json, page_choice=None, dpi=130):
    x = json.loads(item_json)
    path = pdfview.pdf_path(pdf, ticker, fy)
    if not path:
        return None, None, {"error": f"PDF not found: {pdf or ''} (looked in {pdfview.CACHE_DIR}). "
                                     "Download it with the report link above, or run gold.py prepare."}
    doc = fitz.open(path)
    names = list(pages)
    if x.get("_page") and pdfview.PAGE_RE.match(x["_page"]):
        names = [x["_page"]] + [n for n in names if n != x["_page"]]
    label = x.get("label_reader") or x.get("label_parser") or ""
    hits, seen = [], set()
    for side, v in _numbers(x):  # the second reader's figures first
        for h in pdfview.find_value(doc, names, v, label, in_crore=False)[:1]:
            key = (h["page"], round(h["rect"].x0), round(h["rect"].y0))
            if key not in seen:
                seen.add(key)
                h["side"] = side
                hits.append(h)
    if hits:  # figures on the best hit's line first
        best = hits[0]
        hits.sort(key=lambda h: (h["page"] != best["page"], abs(h["line_rect"].y0 - best["line_rect"].y0) > 2))
    else:
        for lab in (x.get("label_reader"), x.get("label_parser")):
            h = pdfview.find_label(doc, names, lab) if lab else None
            if h:
                hits.append(h)
                break
    shown = page_choice or (hits[0]["page"] if hits else (names[0] if names else None))
    if not shown:
        doc.close()
        return None, None, {"error": "The disagreements file lists no pages."}
    png = pdfview.render(doc, shown, hits, dpi=dpi)
    doc.close()
    return png, shown, {"names": names, "found": [h.get("side") for h in hits if h.get("rect") is not None],
                        "line": bool(hits)}


# ── Screen ────────────────────────────────────────────────────────────────────
def render():
    st.markdown("<style>.block-container {max-width: 1500px;}</style>", unsafe_allow_html=True)
    st.title("🥇 Gold-set review")
    files = list_files()
    if not files:
        st.info(f"No disagreements files yet in `{os.path.relpath(GOLD_DIR, ROOT)}`. Session C writes them "
                "(`disagreements_<TICKER>_<FY>_<kind>.json`); see tests/gold/FORMAT.md.")
        return
    docs = {}
    for p in files:
        try:
            docs[p] = load_disagreements(p)
        except Exception as e:
            st.warning(f"Can't read {os.path.basename(p)}: {e}")
    files = [p for p in files if p in docs]
    if not files:
        return
    answered = {p: load_resolutions(p).get("answers", {}) for p in files}

    def n_items(p):
        return len(docs[p].get("disagreements", []))

    def n_done(p):
        return sum(1 for x in docs[p].get("disagreements", []) if x["id"] in answered[p])

    def file_label(p):
        d, n, k = docs[p], n_items(p), n_done(p)
        mark = "✅" if k == n else "🟡" if k else "⬜"
        return f"{mark} {d.get('ticker', '?')} FY{d.get('fy', '?')} {KIND_NAMES.get(d.get('statement'), d.get('statement'))}: {k}/{n}"

    tot = sum(n_items(p) for p in files)
    tot_done = sum(n_done(p) for p in files)
    st.progress(tot_done / tot if tot else 1.0,
                text=f"{tot_done} of {tot} disagreements decided across {len(files)} statements")
    if tot and tot_done == tot:
        st.success("Everything is decided. Build the gold copies with `python gold.py finalize <TICKER> <FY>` "
                   "for each company (or ask Claude Code to do it).")

    default = next((i for i, p in enumerate(files) if n_done(p) < n_items(p)), 0)
    path = st.selectbox("Statement", files, index=default, format_func=file_label, key="gold_file")
    d = docs[path]
    items = d.get("disagreements", [])
    answers = answered[path]
    sid = stmt_id(path)
    st.markdown(f"**{d.get('company') or d.get('ticker')}** · FY{d.get('fy')} · {d.get('scope', 'consolidated')} "
                f"{d.get('statement_name') or KIND_NAMES.get(d.get('statement'), '')} · figures as printed "
                f"(unit: {d.get('unit') or 'rupees'})"
                + (f" · [report PDF]({d['pdf_url']})" if d.get("pdf_url") else ""))
    if not items:
        st.success("No disagreements in this statement: the parser and the second reader agree on every row.")
        return

    key_idx = f"gold_idx_{sid}"
    if key_idx not in st.session_state:
        st.session_state[key_idx] = next((i for i, x in enumerate(items) if x["id"] not in answers), 0)
    idx = st.session_state[key_idx] % len(items)
    x = items[idx]
    kind = x.get("kind", "value")

    nav = st.columns([3, 1, 1])
    nav[0].markdown(f"#### {idx + 1} of {len(items)} · {DIS_KINDS.get(kind, kind)}")
    if nav[1].button("◀ Previous", use_container_width=True, key="g_prev"):
        st.session_state[key_idx] = (idx - 1) % len(items)
        st.rerun()
    if nav[2].button("Next ▶", use_container_width=True, key="g_next"):
        st.session_state[key_idx] = (idx + 1) % len(items)
        st.rerun()

    left, right = st.columns([1, 1.8])
    with left:
        if x.get("pattern_text"):
            st.caption(f"Pattern: {x['pattern_text']}")
        lab = x.get("label_reader") or x.get("label_parser")
        if kind == "value" and lab:
            st.markdown(f"Line item: **{lab}**  \nYear column: **FY{x.get('year')}**")
        c = st.columns(2)
        c[0].markdown("**Parser**")
        c[0].markdown(side_text(x, "parser"))
        c[1].markdown("**Second reader**")
        c[1].markdown(side_text(x, "reader"))
        if x.get("note"):
            st.caption(f"Note: {x['note']}")
        a = answers.get(x["id"])
        if a:
            txt = {"parser": "parser", "reader": "second reader", "neither": "neither"}.get(a.get("choice"), "?")
            extra = {k: a[k] for k in ("value", "label", "values") if k in a}
            st.info(f"Your answer: {txt}" + (f" {extra}" if extra else "") + ". Click again to change it.")

        same = [y for y in items if y.get("pattern") and y.get("pattern") == x.get("pattern")
                and y["id"] != x["id"] and y["id"] not in answers and y.get("kind") == kind]
        apply_all = False
        if same:
            apply_all = st.checkbox(f"Same answer for {len(same)} more like this",
                                    key=f"gold_all_{sid}_{x['id']}",
                                    help="Applies 'parser' or 'second reader' to every undecided item of this "
                                         "statement with the same pattern. Look at a few of them first.")
        nk = f"gold_note_{sid}_{x['id']}"
        if nk not in st.session_state:
            st.session_state[nk] = (a or {}).get("note", "")

        def decide(choice, fields=None):
            e = {"choice": choice, **(fields or {})}
            if st.session_state.get(nk):
                e["note"] = st.session_state[nk]
            entries = {x["id"]: e}
            if apply_all and choice != "neither":
                entries.update({y["id"]: {"choice": choice, "note": f"applied with {x['id']} (same pattern)"}
                                for y in same})
            res = save_answers(path, d, entries)["answers"]
            order = list(range(idx + 1, len(items))) + list(range(idx))
            nxt = next((j for j in order if items[j]["id"] not in res), None)
            st.session_state[key_idx] = nxt if nxt is not None else idx
            st.rerun()

        hints = CHOICE_HINTS.get(kind, {})
        b = st.columns(2)
        if b[0].button("Parser is right", use_container_width=True, key="g_parser", help=hints.get("parser")):
            decide("parser")
        if b[1].button("Second reader is right", use_container_width=True, key="g_reader", help=hints.get("reader")):
            decide("reader")
        if hints:
            st.caption(f"Parser = {hints['parser']}; second reader = {hints['reader']}.")
        if kind != "extra_in_parser":
            with st.form(key=f"gold_neither_{sid}_{x['id']}"):
                yrs = " | ".join(f"FY{y}" for y in d.get("years", []))
                ph = {"value": "e.g. 1,234.56, or (1,234.56) if negative; empty = no figure",
                      "label": "the label exactly as printed",
                      "unit": "crore / lakh / million / thousand (empty = rupees)"}.get(kind, f"label | {yrs}")
                prev = ""
                if a and a.get("choice") == "neither":
                    prev = a.get("label") or ("" if a.get("value") is None else str(a.get("value")))
                    if a.get("values"):
                        prev += " | " + " | ".join("" if v is None else str(v) for v in a["values"].values())
                typed = st.text_input("Neither is right: type the correct one", value=prev, placeholder=ph)
                if st.form_submit_button("Save 'neither'", use_container_width=True):
                    fields, err = parse_neither(kind, typed, d.get("years", []))
                    if err:
                        st.error(err)
                    else:
                        decide("neither", fields)
        st.text_input("Note (optional; type it before clicking)", key=nk)
        ctx = context_rows(d, x)
        if ctx is not None:
            with st.expander("Rows around this line (parser vs second reader)"):
                st.dataframe(ctx, hide_index=True, use_container_width=True)
        if all(y["id"] in answers for y in items):
            st.success(f"All {len(items)} disagreements in this statement are decided "
                       f"(saved in `{os.path.relpath(resolutions_path(path), ROOT)}`).")

    with right:
        pk = f"gold_page_{sid}_{x['id']}"
        png, shown, info = page_view(d.get("pdf"), d.get("ticker"), d.get("fy"), tuple(d["_page_names"]),
                                     json.dumps(x, sort_keys=True, default=str), st.session_state.get(pk))
        if info.get("error"):
            st.error(info["error"])
            return
        names = info["names"]
        if len(names) > 1:
            sel = st.radio("Statement page", names, index=names.index(shown) if shown in names else 0,
                           horizontal=True, key=f"gold_pagesel_{sid}_{x['id']}")
            if sel != shown:
                st.session_state[pk] = sel
                st.rerun()
        found = info.get("found") or []
        if found:
            who = {"reader": "the second reader's figure", "parser": "the parser's figure"}
            st.caption(f"Red box: {who.get(found[0], 'the figure')}; yellow band: its line"
                       + ("; orange: other figures of the row." if len(found) > 1 else "."))
        elif info.get("line"):
            st.caption("No figure to box: the line with the closest wording is highlighted in yellow.")
        else:
            st.caption("This line wasn't found on the page; look for it yourself.")
        st.image(png, caption=f"{d.get('ticker')} FY{d.get('fy')} annual report, PDF page {shown}",
                 use_container_width=True)


if __name__ == "__main__":
    st.set_page_config(page_title="DocFetcher · Gold review", page_icon="🥇", layout="wide")
    render()
