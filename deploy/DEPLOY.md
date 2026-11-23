# Deploying FinXL (V1 beta)

FinXL ships as **one Docker image**. A single FastAPI process (uvicorn) serves the API at `/api/*` and the web app (a Next.js static export) at `/`. Runs go through an in-process queue. State lives on one volume, `/data`, which holds the SQLite library, each run's files and the PDF cache. You don't need Redis, a separate frontend host or a database server.

```
browser ──HTTPS──> reverse proxy / platform ──> finxl container :8000
                                                  ├─ /api/*   FastAPI (queue, SSE progress, Excel, page images)
                                                  ├─ /*       web/out (static app)
                                                  └─ /data    finxl.db · runs/ · pdfs/
```

## 1. Run it on your own machine

```bash
cp deploy/.env.example deploy/.env      # then edit: AI_ENABLED, GEMINI_API_KEY, limits
docker compose -f deploy/docker-compose.yml up -d --build
# open http://localhost:8000
```

Development without Docker (two terminals):

```bash
.venv/Scripts/python -m uvicorn api.main:app --port 8000      # API (reads .env in the repo root)
cd web && npm run dev                                            # app on :3000, /api proxied to :8000
```

## 2. Settings (environment variables)

| Variable | Default | What it does |
|---|---|---|
| `AI_ENABLED` | `false` | Turns the Gemini fallback on. It also needs `GEMINI_API_KEY`. The key stays on the server. |
| `GEMINI_API_KEY` | – | Google AI Studio key. Set it as a platform secret, never in the image. |
| `GEMINI_MODEL` | `gemini-flash-latest` | The model to try first. |
| `MAX_YEARS` | `12` | The most years one run may read. |
| `MAX_CONCURRENT_RUNS` | `1` | How many runs read at once. Keep it at 1 below about 2 GB of RAM. |
| `RUNS_PER_IP_PER_DAY` | `0` (unlimited) | A per-visitor rate limit. Set this for the public beta. |
| `REUSE_DAYS` | `7` | An identical finished request is served again instead of being re-read. |
| `CACHE_MAX_GB` | `0` (unlimited) | Caps the PDF cache; the least recently used files go first. |
| `PORT` | `8000` | The listening port. Most platforms set this themselves. |
| `DATA_DIR`, `DOCFETCHER_CACHE`, `WEB_DIR` | set in the image | Paths. Change them only outside Docker. |
| `DEV_ORIGINS` | empty in the image | Only for `next dev`. Leave it empty in production. |

## 3. Choosing a host

What FinXL needs:
- **A persistent disk** for `/data`. Without one, the library and corrections vanish on every redeploy.
- **About 1–2 GB of RAM.** PyMuPDF holds a whole annual report (often 300+ pages) in memory while reading it.
- **Long requests.** Progress uses server-sent events and a run takes 1–5 minutes, so the proxy must not buffer responses or cut connections after 30–60 s.
- **Outbound HTTPS** to screener.in, bseindia.com, nseindia.com and archives, plus Google's AI API if the fallback is on.

| Host | Fits? | Notes |
|---|---|---|
| **Small VPS** (Hetzner, DigitalOcean, Lightsail, Oracle free ARM) | ✅ best value | Docker plus compose, with Caddy in front for HTTPS (below). Full control and a real disk. |
| **Render** (Docker web service) | ✅ | Add a persistent disk mounted at `/data`. The free tier sleeps and has no disk, so use a paid instance (about 2 GB). |
| **Railway** | ✅ | Deploy from the Dockerfile and attach a volume at `/data`. |
| **Fly.io** | ✅ | Run `fly launch --dockerfile deploy/Dockerfile`, add a volume at `/data` and use a 2 GB machine. Turn off auto-stop if you want runs to survive idle periods. |
| **Google Cloud Run** | ⚠️ | The disk is ephemeral and instances scale to zero, which loses the queue and library. It only works with a mounted bucket and min-instances = 1. Not recommended for this design. |
| **Hugging Face Spaces** (Docker) | ⚠️ | Easy and free, but storage is ephemeral unless you pay for persistent storage, and the port must be 7860 (`PORT=7860`). Fine for a demo. |
| Vercel / Netlify | ❌ | Static hosting and short serverless functions can't run the engine. |

### VPS recipe (Docker + Caddy)

```bash
git clone <repo> finxl && cd finxl
cp deploy/.env.example deploy/.env && nano deploy/.env
docker compose -f deploy/docker-compose.yml up -d --build
```

Caddyfile (automatic HTTPS):

```
finxl.example.com {
    reverse_proxy 127.0.0.1:8000 {
        flush_interval -1        # stream progress events without buffering
    }
}
```

Change the compose port to `"127.0.0.1:8000:8000"`, so that only Caddy is reachable from outside.

## 4. Hosting-day checklist

1. **AI off for the public.** Set `AI_ENABLED=false`, or leave out `GEMINI_API_KEY`. (Harsh asked to confirm this together at hosting time.)
2. Set a rate limit: `RUNS_PER_IP_PER_DAY`, about 10.
3. Cap the PDF cache: `CACHE_MAX_GB` to suit the disk (5–10).
4. Make sure `/data` is a persistent volume. Back it up: `finxl.db` and `runs/` are the library.
5. Check after deploy:
   - `/api/config` reports `"version": "1.0.0-beta"` and `ai.available: false`.
   - The landing page's sample workbook opens.
   - A fresh run streams its progress and its Excel downloads.
6. Behind a proxy, confirm `X-Forwarded-For` reaches the app (the rate limit uses it).

## 5. Operating notes

- **Restarts:** a run that was going when the server stopped is marked failed ("run it again"). Queued runs are lost, so redeploy when the queue is empty.
- **Missing PDFs:** if the cache was cleared, a page image or PDF link downloads the report again from Screener's list for that company.
- **Sample workbook:** `api/seed/r_0000000001` (PIDILITIND FY2020–26, consolidated) loads on first start.
- **Company list:** `web/public/companies.json` comes from NSE's equity list. Refresh it with `python dev/scripts/build_companies.py`, then rebuild.
- **Logs:** stdout (uvicorn). Each run also keeps `events.jsonl` in its folder.
- **Upgrading:** pull, run `docker compose ... up -d --build`; the `/data` volume carries over.
