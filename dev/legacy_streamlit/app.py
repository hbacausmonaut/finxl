"""
app.py — DocFetcher one-click UI
--------------------------------
Ticker + years in, multi-year financial statements Excel out.

Run:
    python -m streamlit run app.py
(or double-click run_app.bat)
"""

import os as _os, sys as _sys  # FinXL engine path
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', "engine"))
import datetime
import os

import pandas as pd
import streamlit as st

import finxl
import llm_extract
from ar_extract import KINDS

st.set_page_config(page_title="DocFetcher · Annual Report → Excel", page_icon="📊", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
div[data-testid="stMetricValue"] {font-size: 1.4rem;}
.small-note {color: #888; font-size: 0.85rem;}
</style>
""", unsafe_allow_html=True)

THIS_YEAR = datetime.date.today().year

# ── Page: Excel generator (default) or one of the review screens ─────────────
PAGE = st.sidebar.radio("Page", ["📊 Generate Excel", "🔍 Sampling audit", "🥇 Gold review"], index=0)
if PAGE != "📊 Generate Excel":
    if PAGE == "🔍 Sampling audit":
        import audit_ui
        audit_ui.render()
    else:
        import review_ui
        review_ui.render()
    st.stop()
st.sidebar.divider()

# ── Sidebar: optional AI fallback ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ AI fallback (optional)")
    st.caption("The free built-in parser handles most reports. AI is only used for "
               "statements that fail the parser's checks.")
    backend = st.radio("Engine", ["Off", "Gemini (free API key)", "Ollama (local, Gemma etc.)"], index=0)
    ai = None
    if backend.startswith("Gemini"):
        key = st.text_input("Gemini API key", value=os.environ.get("GEMINI_API_KEY", ""), type="password",
                            help="Free key from https://aistudio.google.com/apikey")
        model = st.text_input("Model", value="gemini-flash-latest",
                              help="Backup models are tried automatically when Google's free tier is busy")
        ai = {"backend": "gemini", "api_key": key, "model": model}
    elif backend.startswith("Ollama"):
        model = st.text_input("Model", value="gemma3:12b", help="Pull it first: ollama pull gemma3:12b")
        ai = {"backend": "ollama", "model": model}
    if ai:
        mode = st.radio("Use AI", ["Only when the parser fails", "For every statement"], index=0)
        ai["mode"] = "always" if mode.startswith("For every") else "fallback"
        if st.button("Test connection"):
            ok, msg = llm_extract.check_backend(ai["backend"], ai.get("api_key"), ai.get("model"))
            (st.success if ok else st.error)(msg)

# ── Main form ────────────────────────────────────────────────────────────────
st.title("📊 Annual Report → Excel")
st.write("Pulls every annual report for the years you pick from **Screener**, finds the "
         "Balance Sheet, P&L and Cash Flow inside each PDF, and lines every line item up year by year in one Excel file.")

c1, c2, c3, c4 = st.columns([2, 1, 1, 1.4])
ticker = c1.text_input("Screener ticker", value="PIDILITIND", help="As in screener.in/company/<TICKER>/").strip().upper()
start = c2.number_input("From FY", min_value=2005, max_value=THIS_YEAR + 1, value=THIS_YEAR - 5, step=1)
end = c3.number_input("To FY", min_value=2005, max_value=THIS_YEAR + 1, value=THIS_YEAR, step=1)
scope = c4.selectbox("Statements", ["consolidated", "standalone", "both"], index=0,
                     format_func=lambda s: {"consolidated": "Consolidated", "standalone": "Standalone",
                                            "both": "Both"}[s])

restated = st.radio("Figures", ["Latest restated (best for comparing years)", "As originally reported"],
                    index=0, horizontal=True,
                    help="Companies sometimes restate last year's numbers (mergers, accounting changes). "
                         "Restated uses the newest report that shows each year.").startswith("Latest")

go = st.button("⚡ Generate Excel", type="primary", use_container_width=True, disabled=not ticker)

if go:
    if start > end:
        st.error("'From FY' must be before 'To FY'.")
        st.stop()
    if ai and ai["backend"] == "gemini" and not ai.get("api_key"):
        st.error("Enter a Gemini API key in the sidebar, or switch AI fallback off.")
        st.stop()
    bar = st.progress(0.0, text="Starting ...")
    with st.status(f"Working on {ticker} ...", expanded=True) as status:
        lines = []
        box = st.empty()

        def log(msg):
            lines.append(msg)
            box.code("\n".join(lines[-40:]), language=None)

        def progress(f):
            bar.progress(min(1.0, f), text=f"{int(f * 100)}%")

        try:
            path, merged, sources, years, months = finxl.run(ticker, int(start), int(end), scope, ai=ai,
                                                             log=log, progress=progress, restated=restated)
            st.session_state["result"] = {"path": path, "merged": merged, "sources": sources,
                                          "years": years, "months": months, "ticker": ticker, "log": lines}
            status.update(label=f"Done — {os.path.basename(path)}", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Failed", state="error")
            st.error(str(e))

# ── Results ──────────────────────────────────────────────────────────────────
res = st.session_state.get("result")
if res:
    st.divider()
    left, right = st.columns([3, 1])
    left.subheader(f"{res['ticker']} · FY{res['years'][0]}–FY{res['years'][-1]}")
    left.markdown(f"<span class='small-note'>Saved to {res['path']}</span>", unsafe_allow_html=True)
    with open(res["path"], "rb") as f:
        right.download_button("⬇️ Download Excel", f.read(), file_name=os.path.basename(res["path"]),
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              type="primary", use_container_width=True)

    checks = [s for s in res["sources"] if s["check"].startswith(("CHECK", "MISSING"))]
    if checks:
        st.warning(f"{len(checks)} statement(s) didn't pass the automatic checks. Review them in the "
                   "Sources tab, or turn on the AI fallback and run again.")

    tabs = [k for k in finxl.SHEET_NAMES if k in res["merged"]]
    tab_objs = st.tabs([finxl.SHEET_NAMES[k] for k in tabs] + ["Sources"])
    for t, key in zip(tab_objs, tabs):
        with t:
            rows = res["merged"][key]
            data = {"Particulars": [" " * r["level"] + r["label"] for r in rows]}
            for y in res["years"]:
                data[finxl.col_label(y, res.get("months"))] = [r["values"].get(y) for r in rows]
            df = pd.DataFrame(data)
            st.dataframe(df, hide_index=True, use_container_width=True, height=600,
                         column_config={c: st.column_config.NumberColumn(format="%.2f")
                                        for c in df.columns[1:]})
    with tab_objs[-1]:
        src = pd.DataFrame(res["sources"])
        st.dataframe(src, hide_index=True, use_container_width=True,
                     column_config={"url": st.column_config.LinkColumn("Report")})
        with st.expander("Run log"):
            st.code("\n".join(res["log"]), language=None)
