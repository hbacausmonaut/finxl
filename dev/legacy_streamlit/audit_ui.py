"""
audit_ui.py — sampling-audit screen (CHAT_HANDOFF item 4)
--------------------------------------------------------
One sampled figure at a time next to its PDF page, with the value highlighted.
Answers are saved to tests/audit/progress.json after every click, so the
audit can be stopped and resumed. Opened from app.py ("Sampling audit" page).

The sample itself is drawn once with:  python audit.py sample
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', "engine"))
import os

import fitz
import streamlit as st

import audit
import pdfview

REASON_ICONS = {"wrong number": "🔢", "wrong year column": "📅", "wrong sign": "➖", "wrong unit": "📏",
                "garbled label": "🔤", "other": "✏️"}


@st.cache_data(show_spinner=False, max_entries=64)
def page_view(pdf, ticker, fy, pages, value, label, page_choice=None, dpi=130):
    """(png bytes, page shown, info dict) for one figure."""
    path = pdfview.pdf_path(pdf, ticker, fy)
    if not path:
        return None, None, {"error": f"PDF not found in {pdfview.CACHE_DIR} (FY{fy} report of {ticker})."}
    doc = fitz.open(path)
    names = pdfview.parse_pages(pages)
    hits = pdfview.find_value(doc, names, value, label) if value else []
    if not hits:
        h = pdfview.find_label(doc, names, label)
        hits = [h] if h else []
    shown = page_choice or (hits[0]["page"] if hits else (names[0] if names else None))
    if not shown:
        return None, None, {"error": "No statement pages recorded for this figure."}
    png = pdfview.render(doc, shown, hits, dpi=dpi)
    info = {"found": bool(hits and hits[0].get("rect") is not None), "sign_ok": bool(hits and hits[0]["sign_ok"]),
            "printed": hits[0].get("printed") if hits else None, "hit_page": hits[0]["page"] if hits else None,
            "others": len([h for h in hits[1:] if h.get("rect") is not None]), "names": names}
    doc.close()
    return png, shown, info


def _next_unanswered(items, answers, start=0):
    n = len(items)
    for k in range(n):
        i = (start + k) % n
        if items[i]["id"] not in answers:
            return i
    return None


def render():
    st.markdown("<style>.block-container {max-width: 1500px;}</style>", unsafe_allow_html=True)
    st.title("🔍 Sampling audit")
    sample = audit.load_sample()
    if not sample:
        st.info("No sample yet. Draw it once from the project folder (re-runs the pipeline on the test "
                "companies, about the same time as the regression suite):")
        st.code("python audit.py sample", language="bash")
        st.caption(f"The sample is saved to {audit.SAMPLE_FILE} with a fixed seed, so it can be re-shown.")
        return
    items = sample["items"]
    prog = audit.load_progress()
    answers = prog.get("answers", {})
    done = sum(1 for it in items if it["id"] in answers)

    if "audit_idx" not in st.session_state:
        st.session_state.audit_idx = _next_unanswered(items, answers) or 0
    idx = st.session_state.audit_idx % len(items)
    it = items[idx]

    top = st.columns([3, 1, 1, 1.3])
    top[0].progress(done / len(items), text=f"{done} of {len(items)} checked")
    if top[1].button("◀ Previous", use_container_width=True):
        st.session_state.audit_idx = (idx - 1) % len(items)
        st.session_state.pop("audit_wrong", None)
        st.rerun()
    if top[2].button("Next ▶", use_container_width=True):
        st.session_state.audit_idx = (idx + 1) % len(items)
        st.session_state.pop("audit_wrong", None)
        st.rerun()
    if top[3].button("📄 Write report", use_container_width=True, type="primary" if done == len(items) else "secondary"):
        rep = audit.write_report()
        st.session_state.audit_report = audit.report_markdown(rep)

    if st.session_state.get("audit_report"):
        with st.expander("Report (saved to tests/audit/report.md)", expanded=True):
            st.markdown(st.session_state.audit_report)
            if st.button("Close report"):
                st.session_state.pop("audit_report")
                st.rerun()

    left, right = st.columns([1, 1.9])
    with left:
        st.markdown(f"#### Figure {idx + 1} of {len(items)}  ·  `{it['id']}`")
        st.markdown(f"**{it.get('company', it['ticker'])}** ({it['ticker']})")
        st.markdown(f"{it['scope'].title()} **{audit.KIND_NAMES.get(it['kind'], it['kind'])}**")
        st.markdown(f"Year: **FY{it['year']}**  ·  read from the **FY{it['report_fy']}** report")
        st.markdown("Line item:")
        st.markdown(f"> {it['label']}")
        st.metric("Our value (₹ crore)", pdfview.fmt_num(it["value"]))

        page_choice = st.session_state.get(f"audit_page_{it['id']}")
        png, shown, info = page_view(it.get("pdf"), it["ticker"], it["report_fy"], it["pages"], it["value"],
                                     it["label"], page_choice)
        if info.get("found"):
            msg = f"Highlighted in red where the report prints **{pdfview.fmt_num(info['printed'])}**"
            if not info["sign_ok"]:
                msg = (f"⚠️ Found only with the opposite sign (purple box): the report prints "
                       f"**{pdfview.fmt_num(info['printed'])}**")
            if info["others"]:
                msg += f" ({info['others']} other place(s) with the same number in orange)"
            st.caption(msg + ". Check the row and the year column yourself.")
        elif not info.get("error"):
            st.caption("The number wasn't found on the page (the line is highlighted if its name was found). "
                       "Look for it yourself.")

        a = answers.get(it["id"])
        if a:
            txt = {"correct": "✅ correct", "wrong": f"❌ wrong ({a.get('reason')})", "cant_tell": "? can't tell"}
            st.info(f"Your answer: {txt[a['verdict']]}. Click again to change it.")

        def answer(verdict, reason=None):
            audit.record_answer(it["id"], verdict, reason, st.session_state.get(f"audit_note_{it['id']}", ""))
            st.session_state.pop("audit_wrong", None)
            nxt = _next_unanswered(items, audit.load_progress()["answers"], idx + 1)
            st.session_state.audit_idx = nxt if nxt is not None else idx
            st.rerun()

        b = st.columns(3)
        if b[0].button("✅ Correct", use_container_width=True, key="a_ok"):
            answer("correct")
        if b[1].button("❌ Wrong", use_container_width=True, key="a_bad"):
            st.session_state.audit_wrong = it["id"]
        if b[2].button("? Can't tell", use_container_width=True, key="a_ct"):
            answer("cant_tell")
        if st.session_state.get("audit_wrong") == it["id"]:
            st.markdown("**What's wrong?**")
            rc = st.columns(2)
            for k, r in enumerate(audit.REASONS):
                if rc[k % 2].button(f"{REASON_ICONS[r]} {r.capitalize()}", use_container_width=True, key=f"r_{k}"):
                    answer("wrong", r)
        nk = f"audit_note_{it['id']}"
        if nk not in st.session_state:
            st.session_state[nk] = (a or {}).get("note", "")
        st.text_input("Note (optional; type it before clicking an answer)", key=nk)
        if it.get("url"):
            st.markdown(f"[Open the full report PDF]({it['url']})  ·  pages {it['pages']}")
        if done == len(items):
            st.success("All figures checked. Click **Write report**.")

    with right:
        if info.get("error"):
            st.error(info["error"])
        else:
            names = info["names"]
            if len(names) > 1:
                sel = st.radio("Statement page", names, index=names.index(shown) if shown in names else 0,
                               horizontal=True, key=f"audit_pagesel_{it['id']}")
                if sel != shown:
                    st.session_state[f"audit_page_{it['id']}"] = sel
                    st.rerun()
            st.image(png, caption=f"{it['ticker']} FY{it['report_fy']} annual report, PDF page {shown}",
                     use_container_width=True)


if __name__ == "__main__":  # python -m streamlit run audit_ui.py
    st.set_page_config(page_title="DocFetcher · Sampling audit", page_icon="🔍", layout="wide")
    render()
