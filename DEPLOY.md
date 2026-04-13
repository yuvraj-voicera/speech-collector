# Deploying Voicera collector (Postgres + S3 + FastAPI)

## Local dependencies

- **Postgres 16+** with schema from [backend/schema.sql](backend/schema.sql)
- **ffmpeg** / **ffprobe** (same as before)
- Optional **MinIO** or any **S3-compatible** bucket for WAV storage

Quick start:

```bash
cd voicera-collector
docker compose up -d
```

This starts Postgres (user/password/db `voicera`) and MinIO (`minioadmin` / `minioadmin`, API port **9000**, console **9001**). Apply env in `backend/.env` matching [backend/.env.example](backend/.env.example).

Create a bucket in MinIO Console (http://localhost:9001) named e.g. `voicera-recordings`, or let the API attempt `create_bucket` on first upload.

## Backend (FastAPI + ffmpeg)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Set DATABASE_URL, JWT_SECRET (long random), DEEPGRAM_API_KEY, S3_* for MinIO
python main.py
```

Docker image build (optional):

```bash
cd backend
docker build -t voicera-api .
docker run -p 8000:8000 --env-file .env -v voicera-data:/app/data voicera-api
```

- **`FRONTEND_ORIGINS`**: comma-separated CORS allowlist (production HTTPS origins).
- **`STATS_ADMIN_SECRET`**: send header **`X-Stats-Admin-Secret`** for global `/api/stats`.
- Mount **`/app/data`** if you rely on local WAV fallback or JSONL dual-write.

## Postgres under load

- **`max_connections`**: Docker Compose sets **200** on the bundled Postgres. On managed DBs, raise `max_connections` if you add API replicas.
- **Pool sizing** (`DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`): each **Uvicorn worker** opens its own pool. Keep **`workers × DB_POOL_MAX_SIZE`** (plus replicas × same) **below** `max_connections` minus overhead (e.g. leave 20–40 for admin/migrations).
- **`READ_DATABASE_URL`**: optional **read replica** used **only** for `/api/stats` (separate `DB_READ_POOL_*` limits). Primary `DATABASE_URL` still handles inserts and auth.
- **`DB_STATEMENT_TIMEOUT_MS`**: aborts long queries server-side (default 60s); set `0` to disable.
- **Indexes**: fresh installs use [backend/schema.sql](backend/schema.sql). Existing DBs can run [backend/migrations/002_perf_indexes.sql](backend/migrations/002_perf_indexes.sql) for added indexes.
- **Stats queries** use **SQL aggregation** (counts + `SUM(duration)`), not full row scans, so dashboards stay cheap at scale.

Production example (4 workers, 20 connections each → 80; replica optional):

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
# .env: DB_POOL_MAX_SIZE=20
```

## Frontend (static)

1. Copy [frontend/.env.production.example](frontend/.env.production.example) to `frontend/.env.production` and set **`REACT_APP_API_URL`** to the public API URL if the UI is not same-origin.
2. `cd frontend && npm run build`
3. Serve `frontend/build/` from any static host (nginx, S3, Netlify, etc.). Ensure CORS on the API includes that origin.

Dev: `package.json` **`proxy`** points to `http://localhost:8000` so `/api/*` works with an empty `REACT_APP_API_URL`.

## Security checklist

- Use strong **`JWT_SECRET`** and HTTPS in production.
- Set **`ALLOW_OPEN_REGISTRATION=false`** if only admins should create users (add a seed script or SQL insert for the first user).
- Keep buckets **private**; grant download via signed URLs or internal tooling, not public ACLs.

## RunPod (single CPU pod)

Use **[RUNPOD.md](RUNPOD.md)** for `docker-compose.prod.yml`, nginx on port **8000**, network volume paths, and verification scripts under `scripts/runpod-*.sh`.

## Migrating from Appwrite

Historical Appwrite data is not migrated automatically. Export documents and files from Appwrite if you need them, then import into Postgres/S3 with a one-off script, or start fresh.
