"""
Run records in SQLite, plus per-run files under DATA_DIR/runs/<id>/:
  engine.json   the engine's result (merged rows, sources, years...) to re-write the Excel
  run.json      what the app shows (see serialize.py)
  <name>.xlsx   the workbook as extracted
  review/<visitor>.json   a visitor's corrections
  crosscheck.json         outside-source comparison, made on demand
"""

import json
import os
import sqlite3
import threading
import time
import uuid

from . import settings

_lock = threading.Lock()

SCHEMA = """
create table if not exists runs (
  id text primary key,
  symbol text not null, company text, from_fy integer, to_fy integer,
  scope text, figures text, ai text,
  status text not null,            -- queued | running | done | failed
  created_at real, started_at real, finished_at real,
  error text, xlsx text, confirmed_pct real, issues integer, ip text
);
create table if not exists visits (
  run_id text, visitor text, added_at real, hidden integer default 0,
  primary key (run_id, visitor)
);
create index if not exists runs_req on runs(symbol, from_fy, to_fy, scope, figures, ai, status);
"""


def _conn():
    c = sqlite3.connect(settings.DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript(SCHEMA)
        # A run that was going when the server stopped will never finish.
        c.execute("update runs set status='failed', error='The server restarted while this run was going. Run it again.',"
                  " finished_at=? where status in ('queued','running')", (time.time(),))


def run_dir(run_id):
    return os.path.join(settings.RUNS_DIR, run_id)


def create_run(req, company, visitor, ip):
    run_id = "r_" + uuid.uuid4().hex[:10]
    with _lock, _conn() as c:
        c.execute("insert into runs (id, symbol, company, from_fy, to_fy, scope, figures, ai, status, created_at, ip)"
                  " values (?,?,?,?,?,?,?,?, 'queued', ?, ?)",
                  (run_id, req["symbol"], company, req["from"], req["to"], req["scope"], req["figures"], req["ai"],
                   time.time(), ip))
        if visitor:
            c.execute("insert or replace into visits values (?,?,?,0)", (run_id, visitor, time.time()))
    os.makedirs(run_dir(run_id), exist_ok=True)
    return run_id


def add_visit(run_id, visitor):
    if not visitor:
        return
    with _lock, _conn() as c:
        c.execute("insert into visits values (?,?,?,0) on conflict(run_id, visitor) do update set hidden=0, added_at=excluded.added_at",
                  (run_id, visitor, time.time()))


def hide_visit(run_id, visitor):
    with _lock, _conn() as c:
        c.execute("update visits set hidden=1 where run_id=? and visitor=?", (run_id, visitor))


def update_run(run_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"update runs set {cols} where id=?", (*fields.values(), run_id))


def get_run(run_id):
    with _conn() as c:
        r = c.execute("select * from runs where id=?", (run_id,)).fetchone()
    return dict(r) if r else None


def find_reusable(req):
    """An identical run that finished recently, to serve instead of extracting again."""
    since = time.time() - settings.REUSE_DAYS * 86400
    with _conn() as c:
        r = c.execute("select * from runs where symbol=? and from_fy=? and to_fy=? and scope=? and figures=? and ai=?"
                      " and status in ('done','queued','running') and created_at>? order by created_at desc limit 1",
                      (req["symbol"], req["from"], req["to"], req["scope"], req["figures"], req["ai"], since)).fetchone()
    return dict(r) if r else None


def library(visitor):
    with _conn() as c:
        rows = c.execute("select r.*, v.added_at from runs r join visits v on v.run_id=r.id"
                         " where v.visitor=? and v.hidden=0 order by v.added_at desc limit 100", (visitor,)).fetchall()
    return [dict(r) for r in rows]


def queued_ids():
    with _conn() as c:
        return [r[0] for r in c.execute("select id from runs where status='queued' order by created_at").fetchall()]


def runs_today(ip):
    with _conn() as c:
        return c.execute("select count(*) from runs where ip=? and created_at>?", (ip, time.time() - 86400)).fetchone()[0]


# ── Files ────────────────────────────────────────────────────────────────────
def write_json(run_id, name, data):
    path = os.path.join(run_dir(run_id), name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def read_json(run_id, name, default=None):
    path = os.path.join(run_dir(run_id), name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def safe_visitor(v):
    """Visitor ids come from the browser: keep them to a safe file-name alphabet."""
    v = (v or "").strip()
    return v if v and len(v) <= 64 and all(ch.isalnum() or ch in "-_" for ch in v) else ""
