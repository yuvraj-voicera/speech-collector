"""Asyncpg connection pool (primary + optional read replica for stats)."""
from __future__ import annotations

from typing import Any, Dict, Optional

import asyncpg

import settings

_pool: Optional[asyncpg.Pool] = None
_read_pool: Optional[asyncpg.Pool] = None


def _server_settings() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if settings.DB_STATEMENT_TIMEOUT_MS > 0:
        out["statement_timeout"] = str(settings.DB_STATEMENT_TIMEOUT_MS)
    return out


async def init_pool() -> None:
    global _pool, _read_pool
    if not settings.postgres_configured():
        return
    if _pool is not None:
        return

    kwargs: Dict[str, Any] = {
        "min_size": settings.DB_POOL_MIN_SIZE,
        "max_size": settings.DB_POOL_MAX_SIZE,
        "command_timeout": settings.DB_COMMAND_TIMEOUT,
    }
    ss = _server_settings()
    if ss:
        kwargs["server_settings"] = ss

    _pool = await asyncpg.create_pool(settings.DATABASE_URL, **kwargs)

    if settings.read_replica_configured():
        rk = {**kwargs}
        rk["min_size"] = settings.DB_READ_POOL_MIN_SIZE
        rk["max_size"] = settings.DB_READ_POOL_MAX_SIZE
        _read_pool = await asyncpg.create_pool(settings.READ_DATABASE_URL, **rk)


async def close_pool() -> None:
    global _pool, _read_pool
    if _read_pool is not None:
        await _read_pool.close()
        _read_pool = None
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized; set DATABASE_URL")
    return _pool


def read_pool() -> asyncpg.Pool:
    """Use for read-heavy paths (stats). Falls back to primary if no replica."""
    if _read_pool is not None:
        return _read_pool
    return pool()
