# DocFetcher: Project Plan & Decisions

*Living document. Updated as the project moves forward. Last updated: 2026-10-31.*

## Goal

One click: pick an Indian listed company and a range of years, and get a clean Excel file with the **full financial statements** (every line item of the Balance Sheet, P&L and Cash Flow, consolidated and standalone) taken straight from the annual reports. This is more than the summarised data free sites like Screener or Yahoo Finance show.

**Long-term:** a public web app or website.

## Background & vision (from Harsh, 2026-10-30)
- Started as a **personal academic project**: building financial models without access to Capital IQ / S&P-type tools. Earlier attempts and prototypes (months ago) didn't succeed; this version does.
- **Target users (if public):** analysts, students, academics, firms.
- **Monetisation:** open to it, but **only after the tool is near-perfect (~99% accuracy)**. Harsh hasn't built a paid app before.
- **Budget:** effectively **zero**. No paid servers/cloud. Has Lovable Lite (~50–60 credits).
- **Coverage:** Indian listed equities. FY2020–2026 is enough for now; a paid product would need much longer history.
- **Data source for a public product:** BSE/NSE directly, not Screener.
- **Idea:** an **MCP server** so Claude (and any MCP-capable AI) can pull clean statements from our data instead of searching and parsing the web. This saves tokens, and the AI can focus on modelling and analysis.

## Current status

| Area | Status |
|---|---|
| Step 1: download reports from Screener (`fetchdocs.py`) | Done |
| Step 2: extract statements from the PDFs into multi-year Excel (`finxl.py`, `ar_extract.py`) | Done, being hardened (Phase 2) |
| One-click local UI (`app.py`, Streamlit) | Done (test harness) |
| AI fallback for unreadable PDFs (`llm_extract.py`, Gemini / Ollama) | Built; free Gemini key connected (2026-10-31). Not yet needed on a real report |
| Cross-checking against independent sources (`accuracy_check.py`) | Done: NSE XBRL, Screener, Yahoo |
| Regression test suite (`tests/regression.py`) | Done |
| Version control | Git, local only |

## Roadmap

### Phase 1: Protect and lock in (in progress)
- [x] Git repository with history (local)
- [x] Regression suite: re-runs every test company and flags anything that got worse versus `tests/baseline.json`
- [x] PDF cache moved out of OneDrive to `C:\Users\harsh\DocFetcherData` (keeps OneDrive light; disk space is limited)
- [ ] Private GitHub repo as an online backup (later; needs your GitHub login)

### Phase 2: Make the engine near-perfect (in progress)
- [x] Round 1: 7 companies (IT, chemicals, conglomerate, bank, PSU, paints, mid cap)
- [x] Round 2: 31 more companies across sectors (NBFCs, insurers, PSU banks, holding company, small caps, Nestlé year-end change)
  - Result: **95.9% of statements OK, 91.5% of headline figures independently verified** (from 85% / 65% at the start of round 2)
- [x] Round 3: fixed the round-2 open items, then tested 20 *new* companies
  - First run on the unseen companies: 87.4% verified (vs 65% for round 2's first run), so the fixes generalise
  - After fixes: **58 companies, 98.3% of statements OK, 92.8% of figures verified**
- [x] December year-end support (columns labelled e.g. "Dec 2022")
- [x] HDFC Bank regression fixed (TEST_LOG #54), verified on the affected companies
- [x] Full 58-company re-run (2026-10-31): #54 fix confirmed; **98.4% statements OK, 92.8% verified**
- [x] NTPC FY2024 "unreadable" PDF was really **rotated pages**; fixed in the parser, no AI needed (#15)
- [x] Free Gemini key set up (Google AI Studio, free tier, stored in the `GEMINI_API_KEY` environment variable); AI fallback connects. Auto-retry and backup models added because the free tier is often busy (#57)
- [x] **Round 4: make the data prove itself** (approved and done 2026-10-31). Results:
  - **"matches the report" 95.4%** across 63 companies
  - 58 companies: 98.4% of statements OK
  - 5 new companies: 97.3% matches the report at their first run
  - details in RUN_LOG runs #17–#27
- [ ] **Round 5 (proposed, needs go-ahead):**
  - fix the flagged problems: CERA prior-year column (#74), Vinati missing line (#75), IRCTC (#77), PI Industries (#78), BPCL font (#67), Bank of Baroda bilingual pages (#66)
  - send statements that fail the checks to the AI fallback automatically
  - build the sampling-audit screen
- [ ] Round 5: sampling audit screen (Harsh clicks ✅/❌ on random figures next to the PDF snippet)
- [ ] Insurer segment-column Revenue Accounts (#55)
- [ ] Remaining open items (#56)
- [ ] Find a PDF the parser truly can't read (scanned) to test the AI fallback end to end
- [ ] Later: extend years back to FY2015 (early Ind AS), then FY2010 (old Indian GAAP)

### Round 4 plan (done 2026-10-31; kept for reference)
**Why:** until now, checks covered only headline figures (4 per year), compared with outside sites. VBL showed that the rows in between can be garbled while the headlines pass. Round 4 checks **every row against the report's own arithmetic**, which is Harsh's 99% definition.

**A. Parser fixes**
1. Coded-font decoding decided **per font**, not per word (fixes VBL "OVKRSFF", "=J=", "$Total"; ERROR_LOG #58)
2. Join line items that wrap onto two lines (#59)

**B. Automatic checks on every statement and year**

3. Arithmetic checks (footing):
   - **Balance sheet:** items add up to each subtotal; assets = equity + liabilities
   - **P&L:** revenue + other income = total income; total income − total expenses = PBT; PBT − tax = PAT
   - **Cash flow:** operating + investing + financing = net change; opening cash + net change = closing cash
4. Label check against a dictionary of real line items (built from the 58 tested companies). Garbage is flagged and near-misses are corrected. Sentence-like footnote rows are dropped (#60).
5. Excel output:
   - failed cells highlighted yellow with the reason
   - a new **Quality** sheet per statement and year

**C. Testing**

6. Re-run all 58 companies (no regressions allowed)
7. VBL FY2020–25, checked against its annual report
8. 5 new, never-seen companies, to see whether the checks catch problems on their own
9. Report the new measure: **"matches the report"**

**D. Record:** RUN_LOG, ERROR_LOG, TEST_LOG and this plan updated; commit; short summary to Harsh.

**Not in Round 4:**
- the sampling-audit screen (Round 5)
- insurer segment columns (#55)
- the open companies (#56)
- automatically sending flagged rows to the AI (decide after seeing how many rows get flagged)

**Estimate:** ~3–4 hours, mostly background runs. ₹0 (runs locally, no AI calls).

### Phase 3: More data
- [ ] Notes to accounts: segment results, borrowings breakup, related parties, contingent liabilities
- [ ] Quarterly results, in the same Excel format

### Phase 4: Web app
- [ ] Python engine as a FastAPI backend (job queue, results cache in a database)
- [ ] Host the backend (free options: Hugging Face Spaces / Google Cloud Run; see below)
- [ ] Frontend in Lovable, calling the API (**Lovable can't run our Python; it only builds the UI**)

### Phase 5: Before going public
- [ ] Download PDFs from BSE/NSE directly instead of scraping Screener (terms of use)
- [ ] User accounts, rate limits, payments if charging

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-30 | Extraction is **free Python parsing first** (PyMuPDF); AI is only a fallback | Cost; the parser reads text-based PDFs exactly. AI is needed only for scanned/broken PDFs |
| 2026-10-30 | No paid Claude API. Free AI options only: **Gemini free tier** or **local Ollama/Gemma** | User preference |
| 2026-10-30 | Local **Streamlit** app as the UI for now | Test harness until the web app phase |
| 2026-10-30 | Default figures are **latest restated** (newest report showing each year); "as originally reported" is an option | Best for comparing years; matches Screener |
| 2026-10-30 | Statements that fail their checks can only **fill gaps**, never override good data | NTPC FY2024 (then misread, later fixed as rotated pages) overwrote correct FY2022 figures |
| 2026-10-30 | Web app = **Python backend + Lovable frontend**, not a Lovable rewrite | Lovable runs TypeScript only; a rewrite would lose all the parser fixes |
| 2026-10-30 | Hosting: start on **free tiers** (HF Spaces / Cloud Run + Supabase + Lovable free); pay (~$5–25/mo) only when real users need it | Cost |
| 2026-10-30 | **Cache results** per company-year; **don't store PDFs** on the server | Keeps hosting near free |
| 2026-10-30 | Git **local only** for now; GitHub later | User choice |
| 2026-10-30 | Project docs as **Markdown in the repo** (`PROJECT_PLAN.md`, `TEST_LOG.md`) | Versioned with the code, readable anywhere |
| 2026-10-30 | Phase 2 tests cover **FY2020–2026** first; older years later | Get the modern Ind AS format near-perfect first |
| 2026-10-30 | Cross-check sources: **NSE XBRL** (official), **Screener**, **Yahoo Finance** | Independent confirmation; NSE filings are the company's own audited numbers |
| 2026-10-30 | Every parser change is checked with the **regression suite** against `tests/baseline.json` before committing | Round 2 showed fixes for one company can break another (it caught 4 regressions) |
| 2026-10-30 | "Net profit" in the Summary = **total profit** (after tax, associates, discontinued ops; before the owners/NCI split) | Matches NSE/Screener; companies label these lines inconsistently |
| 2026-10-30 | Insurers get a 4th statement, the **Revenue Account** | IRDAI format: the policyholders' account is the main income statement |
| 2026-10-30 | Reports without consolidated statements are marked **N/A**, not failures | Companies without subsidiaries |
| 2026-10-30 | Column headers show the real period end ("Dec 2022" vs "Mar 2025") | December year-end companies (Nestlé) |
| 2026-10-30 | A known regression stays in the baseline at its old value until fixed | So the suite keeps flagging it (HDFC Bank, #54) |
| 2026-10-31 | **99% accuracy = our numbers vs the annual report itself**, not vs Screener/NSE | Harsh's definition. Screener/NSE differ by restatements and definitions; measure with arithmetic checks + sampling audit |
| 2026-10-31 | **Planning/building split:** scope is decided in a separate Claude chat (loops closed in Notion, *DocFetcher: Scope Discussions*); Claude Code builds only items under "Approved to build" in `CHAT_HANDOFF.md`, writes open questions there and records finished items under "Done" | Harsh wants scope control; Claude Code had been choosing next steps itself |
| 2026-10-31 | **Ask Harsh before doing anything:** state the plan, time estimate and cost of each part, then wait for a clear yes. This applies even to approved items, and ambiguous messages are not approval | P13–P14: work was started without asking |
| 2026-10-31 | **Hourly status updates during long work:** what's running, time to finish, successes, failures, what's next | Harsh isn't watching the terminal during long runs |
| 2026-10-31 | Keep **RUN_LOG.md** (every test run) and **ERROR_LOG.md** (every error and fix, incl. process mistakes); plans for testing go in this file | Harsh wants an on-paper record of work done and problems faced |
| 2026-10-31 | AI fallback: **Google AI Studio free key** (Gemini/Gemma, hosted by Google); nothing runs locally, no paid server. Upgrade to paid API only after paying users | Zero budget; annual reports are public, so free-tier data use is acceptable |
| 2026-10-31 | Default AI model `gemini-flash-latest` + automatic backups | Google retires fixed model names; the free tier is often overloaded |
| 2026-10-31 | Future batch "worker" (if needed): Oracle Always Free VM first, else a Pi 5 / N100 mini PC with SSD; public website/API always on free cloud tiers | Laptop can't run everything; home hardware shouldn't serve users |
## Ideas parked for later (product direction, 2026-10-30)
- **Pre-computed dataset, not on-demand extraction:** run the engine in batches on the local PC, publish only the extracted numbers. The website/API/MCP then only *serves data*, so no Python server is needed and hosting stays free.
- **MCP server** over the dataset: tools like `search_company`, `get_statements`, `get_line_item`, `get_ratios`, `compare_peers`, with page-level source links in every answer.
- **Standardised statements** (map each company's lines to a common chart of accounts) alongside "as reported".
- **Row-level arithmetic checks** (items sum to their subtotal) to push towards 99% and flag doubtful numbers.
- **Notes data** (segments, borrowings, related parties, contingent liabilities, capex), **quarterly results** (exchange XBRL), **auto-filled 3-statement / DCF templates**, concall transcript search.
- Freemium: free browsing and limited downloads; paid bulk Excel, long history, API/MCP keys; cheap student/academic tier. Payments via Razorpay (India) or Stripe.
- Download PDFs directly from BSE/NSE (official, no Screener dependency)
- Use NSE XBRL as a **data source** too (not just a cross-check) for the headline numbers. It's official, machine-readable and exact, but it only has summary lines, not the full statements.
- Excel extras: charts, common-size statements, more ratios
- Show "restated" markers on numbers a later report changed

## How accuracy is measured
**Target (Harsh, 2026-10-31): 99% of numbers match the annual report itself.** Outside sites are supporting evidence only, because they differ by restatements and definitions.

| # | Measure | What it checks | Status |
|---|---|---|---|
| 1 | **Statement checks** | balance sheet ties; P&L has revenue and profit rows; cash flow has an operating row; <30% of rows blank | Since Day 1 |
| 2 | **Cross-checks** (`accuracy_check.py`) | revenue, net profit, total assets, operating cash flow per year vs NSE XBRL / Screener / Yahoo (within 0.5%). Headlines only | Since Day 1 |
| 3 | **Regression suite** (`python tests/regression.py`) | nothing got worse vs `tests/baseline.json`; run before every commit of parser changes | Since Day 1 |
| 4 | **Arithmetic checks (footing)** (`quality.py`) | every row: items add up to their subtotals and totals → share of figures **"matching the report"** | Since Round 4: **95.4%** (63 companies) |
| 5 | **Label check** (`quality.py`, `label_words.txt`) | every line-item name is a real word: in the 3+-company dictionary or in the report's own notes text | Since Round 4: 529 labels flagged |
| 6 | **Sampling audit** | ~200 random figures compared with the PDF by Harsh → the true accuracy % to quote to users | Round 5 |

## Record-keeping rules
- **RUN_LOG.md:** every test run, when it happens. Records what was run, the result, what changed and the daily total.
- **ERROR_LOG.md:** every error, parser or process, with cause, fix and lesson.
- **TEST_LOG.md:** companies tested, by sector, with notes.
- **PROJECT_PLAN.md (this file):** plan, decisions and ideas. Updated whenever Harsh makes a decision.
- **CHAT_HANDOFF.md:** what is approved to build, open questions for the planning chat, and what is done.
- **Before any work:** ask Harsh first (plan, time, cost). During long work: an hourly status update.

## Free-hosting notes (for Phase 4)
- **Hugging Face Spaces:** free CPU; sleeps when idle; public.
- **Google Cloud Run:** monthly free allowance; card required.
- **Render:** free but ~512 MB RAM and slow cold starts.
- **Oracle Always Free:** generous VM; more setup.
- **Supabase:** free DB ~500 MB; pauses after a week idle.
- **Lovable:** free plan with daily credits.
- **Gemini API:** free tier is rate-limited; inputs may be used by Google.

*Prices change; verify before committing.*

## Key file map
| File | Role |
|---|---|
| `fetchdocs.py` | Screener lookup + bulk downloader (step 1) |
| `finxl.py` | Pipeline: download → extract → merge years → Excel |
| `ar_extract.py` | PDF statement locator + parser (most hardening lives here) |
| `llm_extract.py` | Gemini / Ollama fallback (sends page images + text) |
| `accuracy_check.py` | Cross-check against NSE XBRL / Screener / Yahoo |
| `tests/regression.py` | Regression suite; `tests/companies.json` = test set, `tests/baseline.json` = baseline |
| `tests/summary.py` | Prints the results table for `TEST_LOG.md`; `--save-baseline` accepts the current results |
| `app.py` | Streamlit UI |
| `quality.py` | Arithmetic (footing) and label checks; Quality sheet figures |
| `label_words.txt` | Dictionary of real line-item words (from 58 companies) for the label check |
| `RUN_LOG.md` / `ERROR_LOG.md` / `TEST_LOG.md` | Test runs / errors and fixes / companies tested |
| `ixbrl_to_excel.py` | Older tool: NSE iXBRL filing → Excel |
