# Test Log

*Every company the extraction engine has been tested on, with issues found and how each was resolved. Last updated: 2026-10-31.*

**How to read this**
- **Statements:** each annual report should give 6 statements (consolidated and standalone × P&L, Balance Sheet, Cash Flow), plus a Revenue Account for insurers.
  - **OK** = found and passed its checks
  - **CHECK** = found but failed a check
  - **MISSING** = not found
  - **N/A** = the report genuinely has none (e.g. no subsidiaries means no consolidated statements). N/A is excluded from the counts.
- **Verified:** revenue / net profit / total assets / operating cash flow per year, confirmed by at least one independent source (NSE XBRL, Screener, Yahoo).
- **Years:** FY2020–FY2026 (comparative columns reach FY2019).
- To reproduce:
  - `python tests/regression.py` re-runs everything and compares against `tests/baseline.json`
  - `python tests/summary.py` prints the table below
  - raw results are in `tests/results/latest.json`

## Summary

| Round | Companies | Statements OK | CHECK | MISSING | Figures verified (outside sources) |
|---|---|---|---|---|---|
| 1 | 7 | 285 / 288 (99.0%) | 1 | 2 | 430 / 444 (96.8%) |
| 2, first run | 31 | 1,019 / 1,200 (85%) | 85 | 96 | 1,126 / 1,728 (65.2%) |
| 2, after fixes | 31 | 1,207 / 1,268 (95.2%) | 32 | 29 | 1,704 / 1,887 (90.3%) |
| 3, first run (20 new companies, never seen) | 20 | 715 / 814 (87.8%) | 57 | 42 | 1,044 / 1,194 (87.4%) |
| After round 3 (all, latest run + HDFCBANK fix) | 58 | 2,340 / 2,381 (98.3%) | 22 | 19 | 3,335 / 3,594 (92.8%) |
| 2026-10-31 full re-run (HDFCBANK fix confirmed + rotated-page fix) | 58 | 2,346 / 2,384 (98.4%) | 21 | 17 | 3,335 / 3,594 (92.8%) |
| **After Round 4 (58 companies)** | **58** | **2,347 / 2,384 (98.4%)** | 23 | 14 | **3,338 / 3,596 (92.8%)** |
| **Round 4, first run (5 new companies, never seen)** | **5** | **179 / 192 (93.2%)** | 11 | 2 | **264 / 303 (87.1%)** |

**New measure from Round 4: "matches the report"** (figures confirmed by the report's own totals). All 63 companies: **193,932 / 203,287 = 95.4%**; 1,060 of 38,040 totals don't add up; 529 labels flagged.

Latest run per round (2026-10-31, after Round 4):

| Round | Statements OK | Verified (outside sources) | Matches the report |
|---|---|---|---|
| 1 (7 companies) | 291 / 291 (100%) | 430 / 444 (96.8%) | 94.4% |
| 2 (31) | 1,247 / 1,273 (98.0%) | 1,749 / 1,912 (91.5%) | 95.5% |
| 3 (20) | 809 / 820 (98.7%) | 1,159 / 1,240 (93.5%) | 95.2% |
| 4 (5 new, first run) | 179 / 192 (93.2%) | 264 / 303 (87.1%) | 97.3% |

Generalisation check: round 4's 5 unseen companies scored 97.3% on "matches the report" at the first attempt (IRCTC's cash-flow wording and two PI Industries cash flows still to fix, ERROR_LOG #77–#78). Earlier: round 2's first run on new companies verified 65% of figures; round 3's first run on 20 *unseen* companies verified 87.4%. The fixes carry over to new companies.

## Latest per-company results (2026-10-31, after Round 4)

**Matches the report** = share of figures confirmed by the report's own arithmetic (part of a total or profit line that adds up as printed). **Totals not adding up** and **garbled labels** are flagged yellow / orange in the Excel.

| Ticker | Sector | Round | Statements OK | Verified | Matches the report | Totals not adding up | Garbled labels |
|---|---|---|---|---|---|---|---|
| HCLTECH | IT services | 1 | 42/42 | 64/64 | 97.3% | 2 | 5 |
| PIDILITIND | Chemicals / adhesives | 1 | 42/42 | 64/64 | 96.2% | 62 | 1 |
| RELIANCE | Conglomerate (O2C, telecom, retail) | 1 | 42/42 | 55/64 | 93.0% | 11 | 3 |
| HDFCBANK | Private bank | 1 | 42/42 | 64/64 | 93.1% | 0 | 1 |
| NTPC | PSU power utility | 1 | 42/42 | 61/64 | 95.2% | 0 | 8 |
| ASIANPAINT | Paints | 1 | 42/42 | 63/64 | 96.2% | 3 | 0 |
| VINATIORGA | Specialty chemicals (mid cap) | 1 | 39/39 | 59/60 | 87.6% | 43 | 30 |
| TCS | IT services | 2 | 42/42 | 61/64 | 92.7% | 34 | 9 |
| INFY | IT services | 2 | 36/36 | 53/64 | 95.7% | 4 | 4 |
| ICICIBANK | Private bank | 2 | 42/42 | 64/64 | 95.8% | 10 | 2 |
| SBIN | PSU bank | 2 | 42/42 | 56/64 | 94.9% | 1 | 10 |
| KOTAKBANK | Private bank | 2 | 42/42 | 63/64 | 94.7% | 0 | 12 |
| BAJFINANCE | NBFC | 2 | 42/42 | 62/64 | 98.4% | 3 | 0 |
| CHOLAFIN | NBFC (vehicle finance) | 2 | 41/42 | 62/63 | 96.8% | 14 | 8 |
| HDFCLIFE | Life insurance | 2 | 47/48 | 32/64 | 90.6% | 26 | 13 |
| ICICIGI | General insurance | 2 | 24/40 | 15/39 | 85.6% | 19 | 16 |
| BAJAJFINSV | Financial holding company | 2 | 42/42 | 58/64 | 96.6% | 16 | 0 |
| HINDUNILVR | FMCG | 2 | 42/42 | 64/64 | 97.6% | 6 | 1 |
| NESTLEIND | FMCG (changed year-end in 2020) | 2 | 24/24 | 21/24 | 89.3% | 30 | 10 |
| ITC | FMCG / conglomerate | 2 | 42/42 | 55/64 | 96.2% | 6 | 0 |
| MARUTI | Automobiles | 2 | 42/42 | 63/64 | 98.4% | 0 | 1 |
| EICHERMOT | Automobiles (2-wheelers, trucks) | 2 | 42/42 | 59/64 | 98.2% | 2 | 10 |
| SUNPHARMA | Pharmaceuticals | 2 | 42/42 | 64/64 | 96.8% | 17 | 4 |
| DRREDDY | Pharmaceuticals | 2 | 39/42 | 62/64 | 96.0% | 5 | 0 |
| TATASTEEL | Metals (steel) | 2 | 42/42 | 55/64 | 95.9% | 57 | 21 |
| HINDALCO | Metals (aluminium, Novelis) | 2 | 42/42 | 58/64 | 96.1% | 18 | 11 |
| ULTRACEMCO | Cement | 2 | 42/42 | 64/64 | 95.6% | 20 | 12 |
| LT | Capital goods / infrastructure | 2 | 42/42 | 58/64 | 94.8% | 55 | 13 |
| ONGC | PSU oil & gas | 2 | 40/42 | 48/62 | 95.1% | 24 | 8 |
| COALINDIA | PSU mining | 2 | 42/42 | 61/64 | 96.5% | 2 | 6 |
| POWERGRID | PSU power transmission | 2 | 36/36 | 60/64 | 96.6% | 6 | 1 |
| BHARTIARTL | Telecom | 2 | 42/42 | 60/64 | 98.0% | 3 | 3 |
| DMART | Retail | 2 | 42/42 | 64/64 | 93.5% | 44 | 4 |
| DLF | Real estate | 2 | 42/42 | 60/64 | 97.9% | 0 | 19 |
| TITAN | Consumer (jewellery, watches) | 2 | 42/42 | 64/64 | 95.2% | 0 | 11 |
| KPRMILL | Textiles (small/mid cap) | 2 | 41/42 | 62/64 | 97.1% | 11 | 29 |
| CERA | Sanitaryware (small cap) | 2 | 39/39 | 60/60 | 88.3% | 37 | 3 |
| SYMPHONY | Consumer durables (small cap) | 2 | 40/42 | 61/64 | 94.5% | 20 | 11 |
| AXISBANK | Private bank | 3 | 36/36 | 56/56 | 94.6% | 0 | 4 |
| BANKBARODA | PSU bank | 3 | 42/42 | 62/64 | 90.3% | 1 | 18 |
| MUTHOOTFIN | NBFC (gold loans) | 3 | 42/42 | 64/64 | 95.7% | 5 | 8 |
| SBILIFE | Life insurance | 3 | 26/28 | 16/32 | 89.2% | 14 | 7 |
| WIPRO | IT services | 3 | 41/42 | 60/64 | 96.6% | 0 | 4 |
| TECHM | IT services | 3 | 42/42 | 63/64 | 97.4% | 3 | 9 |
| HEROMOTOCO | Automobiles (2-wheelers) | 3 | 42/42 | 64/64 | 94.5% | 56 | 13 |
| CIPLA | Pharmaceuticals | 3 | 42/42 | 57/64 | 94.7% | 9 | 7 |
| JSWSTEEL | Metals (steel) | 3 | 42/42 | 61/64 | 95.8% | 60 | 5 |
| VEDL | Metals & mining | 3 | 42/42 | 49/64 | 96.3% | 36 | 7 |
| GRASIM | Holding conglomerate | 3 | 42/42 | 59/64 | 95.5% | 58 | 2 |
| ADANIPORTS | Ports / infrastructure | 3 | 42/42 | 61/64 | 97.9% | 8 | 3 |
| BPCL | PSU oil marketing | 3 | 40/42 | 55/64 | 90.6% | 47 | 48 |
| TATAPOWER | Power utility | 3 | 38/42 | 54/64 | 94.4% | 41 | 1 |
| APOLLOHOSP | Healthcare | 3 | 42/42 | 64/64 | 92.5% | 41 | 4 |
| INDIGO | Aviation | 3 | 42/42 | 62/64 | 96.6% | 0 | 6 |
| BRITANNIA | FMCG | 3 | 42/42 | 63/64 | 95.7% | 28 | 2 |
| HAVELLS | Electricals | 3 | 42/42 | 64/64 | 96.4% | 15 | 4 |
| TTKPRESTIG | Kitchen appliances (small cap) | 3 | 40/42 | 64/64 | 96.2% | 13 | 18 |
| ASTRAL | Pipes (mid cap) | 3 | 42/42 | 61/64 | 97.3% | 2 | 9 |
| DIXON | Electronics manufacturing | 4 | 42/42 | 48/64 | 97.9% | 4 | 20 |
| PIIND | Agrochemicals | 4 | 40/42 | 63/63 | 96.5% | 0 | 0 |
| IRCTC | PSU railway services | 4 | 20/30 | 36/48 | 96.6% | 0 | 9 |
| TRENT | Fashion retail | 4 | 35/36 | 57/64 | 96.9% | 0 | 17 |
| INDHOTEL | Hotels | 4 | 42/42 | 60/64 | 98.1% | 8 | 4 |

*The per-company notes table below was written after round 2. Its round-1/2 notes still apply; round-3 findings are in the issue log (#36–#54).*

## Companies

| # | Ticker | Sector | Round | Statements OK | Verified | Notes |
|---|---|---|---|---|---|---|
| 1 | HCLTECH | IT services | 1 | 42/42 | 64/64 | Shifted-text fonts (`6WDQGDORQH` = Standalone), decoded. Screener's consolidated total assets are reclassified (the PDF is correct). |
| 2 | PIDILITIND | Chemicals / adhesives | 1 | 42/42 | 64/64 | 2-up landscape spreads; image headings; FY2022 restated after a merger. |
| 3 | RELIANCE | Conglomerate | 1 | 42/42 | 55/64 | All 9 unverified = revenue definition (Screener/Yahoo net figure vs the PDF's "Revenue from Operations"). |
| 4 | HDFCBANK | Private bank | 1 | 42/42 | 64/64 | Bank format; ₹ '000; letter-spaced headings. |
| 5 | NTPC | PSU power | 1 | 42/42 | 61/64 | FY2024 pages are stored rotated 270°; fixed 2026-10-31 (#15), all 6 statements now OK. FY2023 cash-flow differences depend on that report (restated there). |
| 6 | ASIANPAINT | Paints | 1 | 42/42 | 63/64 | Capitals-shifted font decoded via the report's vocabulary; revenue total computed from its parts. 1 unverified = FY2020 restated cash flow. |
| 7 | VINATIORGA | Specialty chemicals | 1 | 39/39 | 59/60 | FY2020 has no consolidated statements (N/A). FY2022 total assets restated in the FY2024 report. |
| 8 | TCS | IT services | 2 | 41/42 | 61/64 | Balance sheet split over 3 half-pages (heading repeated): fixed. FY2021 standalone P&L has a few blank rows (open). |
| 9 | INFY | IT services | 2 | 36/36 | 53/64 | No consolidated/standalone split in some years (N/A). Unverified = Screener total-assets reclassification (~1%). |
| 10 | ICICIBANK | Private bank | 2 | 42/42 | 64/64 | |
| 11 | SBIN | PSU bank | 2 | 42/42 | 56/64 | "(000s omitted)" unit fixed; schedules after the balance sheet were being read: fixed. |
| 12 | KOTAKBANK | Private bank | 2 | 39/42 | 61/62 | Navigation band says "Consolidated…" on every page; standalone headings unlabelled: fixed. FY2024/25 P&L not found (open). |
| 13 | BAJFINANCE | NBFC | 2 | 42/42 | 62/64 | |
| 14 | CHOLAFIN | NBFC | 2 | 38/42 | 59/60 | FY2020/21 balance sheets not found (open). |
| 15 | HDFCLIFE | Life insurance | 2 | 40/43 | 24/50 | Insurer format added (Revenue Account, Receipts & Payments). **Screener's FY2025 link is a 42-page excerpt, not the full report.** Revenue checks don't map to insurer statements yet (open). |
| 16 | ICICIGI | General insurance | 2 | 23/40 | 16/37 | Partial: several statements not found / blank rows (open, insurer format). |
| 17 | BAJAJFINSV | Financial holding | 2 | 42/42 | 58/64 | NBFC layout ("Liabilities and Equity", bare "Total" lines). "Profit for the year" printed *after* the minority line is the owners' share: handled. |
| 18 | HINDUNILVR | FMCG | 2 | 42/42 | 64/64 | A 3-year highlights page was taken as the P&L: fixed (statements must cluster together). |
| 19 | NESTLEIND | FMCG | 2 | 24/24 | 21/24 | **December year-end until 2023, then a 15-month period to Mar 2025.** Columns are labelled "Mar YYYY" even for December years (open). No consolidated statements before FY2025 (N/A). |
| 20 | ITC | FMCG / conglomerate | 2 | 40/42 | 54/63 | Revenue is gross of excise (definition). FY2022/23 consolidated cash flow not found (open). |
| 21 | MARUTI | Automobiles | 2 | 42/42 | 63/64 | ₹ million (rupee sign as an odd glyph); a "Page No." column taken as amounts; shifted dates (`PNKMPKOMOQ` = 31.03.2024). All fixed. |
| 22 | EICHERMOT | Automobiles | 2 | 42/42 | 52/64 | Report also contains the subsidiary VECV's consolidated statements, which were picked by mistake (fixed for FY2024+; older years still open). |
| 23 | SUNPHARMA | Pharma | 2 | 42/42 | 62/64 | |
| 24 | DRREDDY | Pharma | 2 | 39/42 | 62/64 | "Indian Rupees millions" (10× off): fixed. FY2021 partially found (open). |
| 25 | TATASTEEL | Metals | 2 | 42/42 | 55/64 | FY2021 standalone restated after the Tata Steel BSL merger (restatement). |
| 26 | HINDALCO | Metals | 2 | 42/42 | 58/64 | Balance sheet totals printed as bare numbers with no label: inferred. |
| 27 | ULTRACEMCO | Cement | 2 | 36/42 | 59/64 | Items/totals/prior-year column layout: fixed. FY2020/21 balance sheets and FY2024 cash flow still CHECK (open). |
| 28 | LT | Capital goods | 2 | 42/42 | 58/64 | A highlights page was taken as the P&L, and the year in the title line was read as a column header (values shifted a year): both fixed. |
| 29 | ONGC | PSU oil & gas | 2 | 39/42 | 48/63 | Revenue gross of levies (definition). FY2020/21 standalone cash flow not parsed (open). |
| 30 | COALINDIA | PSU mining | 2 | 40/42 | 61/63 | FY2023/24 consolidated cash flow not found (open). |
| 31 | POWERGRID | PSU power | 2 | 36/36 | 60/64 | |
| 32 | BHARTIARTL | Telecom | 2 | 36/42 | 54/62 | Standalone P&L net-profit label not recognised (open). |
| 33 | DMART | Retail | 2 | 42/42 | 64/64 | |
| 34 | DLF | Real estate | 2 | 38/42 | 57/63 | FY2021/22 standalone balance sheet totals (open). |
| 35 | TITAN | Consumer | 2 | 42/42 | 57/64 | Shifted roman numerals ("ufK&" = "XI.") glued rows together: fixed. |
| 36 | KPRMILL | Textiles | 2 | 41/42 | 62/64 | FY2022 consolidated balance sheet doesn't tie (open). |
| 37 | CERA | Sanitaryware | 2 | 39/39 | 60/60 | |
| 38 | SYMPHONY | Consumer durables | 2 | 36/42 | 59/64 | Cash flow operating-total label not recognised in 6 statements (open). |

## Issue log
Moved to [ERROR_LOG.md](ERROR_LOG.md) (every error, its cause and its fix). Test runs are in [RUN_LOG.md](RUN_LOG.md).

## Known differences that are *not* errors
- **Restatements:** later reports revise prior-year numbers. Our default is the latest restated figure. NSE XBRL (as filed that year) and sometimes Screener show the original.
- **Revenue definitions:** Reliance, ITC and ONGC report "Revenue from Operations" gross of excise duty/levies. Screener and Yahoo show a net figure.
- **Total assets:** Screener reclassifies some items (HCL, Infosys, Eicher), so its totals can differ by ~1% from the printed balance sheet.
- **Yahoo:** its net income = owners' share, its banks use different definitions, and it covers only about 4 years.
- **NSE XBRL coverage:**
  - annual results XBRL has P&L lines from about FY2018; balance sheet/cash flow appear only in some filings
  - FY2025+ filings moved to NSE's "Integrated Filing" system and aren't read yet

## Round 5 (item 3.5): 37 new companies, chosen 2026-11-04

**Why these:** fill sectors that had only 1–2 companies, and add more mid and small caps. Insurers and bilingual-page PSU banks are left out (out of scope).

| Gap filled | Companies |
|---|---|
| Banks beyond the large ones (private mid cap, small finance bank) | FEDERALBNK, AUBANK |
| More NBFC / financial formats (vehicle/MSME, housing finance, asset manager, depository) | SHRIRAMFIN, LICHSGFIN, HDFCAMC, CDSL |
| IT mid / small caps | PERSISTENT, KPITTECH, MASTEK |
| Autos and auto parts (2-/3-wheelers, components, tyres) | BAJAJ-AUTO, MOTHERSON, BALKRISIND |
| Pharma mid caps | LUPIN, AJANTPHARM |
| FMCG beyond the large three | DABUR, MARICO |
| Cement (had 1) | SHREECEM |
| Chemicals (large, mid, small) | SRF, DEEPAKNTR, FINEORG |
| Capital goods (had 1) | SIEMENS, CUMMINSIND, BEL (PSU, English report) |
| Consumer durables / electricals | VOLTAS, CROMPTON |
| Real estate (had 1) | GODREJPROP, OBEROIRLTY |
| Healthcare (had 1): hospitals, diagnostics | MAXHEALTH, LALPATHLAB |
| Logistics (new sector) | BLUEDART |
| Gas (new sector): city gas, LNG | IGL, PETRONET |
| Private power utility | TORNTPOWER |
| Apparel, tiles, footwear (mid / small caps) | PAGEIND, KAJARIACER, RELAXO |
| Media (new sector) | SUNTV |

Notes from the cloud download: IGL's FY2024 report is hosted on iglonline.net, which the cloud network blocks. CDSL has 3 report links that aren't PDFs. SIEMENS lists 6 reports (it changed year-end).

**Round 5 results:** first run 1,413 / 1,467 statements OK (96.3%), 2,004 / 2,196 verified (91.3%), matches the report 95.7%. After fixes #89–#91: 1,429 / 1,467 OK, 2,027 / 2,196 verified. **All 100 companies:** 3,944 / 4,031 statements OK (97.8%), 5,603 / 6,085 verified (92.1%), matches the report 95.7% (cloud run: no Yahoo). Per-company figures: `tests/results/latest.json`.
