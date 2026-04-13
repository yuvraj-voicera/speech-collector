#!/usr/bin/env bash
# Run on the RunPod host after SSH. Checks CPU/RAM/disk, Docker, and /workspace persistence.
set -euo pipefail

echo "=== CPU / memory ==="
nproc
free -h || true

echo "=== Disk (confirm /workspace is a separate mount = network volume) ==="
df -h /
df -h /workspace 2>/dev/null || echo "No /workspace — attach a RunPod network volume and mount at /workspace"

echo "=== Docker ==="
docker --version
docker compose version

echo "=== Sample /workspace listing ==="
ls -la /workspace 2>/dev/null || true
