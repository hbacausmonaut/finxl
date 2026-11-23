# FinXL V1 beta: build log

Live tracker for the V1 beta build. Plan approved by Harsh on 2026-11-23 (full plan below).
Times are IST. Each "run" is one 5-hour usage window: afternoon (until 6 PM), evening (6–11 PM), night (11 PM–4 AM).

## Schedule and ETAs

| Phase | What | Run | ETA | Status |
|---|---|---|---|---|
| 1 | Copy into `FinXL/` layout, git, dev-tool paths | Afternoon | done | ✅ commit `9857551` (3-company regression check running) |
| 2 | Engine additions: footing groups, EPS expected value, summary picks, as-reported values, corrected-cell marks, vocab-cache fix | Afternoon | ~4:30 PM | in progress |
| 2b | Full regression + gold check on the changed engine (runs in the background, hours of wall time) | Afternoon → evening | starts ~4:30 PM | – |
| 3 | FastAPI service: runs queue + live progress, run.json, library, Excel download, PDF page images, cross-check, config | Afternoon → evening | ~8 PM | – |
| 4 | Second reading (page re-read, no AI) + tests | Evening | ~9:30 PM | – |
| 5 | Frontend on real data: API client, statements from engine rows, Beta tag, static export, company list | Evening → night | ~1 AM | – |
| 6 | Deploy package: Dockerfile, compose, `.env.example`, DEPLOY.md, README | Night | ~2 AM | – |
| 7 | End-to-end verification (real runs, browser checks, Docker), records in CHAT_HANDOFF / PROJECT_PLAN | Night | ~4 AM | – |

**Expected finish: end of the night run (about 4 AM).** If verification turns up larger fixes, a short follow-up run tomorrow morning.

## Progress notes
- 2026-11-23 ~3:20 PM: Phase 1 done. `Y:\Claude Projects\FinXL` created: `engine/` (9 runtime files), `web/` (redesign-v3 frontend), `dev/` (regression, gold, audit tools + retired Streamlit), `docs/`. Dev scripts get one line that adds `engine/` to the import path; no engine code changed. DocFetcher untouched.

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
