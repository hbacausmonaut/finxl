"""
Server settings, all from environment variables (a .env file is read if present).
Import this module before the engine: it points the engine's PDF cache at DATA_DIR.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path):
    """Minimal .env reader (KEY=VALUE lines); real environment variables win."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(ROOT, ".env"))


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


VERSION = "1.0.0-beta"

DATA_DIR = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(ROOT, "data")))
RUNS_DIR = os.path.join(DATA_DIR, "runs")
DB_PATH = os.path.join(DATA_DIR, "finxl.db")
# Downloaded annual reports. Defaults to the cache the engine has always used.
CACHE_DIR = os.path.abspath(os.environ.setdefault(
    "DOCFETCHER_CACHE", os.path.join(os.path.expanduser("~"), "DocFetcherData")))
# Gigabytes of PDFs to keep before the oldest are removed (0 = no limit).
CACHE_MAX_GB = float(os.environ.get("CACHE_MAX_GB", "0"))

# The built frontend (Next.js static export). Served at / when present.
WEB_DIR = os.path.abspath(os.environ.get("WEB_DIR", os.path.join(ROOT, "web", "out")))

# AI fallback (Gemini). Off unless switched on; the key never leaves the server.
AI_ENABLED = _bool("AI_ENABLED", False)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

# Limits for a public beta.
MAX_YEARS = int(os.environ.get("MAX_YEARS", "12"))
MAX_CONCURRENT_RUNS = int(os.environ.get("MAX_CONCURRENT_RUNS", "1"))
RUNS_PER_IP_PER_DAY = int(os.environ.get("RUNS_PER_IP_PER_DAY", "0"))  # 0 = unlimited
RUN_TIMEOUT_MIN = int(os.environ.get("RUN_TIMEOUT_MIN", "30"))
# An identical finished run younger than this is reused instead of re-extracted.
REUSE_DAYS = int(os.environ.get("REUSE_DAYS", "7"))

ENGINE_DIR = os.path.join(ROOT, "engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

for d in (DATA_DIR, RUNS_DIR, CACHE_DIR):
    os.makedirs(d, exist_ok=True)
