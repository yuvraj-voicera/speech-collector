#!/usr/bin/env python3
"""
Download Voicera training data and build a HuggingFace-ready dataset.

Usage:
    python download_training_data.py \
        --api https://m17r541xikyvyl-8000.proxy.runpod.net \
        --secret YOUR_ADMIN_SECRET \
        --out ./voicera_dataset \
        [--max-wer 0.3] [--category customer_query] [--language Hindi]

Then load in Python:
    from datasets import load_dataset
    ds = load_dataset("audiofolder", data_dir="./voicera_dataset", split="train")
    print(ds[0])
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(description="Download Voicera training dataset")
    p.add_argument("--api", default="http://localhost:8000", help="API base URL")
    p.add_argument("--secret", required=True, help="X-Stats-Admin-Secret value")
    p.add_argument("--out", default="./voicera_dataset", help="Output directory")
    p.add_argument("--max-wer", type=float, default=0.35, help="Max WER (0–1)")
    p.add_argument("--min-duration", type=float, default=1.0, help="Min clip duration (s)")
    p.add_argument("--category", default=None, help="Filter by prompt category")
    p.add_argument("--language", default=None, help="Filter by native_language")
    p.add_argument("--include-flagged", action="store_true", help="Include flagged recordings")
    p.add_argument("--url-ttl", type=int, default=86400, help="Signed URL TTL in seconds")
    p.add_argument("--workers", type=int, default=8, help="Parallel download workers")
    p.add_argument("--limit", type=int, default=100000, help="Max records to fetch")
    return p.parse_args()


def fetch_manifest(args):
    params = {
        "max_wer": args.max_wer,
        "min_duration": args.min_duration,
        "url_ttl": args.url_ttl,
        "limit": args.limit,
        "include_flagged": str(args.include_flagged).lower(),
    }
    if args.category:
        params["category"] = args.category
    if args.language:
        params["language"] = args.language

    url = args.api.rstrip("/") + "/api/export/training"
    print(f"Fetching manifest from {url} …")
    r = requests.get(url, headers={"X-Stats-Admin-Secret": args.secret}, params=params, stream=True)
    r.raise_for_status()

    records = []
    for line in r.iter_lines():
        if line:
            records.append(json.loads(line))
    print(f"  {len(records)} records in manifest")
    return records


def download_one(rec, audio_dir):
    out_path = audio_dir / f"{rec['id']}.wav"
    if out_path.exists():
        return rec, True, "cached"
    try:
        r = requests.get(rec["audio_url"], timeout=30)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        return rec, True, "downloaded"
    except Exception as e:
        return rec, False, str(e)


def main():
    args = parse_args()
    out_dir = Path(args.out)
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Fetch manifest
    records = fetch_manifest(args)
    if not records:
        print("No records returned — check filters or admin secret.")
        sys.exit(0)

    # Download audio files in parallel
    print(f"Downloading {len(records)} audio files to {audio_dir} ({args.workers} workers)…")
    ok, failed = 0, 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, rec, audio_dir): rec for rec in records}
        for i, future in enumerate(as_completed(futures), 1):
            rec, success, msg = future.result()
            if success:
                ok += 1
            else:
                failed += 1
                print(f"  FAILED {rec['id']}: {msg}")
            if i % 10 == 0 or i == len(records):
                elapsed = time.time() - t0
                print(f"  {i}/{len(records)} — {ok} ok, {failed} failed — {elapsed:.1f}s")

    # Write HuggingFace metadata.jsonl
    # Format: {"file_name": "audio/xxx.wav", "text": "...", <extra fields>}
    hf_meta_path = out_dir / "metadata.jsonl"
    with open(hf_meta_path, "w") as f:
        for rec in records:
            wav = audio_dir / f"{rec['id']}.wav"
            if not wav.exists():
                continue
            row = {
                "file_name": f"audio/{rec['id']}.wav",
                "text": rec["text"],
                "speaker_id": rec["speaker_id"],
                "language": rec["language"],
                "region": rec["region"],
                "gender": rec["gender"] or "",
                "age_range": rec["age_range"] or "",
                "noise_level": rec["noise_level"],
                "device_type": rec["device_type"],
                "prompt_id": rec["prompt_id"],
                "prompt_category": rec["prompt_category"],
                "wer_score": rec["wer_score"],
                "duration": rec["duration"],
            }
            f.write(json.dumps(row) + "\n")

    total_downloaded = sum(1 for r in records if (audio_dir / f"{r['id']}.wav").exists())
    total_duration = sum(r["duration"] for r in records if (audio_dir / f"{r['id']}.wav").exists())

    print(f"""
Done!
  Audio files : {total_downloaded} WAVs in {audio_dir}
  Manifest    : {hf_meta_path}
  Duration    : {total_duration/60:.1f} minutes
  Failed      : {failed}

Load with HuggingFace:
  from datasets import load_dataset
  ds = load_dataset("audiofolder", data_dir="{out_dir}", split="train")
  print(ds[0])

Fine-tune Whisper:
  # ds already has ds["audio"] (sampled at 16kHz) and ds["text"]
""")


if __name__ == "__main__":
    main()
