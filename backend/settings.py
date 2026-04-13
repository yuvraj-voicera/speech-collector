"""Centralized environment for the collector API."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# Optional read replica for /api/stats only (same schema; streaming replica or RDS read endpoint)
READ_DATABASE_URL = os.getenv("READ_DATABASE_URL", "").strip()

# asyncpg pool (tune per Uvicorn worker: sum(max_size) across workers < Postgres max_connections)
DB_POOL_MIN_SIZE = max(1, int(os.getenv("DB_POOL_MIN_SIZE", "2")))
DB_POOL_MAX_SIZE = max(DB_POOL_MIN_SIZE, int(os.getenv("DB_POOL_MAX_SIZE", "20")))
DB_READ_POOL_MIN_SIZE = max(
    1, int(os.getenv("DB_READ_POOL_MIN_SIZE", str(DB_POOL_MIN_SIZE)))
)
DB_READ_POOL_MAX_SIZE = max(
    DB_READ_POOL_MIN_SIZE,
    int(os.getenv("DB_READ_POOL_MAX_SIZE", str(DB_POOL_MAX_SIZE))),
)
DB_COMMAND_TIMEOUT = float(os.getenv("DB_COMMAND_TIMEOUT", "60"))
# Server-side statement timeout (ms); 0 = disabled
DB_STATEMENT_TIMEOUT_MS = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "60000"))

JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip() or "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

ALLOW_OPEN_REGISTRATION = os.getenv("ALLOW_OPEN_REGISTRATION", "true").lower() in (
    "1",
    "true",
    "yes",
)

STATS_ADMIN_SECRET = os.getenv("STATS_ADMIN_SECRET", "").strip()
DUAL_WRITE_JSONL = os.getenv("DUAL_WRITE_JSONL", "true").lower() in ("1", "true", "yes")

# CORS: comma-separated origins; empty or * = allow all (dev-friendly)
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "").strip()

# S3-compatible storage (MinIO, AWS S3, etc.) — preferred when all fields are set
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "").strip()
S3_BUCKET = os.getenv("S3_BUCKET", "").strip()
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "").strip()
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
S3_REGION = os.getenv("S3_REGION", "us-east-1").strip() or "us-east-1"
S3_USE_SSL = os.getenv("S3_USE_SSL", "true").lower() in ("1", "true", "yes")
S3_ADDRESSING_STYLE = (os.getenv("S3_ADDRESSING_STYLE", "path").strip() or "path")
# Optional public base for signed/download URLs (CDN or external MinIO URL)
S3_PUBLIC_BASE_URL = os.getenv("S3_PUBLIC_BASE_URL", "").strip()

# Alibaba Cloud OSS storage (legacy oss2 SDK)
OSS_BUCKET_NAME = os.getenv("OSS_BUCKET_NAME", "").strip()
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "").strip()
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "").strip()
_env = os.getenv("APP_ENV", "local").strip().lower()
OSS_ENDPOINT = (
    os.getenv("OSS_ENDPOINT_PROD", "").strip()
    if _env in ("prod", "qa")
    else os.getenv("OSS_ENDPOINT_LOCAL", "").strip()
)
OSS_PUBLIC_ENDPOINT = os.getenv("OSS_PUBLIC_ENDPOINT", "").strip()


def postgres_configured() -> bool:
    return bool(DATABASE_URL)


def read_replica_configured() -> bool:
    return bool(READ_DATABASE_URL)


def s3_configured() -> bool:
    return bool(
        S3_ENDPOINT
        and S3_BUCKET
        and S3_ACCESS_KEY_ID
        and S3_SECRET_ACCESS_KEY
    )


def oss_configured() -> bool:
    return bool(
        OSS_BUCKET_NAME
        and OSS_ACCESS_KEY_ID
        and OSS_ACCESS_KEY_SECRET
        and OSS_ENDPOINT
    )


def object_storage_configured() -> bool:
    return s3_configured() or oss_configured()
