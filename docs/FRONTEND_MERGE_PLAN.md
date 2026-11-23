# Merging the FinXL frontend with the DocFetcher engine

*Plan only, written 2026-11-23. Nothing here is approved or built. "Hosted web app / FastAPI backend / job queue" is under **Not approved** in `CHAT_HANDOFF.md`, so the first step is a decision in the planning chat (see "Decisions needed").*

## Where things stand

| Piece | State |
|---|---|
| Engine (`finxl.py`, `ar_extract.py`, `quality.py`, `accuracy_check.py`, `pdfview.py`) | Working; 100-company test set; regression suite and gold check guard it |
| Streamlit app (`app.py`, `audit_ui.py`, `review_ui.py`) | Test harness: generate Excel, sampling audit, gold review |
| Frontend (`frontend/`, Next.js 16) | Light redesign on branch `redesign-v3`, running on mock data only. Not fully reviewed yet (only the landing page and the Summary tab were checked). Has its own git repo, untracked by the root repo |

The frontend was built against a typed seam, `frontend/lib/api.ts`. Every screen gets its data through it, and its mock data mirrors what `finxl.run` returns. Merging means putting a small Python API behind that seam. **No parser code changes in the first phases.**

## Proposed shape

```
Browser ──> Next.js (frontend/, port 3000)
              │  /api/* rewritten to localhost:8000 (no CORS, one origin)
              ▼
            Local API (new file api.py, FastAPI, port 8000)
              │  imports, never edits:
              ▼
            finxl.run · pdfview.render/find_value · accuracy_check.check
              │
              ▼
            ~/DocFetcherData cache (PDFs) + TICKER/ folders (Excel + run JSON)
```

- **Local first.** It runs on the laptop like Streamlit does today. Hosting (PROJECT_PLAN Phase 4) is a separate, later decision.
- **One run at a time**, in a background thread. `finxl.run` already takes `log=` and `progress=` callbacks, and those feed a progress stream. No job queue is needed for one user.
- **Results saved twice.** The Excel file as today, plus a `run.json` beside it with the merged rows, sources and quality. The UI and the library read the JSON, so reopening a workbook never re-runs the parser.
- **Streamlit stays** until the new UI has caught up. The gold review and sampling audit screens stay in Streamlit; they're internal tools.

## Endpoint map

| Frontend call (`lib/api.ts`) | Endpoint | Engine call | Notes |
|---|---|---|---|
| `searchCompanies` | none (bundled list) | – | Ship an NSE symbol list as JSON. Typing stays instant; no Screener call per keystroke |
| `listReports(symbol)` | `GET /api/companies/{t}/reports` | `finxl.list_reports` | One Screener page fetch. Cache for a day |
| start a run (`library.start`) | `POST /api/runs` | `finxl.run` in a thread | Body: ticker, from, to, scope, restated, ai. Returns run id. Rejects a second run while one is going |
| run progress (`lib/run.ts`) | `GET /api/runs/{id}/events` (SSE) | `log` + `progress` callbacks | Replaces the mock timeline. Stage = derived from `progress` bands (0.05 / 0.30 / 0.90 / 1.0) |
| `getWorkbook` | `GET /api/runs/{id}` | reads `run.json` | Adapter described below |
| library list | `GET /api/runs` | scans output folders | Replaces localStorage; works across browsers |
| `downloadExcel` | `GET /api/runs/{id}/xlsx` | file on disk | Phase 4 adds the reader's corrections |
| source page image | `GET /api/pdf/{t}/{fy}/page/{p}.png?value=&label=` | `pdfview.render` + `find_value` | Same highlight the audit screen uses. Replaces the drawn stand-in page |
| open the PDF | `GET /api/pdf/{t}/{fy}.pdf#page=N` | cached file | PDF page position, not printed folio (matches the queued "source-page link" idea) |
| cross-check | `GET /api/runs/{id}/crosscheck` | `accuracy_check.check` | Slow (NSE, Screener); load on demand in the Sources tab |
| `testAiConnection` | `POST /api/ai/test` | `llm_extract.check_backend` | Gemini key sent per request, never stored |

## The one real adapter: statement rows

The engine's merged rows are `{label, level, is_header, values{year}, status{year}, src{year}, label_ok}`, in report order. The frontend currently draws statements from a fixed layout (`lib/sheets.ts`, rows like `rev`, `texp`, `pbt` with formulas). Real reports don't share one layout, so:

1. **Draw statements from the engine's rows**, not the fixed layout. Row id = `scope:kind:index`. Totals are recognised with the same rule `quality.py` uses (`_is_target`), exported as a flag on each row.
2. **Keep the fixed layout only for the Summary tab**, filled the way `write_metrics` / `pick_row` pick revenue, net profit, assets and CFO today. Expose `pick_row` results in `run.json` so the UI and the Excel agree.
3. **The "how it's checked" panel needs the footing groups.** `quality._foot_column` knows which rows make up each total but doesn't return it. Small, read-only addition: return the groups alongside `status`. This is the only engine change in the early phases, and it touches no extraction logic.

## What the UI shows that the engine doesn't produce yet

| UI feature | Engine today | Option |
|---|---|---|
| Per-figure check status (confirmed / doesn't add up) | Yes (`status`, per year) | Use as is |
| Which report each year came from | Yes (`src`) | Use as is |
| Statement pages per report | Yes (Sources: `pages`) | Use as is |
| Garbled label flag | Yes (`label_ok`) | Use as is; drop the "decoded suggestion" until the engine has one |
| EPS looks off | Yes (`eps_check`: flag + text) | Return the expected value too (one-line addition) |
| Restated marker and "as first reported" value | No: the merge keeps one value per year | Phase 5: keep both values during the merge. Until then, hide the toggle |
| "A second reading disagrees" for one figure | No: the AI fallback re-reads whole statements | Hide. Becomes possible with the reliability redesign's "AI second reader on failing pages" |
| Reader's corrections written into the Excel | No | Phase 4: `write_workbook` takes an overrides map; corrected cells marked |
| Exact position of a figure on the page | Found at view time by `pdfview.find_value` | Use as is |

Everything in the "Hide" rows is a UI switch, not a rewrite.

## Phases

| # | What | Done when | Rough time |
|---|---|---|---|
| 0 | Decisions in the planning chat (below); fold `frontend/` into the root repo; review the redesign | Approved item in `CHAT_HANDOFF.md` | – |
| 1 | `api.py` read-only: library, workbook from `run.json`, Excel download, PDF page images. `finxl.run` writes `run.json` | Every existing output opens in the new UI with real figures; regression suite unchanged | 1–1.5 days |
| 2 | Start runs from the UI with live progress (SSE); errors shown as the engine words them | A fresh run of a new company completes from the browser | 1 day |
| 3 | Statement rows from the engine (adapter above), footing groups, cross-check tab | The 15 gold statements display exactly as their gold copies | 1–1.5 days |
| 4 | Corrections round trip: review edits saved per run and written into the Excel | An edited figure appears, marked, in the downloaded file | 0.5–1 day |
| 5 | Restated vs as-reported both kept in the merge (engine change, regression-tested) | Toggle works; regression suite and gold check pass | 1–2 days |
| 6 | Retire `app.py`'s generator page (keep audit and gold screens) | Harsh uses only the new UI for a week | – |

Phases 1–4 don't change extraction. Phase 5 does and needs the usual regression run.

## Decisions needed (planning chat)

1. **Is a local API approved?** It is a FastAPI backend, which is on the Not approved list, but local-only, single-user, no hosting. Approve as a local tool, or wait for Phase 4 of PROJECT_PLAN?
2. **Order against the open work.** Item 5 and the reliability redesign are still waiting. Does the merge come before, after, or alongside them?
3. **Which hides are acceptable for v1:** restated toggle, second readings, label suggestions?
4. **Repo layout:** fold `frontend/` into the DocFetcher repo (one history) or keep it as a separate repo?
5. **Is the redesign (`redesign-v3`) the version to merge?** The earlier versions are tagged `v1-original` and `v2-motion` in the frontend repo.

## Risks

- **Long runs.** A 6-year run takes minutes. The API must not block; one background thread plus SSE handles it. Closing the browser must not stop the run.
- **Excel file locked** (open in Excel). `finxl.run` already saves under a new name; the API must return the actual path it used.
- **Screener limits.** Report lists are cached; no per-keystroke lookups.
- **Windows paths and the cache folder** (`DOCFETCHER_CACHE`). The API reads the same variable as `finxl.py` and `pdfview.py`.
- **Drift between UI and Excel.** The Summary figures must come from the engine's own picks (`pick_row`), never recomputed in the browser.

## Testing

- The regression suite and gold check run unchanged in every phase. Phases 1–4 only import the engine.
- API tests: one per endpoint against a cached company (no network), e.g. HCLTECH.
- UI check per phase: open a real workbook, a failed run, a scanned-report company, both scopes, light and dark, phone width.
