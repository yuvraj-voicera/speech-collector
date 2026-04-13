#!/usr/bin/env bash
# Build API image and start stack. Run from voicera-collector/ with backend/.env present.
set -euo pipefail
cd "$(dirname "$0")/.."
export VOICERA_DATA_DIR="${VOICERA_DATA_DIR:-/workspace/data}"
docker compose -f docker-compose.prod.yml up -d --build
echo "Services starting. Logs: docker compose -f docker-compose.prod.yml logs -f"
echo "Health (via proxy or curl from host): curl -sS http://127.0.0.1:8000/api/health"
