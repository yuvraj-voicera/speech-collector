-- Voicera collector: users + recordings (run once against your Postgres)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(512) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recordings (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    storage_object_key TEXT NOT NULL,
    duration_seconds DOUBLE PRECISION,
    speaker_slug VARCHAR(256) NOT NULL,
    speaker_label VARCHAR(512) NOT NULL,
    speaker_email VARCHAR(320) NOT NULL DEFAULT '',
    native_language VARCHAR(64) NOT NULL,
    region VARCHAR(128) NOT NULL,
    noise_level VARCHAR(32) NOT NULL,
    device_type VARCHAR(32) NOT NULL,
    prompt_id VARCHAR(64) NOT NULL,
    prompt_text TEXT NOT NULL,
    prompt_category VARCHAR(64) NOT NULL,
    session_id VARCHAR(64) NOT NULL DEFAULT '',
    prompt_bank_version VARCHAR(16) NOT NULL DEFAULT '',
    auto_transcript TEXT NOT NULL DEFAULT '',
    final_transcript TEXT NOT NULL DEFAULT '',
    was_corrected BOOLEAN NOT NULL DEFAULT false,
    deepgram_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    deepgram_error TEXT NOT NULL DEFAULT '',
    deepgram_words_json TEXT NOT NULL DEFAULT '',
    age_range VARCHAR(16) DEFAULT NULL,
    gender VARCHAR(32) DEFAULT NULL
);

-- Per-user listings and time-ordered exports
CREATE INDEX IF NOT EXISTS idx_recordings_user_timestamp ON recordings (user_id, timestamp DESC);

-- Stats: filter by user_id + aggregate by category (index-only friendly for counts)
CREATE INDEX IF NOT EXISTS idx_recordings_user_prompt_category ON recordings (user_id, prompt_category);

-- Stats: per-user speaker_slug histograms
CREATE INDEX IF NOT EXISTS idx_recordings_user_speaker_slug ON recordings (user_id, speaker_slug);

-- Global category breakdowns (admin stats); partial benefit when not filtering by user
CREATE INDEX IF NOT EXISTS idx_recordings_prompt_category ON recordings (prompt_category);

-- Optional: coarse time indexing for very large tables (range reports, pruning)
CREATE INDEX IF NOT EXISTS idx_recordings_timestamp_brin ON recordings USING BRIN (timestamp);

-- Export API: filter by category + confidence, ordered by time
CREATE INDEX IF NOT EXISTS idx_recordings_export
    ON recordings (prompt_category, deepgram_confidence, timestamp DESC);
