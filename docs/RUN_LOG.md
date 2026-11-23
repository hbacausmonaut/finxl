# Run Log

*Every test run: what was run, the result, and what improved. Newest day at the bottom. Last updated: 2026-10-31.*

**How to read the numbers**
- **Statements OK:** statements found that passed their checks, out of all statements expected. N/A ones (e.g. no subsidiaries) are left out. A company has about 42 per 7 years.
- **Verified:** headline figures (revenue, net profit, total assets, operating cash flow per year) that at least one outside source (NSE XBRL, Screener, Yahoo) agrees with within 0.5%.
- **Important limit:** both numbers check the *headline* figures only, not every line item. From Round 4 we add **"matches the report"**: the share of all rows confirmed by the report's own arithmetic (items add up to their totals). See P7 in [ERROR_LOG.md](ERROR_LOG.md).
- The raw result of each run is saved in `tests/results/run_<date>_<time>.json`.

---

## Day 1: 2026-10-30 (afternoon to midnight)

### Before testing: building the tool (afternoon, no saved runs)
- **Built:**
  - `finxl.py`: download → find statements → read them → merge years → Excel
  - `ar_extract.py`: the PDF reader
  - `llm_extract.py`: AI fallback, built but not tried
  - `app.py`: the Streamlit app
- **Tried on:** the first 5–7 companies by hand. Fixes for spreads, image headings, coded fonts and split numbers came from these (ERROR_LOG #1–#16).
- **Added:**
  - Git
  - the regression suite (`tests/regression.py`)
  - the 3-source cross-check (`accuracy_check.py`)
  - `PROJECT_PLAN.md` and `TEST_LOG.md`

### Run table

*Per-run attribution of individual fixes wasn't recorded on Day 1 (ERROR_LOG P10), so the fixes listed for runs 3–9 are an approximate grouping, reconstructed from the issue log and commits.*

| # | Time | What was run | Statements OK | Verified | What changed before this run / what it showed |
|---|---|---|---|---|---|
| 1 | 19:16 | Round 1: 7 companies (IT, chemicals, conglomerate, bank, PSU, paints, mid cap) | 285 / 294 (96.9%) | 430 / 444 (96.8%) | First saved baseline after the build fixes (#1–#16) |
| 2 | 19:30 | **Round 2, first run: 29 new companies, never seen before** | 1,019 / 1,200 (84.9%) | 1,126 / 1,728 (65.2%) | Pure test of unseen companies: showed many new formats (banks, NBFCs, insurers, PSUs, units in millions) |
| 3 | 19:41 | Round 2 companies after the first fixes | 1,102 / 1,248 (88.3%) | 1,502 / 1,794 (83.7%) | Units, consolidated/standalone detection, highlights pages (#17, #19, #20) |
| 4 | 19:46 | Rounds 1 + 2 together: 38 companies | 1,460 / 1,608 (90.8%) | 1,977 / 2,313 (85.5%) | Insurer format, bare-number totals (#21, #22) |
| 5 | 19:56 | 38 companies | 1,487 / 1,608 (92.5%) | 2,041 / 2,331 (87.6%) | Column-assignment and schedule fixes (#23–#27) |
| 6 | 20:00 | 38 companies | 1,488 / 1,556 (95.6%) | 2,042 / 2,331 (87.6%) | Reports with no consolidated statements counted as N/A, not failures (#32) |
| 7 | 20:07 | 38 companies | 1,488 / 1,556 (95.6%) | 2,103 / 2,331 (90.2%) | One rule for "net profit" (#30) |
| 8 | 20:14 | 38 companies, **end of Round 2** | 1,492 / 1,556 (95.9%) | 2,134 / 2,331 (91.5%) | Page-number columns, reconciliation tables, title-year shift (#28, #29, #31) |
| 9 | 21:23 | 38 companies after Round 3 fixes | 1,524 / 1,561 (97.6%) | 2,162 / 2,346 (92.2%) | Fixed most of the open items (#36–#43): heading variants, loss years, December year-ends, Eicher subsidiary |
| 10 | 21:38 | **Round 3, first run: 20 new companies, never seen** | 715 / 814 (87.8%) | 1,044 / 1,194 (87.4%) | Generalisation test: unseen companies scored 87% vs 65% in Round 2, so the fixes carry over |
| 11 | 22:45 | All 58 companies | 2,332 / 2,384 (97.8%) | 3,280 / 3,596 (91.2%) | Round 3 fixes (#44–#52). **The suite caught 4 regressions** (Titan, Sun Pharma, ONGC, CERA), all fixed (#53) |
| 12 | 23:22 | All 58 companies, **end of Round 3** | 2,332 / 2,381 (97.9%) | 3,329 / 3,588 (92.8%) | Caught a new regression: HDFC Bank 42 → 34 (#54) |
| 13 | 23:29 | 4 companies: HDFC Bank fix check (HDFCBANK, CERA, SBIN, KOTAKBANK) | 165 / 165 (100%) | 243 / 252 (96.4%) | HDFC Bank back to 42/42 and the others unchanged |

### Day 1 total
- **Companies:** 0 → 58 tested across ~25 sectors (IT, banks, NBFCs, insurers, PSUs, FMCG, autos, pharma, metals, cement, power, telecom, real estate, retail, small caps).
- **Errors:** 54 found and logged (ERROR_LOG #1–#54), about 50 fixed.
- **Score on companies being worked on:** statements OK 85% → 97.9%; verified 65% → 92.8%.
- **Score on unseen companies (first run):** 65% (Round 2) → 87% (Round 3).
- **Safety net:** 5 regressions caught by the suite before they reached you.
- **Tools built:** the extraction engine, the Excel output, the app, the regression suite, the 3-source cross-check, Git, and the plan and test-log docs.
- **Not done:** line-by-line checks of every row (see P7). The headline checks passed while VBL's middle rows were garbled.

---

## Day 2: 2026-10-31

| # | Time | What was run | Statements OK | Verified | What changed / what it showed |
|---|---|---|---|---|---|
| 14 | ~11:00 | AI fallback live test: NTPC FY2024 with the free Gemini key | — | — | Key works; Google's free tier was busy (503s, 2–3 min replies); old model name retired (#57). Showed the AI wasn't the answer: the PDF pages were rotated (#15) |
| 15 | ~11:20 | NTPC FY2024, parser only, after the rotation fix | 6 / 6 | Figures match NTPC's published FY24 results | Rotated pages are now turned upright on load. No AI needed |
| 16 | 11:58 | All 58 companies | **2,346 / 2,384 (98.4%)** | **3,335 / 3,594 (92.8%)** | Confirms the HDFC Bank fix and the rotation fix; NTPC 36 → 42 OK. One flagged change (ICICIGI verified 16 → 15, insurer definition #55), accepted |

### Round 4 (after Harsh's go-ahead, late morning)

*Exact times for runs 17–23 weren't recorded (short development runs); from run 24 on, times are noted when each run starts.*

| # | Time | What was run | Result | What changed / what it showed |
|---|---|---|---|---|
| 17 | – | VBL FY2021–2025, all 6 statements, label scan | Before: 5–18 garbled labels per statement ("=J=", "Q^", "$Total", "OVKRSFF"). After the per-font fix: 0 | Coded-font decision per font, not per word (#58) |
| 18 | – | Same, checking values | Found **silent wrong numbers**: closing cash read as **14** (note number), interest paid read as **47.24** (amount inside the label sentence) | Amount rules: brackets must pair up, a number followed by words or preceded by ₹ is text; wrapped-bracket joining (#59, #61) |
| 19 | – | 58 companies (regression, with the reading fixes) | OK 2,333 / 2,381 (was 2,346); verified 3,335 / 3,595. **Suite caught regressions in 5 companies**: Bank of Baroda 42→36, ICICI Lombard 25→22, Sun Pharma 42→40, BPCL 38→36, HCL Tech 1 figure | Cause: the new per-font rule was fooled by fonts that put an invisible bullet before every label (Sun Pharma), by fonts used for both coded and normal text (Bank of Baroda), and it shifted real spaces (BPCL). Fixed (#58 refined), re-checked on the affected reports |
| 20 | – | New arithmetic checks on VBL, HCL Tech, HDFC Bank, NTPC (FY2024) | 92–96% of figures confirmed by each report's own totals | First version of `quality.py`. Failures investigated one by one (next row) |
| 21 | – | Checks on 8 companies (FY2023) | Real reading errors caught: NTPC/Maruti page numbers read as amounts (#62); SBI amounts lost to a hidden symbol character (#63); SBI signature block read as rows (#64); Bank of Baroda garbled labels (#65). Also checker false alarms (Titan 3+1=4 coincidence; HCL "Net change in trade receivables" taken as a total) | Fixed the reading errors; checker made stricter |
| 22 | – | VBL end-to-end Excel (FY2019–2025) | **97.4% of 2,853 figures confirmed by the reports' own totals; 0 of 536 totals failing; 0 garbled labels** | New Quality sheet, yellow/orange flags |
| 23 | – | Regressed reports re-tested (Sun Pharma 2023, BPCL 2022, Bank of Baroda 2023/25, HCL 2024, VBL 2021) | All statements found again; VBL still clean. BPCL FY2022 found but only ~40% confirmed: an unknown font encoding, now **flagged** instead of passing silently (#67) | Label check also found HCL's "ff" ligature misread ("Eႇect" = "Effect", #68) |
| 24 | ~13:30 | 58 companies, all Round 4 changes | OK 2,341 / 2,384; verified 3,335 / 3,595; **first "matches the report": 94.9% (178,296 / 187,950 figures)**; 1,134 / 35,022 totals not adding up; 485 garbled labels. **Regressions in 4 companies**: HCL Tech FY2020 (42→40), Infosys FY2022 (36→34), ICICI Lombard (25→23), Sun Pharma FY2022 (42→41) | Causes: (a) coded fonts that also carry genuine capitals ("EQUITY" shifted to "bnrfqv"); (b) the new SBI footer phrase "…reported using the indirect method" sits at the *top* of Infosys's cash flow; (c) Sun Pharma's "capitals-as-lowercase" code relied on spaces being shifted. All fixed (#70–#72) and re-checked; ICICI Lombard FY2023 is a wrong-page case in both versions (#55) |
| 25 | 14:13 | 58 companies, after the #70–#72 fixes | OK 2,346 / 2,384 (MISSING 17 → 14); verified 3,338 / 3,596; **matches the report 95.0%** (178,994 / 188,388); 1,122 totals not adding up; 480 garbled labels. Only flag: ICICI Lombard 25 → 23 | ICICI Lombard: the new rules correctly stopped reading amounts inside footnote sentences, which then counted as blank rows. Fix: drop footnote sentences before the blank-row check; insurer "The above … Receipts & Payments Account" ends the statement (#76). Its cash flow now 100% confirmed |
| 26 | 14:43 | **Final run: 58 companies + 5 new, never-seen companies** (Dixon, PI Industries, IRCTC, Trent, Indian Hotels) | **58 companies: OK 2,347 / 2,384 (98.4%, best so far), MISSING 14 (was 17), verified 3,338 / 3,596.** **5 new companies (first run): OK 179 / 192 (93.2%), verified 264 / 303 (87.1%), matches the report 97.3%.** **All 63: matches the report 95.4% (193,932 / 203,287 figures)**; 1,060 of 38,040 totals don't add up; 529 labels flagged. Only flag vs baseline: ICICI Lombard 25 → 24 (insurer format, #79) | New issues from the unseen companies: IRCTC cash-flow wording (#77), PI Industries consolidated cash flow (#78). Baseline saved for 63 companies |
| 27 | 15:18 | VBL FY2020–2026 Excel, final code (saved in `VBL\`) | **97.4% of figures confirmed by the reports' own totals; 0 totals failing; 1 label flagged** (a typo in VBL's own report: "exisiting") | The Excel Harsh tested on Day 1, now clean |

### Day 2 total
- **NTPC FY2024 rescued** (marked "unreadable" on Day 1; really rotated pages).
- **AI fallback** connected with a free Gemini key; automatic retry and backup models.
- **New logs:** `RUN_LOG.md` (this file) and `ERROR_LOG.md`, plus 10 process mistakes recorded.
- **Round 4 complete:**
  - VBL garbled text fixed
  - silent wrong numbers fixed (note numbers, page numbers, amounts inside sentences, lost amounts)
  - new **arithmetic and label checks** on every statement, shown in Excel (yellow / orange cells, Quality sheet)
- **New measure "matches the report": 95.4%** of all figures across 63 companies are confirmed by the reports' own totals. The remaining ~4.6% are mostly figures that sit outside any total (EPS, memo lines) plus the flagged problems.
- **Regressions:** the suite caught 3 rounds of them (6 different companies) during the day; all fixed except ICICI Lombard (insurer, kept open).
- **Errors logged:** 23 (#57–#79); 16 fixed, 7 open.
- **Test runs:** 14 (#14–#27).

---

## Day 3: 2026-11-04 (cloud session A, item 3.4 A+B)

*Runs on the cloud machine: Yahoo isn't reachable there, and two reports (KOTAKBANK, TECHM, one year each) sit on hosts the cloud blocks. So the comparison point is the cloud run of the old code (#28), not the laptop baseline.*

| # | Time (UTC) | What was run | Statements OK | Verified | What changed / what it showed |
|---|---|---|---|---|---|
| 28 | 10:58 | 63 companies, old code (cloud starting point) | 2,514 / 2,564 | 3,570 / 3,889 | Matches the report 95.4% (193,248 / 202,504); 1,042 totals not adding up; 540 garbled labels. Drops vs the laptop baseline are Yahoo-only figures and the 2 unreachable reports. Saved as `tests/results/cloud_start_20261104.json` |
| 29 | ~11:25 | SBIN FY2020–26, all statements, after the SBI fixes (#80–#86) | 42 / 42 | 56 / 64 | Totals not adding up 1 → 0; EPS ₹39.64–91.16 (was 0.0040–0.0091); no page strips, headings or "J J" rows left |
| 30 | 11:46 | 63 companies, new code (interrupted run at 11:35 discarded) | 2,515 | 3,570 | Matches the report **95.7%**; totals not adding up 1,042 → 977; garbled labels 540 → 511; new counts: 55 junk rows, 14 / 812 EPS figures flagged. **Regressions in 4 companies** (ASTRAL, BPCL, GRASIM, INDIGO: verified totals went missing for one early year), caused by the strict one-report-per-year rule (#81) |
| 31 | ~12:45 | ASTRAL, BPCL, GRASIM, INDIGO, SBIN after refining #81 | all OK | all back | Rule now applies only to well-read columns, and an older report may fill a total the newer one lost |
| 32 | ~12:50 | 63 companies, final code | **2,515** | **3,576 / 3,889** | **No regressions vs #28.** Matches the report **95.7% (193,675 / 202,391)**; 977 / 37,720 totals not adding up; 511 garbled labels; 55 junk rows; EPS flagged 14 / 813 (KOTAKBANK 5, TTKPRESTIG 8, BAJFINANCE 1, to look at). **EPS unit bug: 27 of 63 companies affected** (every company reporting in ₹ lakh, million or thousand). Baseline updated for the 49 companies that didn't drop for cloud-only reasons; the other 14 keep their laptop values |

### Item 3.5: round 5, first (unseen) run

| # | Time (UTC) | What was run | Statements OK | Verified | What changed / what it showed |
|---|---|---|---|---|---|
| 33 | ~13:05 | **37 new companies, first run, code from #32** (list and reasons in TEST_LOG, Round 5) | **1,413 / 1,467 (96.3%)**, CHECK 36, MISSING 18 | **2,004 / 2,196 (91.3%)** | **Matches the report 95.7%** (105,004 / 109,765); 629 / 21,754 totals not adding up; 396 garbled labels; 28 junk rows; EPS flagged 3 / 421. Best first run on unseen companies so far (round 4: 93.2% OK, 87.1% verified). Recurring patterns, most frequent first: (1) balance-sheet totals not found, 17 statements in 5 companies (AUBANK, FEDERALBNK: bank formats; CROMPTON, CUMMINSIND, SUNTV); (2) operating cash-flow row not found, 13 statements in 4 companies (KAJARIACER, MOTHERSON, SHRIRAMFIN, SRF); (3) statement not found, 18 in 6 companies (AUBANK, CUMMINSIND, FEDERALBNK, LUPIN, MOTHERSON, SRF). Results: `tests/results/round5_first_run_20261104.json` |
| 34 | ~13:55 | 5 affected companies after round-5 fixes #89–#91 | CUMMINSIND 36→38, KAJARIACER 35→42, SUNTV 38→42, CROMPTON 41→42, MOTHERSON 34→36 | CUMMINSIND 48→60, KAJARIACER 53→60 | First try lost CUMMINSIND's lakh unit (fake-bold letters split); fixed before the full run |
| 35 | 14:08 | **All 100 companies** | 3,944 / 4,031 | 5,596 / 6,085 | **Regressions in 2**: HINDALCO and LICHSGFIN operating cash flow, because the wider "net cash … operations" match (#90) picked other lines. Fixed: "operating" lines first, "operations" only as a fallback, never "continuing / discontinued" |
| 36 | 14:47 | HINDALCO, LICHSGFIN, KAJARIACER, MOTHERSON after that fix | all back to their earlier values | | Merged into #35 for the final figures |
| | | **Final, 100 companies (item 3.5 done)** | **3,944 / 4,031 (97.8%)**, CHECK 53, MISSING 34 | **5,603 / 6,085 (92.1%)** | **Matches the report 95.7% (298,776 / 312,179)**; 1,598 / 59,494 totals not adding up; 902 garbled labels; 76 junk rows; EPS flagged 17 / 1,234. Original 63: no regressions vs #32. Round 5 (37): OK 1,413 → 1,429, verified 2,004 → 2,027. **Stopped by the rule "no remaining pattern affects 2+ companies"**: what's left is one-off (LUPIN FY2020 and SRF FY2026 garbled fonts; MOTHERSON standalone pages labelled consolidated; AUBANK bank layout and highlights page; SHRIRAMFIN FY2026 wrong page; CUMMINSIND FY2020 balance sheet). Baseline now has all 100 companies |

## Day 4: 2026-11-05 (laptop, CLOUD_PLAN Part 3)

*First run of the merged code (sessions C, B and A together), and the first on the laptop, where Yahoo and the reports blocked from the cloud are reachable. Merged code includes session C's stricter NSE-first accuracy check, so "Verified" is not directly comparable with earlier runs.*

| # | Time (IST) | What was run | Statements OK | Verified | What changed / what it showed |
|---|---|---|---|---|---|
| 37 | 15:37-16:35 | **All 100 companies, merged code, 5 workers, with the gold and silver check** | **3,962 / 4,049 (97.9%)**, CHECK 53, MISSING 34 | **5,686 / 6,097 (93.3%)**, NSE-first check | **Matches the report 95.7% (299,898 / 313,419)**; 1,622 / 59,783 totals not adding up; 898 garbled labels; 76 junk rows; EPS flagged 17 / 1,237. Silver: 120 statements, 84 with differences (warnings). Gold: no copies yet. The suite listed 26 companies as regressions, all verified figures only. Rescoring the same Excels with session A's earlier check gave at least the old baseline in all 26, so these came from the stricter check, not the parser. Baseline reset to this run (ERROR_LOG P17). Results: `tests/results/latest.json`, `tests/results/gold_latest.json` |
| 38 | 11-08 | **Gold set finished, silver sample and audit checked by Claude against the PDFs** | | | Gold: 15 statements, 737 rows, 9 disagreements (4 decided by Harsh, 5 by Claude); check gives 1 failure, Symphony balance sheet (#96). Silver sample: 30 of 30 correct. Silver value differences: all 7 traced, parser wrong or misplaced in each (#97, #98). Audit: 95 of 100 correct; 3 wrong figures (#93, #94), 2 garbled labels (#95). Report: `tests/audit/report.md`. |
| 39 | 11-08 | **All 551 silver differences reviewed; Tata Steel check across years** | | | Labels 232 (figures fine). Missing 61: 49 headings, 12 with figures (10 real gaps, 2 misplaced). Extra 251: 110 without figures, 141 with figures, all printed in the report: 57 memo rows, 75 reconciliation rows under wrong columns (#99), 9 years read as figures (#101). 7 of 120 statements have a wrong or missing figure on the statement itself; 36 of 120 match on every label and row. Tata Steel: 40 of 40 sampled figures across FY2019-26 match the PDF, plus 305 of 305 FY2026 figures against the AI reading. Its Screener differences are figures printed in the report. Saved: `tests/gold/silver_differences.json`, `tests/audit/tata_check.json`. |
