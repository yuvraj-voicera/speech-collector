# Future: async transcription workers

Today, **ffmpeg** and **Deepgram** run in FastAPI so secrets stay on the server and audio is normalized to 16 kHz WAV before ASR.

**Possible evolution:** trigger a **queue consumer** or **cloud function** on object-storage `ObjectCreated` (S3 event, MinIO webhook, etc.). The worker would:

1. Read the uploaded object (or accept a key from a message).
2. Call Deepgram with `DEEPGRAM_API_KEY` in the worker environment.
3. Update transcript fields in **Postgres** (or enqueue a second job).

**Tradeoffs:** you still need ffmpeg somewhere unless you standardize on browser-native formats and accept larger files or different training format. Running ffmpeg inside a function is possible but increases package size and cold start; a small always-on API container (this repo) is often simpler until scale demands otherwise.
