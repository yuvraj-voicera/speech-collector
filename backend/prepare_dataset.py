#!/usr/bin/env python3
"""
prepare_dataset.py — Build HuggingFace-compatible ASR manifest from VoiceraCX data.

Postgres mode requires: pip install psycopg2-binary
HuggingFace push requires: pip install datasets huggingface_hub

Usage:
    python prepare_dataset.py --min-confidence 0.7 --output-dir ./dataset
    python prepare_dataset.py --source postgres --exclude-identity
    python prepare_dataset.py --push-to-hub voicera/indian-english-asr
"""
from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterator, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def iter_jsonl(
    jsonl_path: Path,
    min_confidence: float,
    exclude_identity: bool,
) -> Iterator[dict]:
    if not jsonl_path.exists():
        print(f"[warn] JSONL not found: {jsonl_path}")
        return
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            cat = r.get("prompt", {}).get("category", "")
            if exclude_identity and cat == "identity":
                continue
            conf = r.get("transcription", {}).get("deepgram_confidence") or 0.0
            if conf < min_confidence:
                continue
            transcript = r.get("transcription", {}).get("final_transcript", "").strip()
            if not transcript:
                continue
            spk = r.get("speaker", {})
            yield {
                "recording_id": r.get("id"),
                "audio_path": r.get("audio_path"),
                "storage_object_key": r.get("storage_object_key"),
                "final_transcript": transcript,
                "auto_transcript": r.get("transcription", {}).get("auto_transcript", ""),
                "was_corrected": r.get("transcription", {}).get("was_corrected", False),
                "deepgram_confidence": conf,
                "speaker_id": spk.get("id", "unknown"),
                "native_language": spk.get("native_language", ""),
                "region": spk.get("region", ""),
                "age_range": spk.get("age_range"),
                "gender": spk.get("gender"),
                "duration_seconds": r.get("recording", {}).get("duration_seconds"),
                "noise_level": r.get("recording", {}).get("noise_level", ""),
                "device_type": r.get("recording", {}).get("device_type", ""),
                "prompt_id": r.get("prompt", {}).get("id", ""),
                "prompt_category": cat,
                "session_id": r.get("session_id", ""),
                "prompt_bank_version": r.get("prompt_bank_version", ""),
                "timestamp": r.get("timestamp", ""),
            }


def iter_postgres(
    database_url: str,
    min_confidence: float,
    exclude_identity: bool,
) -> Iterator[dict]:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        raise SystemExit("psycopg2-binary required for Postgres mode: pip install psycopg2-binary")

    conditions = [f"deepgram_confidence >= {min_confidence}", "final_transcript != ''"]
    if exclude_identity:
        conditions.append("prompt_category != 'identity'")

    sql = f"""
        SELECT
            id AS recording_id,
            storage_object_key,
            NULL AS audio_path,
            final_transcript,
            auto_transcript,
            was_corrected,
            deepgram_confidence,
            speaker_slug AS speaker_id,
            native_language,
            region,
            age_range,
            gender,
            duration_seconds,
            noise_level,
            device_type,
            prompt_id,
            prompt_category,
            session_id,
            prompt_bank_version,
            timestamp::text AS timestamp
        FROM recordings
        WHERE {" AND ".join(conditions)}
        ORDER BY timestamp DESC
    """
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            for row in cur:
                yield dict(row)
    finally:
        conn.close()


def to_hf_row(record: dict) -> dict:
    return {
        "file": record.get("storage_object_key") or record.get("audio_path") or "",
        "text": (record.get("final_transcript") or "").strip(),
        "speaker_id": record.get("speaker_id", "unknown"),
        "native_language": record.get("native_language", ""),
        "region": record.get("region", ""),
        "age_range": record.get("age_range"),
        "gender": record.get("gender"),
        "duration": record.get("duration_seconds"),
        "prompt_category": record.get("prompt_category", ""),
        "noise_level": record.get("noise_level", ""),
        "device_type": record.get("device_type", ""),
        "was_corrected": record.get("was_corrected", False),
        "confidence": record.get("deepgram_confidence", 0.0),
        "prompt_bank_version": record.get("prompt_bank_version", ""),
    }


def stratified_split(
    rows: list,
    train_frac: float = 0.90,
    val_frac: float = 0.05,
    seed: int = 42,
) -> tuple:
    rng = random.Random(seed)
    by_speaker: dict = defaultdict(list)
    for r in rows:
        by_speaker[r.get("speaker_id", "unknown")].append(r)

    train, val, test = [], [], []
    for spk_rows in by_speaker.values():
        rng.shuffle(spk_rows)
        n = len(spk_rows)
        n_train = max(1, round(n * train_frac))
        n_val = round(n * val_frac)
        if n >= 3:
            n_val = max(1, n_val)
        n_test = n - n_train - n_val
        if n_test < 0:
            train.extend(spk_rows)
        else:
            train.extend(spk_rows[:n_train])
            val.extend(spk_rows[n_train:n_train + n_val])
            test.extend(spk_rows[n_train + n_val:])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def write_manifest(rows: list, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  wrote {len(rows):,} rows -> {out_path}")


def push_to_hub(output_dir: Path, hub_repo: str, hf_token: str) -> None:
    try:
        from datasets import load_dataset
        from huggingface_hub import HfApi
    except ImportError:
        raise SystemExit("HuggingFace push requires: pip install datasets huggingface_hub")

    api = HfApi(token=hf_token)
    api.create_repo(repo_id=hub_repo, repo_type="dataset", exist_ok=True, token=hf_token)

    ds = load_dataset(
        "json",
        data_files={
            "train": str(output_dir / "train.jsonl"),
            "validation": str(output_dir / "val.jsonl"),
            "test": str(output_dir / "test.jsonl"),
        },
    )
    ds.push_to_hub(hub_repo, token=hf_token)
    print(f"  pushed to https://huggingface.co/datasets/{hub_repo}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare ASR training dataset from VoiceraCX")
    p.add_argument("--min-confidence", type=float, default=0.7,
                   help="Minimum Deepgram confidence (default 0.7)")
    p.add_argument("--output-dir", type=Path, default=Path("./dataset"),
                   help="Output directory for train/val/test manifests")
    p.add_argument("--exclude-identity", action="store_true",
                   help="Exclude identity category prompts (name/email)")
    p.add_argument("--push-to-hub", metavar="REPO_ID",
                   help="HuggingFace Hub repo ID, e.g. voicera/indian-english-asr")
    p.add_argument("--source", choices=["auto", "jsonl", "postgres"], default="auto",
                   help="Data source (default: auto-detect from DATABASE_URL)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--train-frac", type=float, default=0.90)
    p.add_argument("--val-frac", type=float, default=0.05)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.getenv("DATABASE_URL", "").strip()

    source = args.source
    if source == "auto":
        source = "postgres" if database_url else "jsonl"

    print(f"Source: {source} | min_confidence={args.min_confidence} | exclude_identity={args.exclude_identity}")

    if source == "postgres":
        print("Reading from Postgres...")
        raw_rows = list(iter_postgres(database_url, args.min_confidence, args.exclude_identity))
    else:
        jsonl_path = Path(os.getenv("METADATA_FILE", "./data/metadata.jsonl"))
        print(f"Reading from JSONL: {jsonl_path}")
        raw_rows = list(iter_jsonl(jsonl_path, args.min_confidence, args.exclude_identity))

    print(f"Total qualifying records: {len(raw_rows):,}")
    if not raw_rows:
        print("No records found. Check filters or data source.")
        return

    hf_rows = [to_hf_row(r) for r in raw_rows]
    train, val, test = stratified_split(hf_rows, args.train_frac, args.val_frac, args.seed)

    print(f"Split: train={len(train):,}  val={len(val):,}  test={len(test):,}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(train, args.output_dir / "train.jsonl")
    write_manifest(val, args.output_dir / "val.jsonl")
    write_manifest(test, args.output_dir / "test.jsonl")

    if args.push_to_hub:
        hf_token = os.getenv("HF_TOKEN", "").strip()
        if not hf_token:
            raise SystemExit("HF_TOKEN env var required for --push-to-hub")
        print(f"Pushing to HuggingFace Hub: {args.push_to_hub}")
        push_to_hub(args.output_dir, args.push_to_hub, hf_token)

    print("Done.")


if __name__ == "__main__":
    main()
