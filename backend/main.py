import asyncio
import csv
import io
import json
import os
import re
import random
import uuid
import wave as _wave_module
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import jwt
import subprocess
from collections import defaultdict
from dotenv import load_dotenv

try:
    import imageio_ffmpeg as _iio_ffmpeg
    _FFMPEG_EXE = _iio_ffmpeg.get_ffmpeg_exe()
    _FFPROBE_EXE = _FFMPEG_EXE.replace("ffmpeg", "ffprobe")
    import os as _os
    if not _os.path.exists(_FFPROBE_EXE):
        _FFPROBE_EXE = "ffprobe"
except Exception:
    _FFMPEG_EXE = "ffmpeg"
    _FFPROBE_EXE = "ffprobe"

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

import auth_routes
import database
import jwt_utils
import recordings_repo
import settings
import storage_s3

# ---------------------------------------------------------------------------
# Whisper model (lazy-loaded on first transcription, shared across requests)
# ---------------------------------------------------------------------------
_whisper_model = None
_whisper_lock = asyncio.Lock()

WER_FLAG_THRESHOLD = 0.4   # flag recording if WER > 40%


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await database.init_pool()
    yield
    await database.close_pool()


app = FastAPI(title="VoiceraCX Data Collector", lifespan=lifespan)

_cors_raw = settings.FRONTEND_ORIGINS
if _cors_raw and _cors_raw != "*":
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


STORAGE_DIR = Path("./data")
AUDIO_DIR = STORAGE_DIR / "audio"
METADATA_FILE = STORAGE_DIR / "metadata.jsonl"
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
METADATA_FILE.touch(exist_ok=True)

app.include_router(auth_routes.router)


def _resolve_user_id_optional(authorization: Optional[str]) -> Optional[UUID]:
    if not settings.postgres_configured():
        return None
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        payload = jwt_utils.decode_token(token)
        return jwt_utils.token_subject_user_id(payload)
    except (jwt.InvalidTokenError, ValueError, jwt.ExpiredSignatureError):
        return None


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "postgres": settings.postgres_configured(),
        "read_replica": settings.read_replica_configured(),
        "db_pool_max": settings.DB_POOL_MAX_SIZE,
        "object_storage": settings.object_storage_configured(),
        "s3": settings.s3_configured(),
        "oss": settings.oss_configured(),
    }


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def convert_to_16k_mono_wav(input_path: Path, output_path: Path) -> bool:
    try:
        result = subprocess.run(
            [
                _FFMPEG_EXE, "-y", "-i", str(input_path),
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                str(output_path),
            ],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _verify_wav_spec(wav_path: Path) -> bool:
    try:
        with _wave_module.open(str(wav_path), "rb") as wf:
            ok = wf.getnchannels() == 1 and wf.getframerate() == 16000 and wf.getsampwidth() == 2
            if not ok:
                print(f"[wav] spec mismatch: ch={wf.getnchannels()} rate={wf.getframerate()} sw={wf.getsampwidth()}")
            return ok
    except Exception as exc:
        print(f"[wav] verify failed: {exc}")
        return False


def _wav_duration(wav_path: Path) -> Optional[float]:
    try:
        with _wave_module.open(str(wav_path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Text normalisation & WER
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate: Levenshtein distance on word tokens / reference length."""
    from rapidfuzz.distance import Levenshtein
    ref_words = _normalize(reference).split()
    hyp_words = _normalize(hypothesis).split()
    if not ref_words:
        return 0.0
    distance = Levenshtein.distance(ref_words, hyp_words)
    return distance / len(ref_words)


# ---------------------------------------------------------------------------
# Transcription engines
# ---------------------------------------------------------------------------

async def transcribe_with_deepgram(audio_path: Path) -> dict:
    if not DEEPGRAM_API_KEY:
        return {"transcript": "", "confidence": 0.0, "words": [], "detected_language": "", "error": "No API key"}

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.deepgram.com/v1/listen",
            headers={
                "Authorization": f"Token {DEEPGRAM_API_KEY}",
                "Content-Type": "audio/wav",
            },
            params={
                "model": "nova-2",
                "language": "multi",
                "smart_format": "true",
                "punctuate": "true",
                "diarize": "false",
                "utterances": "false",
            },
            content=audio_bytes,
        )

    if response.status_code != 200:
        return {"transcript": "", "confidence": 0.0, "words": [], "detected_language": "", "error": response.text}

    data = response.json()
    channel = data["results"]["channels"][0]
    alt = channel["alternatives"][0]
    return {
        "transcript": alt.get("transcript", ""),
        "confidence": alt.get("confidence", 0.0),
        "words": alt.get("words", []),
        "detected_language": channel.get("detected_language", ""),
        "error": None,
    }


def _whisper_transcribe_sync(audio_path: Path) -> dict:
    """CPU-bound — run via run_in_executor."""
    global _whisper_model
    try:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            print("[whisper] Loading base model…")
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            print("[whisper] Model loaded.")

        segments, info = _whisper_model.transcribe(
            str(audio_path), beam_size=5, word_timestamps=True
        )
        words = []
        parts = []
        for seg in segments:
            parts.append(seg.text.strip())
            if seg.words:
                for w in seg.words:
                    words.append({
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    })
        transcript = " ".join(parts).strip()
        confidence = (
            sum(w["probability"] for w in words) / len(words) if words else 0.0
        )
        return {
            "transcript": transcript,
            "confidence": round(confidence, 4),
            "words": words,
            "detected_language": info.language,
            "error": None,
        }
    except Exception as exc:
        print(f"[whisper] transcription error: {exc}")
        return {"transcript": "", "confidence": 0.0, "words": [], "detected_language": "", "error": str(exc)}


async def transcribe_with_whisper(audio_path: Path) -> dict:
    """Async wrapper — offloads CPU work to thread pool."""
    loop = asyncio.get_event_loop()
    async with _whisper_lock:
        return await loop.run_in_executor(None, _whisper_transcribe_sync, audio_path)


async def _transcribe_with_verification(
    audio_path: Path,
    prompt_text: str,
    prompt_category: str,
) -> tuple[dict, str, Optional[float], bool, Optional[str]]:
    """
    Returns (result, engine, wer_score, flagged, flag_reason).

    Strategy:
      1. Try Deepgram. If it succeeds and WER is fine → done.
      2. If Deepgram WER > threshold → run Whisper as second opinion.
         - Whisper clears the flag (WER ≤ threshold) → use Whisper, not flagged.
         - Both engines agree it's bad → flag; use whichever has the lower WER.
      3. If no Deepgram key or Deepgram hard-fails → Whisper only.
    Identity prompts are never WER-checked (ground truth is used anyway).
    """
    is_identity = prompt_category == "identity"

    def _wer_check(result: dict) -> tuple[Optional[float], bool]:
        if is_identity or not result["transcript"]:
            return None, False
        wer = compute_wer(prompt_text, result["transcript"])
        return wer, wer > WER_FLAG_THRESHOLD

    if DEEPGRAM_API_KEY:
        dg = await transcribe_with_deepgram(audio_path)
        if not dg["error"] and dg["transcript"]:
            dg_wer, dg_flagged = _wer_check(dg)
            if dg_flagged:
                print(
                    f"[transcribe] Deepgram WER={dg_wer:.2f} > threshold "
                    f"— running Whisper for second opinion"
                )
                ws = await transcribe_with_whisper(audio_path)
                ws_wer, ws_flagged = _wer_check(ws)
                if not ws_flagged:
                    # Whisper disagrees — recording is fine, use Whisper result
                    print(f"[transcribe] Whisper WER={ws_wer:.2f} clears the flag — using Whisper")
                    return ws, "whisper", ws_wer, False, None
                # Both engines agree it's a mismatch — use whichever scored lower
                print(
                    f"[transcribe] Both engines flag: "
                    f"Deepgram WER={dg_wer:.2f}, Whisper WER={ws_wer:.2f}"
                )
                if ws_wer <= dg_wer:
                    return ws, "whisper", ws_wer, True, "text_mismatch"
                return dg, "deepgram", dg_wer, True, "text_mismatch"
            return dg, "deepgram", dg_wer, False, None
        print(f"[transcribe] Deepgram failed ({dg['error']}) — falling back to Whisper")

    ws = await transcribe_with_whisper(audio_path)
    ws_wer, ws_flagged = _wer_check(ws)
    return ws, "whisper", ws_wer, ws_flagged, "text_mismatch" if ws_flagged else None


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------

async def process_recording_background(
    *,
    recording_id: str,
    wav_path: Path,
    raw_path: Path,
    converted: bool,
    user_id: Optional[UUID],
    prompt_id: str,
    prompt_text: str,
    prompt_category: str,
    speaker_name: str,
    speaker_email: str,
    jwt_email: str,
    corrected_transcript: Optional[str],
    jsonl_record: dict,
) -> None:
    """
    Runs after the HTTP response is sent:
      1. Transcribe (Deepgram → Whisper fallback)
      2. Build final transcript
      3. Compute WER vs prompt_text → flag if mismatch
      4. Upload audio to object storage
      5. UPDATE recordings row
      6. Dual-write JSONL (if configured)
      7. Clean up raw temp file
    """
    print(f"[bg:{recording_id}] Starting background processing")

    # 1. Transcribe — Deepgram first, Whisper second-opinion if flagged
    tr_result, engine, wer_score, flagged, flag_reason = await _transcribe_with_verification(
        wav_path, prompt_text, prompt_category
    )
    auto_transcript = tr_result["transcript"]

    # 2. Determine final transcript
    if prompt_category == "identity":
        if prompt_id == "id_001":
            ground_truth = speaker_name.strip()
        elif prompt_id == "id_002":
            ground_truth = (speaker_email or jwt_email or "").strip()
        else:
            ground_truth = ""
        final_transcript = ground_truth if ground_truth else auto_transcript
        wer_score = None      # identity prompts are never WER-checked
        flagged = False
        flag_reason = None
    elif corrected_transcript and corrected_transcript.strip():
        # User manually corrected — re-score the correction, not the auto transcript
        final_transcript = corrected_transcript.strip()
        wer_score = compute_wer(prompt_text, final_transcript)
        flagged = wer_score > WER_FLAG_THRESHOLD
        flag_reason = "text_mismatch" if flagged else None
    else:
        final_transcript = auto_transcript
        # wer_score / flagged / flag_reason already set by _transcribe_with_verification

    was_corrected = final_transcript != auto_transcript
    words_json = json.dumps(tr_result["words"] or [])

    wer_display = f"{wer_score:.2f}" if wer_score is not None else "n/a"
    print(
        f"[bg:{recording_id}] engine={engine} wer={wer_display} "
        f"flagged={flagged} transcript={repr(final_transcript[:60])}"
    )

    # 3. Upload to object storage
    storage_object_key: Optional[str] = None
    if user_id and settings.object_storage_configured():
        key = storage_s3.build_object_key(str(user_id), recording_id)
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, storage_s3.upload_wav_file, wav_path, key
            )
            storage_object_key = key
            print(f"[bg:{recording_id}] Uploaded to object storage: {key}")
        except Exception as exc:
            print(f"[bg:{recording_id}] Object storage upload failed: {exc}")

    if not storage_object_key and user_id:
        storage_object_key = f"local/{recording_id}.wav"

    # 4. Update DB
    if user_id and settings.postgres_configured():
        try:
            async with database.pool().acquire() as conn:
                await recordings_repo.update_transcription_result(
                    conn,
                    recording_id=recording_id,
                    storage_object_key=storage_object_key,
                    auto_transcript=auto_transcript,
                    final_transcript=final_transcript,
                    was_corrected=was_corrected,
                    deepgram_confidence=tr_result["confidence"],
                    deepgram_error=tr_result["error"],
                    deepgram_words_json=words_json,
                    transcription_status="done",
                    transcription_engine=engine,
                    wer_score=wer_score,
                    flagged=flagged,
                    flag_reason=flag_reason,
                )
            print(f"[bg:{recording_id}] DB updated — status=done")
        except Exception as exc:
            print(f"[bg:{recording_id}] DB update failed: {exc}")

    # 5. JSONL dual-write (with final transcript data)
    if not settings.postgres_configured() or settings.DUAL_WRITE_JSONL:
        jsonl_record["transcription"].update({
            "auto_transcript": auto_transcript,
            "final_transcript": final_transcript,
            "was_corrected": was_corrected,
            "engine": engine,
            "deepgram_confidence": tr_result["confidence"],
            "deepgram_detected_language": tr_result.get("detected_language", ""),
            "deepgram_words": tr_result["words"],
            "deepgram_error": tr_result["error"],
            "wer_score": wer_score,
            "flagged": flagged,
            "flag_reason": flag_reason,
        })
        if storage_object_key:
            jsonl_record["storage_object_key"] = storage_object_key
        try:
            with open(METADATA_FILE, "a") as f:
                f.write(json.dumps(jsonl_record) + "\n")
        except Exception as exc:
            print(f"[bg:{recording_id}] JSONL write failed: {exc}")

    # 6. Clean up raw temp file
    if converted and raw_path != wav_path and raw_path.exists():
        raw_path.unlink(missing_ok=True)

    print(f"[bg:{recording_id}] Background processing complete")


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_recording(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    speaker_id: str = Form(...),
    speaker_name: str = Form(...),
    native_language: str = Form(...),
    region: str = Form(...),
    prompt_id: str = Form(...),
    prompt_text: str = Form(...),
    prompt_category: str = Form(...),
    noise_level: str = Form(...),
    device_type: str = Form(...),
    speaker_email: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    prompt_bank_version: Optional[str] = Form(None),
    corrected_transcript: Optional[str] = Form(None),
    age_range: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    # --- Auth ---
    user: Optional[dict] = None
    jwt_email = ""
    if settings.postgres_configured():
        user = await auth_routes.get_current_user_public(authorization)
        jwt_email = user["email"]

    se = (speaker_email or "").strip()
    if jwt_email and se and se.lower() != jwt_email.lower():
        raise HTTPException(
            status_code=400,
            detail="speaker_email does not match the logged-in account",
        )

    # --- Save raw audio ---
    recording_id = str(uuid.uuid4())[:8]
    ts = datetime.now(timezone.utc)
    timestamp = ts.isoformat()

    raw_path = AUDIO_DIR / f"{recording_id}_raw{Path(audio.filename).suffix or '.webm'}"
    wav_path = AUDIO_DIR / f"{recording_id}.wav"

    raw_bytes = await audio.read()
    with open(raw_path, "wb") as f:
        f.write(raw_bytes)

    # --- Convert to 16 kHz mono WAV ---
    converted = convert_to_16k_mono_wav(raw_path, wav_path)
    if converted:
        if not _verify_wav_spec(wav_path):
            print(f"[wav] invalid spec after conversion, falling back to raw for {recording_id}")
            wav_path = raw_path
    else:
        wav_path = raw_path

    # --- Duration validation (fast — only reads WAV header) ---
    duration_seconds = _wav_duration(wav_path)
    MIN_DURATION, MAX_DURATION = 1.0, 30.0

    if duration_seconds is not None:
        if duration_seconds < MIN_DURATION:
            for p in (raw_path, wav_path):
                p.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail=f"Recording too short ({duration_seconds:.2f}s). Minimum is {MIN_DURATION}s.",
            )
        if duration_seconds > MAX_DURATION:
            for p in (raw_path, wav_path):
                p.unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail=f"Recording too long ({duration_seconds:.2f}s). Maximum is {MAX_DURATION}s.",
            )

    # --- Metadata ---
    pbv = (prompt_bank_version or "").strip() or "2.0"
    sid = (session_id or "").strip()
    age_range_val: Optional[str] = (age_range.strip() or None) if age_range else None
    gender_val: Optional[str] = (gender.strip() or None) if gender else None

    # --- Insert pending DB row immediately ---
    if user and settings.postgres_configured():
        try:
            async with database.pool().acquire() as conn:
                await recordings_repo.insert_recording(
                    conn,
                    recording_id=recording_id,
                    user_id=UUID(user["id"]),
                    timestamp=ts,
                    storage_object_key=None,       # filled in by background task
                    duration_seconds=duration_seconds,
                    speaker_slug=speaker_id,
                    speaker_label=speaker_name,
                    speaker_email=se,
                    native_language=native_language,
                    region=region,
                    noise_level=noise_level,
                    device_type=device_type,
                    prompt_id=prompt_id,
                    prompt_text=prompt_text,
                    prompt_category=prompt_category,
                    session_id=sid,
                    prompt_bank_version=pbv,
                    auto_transcript="",
                    final_transcript="",
                    was_corrected=False,
                    deepgram_confidence=0.0,
                    deepgram_error=None,
                    deepgram_words_json="[]",
                    age_range=age_range_val,
                    gender=gender_val,
                    transcription_status="pending",
                )
        except Exception as exc:
            print(f"[postgres] initial insert failed: {exc}")
            raise HTTPException(status_code=502, detail=f"Database write failed: {exc}") from exc

    # JSONL skeleton — filled in by background task
    jsonl_record: dict = {
        "id": recording_id,
        "timestamp": timestamp,
        "audio_path": str(wav_path.name),
        "session_id": sid,
        "prompt_bank_version": pbv,
        "speaker": {
            "id": speaker_id,
            "name": speaker_name,
            "email": se,
            "native_language": native_language,
            "region": region,
            "age_range": age_range_val,
            "gender": gender_val,
        },
        "prompt": {"id": prompt_id, "text": prompt_text, "category": prompt_category},
        "recording": {
            "noise_level": noise_level,
            "device_type": device_type,
            "duration_seconds": duration_seconds,
            "sample_rate": 16000,
            "channels": 1,
            "format": "wav",
        },
        "transcription": {},   # filled in by background task
    }

    # --- Kick off background task and return immediately ---
    background_tasks.add_task(
        process_recording_background,
        recording_id=recording_id,
        wav_path=wav_path,
        raw_path=raw_path,
        converted=converted,
        user_id=UUID(user["id"]) if user else None,
        prompt_id=prompt_id,
        prompt_text=prompt_text,
        prompt_category=prompt_category,
        speaker_name=speaker_name,
        speaker_email=se,
        jwt_email=jwt_email,
        corrected_transcript=corrected_transcript,
        jsonl_record=jsonl_record,
    )

    return JSONResponse({
        "success": True,
        "recording_id": recording_id,
        "duration_seconds": duration_seconds,
        "status": "processing",
        "message": "Recording accepted. Transcription is running in the background.",
    })


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def _stats_from_jsonl() -> dict:
    if not METADATA_FILE.exists():
        return {
            "total_recordings": 0,
            "total_duration_seconds": 0,
            "speakers": {},
            "categories": {},
        }
    records = []
    with open(METADATA_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    speakers = {}
    categories = {}
    total_duration = 0.0
    for r in records:
        sid = r["speaker"]["id"]
        speakers[sid] = speakers.get(sid, 0) + 1
        cat = r["prompt"]["category"]
        categories[cat] = categories.get(cat, 0) + 1
        total_duration += r["recording"].get("duration_seconds") or 0
    return {
        "total_recordings": len(records),
        "total_duration_seconds": round(total_duration, 1),
        "total_duration_minutes": round(total_duration / 60, 1),
        "unique_speakers": len(speakers),
        "speakers": speakers,
        "categories": categories,
        "source": "local_jsonl",
    }


@app.get("/api/stats")
async def get_stats(
    authorization: Optional[str] = Header(None),
    x_stats_admin_secret: Optional[str] = Header(None, alias="X-Stats-Admin-Secret"),
):
    if settings.postgres_configured():
        secret_ok = (
            settings.STATS_ADMIN_SECRET
            and x_stats_admin_secret
            and x_stats_admin_secret == settings.STATS_ADMIN_SECRET
        )
        if secret_ok:
            async with database.read_pool().acquire() as conn:
                return await recordings_repo.stats_global(conn)
        uid = _resolve_user_id_optional(authorization)
        if uid:
            async with database.read_pool().acquire() as conn:
                return await recordings_repo.stats_for_user(conn, uid)
        raise HTTPException(
            status_code=401,
            detail="Send Authorization: Bearer <JWT> for your stats, or X-Stats-Admin-Secret for global totals",
        )
    return _stats_from_jsonl()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _export_from_jsonl(
    min_confidence: float,
    category: Optional[str],
    min_duration: float,
    was_corrected: Optional[bool],
    limit: int,
) -> list:
    if not METADATA_FILE.exists():
        return []
    results = []
    with open(METADATA_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            conf = r.get("transcription", {}).get("deepgram_confidence") or 0.0
            if conf < min_confidence:
                continue
            dur = r.get("recording", {}).get("duration_seconds") or 0.0
            if dur < min_duration:
                continue
            cat = r.get("prompt", {}).get("category", "")
            if category and cat != category:
                continue
            corrected = r.get("transcription", {}).get("was_corrected")
            if was_corrected is not None and corrected != was_corrected:
                continue
            spk = r.get("speaker", {})
            tr = r.get("transcription", {})
            results.append({
                "recording_id": r.get("id"),
                "timestamp": r.get("timestamp"),
                "storage_object_key": r.get("storage_object_key"),
                "audio_path": r.get("audio_path"),
                "duration_seconds": dur,
                "speaker_slug": spk.get("id"),
                "native_language": spk.get("native_language"),
                "region": spk.get("region"),
                "noise_level": r.get("recording", {}).get("noise_level"),
                "device_type": r.get("recording", {}).get("device_type"),
                "prompt_id": r.get("prompt", {}).get("id"),
                "prompt_text": r.get("prompt", {}).get("text"),
                "prompt_category": cat,
                "session_id": r.get("session_id"),
                "prompt_bank_version": r.get("prompt_bank_version"),
                "final_transcript": tr.get("final_transcript"),
                "auto_transcript": tr.get("auto_transcript"),
                "was_corrected": corrected,
                "deepgram_confidence": conf,
                "transcription_engine": tr.get("engine"),
                "wer_score": tr.get("wer_score"),
                "flagged": tr.get("flagged"),
                "flag_reason": tr.get("flag_reason"),
                "age_range": spk.get("age_range"),
                "gender": spk.get("gender"),
            })
            if len(results) >= limit:
                break
    return results


EXPORT_COLUMNS = [
    "recording_id", "timestamp", "storage_object_key", "audio_path",
    "duration_seconds", "speaker_slug", "native_language", "region",
    "noise_level", "device_type", "prompt_id", "prompt_text",
    "prompt_category", "session_id", "prompt_bank_version",
    "final_transcript", "auto_transcript", "was_corrected",
    "deepgram_confidence", "transcription_engine", "wer_score",
    "flagged", "flag_reason", "age_range", "gender",
]


@app.get("/api/export")
async def export_recordings(
    x_stats_admin_secret: Optional[str] = Header(None, alias="X-Stats-Admin-Secret"),
    format: str = Query("jsonl", pattern="^(jsonl|csv)$"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    category: Optional[str] = Query(None),
    min_duration: float = Query(0.0, ge=0.0),
    was_corrected: Optional[bool] = Query(None),
    flagged: Optional[bool] = Query(None),
    limit: int = Query(10000, ge=1, le=100000),
):
    secret_ok = (
        settings.STATS_ADMIN_SECRET
        and x_stats_admin_secret
        and x_stats_admin_secret == settings.STATS_ADMIN_SECRET
    )
    if not secret_ok:
        raise HTTPException(
            status_code=401,
            detail="X-Stats-Admin-Secret header required for export",
        )

    media_type = "application/x-ndjson" if format == "jsonl" else "text/csv"
    filename = f"voicera_export.{format}"

    if settings.postgres_configured():
        wheres: list = []
        params: list = []

        if min_confidence > 0:
            params.append(min_confidence)
            wheres.append(f"deepgram_confidence >= ${len(params)}")
        if min_duration > 0:
            params.append(min_duration)
            wheres.append(f"duration_seconds >= ${len(params)}")
        if category:
            params.append(category)
            wheres.append(f"prompt_category = ${len(params)}")
        if was_corrected is not None:
            params.append(was_corrected)
            wheres.append(f"was_corrected = ${len(params)}")
        if flagged is not None:
            params.append(flagged)
            wheres.append(f"flagged = ${len(params)}")

        where_sql = " AND ".join(wheres) if wheres else "TRUE"
        params.append(limit)

        sql = f"""
            SELECT
                id AS recording_id,
                timestamp::text AS timestamp,
                storage_object_key,
                NULL::text AS audio_path,
                duration_seconds,
                speaker_slug,
                native_language,
                region,
                noise_level,
                device_type,
                prompt_id,
                prompt_text,
                prompt_category,
                session_id,
                prompt_bank_version,
                final_transcript,
                auto_transcript,
                was_corrected,
                deepgram_confidence,
                transcription_engine,
                wer_score,
                flagged,
                flag_reason,
                age_range,
                gender
            FROM recordings
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ${len(params)}
        """

        async def pg_stream():
            async with database.read_pool().acquire() as conn:
                rows = await conn.fetch(sql, *params)
            if format == "jsonl":
                for row in rows:
                    yield json.dumps(dict(row)) + "\n"
            else:
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
                writer.writeheader()
                yield buf.getvalue()
                for row in rows:
                    buf = io.StringIO()
                    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
                    writer.writerow({k: (dict(row).get(k) or "") for k in EXPORT_COLUMNS})
                    yield buf.getvalue()

        return StreamingResponse(
            pg_stream(),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    else:
        records = _export_from_jsonl(
            min_confidence=min_confidence,
            category=category,
            min_duration=min_duration,
            was_corrected=was_corrected,
            limit=limit,
        )

        def local_stream():
            if format == "jsonl":
                for rec in records:
                    yield json.dumps(rec) + "\n"
            else:
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
                writer.writeheader()
                yield buf.getvalue()
                for rec in records:
                    buf = io.StringIO()
                    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS)
                    writer.writerow({k: (rec.get(k) or "") for k in EXPORT_COLUMNS})
                    yield buf.getvalue()

        return StreamingResponse(
            local_stream(),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


# ---------------------------------------------------------------------------
# Admin — flagged recording review queue (A)
# ---------------------------------------------------------------------------

def _require_admin(x_stats_admin_secret: Optional[str]) -> None:
    if (
        not settings.STATS_ADMIN_SECRET
        or x_stats_admin_secret != settings.STATS_ADMIN_SECRET
    ):
        raise HTTPException(status_code=401, detail="X-Stats-Admin-Secret required")


@app.get("/api/admin/flagged")
async def admin_flagged_recordings(
    x_stats_admin_secret: Optional[str] = Header(None, alias="X-Stats-Admin-Secret"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List recordings flagged by both transcription engines for admin review."""
    _require_admin(x_stats_admin_secret)
    async with database.read_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id, timestamp, prompt_text, prompt_category, prompt_id,
                auto_transcript, final_transcript, was_corrected,
                transcription_engine, wer_score, flag_reason,
                deepgram_confidence, duration_seconds,
                speaker_slug, native_language, region,
                transcription_status
            FROM recordings
            WHERE flagged = TRUE
              AND transcription_status != 'rejected'
            ORDER BY timestamp DESC
            LIMIT $1 OFFSET $2
            """,
            limit, offset,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM recordings WHERE flagged = TRUE AND transcription_status != 'rejected'"
        )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "recordings": [dict(r) for r in rows],
    }


class ReviewBody(dict):
    pass


@app.patch("/api/admin/recordings/{recording_id}")
async def admin_review_recording(
    recording_id: str,
    body: dict,
    x_stats_admin_secret: Optional[str] = Header(None, alias="X-Stats-Admin-Secret"),
):
    """
    Approve or reject a flagged recording.

    Body for approve:
        {"action": "approve", "final_transcript": "corrected text"}
    Body for reject:
        {"action": "reject"}
    """
    _require_admin(x_stats_admin_secret)

    action = (body.get("action") or "").strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    async with database.pool().acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM recordings WHERE id = $1", recording_id
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Recording not found")

        if action == "approve":
            final_transcript = (body.get("final_transcript") or "").strip()
            if not final_transcript:
                raise HTTPException(
                    status_code=400,
                    detail="final_transcript is required for approve",
                )
            await conn.execute(
                """
                UPDATE recordings SET
                    final_transcript     = $2,
                    was_corrected        = TRUE,
                    flagged              = FALSE,
                    flag_reason          = NULL,
                    transcription_status = 'done'
                WHERE id = $1
                """,
                recording_id,
                final_transcript,
            )
        else:  # reject
            await conn.execute(
                """
                UPDATE recordings SET
                    transcription_status = 'rejected'
                WHERE id = $1
                """,
                recording_id,
            )

    return {"ok": True, "recording_id": recording_id, "action": action}


@app.get("/api/admin/stats")
async def admin_flagged_stats(
    x_stats_admin_secret: Optional[str] = Header(None, alias="X-Stats-Admin-Secret"),
):
    """Quick overview of flagged / pending / rejected counts."""
    _require_admin(x_stats_admin_secret)
    async with database.read_pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                transcription_status,
                flagged,
                COUNT(*)::int AS n
            FROM recordings
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )
    breakdown: dict = {}
    for r in rows:
        key = r["transcription_status"]
        breakdown.setdefault(key, {"total": 0, "flagged": 0})
        breakdown[key]["total"] += r["n"]
        if r["flagged"]:
            breakdown[key]["flagged"] += r["n"]
    return {"breakdown": breakdown}


# ---------------------------------------------------------------------------
# Training data export
# ---------------------------------------------------------------------------

@app.get("/api/export/training")
async def export_training(
    x_stats_admin_secret: Optional[str] = Header(None, alias="X-Stats-Admin-Secret"),
    # Quality filters
    max_wer: float = Query(0.35, ge=0.0, le=1.0, description="Max WER — lower = cleaner"),
    min_duration: float = Query(1.0, ge=0.0, description="Minimum clip duration in seconds"),
    max_duration: float = Query(30.0, ge=0.0, description="Maximum clip duration in seconds"),
    # Content filters
    category: Optional[str] = Query(None, description="Restrict to one prompt category"),
    language: Optional[str] = Query(None, description="Filter by native_language"),
    include_flagged: bool = Query(False, description="Include flagged recordings"),
    # Signed URL TTL
    url_ttl: int = Query(86400, ge=3600, le=604800, description="Signed URL TTL in seconds (1h–7d)"),
    limit: int = Query(100000, ge=1, le=100000),
):
    """
    Export clean recordings as a HuggingFace-ready JSONL manifest.
    Each line: { id, audio_url (signed), text, duration, speaker_id,
                 language, region, gender, age_range, noise_level,
                 device_type, prompt_id, prompt_category, wer_score,
                 transcription_engine, url_expires_in }

    Load in Python:
        import datasets
        ds = datasets.load_dataset("json", data_files="manifest.jsonl", split="train")
        ds = ds.cast_column("audio_url", datasets.Audio(sampling_rate=16000))
    """
    _require_admin(x_stats_admin_secret)

    if not settings.postgres_configured():
        raise HTTPException(status_code=400, detail="Postgres required for training export")
    if not settings.object_storage_configured():
        raise HTTPException(status_code=400, detail="Object storage required for training export")

    wheres = [
        "transcription_status = 'done'",
        "storage_object_key IS NOT NULL",
        "final_transcript != ''",
    ]
    params: list = []

    if not include_flagged:
        wheres.append("flagged = FALSE")

    if max_wer < 1.0:
        params.append(max_wer)
        wheres.append(f"(wer_score IS NULL OR wer_score <= ${len(params)})")

    if min_duration > 0:
        params.append(min_duration)
        wheres.append(f"duration_seconds >= ${len(params)}")

    if max_duration < 30.0:
        params.append(max_duration)
        wheres.append(f"duration_seconds <= ${len(params)}")

    if category:
        params.append(category)
        wheres.append(f"prompt_category = ${len(params)}")

    if language:
        params.append(language)
        wheres.append(f"LOWER(native_language) = LOWER(${len(params)})")

    params.append(limit)
    sql = f"""
        SELECT
            id, storage_object_key, final_transcript, duration_seconds,
            speaker_slug, native_language, region, gender, age_range,
            noise_level, device_type, prompt_id, prompt_text, prompt_category,
            wer_score, transcription_engine, flagged
        FROM recordings
        WHERE {" AND ".join(wheres)}
        ORDER BY timestamp ASC
        LIMIT ${len(params)}
    """

    async def stream():
        loop = asyncio.get_event_loop()
        async with database.read_pool().acquire() as conn:
            rows = await conn.fetch(sql, *params)

        skipped = 0
        for row in rows:
            key = row["storage_object_key"]
            try:
                signed_url = await loop.run_in_executor(
                    None, storage_s3.generate_signed_url, key, url_ttl
                )
            except Exception as exc:
                print(f"[training-export] signed URL failed for {key}: {exc}")
                skipped += 1
                continue

            record = {
                "id": row["id"],
                "audio_url": signed_url,
                "text": row["final_transcript"],
                "duration": round(float(row["duration_seconds"] or 0), 3),
                "speaker_id": row["speaker_slug"],
                "language": row["native_language"],
                "region": row["region"],
                "gender": row["gender"],
                "age_range": row["age_range"],
                "noise_level": row["noise_level"],
                "device_type": row["device_type"],
                "prompt_id": row["prompt_id"],
                "prompt_text": row["prompt_text"],
                "prompt_category": row["prompt_category"],
                "wer_score": round(float(row["wer_score"]), 4) if row["wer_score"] is not None else None,
                "transcription_engine": row["transcription_engine"],
                "flagged": row["flagged"],
                "url_expires_in": url_ttl,
            }
            yield json.dumps(record) + "\n"

        if skipped:
            print(f"[training-export] {skipped} rows skipped due to signed URL errors")

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="training_manifest.jsonl"'},
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def stratified_sample(prompts: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    if count <= 0 or not prompts:
        return []
    n = len(prompts)
    if count >= n:
        out = list(prompts)
        random.shuffle(out)
        return out

    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in prompts:
        by_cat[p["category"]].append(p)

    categories = list(by_cat.keys())
    quotas_float = {c: count * len(by_cat[c]) / n for c in categories}
    quotas = {c: int(q) for c, q in quotas_float.items()}
    remainder = count - sum(quotas.values())
    frac_order = sorted(
        categories, key=lambda c: quotas_float[c] - quotas[c], reverse=True
    )
    for i in range(remainder):
        quotas[frac_order[i % len(frac_order)]] += 1

    out: List[Dict[str, Any]] = []
    for c in categories:
        k = min(quotas[c], len(by_cat[c]))
        out.extend(random.sample(by_cat[c], k))

    out_ids = {p["id"] for p in out}
    remaining = [p for p in prompts if p["id"] not in out_ids]
    while len(out) < count and remaining:
        idx = random.randrange(len(remaining))
        out.append(remaining.pop(idx))

    random.shuffle(out)
    return out[:count]


@app.get("/api/prompts")
async def get_prompts(
    refresh: bool = Query(False),
    count: int = Query(20, ge=1, le=500),
    full: bool = Query(False),
):
    from prompts import PROMPTS

    source = os.getenv("PROMPTS_SOURCE", "static").strip().lower()
    if source == "llm":
        try:
            from llm_prompts import get_llm_prompts
            bank = await get_llm_prompts(force_refresh=refresh)
            src = "llm"
        except Exception as exc:
            print(f"[prompts] LLM generation failed, using static bank: {exc}")
            bank = PROMPTS
            src = "static_fallback"
            out = bank if full else stratified_sample(bank, count)
            return {
                "prompts": out,
                "source": src,
                "llm_error": str(exc),
                "sample_size": len(out),
                "bank_size": len(bank),
            }
        out = bank if full else stratified_sample(bank, count)
        return {"prompts": out, "source": src, "sample_size": len(out), "bank_size": len(bank)}

    bank = PROMPTS
    out = bank if full else stratified_sample(bank, count)
    return {"prompts": out, "source": "static", "sample_size": len(out), "bank_size": len(bank)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
