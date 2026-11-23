# FinXL V1 beta: build log

Live tracker for the V1 beta build. Plan approved by Harsh on 2026-11-23 (full plan below).
Times are IST. Each "run" is one 5-hour usage window: afternoon (until 6 PM), evening (6–11 PM), night (11 PM–4 AM).

## Schedule and ETAs

| Phase | What | Run | ETA | Status |
|---|---|---|---|---|
| 1 | Copy into `FinXL/` layout, git, dev-tool paths | Afternoon | done | ✅ commit `9857551` (3-company regression check running) |
| 2 | Engine additions: footing groups, EPS expected value, summary picks, as-reported values, corrected-cell marks, vocab-cache fix | Afternoon | done | ✅ `c74bf8e` |
| 2b | Full 100-company regression + gold check on the changed engine (background) | Afternoon | done | ✅ no parser regressions (RUN_LOG #40–#41) |
| 3 | FastAPI service: runs queue + live progress, run.json, library, Excel download, PDF page images, cross-check, config | Afternoon | done | ✅ `7fc04f8`, smoke-tested with a real HCLTECH run |
| 4 | Second reading (page re-read, no AI) + tests | Afternoon | done | ✅ `7fc04f8`, `dev/tests/test_second_reading.py` passes |
| 5 | Frontend on real data: API client, statements from engine rows, Beta tag, static export, company list | Afternoon | done | ✅ `d4f0fab`, checked in the browser with real runs |
| 6 | Deploy package: Dockerfile, compose, `.env.example`, DEPLOY.md, README | Afternoon | done | ✅ `b0c07e3` (Docker build untested: no Docker on the laptop) |
| 7 | End-to-end verification (real runs, browser checks, Docker), records in CHAT_HANDOFF / PROJECT_PLAN | Afternoon → evening | records done; remaining checks ~7:30 PM | in progress |

**Now expected: finished in the evening run (about 7:30 PM)**, well ahead of the 1 AM estimate. Left for the evening run: dark mode and phone-width checks, an Excel download with a correction opened, a second-reading proposal shown in the UI, a lint pass. A Docker build needs Docker Desktop (Harsh's call) or the host itself.

## Progress notes
- 2026-11-23 ~3:20 PM: Phase 1 done. `Y:\Claude Projects\FinXL` created: `engine/` (9 runtime files), `web/` (redesign-v3 frontend), `dev/` (regression, gold, audit tools + retired Streamlit), `docs/`. Dev scripts get one line that adds `engine/` to the import path; no engine code changed. DocFetcher untouched.

- ~3:25 PM: Phase 1 check: 3-company regression on the moved engine, no regressions vs baseline, gold check 0 failures.
- ~3:25 PM: Phase 2 done. HCLTECH smoke test: groups, own/newest values, summary picks and a marked Excel all work.
- ~3:40 PM: Phase 3 done. `api/` (settings, storage, jobs, serialize, main). Local venv `FinXL/.venv` (PyMuPDF pinned 1.28.0). Real run through the API: stages and years stream live, run.json, page PNG, library, corrected Excel, run reuse, bad-ticker rejection all verified.
- ~3:50 PM: Phase 4 done. Second reading proposes a figure only when a number printed on that line of the page makes the total tie, and only one does. A "flip the sign" guess was dropped after checking PIDILITIND FY2021: the report itself prints an OCI total that doesn't add up, and the guess contradicted the page. Expect few proposals on real runs: most failing totals are report quirks or grouping, not misreads.

- ~5:15 PM: Phase 5 done (`d4f0fab`). The app reads real runs:
  - Statements are drawn from the engine's rows, and totals are re-checked after edits using the report's footing.
  - Progress streams live from the server.
  - The library and corrections are stored on the server.
  - The inspector shows the real PDF page with the figure outlined.
  - The cross-check runs on demand. Company search uses NSE's list of 2,643 equities.
  - A Beta tag sits beside the name.
  - The sample workbook is seeded on first start.
  - The static export builds; Next is bumped to 16.4.6 for a security advisory.
  - Checked in the browser:
    - the PIDILITIND sample;
    - VINATIORGA, both scopes, 3 years;
    - INFY, 3 years, Extract → live progress → workbook.
- ~5:30 PM: Phase 6 done (`b0c07e3`): Dockerfile, compose, `.env.example`, DEPLOY.md, README. The PDF cache cap now works. The local `.env` turns AI on, and the key comes from the Windows environment; `/api/ai/test` answers.
- ~5:50 PM: Regression checked (RUN_LOG #40–#41). The full run flagged 3 companies for verified figures. Re-running them on the pre-change engine and the new one gives identical numbers, so the drops were outside sources failing mid-run. The Symphony gold failure predates this work (#96).
- Records: CHAT_HANDOFF (answer + Done), PROJECT_PLAN decisions log, RUN_LOG Day 5.

## How to run (development)
- API: `cd FinXL && .venv/Scripts/python -m uvicorn api.main:app --port 8000` (data in `FinXL/data/`, PDFs in `~/DocFetcherData`).
- Frontend: `cd web && npm run dev` (port 3000; `/api` is proxied to :8000, and the progress stream goes straight to :8000 because the dev proxy buffers it).
- Production-like: `cd web && npm run build`, then the API serves `web/out` at http://127.0.0.1:8000.
- API docs: http://127.0.0.1:8000/api/docs

## Phase 5 notes (frontend wiring)
- run.json shape: `api/serialize.py run_payload`. Rows: `label, level, header, total, values{y}, status{y}, src{y}, group{y: {ok, members[[row, sign]]}}, labelOk, junk?, restated?{y: {own, newest, newestFy}}, epsFlag?, epsExpect?`. Summary: `books[scope].summary = [{label, kind, rows{y}, values{y}}]`. `secondReadings: [{scope, kind, year, reportFy, totalRow, row, value, printed, page, note}]`.
- Review keys: edits `scope:kind:row:year`, labels `scope:kind:row` (row = index in that statement's rows).
- Events: `queued{position}`, `start`, `stage{stage}`, `progress{fraction}`, `year{stage, fy}`, `log{level, text}`, `stage-end`, `done{confirmedPct, issues}`, `failed{error}`. The merge stage can be skipped (read goes straight to write).
- Headers: every call sends `X-Visitor: <uuid from localStorage>`.
- Static export: `/w/[id]` → `/w?id=`; `trailingSlash: true` so FastAPI's StaticFiles serves `library/index.html`.

## Decisions (Harsh, 2026-11-23)
- All merge phases approved; Streamlit UI retired (kept in `dev/legacy_streamlit/`).
- Second reading in V1 = page re-read only, no AI.
- Gemini AI fallback: code and server key kept, `AI_ENABLED=true` on Harsh's laptop; turned off for the public at hosting time (ask Harsh then).
- Screener stays the download source, as is.
- "Beta" tag beside the FinXL name.
- All current frontend features kept.
- V2 (in about a month): ratio analysis tab in UI and Excel, Excel redesign, parser training on 10 years.

## Architecture (approved)
One Docker image: FastAPI (uvicorn) serves `/api/*` and the Next.js static export from one port. In-process job queue (1 run at a time), SQLite + files on a `/data` volume. Same thing runs on the laptop (`docker compose up`, or `uvicorn` + `npm run dev` for development). Host not chosen yet.

## Implementation notes (for whoever continues)
- Runtime engine files: finxl, ar_extract, quality, llm_extract, fetchdocs, ixbrl_to_excel, pdfview, accuracy_check + label_words.txt. Missing from requirements: Pillow. pandas/streamlit only for the legacy UI.
- `finxl.run(ticker, start, end, scope, ai, out_dir, log, progress, restated)` returns `(out_path, merged, sources, years, months)`. Always pass `out_dir`.
- Merged row: `label, level, is_header, values{y}, prio{y}, status{y}, src{y}, label_ok, junk, eps_flag{y}`.
- Footing groups: `quality._foot` builds them internally (`find_sum`/`find_signed` return covered rows); expose per column as `row["groups"][c]`.
- `merge_years` discards the non-chosen value per year (finxl.py ~318–329): keep own-report and newest-report values for the restated marker.
- `eps_check` computes the expected EPS (`expect`, finxl.py ~536) but only returns it as text.
- `ar_extract._vocab_cache` keyed by `id(doc)`, never cleared: clear on doc close for a long-running server.
- PyMuPDF isn't thread-safe: one worker, each run opens its own docs.
- Second reading tools: `pdfview.find_label` (line rect) + `pdfview._num_tokens` (numbers on a line) + footing groups.
- Regression: `python dev/tests/regression.py [TICKERS] [--no-gold] [--workers N]` (no `--help`; any run writes `dev/test_output/`).
