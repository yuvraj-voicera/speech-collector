-- Migration 003: speaker demographics (safe to re-run)
ALTER TABLE recordings
    ADD COLUMN IF NOT EXISTS age_range VARCHAR(16) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS gender    VARCHAR(32) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_recordings_export
    ON recordings (prompt_category, deepgram_confidence, timestamp DESC);
