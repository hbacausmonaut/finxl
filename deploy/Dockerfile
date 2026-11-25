# FinXL: one image, one port. The FastAPI service serves /api and the built web app.
# Build from the repository root:  docker build -f deploy/Dockerfile -t finxl .

# ── 1. Web app: Next.js static export → web/out ───────────────────────────────
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ── 2. API + engine ───────────────────────────────────────────────────────────
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MALLOC_ARENA_MAX=2 \
    DATA_DIR=/data \
    DOCFETCHER_CACHE=/data/pdfs \
    WEB_DIR=/app/web/out \
    DEV_ORIGINS= \
    PORT=8000

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY engine/ engine/
COPY api/ api/
COPY --from=web /web/out web/out

# Run as an unprivileged user; /data is the only place it writes.
RUN useradd --create-home --uid 10001 finxl && mkdir -p /data && chown finxl /data
USER finxl
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/config', timeout=4)"

# One worker process: runs, the queue and PyMuPDF all live in it.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
