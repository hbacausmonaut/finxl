# CHAT_HANDOFF.md

*Communication file between Claude chat (planning) and Claude Code (building). Keep it in the repo root.*

## Rules for Claude Code
1. Read this file at the start of every session.
2. Only build items listed under **Approved to build**. If something isn't listed, don't start it, even if it seems like an obvious next step.
3. If a task needs a design or scope decision that isn't covered here, stop and write the question under **Questions for chat**. Don't decide it yourself.
4. When an approved item is done, move it to **Done** with the date, one line on what changed, and the run/commit reference.
5. Never edit **Approved to build** or **Not approved** yourself. Those come from chat via Harsh.

## Rules for chat
- Items go into **Approved to build** only after a loop in Notion (*DocFetcher: Scope Discussions*) is closed.
- Each item says what "done" means.

---

## Approved to build
*Goal: close v1. No fixed deadline. Order: item 3.4 → 3.5 → 4 → 5.*

> **2026-11-04: CLOUD RUN APPROVED.** Harsh wants to use his expiring Claude Code on the web credits (they expire 2026-11-05) to run items 3.4, 3.5, 4 and 5 in parallel cloud sessions. **Item 6 below comes first**: the setup, then launching three cloud sessions. Full instructions and the three session prompts are in **`CLOUD_PLAN.md`**. **Update (16:05):** the gold set's second reader is now **Claude itself** (not Gemini), and leftover credits go to a larger AI-verified "silver" set. See CLOUD_PLAN.md, "Gold and silver sets". Harsh approves item 6 and the cloud run in one go when he reads the plan. After that, work autonomously and only ping him for the "Ping Harsh only if" cases in CLOUD_PLAN.md. This one-time go-ahead replaces the usual "ask before each item" rule for this run.

### 6. Cloud setup + launch (approved 2026-11-04; do this FIRST, from the local Claude Code)
See `CLOUD_PLAN.md`, Part 1 (setup) and Part 2 (launch). **Done when:**
- the repo is on GitHub as a private repo, with the Claude GitHub App installed
- a cloud environment exists with the network, secret and setup settings from the plan
- sessions A, B and C are running
- their links are recorded under **Done** here

### Earlier items (finished; see Done)
- ~~Round 4: finish and record~~ (done)
- ~~Switch report downloads from Screener to BSE/NSE~~ (**withdrawn 2026-10-31 by Harsh:** stay on Screener; revisit only if the project goes commercial)
- ~~Fix stale docs~~ (done)

### 3.4 Clean-output fixes + "gold set" of fully verified statements (approved 2026-10-31; do this BEFORE item 3.5)
Triggered by Harsh's own test: `SBIN_Financials_FY2023-FY2026.xlsx` (consolidated). Its Quality sheet said 94.9% confirmed with 0 garbled labels, but the file had obvious problems. The current checks have blind spots.

**A. Fix the bugs found in the SBI file. Treat each one as a general pattern, not an SBI one-off.**
1. **Per-share figures are unit-converted (most serious).** Basic and diluted EPS showed 0.0062 instead of about ₹62, because the "₹000s → ₹ crore" conversion was applied to EPS. Per-share rows (EPS, dividend per share, face value) must never be unit-converted. **Check how many of the 63 companies are affected** and report it.
2. **₹ symbol stored as a letter.** "J J", "Basic (in H)", "Face value J 1", "(in `)". Map these rupee glyph codes back to ₹, or drop them when they're a column header.
3. **Page furniture read as rows.** The navigation strip "Company Overview Responsible Approach Governance Statutory R…", with the page number read as an amount (0.0265, 0.0307, and "Subtotal 0.0357"). Drop these rows, and never read a page number as a value.
4. **Heading lines kept as rows.** "State Bank of India", "Consolidated Profit and Loss Account for the year ended…", "(000s omitted)", "As at 31.03.2025 As at 31.03.2024", "Schedule No. (Current Year) (Previous Year)", and duplicate "INCOME". Strip anything above the first real line item.
5. **Split rows.**
   - Wrapped labels: "Ventures / Associates" and "(before adjustment for Share in Profit…)" sitting on their own rows.
   - The same item reworded between years, landing as two half-empty rows (e.g. "(Profit)/Loss on sale of Investments in Subsidiaries…" vs "Loss on sale of Investments in Subsidiaries…"; "Basic (in H)" vs "Basic (in `)").
   - Merge these into one row.
6. **Suspicious investing-activity values** for SBI FY2025 (purchase = 1, proceeds = −6.519; the one flagged total). Find the cause.

**B. Add two checks so these can't pass silently again.**
- **Per-share sanity:** EPS ≈ net profit attributable to owners ÷ weighted shares (within a sensible tolerance). Flag anything off by a factor of 10 or more.
- **Junk-row check:** flag rows that are headings, page strips, symbol codes, or repeated words. Count them in the Quality sheet. "0 garbled labels" must not be reported when junk rows exist.

**C. Gold set: a few statements verified completely, row by row (quality over quantity).**
- **Pick about 5 companies × 1 year × 3 statements (consolidated): about 15 statements.** Choose for variety: SBI (bank), one NBFC, one IT company, one manufacturer, one small cap. Propose the list to Harsh.
- **Build the reference copy of each statement:**
  - Use the free Gemini key as an independent second reader of the PDF page images.
  - Compare its reading with the parser's, row by row: every label, every value, every year, and row order.
  - Show Harsh **only the disagreements**, next to the PDF page, so he can decide which is right. This reuses the review screen from item 4 (build that screen's core here).
  - **Capacity:** about 15–25 page images in total, a one-time job, well within the free tier. Check the current free-tier limits before starting. Earlier "busy" errors were server overload (503), not quota, so use the existing retry and backup models.
  - **If Gemini fails twice for a page, use Claude Code itself as the second reader** (read the page image directly; this runs on Harsh's subscription, not a paid API). Only if both fail does Harsh review the whole statement next to the PDF.
  - The regression gold check afterwards is plain file comparison: no AI calls.
- **Save the result** in `tests/gold/` as the fully verified reference for each statement.
- **Add a gold check to the regression suite.** After every code change, compare the full output for these statements with the gold copies. Report missing rows, extra rows, wrong labels and wrong values. Any new difference is a regression.
- **Report the gold result:** e.g. "15 statements, 612 rows: 0 missing, 0 extra, 0 wrong values."

**Rules:** regression suite plus gold check after every fix; no regressions on the 63; log everything in ERROR_LOG and RUN_LOG.
**Done when:** A and B are fixed and checked on SBI and all 63 companies (with the per-share impact reported), the gold set exists and passes, and everything is committed.

### 3.5 Extend the test set from 63 to 100 companies (approved 2026-10-31; do this BEFORE item 4)
- **Pick 37 new companies** that fill sector and size gaps in `tests/companies.json` (e.g. sectors with only 1–2 companies, more mid and small caps). Avoid insurers and bilingual-page PSU banks (out of scope). Write the chosen list and the reasoning into TEST_LOG.
- **Run them once** as a first, unseen run and record the result in RUN_LOG.
- **Fix all recurring failure patterns** on your own, most frequent first. Harsh does not need to approve each individual fix within this item, but report progress at the usual hourly check-ins.
- **Rules:** run the regression suite after every fix, with no regressions allowed on the existing 63. Every fix is logged in ERROR_LOG.
- **Stop when** any of these is true, and leave the remainder flagged:
  - no remaining pattern affects 2+ companies
  - a fix can't be made without a regression
  - a pattern is in an out-of-scope category
- **Disk:** check free space before downloading. If it's tight, ask Harsh before deleting anything.
- **Done when:** 100 companies are in the test set and the baseline, the final run is logged with the 100-company totals (statements OK, verified, matches the report), and the work is committed.

### 4. Sampling-audit screen (approved 2026-10-31)
Build a review screen in the Streamlit app so Harsh can check extracted figures against the PDF by eye.
- **Sample:** 100 random figures from the Excels of all 100 test companies (after item 3.5), spread across companies, statement types, consolidated/standalone and years. Deliberately include all three groups from the arithmetic check: *confirmed*, *can't be checked* (EPS, memo lines etc.) and *flagged*. Use a fixed random seed and save the sample, so it can be re-shown.
- **Screen:** one figure at a time, showing company, statement, year, label and our value, next to the PDF page with the value highlighted. If exact positions aren't stored, render the page and search for the value to highlight it.
- **Buttons:** ✅ correct / ❌ wrong / ? can't tell. On ❌, a quick reason: wrong number, wrong year column, wrong sign, wrong unit, garbled label, other.
- **Progress** is saved after every click, so Harsh can stop and resume.
- **Part B (whole statements):** covered by the gold set in item 3.4. Reuse that screen; no separate build.
- **Report:** overall accuracy and accuracy per group, with a 95% confidence range, plus a list of errors by reason. Save to `tests/audit/` and add a summary to RUN_LOG.
- **Done when:** Harsh can launch the screen from the app, complete a session, and the report is generated. The build must not change any extraction code.

### 5. Fixes after the audit (approved 2026-10-31; starts after Harsh completes item 4)
- **a. Audit findings.** Group the errors Harsh found by pattern and propose fixes, most frequent first, with time estimates. Wait for Harsh's go-ahead on the list.
- **b. Known small fixes:** IRCTC cash-flow label (#77), PI Industries consolidated cash flow (#78), CERA prior-year column (#74), Vinati missing line (#75).
- **c. NSE-first cross-check** in `accuracy_check.py`:
  - report "agrees with NSE XBRL" as the main cross-check figure
  - use Screener only where NSE has no figure, reported separately
  - drop Yahoo, or show it for information only
  - compare NSE filings with the *as originally reported* figure for that year, not the restated one
- **Out of scope here:** insurers (#55, #79), Bank of Baroda bilingual pages (#66), BPCL font (#67). Leave them flagged.
- **Done when:** fixes are in, the regression suite shows no regressions, and logs, baseline and commit are updated.

## Not approved (do not start)
- Paid tier, user accounts, payments
- Hosted web app / FastAPI backend / job queue (PROJECT_PLAN Phase 4)
- Switching downloads from Screener to BSE/NSE (deferred until a commercial phase)
- Batch run on 500 companies (still being discussed)
- Quarterly results
- MCP server
- Standardised chart of accounts, notes to accounts
- Source-page link in each year's column header (e.g. "FY2025 · p.212" opening the PDF at that page). **Agreed idea, queued for after the final tests.** Note: use the PDF page position, not the printed page number

## Questions for chat
*(Claude Code writes here.)*

- **Extend to 10 years (Harsh, 2026-11-05):** after the current workflow is finished, Harsh wants an update where the parser is trained and tested on the last 10 years of data, from 2016 (the tested range today is FY2020–FY2026). PROJECT_PLAN only lists this as "later", so it needs a scope decision and an Approved item. To settle: exact start year (FY2016 or calendar 2016), how many companies to test, what "done" means, and how scanned or old-format reports should be handled. Not started.

- **Who checked the gold set and audit (2026-11-08):** Harsh asked Claude to finish these. Claude decided 5 of the 9 gold items and all 100 audit figures, and Claude was also the gold set's second reader. Each answer is marked. **Answered 2026-11-08 by Harsh: yes, these count as human-verified.**
- **Scale check (2026-11-08):** the arithmetic checks can't see a wrong unit, so DIXON's 100x error counted as OK (#93). Item 5 should consider a check that fails a statement when a year is out of scale with its neighbours or with Screener/NSE. Is that in scope?

- **Reliability redesign (Harsh, 2026-11-08):** Harsh's first priority is 98-99% accuracy in amounts, on companies the tool hasn't seen, without adding more format rules. Proposal from Claude Code: (1) a 20-company holdout set, never used for fixing, as the headline score; (2) guardrails that make each amount prove itself: every printed number accounted for, scale check, tie-outs between statements, same year compared across two reports, NSE/Screener results feeding the status; (3) statements marked OK only with evidence, and each amount shown green, amber or red; (4) rebuild row and column reading on page geometry (alignment, font, indent), replacing text patterns; (5) AI second reader only on pages that fail. Rough estimate 2-3 weeks. To decide: does this replace item 5, is the target per amount on the holdout set, and is the amber/red marking wanted in the Excel? Not started.

- **Merging the new frontend with the engine (Harsh, 2026-11-23):** Harsh asked for a merge plan for the Next.js frontend in `frontend/` (redesign on branch `redesign-v3`, mock data only). Plan: `docs/FRONTEND_MERGE_PLAN.md`. It needs a small local API (FastAPI) around `finxl.run`, which is under **Not approved** ("Hosted web app / FastAPI backend"). To decide: (1) approve a local-only, single-user API, or wait for PROJECT_PLAN Phase 4; (2) order against item 5 and the reliability redesign; (3) which UI features may be hidden for v1 (restated toggle, per-figure second readings, label suggestions); (4) fold `frontend/` into this repo or keep it separate; (5) confirm `redesign-v3` is the version to merge. Phases 1–4 of the plan change no extraction code. Not started.

## Done
*(Claude Code writes here.)*

- **2026-11-04: item 3.5 done (session A, cloud, branch `cloud/a-parser`).** 37 new companies (list and reasons in TEST_LOG, Round 5); 100 in the test set and the baseline. First unseen run: 96.3% OK, 91.3% verified (RUN_LOG #33). Fixes #89–#91; final (RUN_LOG #34–#36): **100 companies 3,944 / 4,031 OK (97.8%), 5,603 / 6,085 verified (92.1%), matches the report 95.7%**; no regressions on the original 63. Stopped by the rule "no pattern affects 2+ companies"; the rest are one-offs (#92, open).

- **2026-11-04: item 3.4 parts A and B done (session A, cloud, branch `cloud/a-parser`).** All six SBI patterns fixed as general rules (ERROR_LOG #80–#86), plus the junk-row and EPS checks (#87). Final run on 63 companies (RUN_LOG #32): **no regressions vs the cloud starting point**, matches the report 95.4% → 95.7%, totals not adding up 1,042 → 977, garbled labels 540 → 511. **EPS unit bug affected 27 of 63 companies.** 14 EPS figures are still flagged (KOTAKBANK, TTKPRESTIG, BAJFINANCE; #88, open). Part C (gold set) is session C's. Baseline updated for 49 companies (the other 14 keep laptop values, because their cloud drops come from Yahoo/download limits only).

- **2026-10-31: Round 4: finish and record (approved item 1).** The final run (58 + 5 new companies) is logged as RUN_LOG #26–#27. ERROR_LOG, TEST_LOG and PROJECT_PLAN are updated. Result: 95.4% of figures match the reports' own totals; 98.4% of the 58 companies' statements OK. Commit `e31d32c`.
- **2026-10-31: Fix stale docs (approved item 3).**
  - README: NTPC FY2024 is now described as rotated pages, fixed (not "needs AI").
  - README also now describes the Quality sheet, the three cross-check sources and the new files.
  - PROJECT_PLAN: Round 4 is marked done, and the old "unreadable" wording is corrected.
  - Commit: see the next commit after `e31d32c`.
- **2026-11-04: Cloud setup + launch (approved item 6).**
  - Repo (Private): https://github.com/hbacausmonaut/docfetcher, with the Claude GitHub App installed on this repo only.
  - Cloud environment: `docfetcher`.
  - Sessions launched at about 16:25 IST:
    - A (Parser): https://claude.ai/code/session_011bos8ipeDTjosjut2HtDSM
    - B (Screens): https://claude.ai/code/session_011bos8hoefHEknKMC462q7h
    - C (Checks): https://claude.ai/code/session_011bos8gyr3zAoNnqd75cMDJ
  - Credit at launch: $100, expiring 13:29 IST on 2026-11-05. It was confirmed drawing down, with the weekly limit unchanged.
  - Deviations from CLOUD_PLAN (recorded under "Launch amendments" there):
    - `GEMINI_API_KEY` not set and Yahoo not added (Harsh's choice).
    - Session A uses batched testing and sets a cloud starting baseline.
    - Sessions were given short prompts pointing at CLOUD_PLAN.md, because the full prompt froze the page.
    - Setup script installs the packages by name, because `requirements.txt` isn't reachable when it runs. Session A started before this fix, so its setup step shows as failed.
    - Hard stop added: all sessions end by 07:30 UTC on 2026-11-05.
- **2026-11-04: Cloud run stopped early (about 17:05 IST).**
  - Why: the credit fell from $99 to $42 in 31 minutes (about $110/hour) and would have run out around 17:20 IST. After that the sessions would have used Harsh's regular limits. All three were told to push and stop; they stopped by themselves at 11:29–11:35 UTC.
  - Credit at the 17:11 IST check: $35 of $100 left. Weekly limit: 44% (43% at launch).
  - Session A: pushed to `cloud/a-parser`, no pull request yet. Item 3.4 A+B bugs fixed and both new checks added, but the full regression stopped at 27 of 63 companies. EPS impact count, logs and baseline not done. Item 3.5: only the 37-company list is ready.
  - Session B: finished; PR #1 (`cloud/b-screens`).
  - Session C: PR #2 (`cloud/c-checks`). Gold has 15 statements with 125 disagreements awaiting Harsh. NSE-first check done. Silver covers 120 statements across 40 companies (batches 1–4).
  - Nothing is merged. CLOUD_PLAN Part 3 hasn't started.
- **2026-11-04: Session A resumed and stopped at about 18:25 IST.** Harsh let it continue on regular usage up to 75% of the weekly limit. It finished its steps and is waiting for a go-ahead; it wasn't stopped by the limit.
  - Item 3.4 A+B: done on `cloud/a-parser`, PR #3 open, not merged. RUN_LOG #32 (63 companies, cloud): 2,515 statements OK, 3,576 / 3,889 verified, 95.7% match the report, no regressions against the cloud start. EPS unit bug affected 27 of 63 companies. Still needed before merging: one full regression on the laptop, where Yahoo is reachable. Open: 14 flagged EPS figures (#88).
  - Item 3.5: **not done.** 37 companies added and the first unseen run logged (RUN_LOG #33): 1,413 / 1,467 statements OK (96.3%), 2,004 / 2,196 verified (91.3%), 95.7% match the report. Fixing the three recurring patterns hasn't started.
  - Usage at the 18:37 IST check: $33 of $100 credit left, weekly limit 47%, current session 14%.
- **2026-11-04: Session A finished item 3.5 at about 20:21 IST** (Harsh's go-ahead at 19:28 IST). On `cloud/a-parser`, PR #3, not merged.
  - Result as reported by session A (RUN_LOG #33–#36, ERROR_LOG #89–#92): 100 companies in the test set and baseline, 3,944 / 4,031 statements OK (97.8%), 5,603 / 6,085 verified (92.1%), 95.7% match the report, no regressions on the original 63. Cloud figures, without Yahoo.
  - Fixed: fake-bold text, scrambled "EQUITY", "LIABLITIES" typo, "generated from operations" wording.
  - Left flagged under the 3.5 stop rule (no pattern affects 2+ companies): one-off missing statements at LUPIN, SRF, MOTHERSON, AUBANK, SHRIRAMFIN (#92).
  - Still needed before merging: one full run on the laptop, where Yahoo and the blocked reports (KOTAKBANK, TECHM, IGL) are reachable. 17 flagged EPS figures not reviewed (#88).
  - Usage at the 20:31 IST check: $29 of $100 credit left, weekly limit 50%, current session 35%.
- **2026-11-05: CLOUD_PLAN Part 3, merge and laptop test.** Merged C, B and A with no conflicts (PRs #1, #2, #3). Gold and silver check added to `tests/regression.py`: gold differences fail, silver differences warn.
  - Laptop run (RUN_LOG #37): 100 companies, 3,962 / 4,049 statements OK (97.9%), 5,686 / 6,097 verified (93.3%, NSE-first), 95.7% match the report.
  - The suite flagged 26 companies, all verified figures. Same Excels under the older check: all at or above the old baseline, so no parser damage (ERROR_LOG P17). Baseline reset to this run.
  - Silver: 84 of 120 statements differ (warnings, not yet looked at). Gold copies don't exist until Harsh finishes the review.
- **2026-11-08: Gold set (3.4 C) and audit (item 4) completed by Claude at Harsh's request.** Gold: 15 copies built, 1 failure (Symphony, #96). Silver sample 30 of 30 correct. Audit: 95 of 100 correct, `tests/audit/report.md`. New open items #93-#98. Item 5 not started: it needs Harsh's go-ahead on the fix list.
- **2026-11-08: All silver differences reviewed.** 551 differences sorted (RUN_LOG #39). New open items #99-#101. Tata Steel check: 40 of 40 figures match the PDF. Item 5 still needs Harsh's go-ahead on the fix list.
