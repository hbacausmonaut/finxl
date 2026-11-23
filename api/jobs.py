"""
Runs extractions in background worker threads, one run per worker.
Each run's progress is a list of events (kept in memory, and in events.jsonl
so a finished run's log survives a restart) that the SSE endpoint streams.

Stages follow finxl.run's own progress() bands:
  lookup < 0.05 ≤ download < 0.30 ≤ read < 0.90 ≤ merge < 1.0 = write
"""

import json
import os
import queue
import re
import threading
import time
import traceback

from . import settings, storage

import finxl
import second_reading
from .serialize import engine_payload, headline, run_payload

_q = queue.Queue()
_events = {}  # run id -> list of event dicts
_cond = threading.Condition()

STAGES = [("lookup", 0.0), ("download", 0.05), ("read", 0.30), ("merge", 0.90), ("write", 1.0)]
YEAR_DL = re.compile(r"^\s+FY(\d{4}): .*(MB\)|not a PDF|download failed)")
YEAR_READ = re.compile(r"^\s+FY(\d{4}):\s*$")
WARN = re.compile(r"\bCHECK\b|failed|not found|EPS check|skipped|AI fallback failed", re.I)


def stage_of(fraction):
    name = STAGES[0][0]
    for s, start in STAGES:
        if fraction >= start:
            name = s
    return name


def emit(run_id, ev):
    ev = {"seq": 0, "t": round(time.time(), 2), **ev}
    with _cond:
        lst = _events.setdefault(run_id, [])
        ev["seq"] = len(lst)
        lst.append(ev)
        _cond.notify_all()
    try:
        with open(os.path.join(storage.run_dir(run_id), "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        pass


def events_since(run_id, seq):
    with _cond:
        lst = _events.get(run_id)
    if lst is None:  # not in memory (finished before a restart): read the saved log
        path = os.path.join(storage.run_dir(run_id), "events.jsonl")
        lst = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                lst = [json.loads(line) for line in f if line.strip()]
        with _cond:
            _events.setdefault(run_id, lst)
    return lst[seq:]


def wait_for_events(run_id, seq, timeout=15):
    with _cond:
        _cond.wait_for(lambda: len(_events.get(run_id, [])) > seq, timeout=timeout)


def enqueue(run_id):
    emit(run_id, {"type": "queued", "position": position(run_id)})
    _q.put(run_id)


def position(run_id):
    ids = storage.queued_ids()
    return ids.index(run_id) + 1 if run_id in ids else 0


def ai_config(mode):
    if mode == "off" or not settings.AI_ENABLED or not settings.GEMINI_API_KEY:
        return None
    return {"backend": "gemini", "api_key": settings.GEMINI_API_KEY, "model": settings.GEMINI_MODEL, "mode": mode}


def _execute(run_id):
    run = storage.get_run(run_id)
    storage.update_run(run_id, status="running", started_at=time.time())
    emit(run_id, {"type": "start"})
    state = {"stage": None, "reading": None}

    def progress(f):
        st = stage_of(f)
        if st != state["stage"]:
            if state["stage"] == "read" and state["reading"]:
                emit(run_id, {"type": "year", "stage": "read", "fy": state["reading"]})
            if state["stage"]:
                emit(run_id, {"type": "stage-end", "stage": state["stage"]})
            state["stage"] = st
            emit(run_id, {"type": "stage", "stage": st})
        emit(run_id, {"type": "progress", "fraction": round(f, 3)})

    def log(msg):
        m = YEAR_DL.match(msg)
        if m and state["stage"] == "download":
            emit(run_id, {"type": "year", "stage": "download", "fy": int(m.group(1))})
        m = YEAR_READ.match(msg)
        if m:
            if state["reading"]:
                emit(run_id, {"type": "year", "stage": "read", "fy": state["reading"]})
            state["reading"] = int(m.group(1))
        level = "ok" if msg.startswith("Saved") else "warn" if WARN.search(msg) else "info"
        emit(run_id, {"type": "log", "level": level, "text": msg.rstrip()})

    req = {"symbol": run["symbol"], "from": run["from_fy"], "to": run["to_fy"], "scope": run["scope"],
           "figures": run["figures"], "ai": run["ai"]}
    try:
        progress(0.0)
        url, company, reports = finxl.list_reports(req["symbol"])
        storage.update_run(run_id, company=company)
        out = finxl.run(req["symbol"], req["from"], req["to"], req["scope"], ai=ai_config(req["ai"]),
                        out_dir=storage.run_dir(run_id), log=log, progress=progress,
                        restated=req["figures"] == "restated")
        eng = engine_payload(req["symbol"], company, url, req, out)
        storage.write_json(run_id, "engine.json", eng)
        reps = [{"fy": r["year"], "url": r["url"], "label": r["label"]}
                for r in reports if req["from"] <= r["year"] <= req["to"]]
        payload = run_payload(storage.get_run(run_id), eng, reps)
        log("Second reading: re-reading the pages of totals that don't add up …")
        try:
            payload["secondReadings"] = second_reading.for_run(eng, log=log)
        except Exception as e:  # a helper; never fail the run over it
            log(f"  second reading skipped ({e})")
        storage.write_json(run_id, "run.json", payload)
        pct, issues = headline(eng)
        storage.update_run(run_id, status="done", finished_at=time.time(), xlsx=os.path.basename(out[0]),
                           confirmed_pct=pct, issues=issues)
        if state["stage"]:
            emit(run_id, {"type": "stage-end", "stage": state["stage"]})
        emit(run_id, {"type": "done", "confirmedPct": pct, "issues": issues})
    except Exception as e:
        traceback.print_exc()
        msg = str(e) or e.__class__.__name__
        storage.update_run(run_id, status="failed", finished_at=time.time(), error=msg)
        emit(run_id, {"type": "failed", "error": msg})


def _worker():
    while True:
        run_id = _q.get()
        try:
            _execute(run_id)
        finally:
            _q.task_done()
            for rid in storage.queued_ids():  # tell the others they moved up
                emit(rid, {"type": "queued", "position": position(rid)})


_started = False


def start_workers():
    global _started
    if _started:
        return
    _started = True
    for i in range(max(1, settings.MAX_CONCURRENT_RUNS)):
        threading.Thread(target=_worker, name=f"finxl-worker-{i}", daemon=True).start()
