#!/usr/bin/env bash
# Build React static files without local Node (uses node:20-alpine). Run from repo root: voicera-collector/
set -euo pipefail
cd "$(dirname "$0")/.."
cd frontend

# Same-origin behind nginx → empty API base
: > .env.production
docker run --rm -v "$(pwd):/app" -w /app node:20-alpine sh -c "npm ci && npm run build"
echo "Built: frontend/build/"
