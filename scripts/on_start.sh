#!/usr/bin/env bash
# RunPod startup script — runs automatically on every pod start
# Starts: PostgreSQL, nginx, Voicera FastAPI backend
set -euo pipefail

echo "[on_start] $(date) — starting Voicera services"

# ── Postgres ──────────────────────────────────────────────────────────────────
pg_ctlcluster 12 main start 2>/dev/null || true
echo "[on_start] Postgres started"

# ── nginx ─────────────────────────────────────────────────────────────────────
nginx -t && (nginx 2>/dev/null || nginx -s reload 2>/dev/null || true)
echo "[on_start] nginx started"

# ── FastAPI (uvicorn) ──────────────────────────────────────────────────────────
cd /root/voicera-collector/backend
PYTHONUNBUFFERED=1 nohup /root/voicera-venv/bin/uvicorn main:app \
  --host 127.0.0.1 --port 8002 --workers 1 \
  >> /tmp/voicera-api.log 2>&1 &
echo "[on_start] uvicorn started (pid $!)"

echo "[on_start] All services up — $(date)"
