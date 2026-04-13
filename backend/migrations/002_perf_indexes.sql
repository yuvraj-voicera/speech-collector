-- Apply on existing databases that already ran an older schema.sql (idempotent).
-- New installs get these from schema.sql.

CREATE INDEX IF NOT EXISTS idx_recordings_user_prompt_category ON recordings (user_id, prompt_category);
CREATE INDEX IF NOT EXISTS idx_recordings_user_speaker_slug ON recordings (user_id, speaker_slug);
CREATE INDEX IF NOT EXISTS idx_recordings_timestamp_brin ON recordings USING BRIN (timestamp);

-- Replace non-DESC user_timestamp index if present (optional; skip if you rely on old name only)
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recordings_user_timestamp_new ON recordings (user_id, timestamp DESC);
-- DROP INDEX CONCURRENTLY IF EXISTS idx_recordings_user_timestamp;
