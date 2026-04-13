"""JWT auth: register, login, me."""
from __future__ import annotations

from typing import Annotated, Optional

import asyncpg
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

import jwt_utils
import password_utils
import settings
from database import pool


router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = ""


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserPublic(BaseModel):
    id: str
    email: str
    name: str


async def get_current_user_public(
    authorization: Optional[str] = Header(None),
) -> dict:
    if not settings.postgres_configured():
        raise HTTPException(
            status_code=503,
            detail="Database auth not configured (DATABASE_URL)",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Bearer token",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt_utils.decode_token(token)
        uid = jwt_utils.token_subject_user_id(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e

    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, display_name FROM users WHERE id = $1",
            uid,
        )
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["display_name"] or "",
    }


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterBody) -> TokenResponse:
    if not settings.postgres_configured():
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    if not settings.JWT_SECRET:
        raise HTTPException(status_code=503, detail="JWT_SECRET not set")
    if not settings.ALLOW_OPEN_REGISTRATION:
        raise HTTPException(status_code=403, detail="Open registration is disabled")

    h = password_utils.hash_password(body.password)
    name = (body.name or body.email.split("@")[0]).strip()[:512]

    async with pool().acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, password_hash, display_name)
                VALUES (LOWER(TRIM($1)), $2, $3)
                RETURNING id, email, display_name
                """,
                str(body.email),
                h,
                name,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Email already registered") from None

    assert row is not None
    token = jwt_utils.create_access_token(
        user_id=str(row["id"]),
        email=row["email"],
    )
    return TokenResponse(
        access_token=token,
        user={
            "id": str(row["id"]),
            "email": row["email"],
            "name": row["display_name"] or "",
        },
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginBody) -> TokenResponse:
    if not settings.postgres_configured():
        raise HTTPException(status_code=503, detail="DATABASE_URL not set")
    if not settings.JWT_SECRET:
        raise HTTPException(status_code=503, detail="JWT_SECRET not set")

    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, email, display_name, password_hash FROM users
            WHERE LOWER(email) = LOWER(TRIM($1))
            """,
            str(body.email),
        )

    if not row or not password_utils.verify_password(
        body.password, row["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = jwt_utils.create_access_token(
        user_id=str(row["id"]),
        email=row["email"],
    )
    return TokenResponse(
        access_token=token,
        user={
            "id": str(row["id"]),
            "email": row["email"],
            "name": row["display_name"] or "",
        },
    )


@router.get("/me", response_model=UserPublic)
async def me(user: Annotated[dict, Depends(get_current_user_public)]) -> UserPublic:
    return UserPublic(id=user["id"], email=user["email"], name=user["name"])


__all__ = ["router", "get_current_user_public"]
