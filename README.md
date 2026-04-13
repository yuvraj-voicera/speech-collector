# VoiceraCX Speech Data Collector

Internal tool for collecting labeled speech data from employees to fine-tune the
Wav2Vec2-BERT 2.0 ASR adapter pipeline.

**Primary app in this repo:** this folder (`voicera-collector/`). The parent `speech-collector/` directory is an optional Appwrite + Vite starter demo.

## What it does

- **~100 prompts** in the static bank across **8** content categories (v2.0); each session uses **2 spoken identity prompts** plus a **stratified sample of 20** from the bank (**22** total)
- Records audio directly in the browser (16kHz mono, WAV)
- Transcribes each recording via Deepgram Nova-2 (`en-IN`) immediately
- Lets the speaker correct the transcript inline before saving
- Stores audio files + JSONL metadata in a training-ready format
- Tracks collection progress by speaker, category, and total duration

## Prompt categories

| Category | Count | Purpose |
|---|---|---|
| `domain_vocabulary` | 15 | OOV proper nouns, product jargon |
| `customer_query` | 15 | Call-center style English |
| `hinglish` | 12 | Code-switched Hindi/English |
| `alphanumeric` | 12 | IDs, phone digits, codes |
| `phonetic_indian` | 20 | Retroflex, aspiration, fricatives, vowel length — natural CX phrasing |
| `disfluent` | 8 | Hesitations, self-corrections |
| `dates_addresses` | 10 | Indian dates, addresses, PINs, cities |
| `numbers_currency` | 8 | Rupees, percentages, spoken numbers |
| `identity` | 2/session | Spoken full name + spelled email (not in static bank) |

Legacy metadata may still use `phonetic` (old bank); the UI maps it to **Phonetic (legacy)**.

## RunPod

One-command-style deploy (Postgres + MinIO + API + nginx on port **8000**): see **[RUNPOD.md](RUNPOD.md)** and `docker-compose.prod.yml`.

## Backend: Postgres + JWT + object storage

When **`DATABASE_URL`** and **`JWT_SECRET`** are set:

1. **Schema** (once): apply [backend/schema.sql](backend/schema.sql) to Postgres (or start [docker-compose.yml](docker-compose.yml), which mounts it on first DB init).
2. **Auth**: email/password via **`POST /api/auth/register`** and **`POST /api/auth/login`**; the SPA stores the access token and sends **`Authorization: Bearer …`** to **`/api/upload`** and **`/api/stats`**.
3. **Metadata**: each recording is a row in **`recordings`** (see schema).
4. **Audio**: WAV is uploaded to **S3-compatible storage** when **`S3_BUCKET`**, **`S3_ACCESS_KEY_ID`**, and **`S3_SECRET_ACCESS_KEY`** are set (`S3_ENDPOINT` for MinIO / custom endpoints). Otherwise the file stays on the API server disk and the DB stores `storage_object_key` like `local/{id}.wav`.
5. **JSONL**: set **`DUAL_WRITE_JSONL=true`** to also append `backend/data/metadata.jsonl`.
6. **Stats**: JWT → per-user aggregates; org-wide totals with **`STATS_ADMIN_SECRET`** + header **`X-Stats-Admin-Secret`** ([DEPLOY.md](DEPLOY.md)).

If **`DATABASE_URL`** is **unset**, the API runs in **local-only** mode (no login): JSONL + disk only. The UI shows “Local mode” after **`GET /api/health`** reports `postgres: false`.

**Local stack:** `docker compose up` in `voicera-collector/` starts Postgres + MinIO; create an S3 bucket (or rely on first-upload auto-create) and match env vars in `backend/.env`.

**DB load:** tune `DB_POOL_*`, optional `READ_DATABASE_URL` for stats on a replica, and Postgres `max_connections` — see [DEPLOY.md](DEPLOY.md#postgres-under-load).

### LLM-generated prompts (optional)

Set `PROMPTS_SOURCE=llm` and `GROQ_API_KEY` in `backend/.env` (Groq’s OpenAI-compatible API; optional `GROQ_BASE_URL` / `GROQ_MODEL`). For a non-Groq host, leave `GROQ_API_KEY` empty and use `OPENAI_API_KEY` plus `OPENAI_BASE_URL` / `OPENAI_MODEL`. The first request builds **100** utterances matching the v2.0 category counts in `prompts.py`, then caches them in `backend/data/llm_prompts_cache.json`. Delete that file if you upgrade from an older LLM cache shape. Force regeneration: `GET /api/prompts?refresh=1`. **API:** `GET /api/prompts?count=20` returns a stratified sample (default `count=20`); `full=1` returns the entire bank. If the LLM call fails, the API falls back to the static bank and sets `source: static_fallback` in the JSON.

## Setup

### Backend (FastAPI)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Set your Deepgram API key
export DEEPGRAM_API_KEY=your_key_here
# Copy .env.example to .env — set DATABASE_URL, JWT_SECRET, Deepgram, optional S3

# Make sure ffmpeg is installed (for audio conversion)
# Ubuntu: sudo apt install ffmpeg
# macOS:  brew install ffmpeg

python main.py
# Runs on http://localhost:8000
```

### Frontend (React)

```bash
cd frontend
npm install
npm start
# Runs on http://localhost:3000
```

Production static build: see `frontend/.env.production.example`.

## Data output

With Postgres configured, canonical metadata is in the **`recordings`** table; WAVs are in your object bucket (or on disk under `data/audio/` when S3 env is omitted). `backend/data/` always holds temp/processed files during each upload; optional **`metadata.jsonl`** mirrors rows when `DUAL_WRITE_JSONL=true`.

Local artifacts under `backend/data/`:

```
data/
├── audio/
│   ├── a3f7c2b1.wav        # 16kHz mono WAV, training-ready
│   ├── b8e1d4f9.wav
│   └── ...
└── metadata.jsonl          # One JSON record per line
```

Each JSONL record:
```json
{
  "id": "a3f7c2b1",
  "timestamp": "2025-04-01T10:23:45.123456",
  "audio_path": "a3f7c2b1.wav",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "prompt_bank_version": "2.0",
  "speaker": {
    "id": "arjun_sharma",
    "name": "Arjun Sharma",
    "email": "arjun@company.com",
    "native_language": "Marathi",
    "region": "Maharashtra"
  },
  "prompt": {
    "id": "dv_001",
    "text": "I'd like to check my VoiceraCX account balance please.",
    "category": "domain_vocabulary"
  },
  "recording": {
    "noise_level": "quiet",
    "device_type": "headset",
    "duration_seconds": 4.2,
    "sample_rate": 16000,
    "channels": 1,
    "format": "wav"
  },
  "transcription": {
    "auto_transcript": "I'd like to check my VoiceraCX account balance please.",
    "final_transcript": "I'd like to check my VoiceraCX account balance please.",
    "was_corrected": false,
    "deepgram_confidence": 0.94,
    "deepgram_words": [...],
    "deepgram_error": null
  }
}
```

## Converting to HuggingFace Dataset

```python
import json
import pandas as pd
from datasets import Dataset, Audio

records = []
with open("backend/data/metadata.jsonl") as f:
    for line in f:
        r = json.loads(line)
        records.append({
            "audio": f"backend/data/audio/{r['audio_path']}",
            "text": r["transcription"]["final_transcript"],
            "speaker_id": r["speaker"]["id"],
            "native_language": r["speaker"]["native_language"],
            "region": r["speaker"]["region"],
            "prompt_category": r["prompt"]["category"],
            "duration_seconds": r["recording"]["duration_seconds"],
            "noise_level": r["recording"]["noise_level"],
        })

df = pd.DataFrame(records)
dataset = Dataset.from_pandas(df)
dataset = dataset.cast_column("audio", Audio(sampling_rate=16000))

# Split 90/5/5
dataset = dataset.train_test_split(test_size=0.1, seed=42)

# Push to HuggingFace (private repo)
dataset.push_to_hub("your-org/voiceracx-employee-speech", private=True)
```

## Target

- Example: **30 speakers** × **~22 prompts per session** (2 identity + 20 sampled) ≈ **660** recordings if each completes one session
- Estimated total audio: ~5 hours (depends on clip length)
- Expected human effort: ~15–20 minutes per employee per session

## Notes

- Session prompts are a **stratified random sample** from the bank (proportional to category size), then shuffled; identity prompts are always first
- `was_corrected: true` in metadata flags recordings where the speaker 
  fixed the Deepgram transcript — these are high-value training examples
- Add or edit prompts in `backend/prompts.py` — update category counts in `llm_prompts.py` if you use `PROMPTS_SOURCE=llm`
- Production Docker, env, and MinIO bucket setup: [DEPLOY.md](DEPLOY.md)
- Optional: run Deepgram or workers as separate services — see [FUNCTIONS.md](FUNCTIONS.md)
