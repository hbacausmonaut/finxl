"""
FinXL API: one FastAPI app that serves /api/* and the built frontend.

Run locally:   .venv/Scripts/python -m uvicorn api.main:app --port 8000
In Docker:     see deploy/Dockerfile (uvicorn on $PORT)
"""

import asyncio
import datetime
import json
import os
import re
import tempfile
import threading
import time

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import settings, storage  # settings first: it points the engine at DATA_DIR

import accuracy_check
import ar_extract
import fitz
import finxl
import llm_extract
import pdfview

from . import jobs
from .serialize import load_engine

app = FastAPI(title="FinXL API", version=settings.VERSION, docs_url="/api/docs", openapi_url="/api/openapi.json")
if settings.CORS_ORIGINS or settings.CORS_ORIGIN_REGEX:
    # The web app lives on another origin (e.g. Vercel) and calls this API directly.
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS + settings.DEV_ORIGINS,
                       allow_origin_regex=settings.CORS_ORIGIN_REGEX,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"], max_age=600)
elif settings.DEV_ORIGINS:
    # `next dev` buffers proxied event streams, so in development the page opens them on this port directly.
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=settings.DEV_ORIGINS, allow_methods=["GET"], allow_headers=["*"])

TICKER = re.compile(r"^[A-Z0-9&_-]{1,20}$")
PAGE = re.compile(r"^\d{1,4}[LR]?$")
THIS_YEAR = datetime.date.today().year


@app.on_event("startup")
def _startup():
    storage.init()
    storage.seed(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed"))
    jobs.start_workers()


def _ticker(t):
    t = (t or "").strip().upper()
    if not TICKER.match(t):
        raise HTTPException(400, "That doesn't look like an NSE symbol (letters and digits, e.g. HCLTECH).")
    return t


def _ip(request: Request):
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else request.client.host if request.client else "") or "?"


def _summary(r):
    return {
        "id": r["id"],
        "request": {"symbol": r["symbol"], "from": r["from_fy"], "to": r["to_fy"], "scope": r["scope"],
                    "figures": r["figures"], "ai": r["ai"]},
        "companyName": r["company"] or r["symbol"],
        "status": r["status"],
        "createdAt": r["created_at"],
        "startedAt": r["started_at"],
        "durationSec": round(r["finished_at"] - (r["started_at"] or r["created_at"])) if r["finished_at"] else None,
        "confirmedPct": r["confirmed_pct"],
        "issues": r["issues"],
        "error": r["error"],
        "position": jobs.position(r["id"]) if r["status"] == "queued" else 0,
    }


def _run_or_404(run_id):
    r = storage.get_run(run_id) if re.match(r"^r_[0-9a-f]{10}$", run_id or "") else None
    if not r:
        raise HTTPException(404, "No such run.")
    return r


# ── Config ───────────────────────────────────────────────────────────────────
@app.get("/api/config")
def config():
    return {
        "version": settings.VERSION,
        "ai": {"available": settings.AI_ENABLED and bool(settings.GEMINI_API_KEY), "model": settings.GEMINI_MODEL},
        "limits": {"maxYears": settings.MAX_YEARS, "runsPerDay": settings.RUNS_PER_IP_PER_DAY or None},
    }


# ── Companies ────────────────────────────────────────────────────────────────
_reports_cache = {}
_reports_lock = threading.Lock()


@app.get("/api/companies/{ticker}/reports")
async def company_reports(ticker: str):
    t = _ticker(ticker)
    with _reports_lock:
        hit = _reports_cache.get(t)
    if hit and time.time() - hit[0] < 86400:
        return hit[1]
    try:
        url, company, reports = await run_in_threadpool(finxl.list_reports, t)
    except Exception as e:
        raise HTTPException(404, str(e) or f"Could not find {t} on screener.in.")
    data = {"symbol": t, "name": company, "url": url,
            "reports": [{"fy": r["year"], "url": r["url"], "label": r["label"]} for r in reports]}
    with _reports_lock:
        _reports_cache[t] = (time.time(), data)
    return data


# ── Runs ─────────────────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    symbol: str
    from_: int = Field(alias="from")
    to: int
    scope: str = "consolidated"
    figures: str = "restated"
    ai: str = "off"


@app.post("/api/runs")
def start_run(body: RunRequest, request: Request, x_visitor: str = Header(default="")):
    t = _ticker(body.symbol)
    if body.scope not in ("consolidated", "standalone", "both"):
        raise HTTPException(400, "Statements must be consolidated, standalone or both.")
    if body.figures not in ("restated", "as-reported"):
        raise HTTPException(400, "Figures must be restated or as-reported.")
    if not (2005 <= body.from_ <= body.to <= THIS_YEAR + 1):
        raise HTTPException(400, "Choose a valid range of fiscal years.")
    if body.to - body.from_ + 1 > settings.MAX_YEARS:
        raise HTTPException(400, f"Up to {settings.MAX_YEARS} years per run.")
    ai = body.ai if body.ai in ("off", "fallback", "always") and settings.AI_ENABLED else "off"
    req = {"symbol": t, "from": body.from_, "to": body.to, "scope": body.scope, "figures": body.figures, "ai": ai}
    visitor = storage.safe_visitor(x_visitor)

    reuse = storage.find_reusable(req)
    if reuse:
        storage.add_visit(reuse["id"], visitor)
        return _summary(reuse)

    ip = _ip(request)
    if settings.RUNS_PER_IP_PER_DAY and storage.runs_today(ip) >= settings.RUNS_PER_IP_PER_DAY:
        raise HTTPException(429, "You've reached today's limit for new extractions. Try again tomorrow.")
    with _reports_lock:
        known = _reports_cache.get(t)
    run_id = storage.create_run(req, known[1]["name"] if known else None, visitor, ip)
    jobs.enqueue(run_id)
    return _summary(storage.get_run(run_id))


@app.get("/api/runs")
def list_runs(x_visitor: str = Header(default="")):
    v = storage.safe_visitor(x_visitor)
    return [_summary(r) for r in storage.library(v)] if v else []


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, x_visitor: str = Header(default="")):
    r = _run_or_404(run_id)
    storage.add_visit(run_id, storage.safe_visitor(x_visitor))  # opening a shared link files it in your library
    return _summary(r)


@app.delete("/api/runs/{run_id}")
def remove_run(run_id: str, x_visitor: str = Header(default="")):
    _run_or_404(run_id)
    storage.hide_visit(run_id, storage.safe_visitor(x_visitor))
    return {"ok": True}


@app.get("/api/runs/{run_id}/workbook")
def workbook(run_id: str):
    r = _run_or_404(run_id)
    if r["status"] != "done":
        raise HTTPException(409, "This run hasn't finished.")
    path = os.path.join(storage.run_dir(run_id), "run.json")
    return FileResponse(path, media_type="application/json")


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request, since: int = 0):
    _run_or_404(run_id)
    last = request.headers.get("last-event-id")
    seq = int(last) + 1 if last and last.isdigit() else since

    async def stream():
        nonlocal seq
        while True:
            for ev in jobs.events_since(run_id, seq):
                seq = ev["seq"] + 1
                yield f"id: {ev['seq']}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                if ev["type"] in ("done", "failed"):
                    return
            r = storage.get_run(run_id)
            if r["status"] in ("done", "failed") and not jobs.events_since(run_id, seq):
                # finished before this server kept events: close with the outcome
                yield f"data: {json.dumps({'type': r['status'], 'error': r['error']})}\n\n"
                return
            if await request.is_disconnected():
                return
            await run_in_threadpool(jobs.wait_for_events, run_id, seq, 10)
            yield ": keep-alive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Review (a visitor's corrections) ─────────────────────────────────────────
class Review(BaseModel):
    edits: dict = {}
    labels: dict = {}
    kept: list = []


@app.get("/api/runs/{run_id}/review")
def get_review(run_id: str, x_visitor: str = Header(default="")):
    _run_or_404(run_id)
    v = storage.safe_visitor(x_visitor)
    return storage.read_json(run_id, f"review/{v}.json", {"edits": {}, "labels": {}, "kept": []}) if v else \
        {"edits": {}, "labels": {}, "kept": []}


@app.put("/api/runs/{run_id}/review")
def put_review(run_id: str, body: Review, x_visitor: str = Header(default="")):
    _run_or_404(run_id)
    v = storage.safe_visitor(x_visitor)
    if not v:
        raise HTTPException(400, "Missing visitor id.")
    if len(json.dumps(body.model_dump())) > 500_000:
        raise HTTPException(413, "Too many corrections.")
    storage.write_json(run_id, f"review/{v}.json", body.model_dump())
    return {"ok": True}


def _apply_review(merged, review):
    """Corrections onto the merged rows. Keys: 'scope:kind:row:year' and 'scope:kind:row'."""
    marks = {}
    for key, value in (review.get("edits") or {}).items():
        try:
            scope, kind, row, year = key.split(":")
            row, year = int(row), int(year)
            rows = merged[(scope, kind)]
            was = rows[row]["values"].get(year)
            rows[row]["values"][year] = round(float(value), 4)
            rows[row].get("status", {}).pop(year, None)
            marks.setdefault((scope, kind), {})[(row, year)] = was
        except (ValueError, KeyError, IndexError):
            continue
    for key, label in (review.get("labels") or {}).items():
        try:
            scope, kind, row = key.split(":")
            merged[(scope, kind)][int(row)]["label"] = str(label)[:200]
            merged[(scope, kind)][int(row)]["label_ok"] = True
        except (ValueError, KeyError, IndexError):
            continue
    return marks


@app.get("/api/runs/{run_id}/xlsx")
def download_xlsx(run_id: str, visitor: str = "", x_visitor: str = Header(default="")):
    r = _run_or_404(run_id)
    if r["status"] != "done":
        raise HTTPException(409, "This run hasn't finished.")
    base = os.path.join(storage.run_dir(run_id), r["xlsx"])
    v = storage.safe_visitor(x_visitor or visitor)
    review = storage.read_json(run_id, f"review/{v}.json") if v else None
    if not review or not (review.get("edits") or review.get("labels")):
        return FileResponse(base, filename=r["xlsx"],
                            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    eng = storage.read_json(run_id, "engine.json")
    merged, months = load_engine(eng)
    marks = _apply_review(merged, review)
    fd, tmp = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    finxl.write_workbook(tmp, eng["company"], eng["ticker"], eng["url"], eng["years"], merged, eng["sources"],
                         eng["scopes"], eng["restated"], months, marks=marks)
    data = open(tmp, "rb").read()
    os.remove(tmp)
    name = r["xlsx"].replace(".xlsx", "_reviewed.xlsx")
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ── Cross-check (on demand) ──────────────────────────────────────────────────
_cc_lock = threading.Lock()


@app.get("/api/runs/{run_id}/crosscheck")
async def crosscheck(run_id: str):
    r = _run_or_404(run_id)
    if r["status"] != "done":
        raise HTTPException(409, "This run hasn't finished.")
    cached = storage.read_json(run_id, "crosscheck.json")
    if cached is not None:
        return cached

    def work():
        with _cc_lock:  # NSE and Screener don't like many requests at once
            path = os.path.join(storage.run_dir(run_id), r["xlsx"])
            _, results, per_source = accuracy_check.check(r["symbol"], path=path)
            return {"results": results, "perSource": per_source}

    try:
        data = await run_in_threadpool(work)
    except Exception as e:
        raise HTTPException(502, f"Couldn't reach the outside sources right now ({e}).")
    storage.write_json(run_id, "crosscheck.json", data)
    return data


# ── Report PDFs ──────────────────────────────────────────────────────────────
_download_lock = threading.Lock()


def _pdf(ticker, fy):
    """The cached report PDF, downloaded again from Screener's list if the cache was cleared."""
    t = _ticker(ticker)
    path = pdfview.pdf_path(None, t, fy)
    if path:
        return path
    with _download_lock:
        path = pdfview.pdf_path(None, t, fy)
        if path:
            return path
        try:
            _, _, reports = finxl.list_reports(t)
            item = next((r for r in reports if r["year"] == fy), None)
            if item:
                path = finxl.download_report(item, os.path.join(settings.CACHE_DIR, t, "AnnualReports"))
        except Exception:
            path = None
    if not path:
        raise HTTPException(404, f"The FY{fy} report for {t} isn't available.")
    return path


@app.get("/api/pdf/{ticker}/{fy}.pdf")
def report_pdf(ticker: str, fy: int):
    return FileResponse(_pdf(ticker, fy), media_type="application/pdf", filename=f"{ticker.upper()}_AR_FY{fy}.pdf",
                        content_disposition_type="inline")


_render_lock = threading.Lock()  # PyMuPDF isn't thread-safe


@app.get("/api/pdf/{ticker}/{fy}/page/{page}.png")
async def report_page(ticker: str, fy: int, page: str, value: float | None = None, label: str = "", dpi: int = 110):
    if not PAGE.match(page):
        raise HTTPException(400, "Bad page.")
    path = await run_in_threadpool(_pdf, ticker, fy)
    dpi = max(60, min(dpi, 200))

    def work():
        with _render_lock:
            doc = fitz.open(path)
            try:
                hits = pdfview.find_value(doc, [page], value, label=label) if value is not None else []
                if not hits and label:
                    h = pdfview.find_label(doc, [page], label)
                    hits = [h] if h else []
                return pdfview.render(doc, page.upper(), hits[:3], dpi=dpi)
            finally:
                ar_extract.forget_doc(doc)
                doc.close()

    try:
        png = await run_in_threadpool(work)
    except Exception as e:
        raise HTTPException(404, f"Couldn't render that page ({e}).")
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


# ── AI ───────────────────────────────────────────────────────────────────────
@app.post("/api/ai/test")
async def ai_test():
    if not settings.AI_ENABLED:
        return {"ok": False, "message": "The AI fallback is switched off on this server."}
    ok, msg = await run_in_threadpool(llm_extract.check_backend, "gemini", settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    return {"ok": bool(ok), "message": msg}


@app.exception_handler(HTTPException)
async def _http_error(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ── Frontend ─────────────────────────────────────────────────────────────────
class _WebFiles(StaticFiles):
    """
    The static app. Next's client asks for segment prefetch data as one dotted name
    ("w/__next.!KGFwcCk.w.__PAGE__.txt") while the export writes it as folders
    ("w/__next.!KGFwcCk/w/__PAGE__.txt"); serve the folder form when the dotted one is missing.
    """

    async def get_response(self, path, scope):
        if "__next." in path and path.endswith(".txt"):
            head, _, tail = path.rpartition("__next.")
            alt = head + "__next." + "/".join(tail[:-4].split(".")) + ".txt"
            if alt != path:
                full, stat = self.lookup_path(alt)
                if stat is not None and not os.path.isdir(full):
                    return self.file_response(full, stat, scope)
        return await super().get_response(path, scope)


if os.path.isdir(settings.WEB_DIR):
    app.mount("/", _WebFiles(directory=settings.WEB_DIR, html=True), name="web")
