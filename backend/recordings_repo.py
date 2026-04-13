"""Recording rows and stats queries."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg


async def insert_recording(
    conn: asyncpg.Connection,
    *,
    recording_id: str,
    user_id: UUID,
    timestamp: datetime,
    storage_object_key: Optional[str],
    duration_seconds: Optional[float],
    speaker_slug: str,
    speaker_label: str,
    speaker_email: str,
    native_language: str,
    region: str,
    noise_level: str,
    device_type: str,
    prompt_id: str,
    prompt_text: str,
    prompt_category: str,
    session_id: str,
    prompt_bank_version: str,
    auto_transcript: str,
    final_transcript: str,
    was_corrected: bool,
    deepgram_confidence: float,
    deepgram_error: Optional[str],
    deepgram_words_json: str,
    age_range: Optional[str] = None,
    gender: Optional[str] = None,
    transcription_status: str = "pending",
    transcription_engine: Optional[str] = None,
    wer_score: Optional[float] = None,
    flagged: bool = False,
    flag_reason: Optional[str] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO recordings (
            id, user_id, timestamp, storage_object_key, duration_seconds,
            speaker_slug, speaker_label, speaker_email, native_language, region,
            noise_level, device_type, prompt_id, prompt_text, prompt_category,
            session_id, prompt_bank_version, auto_transcript, final_transcript,
            was_corrected, deepgram_confidence, deepgram_error, deepgram_words_json,
            age_range, gender,
            transcription_status, transcription_engine, wer_score, flagged, flag_reason
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
            $16, $17, $18, $19, $20, $21, $22, $23, $24, $25,
            $26, $27, $28, $29, $30
        )
        """,
        recording_id,
        user_id,
        timestamp,
        storage_object_key,
        duration_seconds,
        speaker_slug,
        speaker_label,
        speaker_email,
        native_language,
        region,
        noise_level,
        device_type,
        prompt_id,
        prompt_text,
        prompt_category,
        session_id,
        prompt_bank_version,
        auto_transcript,
        final_transcript,
        was_corrected,
        float(deepgram_confidence or 0),
        (deepgram_error or "")[:2000],
        (deepgram_words_json or "")[:16000],
        (age_range or None),
        (gender or None),
        transcription_status,
        transcription_engine,
        wer_score,
        flagged,
        flag_reason,
    )


async def update_transcription_result(
    conn: asyncpg.Connection,
    *,
    recording_id: str,
    storage_object_key: Optional[str],
    auto_transcript: str,
    final_transcript: str,
    was_corrected: bool,
    deepgram_confidence: float,
    deepgram_error: Optional[str],
    deepgram_words_json: str,
    transcription_status: str,
    transcription_engine: str,
    wer_score: Optional[float],
    flagged: bool,
    flag_reason: Optional[str],
) -> None:
    await conn.execute(
        """
        UPDATE recordings SET
            storage_object_key   = COALESCE($2, storage_object_key),
            auto_transcript      = $3,
            final_transcript     = $4,
            was_corrected        = $5,
            deepgram_confidence  = $6,
            deepgram_error       = $7,
            deepgram_words_json  = $8,
            transcription_status = $9,
            transcription_engine = $10,
            wer_score            = $11,
            flagged              = $12,
            flag_reason          = $13
        WHERE id = $1
        """,
        recording_id,
        storage_object_key,
        auto_transcript,
        final_transcript,
        was_corrected,
        float(deepgram_confidence or 0),
        (deepgram_error or "")[:2000],
        (deepgram_words_json or "")[:16000],
        transcription_status,
        transcription_engine,
        wer_score,
        flagged,
        flag_reason,
    )


def _aggregate(rows: List[asyncpg.Record]) -> Dict[str, Any]:
    speakers: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    total_duration = 0.0
    for row in rows:
        sid = row["speaker_slug"] or row["speaker_label"] or "unknown"
        speakers[sid] = speakers.get(sid, 0) + 1
        cat = row["prompt_category"] or "unknown"
        categories[cat] = categories.get(cat, 0) + 1
        total_duration += float(row["duration_seconds"] or 0)
    return {
        "total_recordings": len(rows),
        "total_duration_seconds": round(total_duration, 1),
        "total_duration_minutes": round(total_duration / 60, 1),
        "unique_speakers": len(speakers),
        "speakers": speakers,
        "categories": categories,
        "source": "postgres",
    }


async def _stats_aggregated_sql(
    conn: asyncpg.Connection,
    where_sql: str,
    user_id: Optional[UUID],
) -> Dict[str, Any]:
    """Single-user (user_id set) or global (user_id None) stats via SQL aggregation."""
    params: List[Any] = []
    if user_id is not None:
        params.append(user_id)

    total_row = await conn.fetchrow(
        f"""
        SELECT
            COUNT(*)::bigint AS n,
            COALESCE(SUM(duration_seconds), 0)::double precision AS dur
        FROM recordings
        WHERE {where_sql}
        """,
        *params,
    )
    n = int(total_row["n"] or 0) if total_row else 0
    dur = float(total_row["dur"] or 0) if total_row else 0.0

    speaker_rows = await conn.fetch(
        f"""
        SELECT
            COALESCE(NULLIF(TRIM(speaker_slug), ''), NULLIF(TRIM(speaker_label), ''), 'unknown') AS sid,
            COUNT(*)::int AS c
        FROM recordings
        WHERE {where_sql}
        GROUP BY 1
        """,
        *params,
    )
    speakers = {r["sid"]: r["c"] for r in speaker_rows}

    cat_rows = await conn.fetch(
        f"""
        SELECT prompt_category AS cat, COUNT(*)::int AS c
        FROM recordings
        WHERE {where_sql}
        GROUP BY prompt_category
        """,
        *params,
    )
    categories = {r["cat"] or "unknown": r["c"] for r in cat_rows}

    return {
        "total_recordings": n,
        "total_duration_seconds": round(dur, 1),
        "total_duration_minutes": round(dur / 60, 1),
        "unique_speakers": len(speakers),
        "speakers": speakers,
        "categories": categories,
        "source": "postgres",
    }


async def stats_for_user(conn: asyncpg.Connection, user_id: UUID) -> Dict[str, Any]:
    base = await _stats_aggregated_sql(conn, "user_id = $1", user_id)
    base["scope"] = "user"
    return base


async def stats_global(conn: asyncpg.Connection) -> Dict[str, Any]:
    base = await _stats_aggregated_sql(conn, "TRUE", None)
    base["scope"] = "global"
    return base
