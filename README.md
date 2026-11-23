# FinXL · beta

**Annual reports in, one Excel workbook out.** Pick an NSE-listed company and a span of years. FinXL downloads each annual report, finds the Profit & Loss, Balance Sheet and Cash Flow statements, reads every line item, and lines the years up side by side in one workbook.

Every figure is checked against the report's own printed totals. Anything that doesn't add up is flagged for review, with the original PDF page one click away.

> V1 beta. Built for students, academics and finance professionals who need multi-year statements without retyping them.

## What it does

- **Extract:** consolidated, standalone or both, for up to 12 years in one run. Live progress, with a queue when the server is busy.
- **Check:**
  - Each total is re-added from its items. About 95% of figures across a 100-company test set are confirmed this way.
  - EPS is checked as profit ÷ shares.
  - Garbled labels are flagged.
- **Second reading:** when a total doesn't add up, FinXL re-reads that line on the page. It proposes a fix only when exactly one printed number makes the total tie.
- **Review:**
  - The table is keyboard-navigable.
  - Selecting a figure shows the PDF page it came from, outlined.
  - Corrections re-check totals instantly.
  - Restated years can be shown as "latest" or "as first reported".
- **Cross-check:** headline figures against NSE XBRL filings and Screener.
- **Download:** the Excel workbook (Summary, statements, Sources, Quality) with your corrections marked. Any sheet can also be copied or saved as CSV.

## How it's built

| Part | Where | What |
|---|---|---|
| Engine | `engine/` | Python. Finds reports on Screener, downloads PDFs, reads statements (PyMuPDF parser, optional Gemini fallback), checks totals (`quality.py`), merges years and writes the Excel (`finxl.py`). Second reading is in `second_reading.py`. |
| API | `api/` | FastAPI. Runs a run queue with server-sent progress, keeps a SQLite library per anonymous visitor, serves Excel downloads with corrections, renders PDF pages to PNG and runs the cross-check. |
| Web app | `web/` | Next.js 16 static export with React 19, Tailwind 4, Radix and cmdk. It talks only to `/api`. |
| Deploy | `deploy/` | One Docker image (the API also serves the app), compose file, `.env.example`, `DEPLOY.md`. |
| Dev tools | `dev/` | 100-company regression, gold/silver sets, audit tools, the retired Streamlit UI. Not deployed. |

## Run it

```bash
# Docker (one port)
cp deploy/.env.example deploy/.env
docker compose -f deploy/docker-compose.yml up -d --build      # http://localhost:8000

# Development
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn api.main:app --port 8000
cd web && npm install && npm run dev                            # http://localhost:3000
```

API docs: `/api/docs`. Hosting options and the go-live checklist: [deploy/DEPLOY.md](deploy/DEPLOY.md).

## Tests

```bash
python dev/tests/regression.py [TICKERS] [--workers N]      # 100 companies vs baseline + gold set
.venv/Scripts/python -m pytest dev/tests/test_second_reading.py -q
cd web && npx tsc --noEmit && npm run build
```

## Known limits (beta)

- Depends on Screener's list of annual reports. If a company or year isn't there, FinXL can't fetch it.
- Scanned reports with no text layer can't be read without the AI fallback, which is off on the public server.
- Indian listed companies only, with Ind AS statement layouts. Banks and insurers are supported with their own layouts.
- No accounts. Your library is tied to this browser through an anonymous id.

## Roadmap (V2)

A ratio analysis tab in the app and the Excel, a redesigned Excel, and a parser retrained on 10 years of reports.
