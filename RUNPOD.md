# Deploy on RunPod (CPU pod)

Single-pod layout: **Postgres + MinIO + FastAPI + nginx** on port **8000**, matching the RunPod HTTPS proxy (`https://<POD_ID>-8000.proxy.runpod.net`).

**Constraints:** RunPod container disk is small and ephemeral. Attach a **network volume** and mount it at **`/workspace`** so `VOICERA_DATA_DIR` (default `/workspace/data`) survives restarts.

## 1. SSH and verify environment

```bash
ssh -i ~/.ssh/id_ed25519 <user>@ssh.runpod.io
```

On the pod:

```bash
bash voicera-collector/scripts/runpod-verify.sh
```

Confirm `df -h /workspace` shows a dedicated volume (not only overlay storage).

## 2. Upload code

From your laptop (adjust paths and SSH target):

```bash
scp -i ~/.ssh/id_ed25519 -r voicera-collector/ <user>@ssh.runpod.io:/workspace/speech-collector/
```

Or clone inside `/workspace`:

```bash
cd /workspace && git clone <your-repo-url> speech-collector
cd speech-collector/voicera-collector   # if repo root contains this folder
```

## 3. Persistent data directories

```bash
cd /workspace/speech-collector/voicera-collector   # repo path as uploaded
bash scripts/runpod-bootstrap.sh
```

Equivalent: `mkdir -p /workspace/data/{pgdata,miniodata,appdata}`.

Override root: `export VOICERA_DATA_DIR=/your/volume/path` before compose commands.

## 4. Build the React frontend

Requires Docker (no host Node needed):

```bash
cd /workspace/speech-collector/voicera-collector
bash scripts/runpod-build-frontend.sh
```

This writes `frontend/.env.production` (empty `REACT_APP_API_URL` = same-origin) and produces **`frontend/build/`**, which nginx mounts.

## 5. Backend env + compose files

Repo already includes:

- `docker-compose.prod.yml` — tuned for ~2 vCPU / 8 GB RAM
- `nginx.conf` — port 8000, `/api/` → API, SPA fallback
- `backend/.env.runpod.example` — template

Create secrets on the pod:

```bash
cp backend/.env.runpod.example backend/.env
nano backend/.env   # or vi
```

Set at minimum:

- `DEEPGRAM_API_KEY`
- `JWT_SECRET` (e.g. `openssl rand -hex 32`)
- `FRONTEND_ORIGINS=https://<POD_ID>-8000.proxy.runpod.net` (your real proxy URL; `POD_ID` matches the SSH hostname segment before the first dash)
- `STATS_ADMIN_SECRET` (optional, for `/api/stats` admin header)

Keep **`S3_BUCKET=voicera-recordings`** unless you change **`minio_init`** in `docker-compose.prod.yml` to the same name.

## 6. Launch Docker Compose

```bash
cd /workspace/speech-collector/voicera-collector
bash scripts/runpod-up.sh
```

Or manually:

```bash
export VOICERA_DATA_DIR=/workspace/data   # default if unset
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f
```

**MinIO bucket:** `minio_init` runs once and creates `voicera-recordings`. The API also attempts bucket creation on first upload.

**Local / non-RunPod test:** `export VOICERA_DATA_DIR=./data` from `voicera-collector/` and ensure `./data/pgdata` etc. exist.

## 7. Smoke test (E2E)

1. Open **`https://<POD_ID>-8000.proxy.runpod.net`** — login/register UI.
2. Register, complete speaker flow, record one prompt.
3. **API health:** `curl -sS https://<POD_ID>-8000.proxy.runpod.net/api/health` → `ok`, `postgres`, `object_storage`, `s3` true.
4. **Postgres:**

   ```bash
   docker compose -f docker-compose.prod.yml exec postgres \
     psql -U voicera -d voicera -c "SELECT count(*) FROM recordings;"
   ```

5. **MinIO objects** (run a one-off client; API container has no `mc`):

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --entrypoint /bin/sh minio_init -c \
     "mc alias set local http://minio:9000 minioadmin minioadmin && mc ls local/voicera-recordings/"
   ```

6. **JSONL** (dual-write): `wc -l /workspace/data/appdata/metadata.jsonl` (or your `VOICERA_DATA_DIR`).

## Notes

- **`deploy.resources`** in Compose is **ignored** except under Docker Swarm; limits are documentation-only unless you use Swarm/Kubernetes.
- **HTTPS** is terminated at RunPod; no TLS certs in the pod for the proxy port.
- **Backups:** periodic `pg_dump` and archive of `miniodata` + `appdata`.
- See also [DEPLOY.md](DEPLOY.md).
