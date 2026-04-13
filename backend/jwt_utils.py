"""JWT access tokens for API auth."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

import settings


def create_access_token(*, user_id: str, email: str) -> str:
    if not settings.JWT_SECRET:
        raise ValueError("JWT_SECRET is not set")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict[str, Any]:
    if not settings.JWT_SECRET:
        raise jwt.InvalidTokenError("JWT_SECRET is not set")
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


def token_subject_user_id(payload: dict[str, Any]) -> UUID:
    sub = payload.get("sub")
    if not sub:
        raise jwt.InvalidTokenError("missing sub")
    return UUID(str(sub))
