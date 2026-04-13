#!/usr/bin/env bash
# Creates persistent data dirs (default: /workspace/data). Run on RunPod after attaching a network volume.
set -euo pipefail

ROOT="${VOICERA_DATA_DIR:-/workspace/data}"
mkdir -p "$ROOT/pgdata" "$ROOT/miniodata" "$ROOT/appdata"
echo "Created: $ROOT/{pgdata,miniodata,appdata}"
ls -la "$ROOT"
