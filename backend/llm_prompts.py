"""
Optional LLM-generated prompt bank for speech collection.
Uses OpenAI-compatible Chat Completions (default: Groq; override with OPENAI_* for other hosts).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

DATA_DIR = Path(__file__).resolve().parent / "data"
CACHE_FILE = DATA_DIR / "llm_prompts_cache.json"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

GROQ_BASE_URL_DEFAULT = "https://api.groq.com/openai/v1"
OPENAI_BASE_URL_DEFAULT = "https://api.openai.com/v1"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
OPENAI_MODEL_DEFAULT = "gpt-4o-mini"


def _llm_config() -> Tuple[str, str, str]:
    """Returns (api_key, base_url, model). Groq key takes precedence over legacy OPENAI_API_KEY."""
    if GROQ_API_KEY:
        base = os.getenv("GROQ_BASE_URL", GROQ_BASE_URL_DEFAULT).rstrip("/")
        model = os.getenv("GROQ_MODEL", GROQ_MODEL_DEFAULT).strip()
        return GROQ_API_KEY, base, model
    if OPENAI_API_KEY:
        base = os.getenv("OPENAI_BASE_URL", OPENAI_BASE_URL_DEFAULT).rstrip("/")
        default_model = (
            GROQ_MODEL_DEFAULT if "groq.com" in base.lower() else OPENAI_MODEL_DEFAULT
        )
        model = os.getenv("OPENAI_MODEL", default_model).strip()
        return OPENAI_API_KEY, base, model
    return "", "", ""


# Must match category distribution in prompts.py (v2.0 bank, no identity prompts)
CATEGORY_COUNTS: Dict[str, int] = {
    "domain_vocabulary": 15,
    "customer_query": 15,
    "hinglish": 12,
    "alphanumeric": 12,
    "phonetic_indian": 20,
    "disfluent": 8,
    "dates_addresses": 10,
    "numbers_currency": 8,
}

ID_PREFIX: Dict[str, str] = {
    "domain_vocabulary": "dv",
    "customer_query": "cq",
    "hinglish": "hs",
    "alphanumeric": "an",
    "phonetic_indian": "pi",
    "disfluent": "nf",
    "dates_addresses": "da",
    "numbers_currency": "nc",
}

CATEGORY_ORDER = list(CATEGORY_COUNTS.keys())

_SYSTEM_TOTAL = sum(CATEGORY_COUNTS.values())

SYSTEM_INSTRUCTIONS = f"""You generate short spoken lines for Indian English speech data collection to train ASR.
Output MUST be a single JSON object with key "prompts" whose value is an array of objects.
Each object: {{"category": <one of the allowed categories>, "text": <one sentence or short utterance the speaker will read aloud>}}.

Allowed categories and exact counts (total {_SYSTEM_TOTAL} items):
- domain_vocabulary ({CATEGORY_COUNTS['domain_vocabulary']}): VoiceraCX, Pipecat, LiveKit, Deepgram, voice AI, call-center product jargon. Varied wording.
- customer_query ({CATEGORY_COUNTS['customer_query']}): Natural customer-service English, emotional or neutral.
- hinglish ({CATEGORY_COUNTS['hinglish']}): Hindi-English code-switching in one utterance (roman script).
- alphanumeric ({CATEGORY_COUNTS['alphanumeric']}): Booking IDs, phone digits, codes spelled or grouped for dictation.
- phonetic_indian ({CATEGORY_COUNTS['phonetic_indian']}): Indian English in natural CX/business contexts. Include retroflex-friendly placenames/words, aspiration contrasts (t vs th, p vs ph patterns in English words), word-final fricatives (sh, ch, s, z), vowel length contrasts (ship/sheep, pull/pool style), consonant clusters. No IPA.
- disfluent ({CATEGORY_COUNTS['disfluent']}): Hesitations (um, uh), self-corrections, conversational fragments — still readable.
- dates_addresses ({CATEGORY_COUNTS['dates_addresses']}): Indian-style dates, street addresses, PIN codes, Indian city and state names.
- numbers_currency ({CATEGORY_COUNTS['numbers_currency']}): Rupee amounts, percentages, phone-style number strings, measurements — natural spoken phrasing.

No numbering in text. No JSON inside text. Keep each text under 220 characters unless alphanumeric or addresses need more.
Total items and per-category counts in the user message MUST be matched exactly."""


def _assign_ids(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_cat: Dict[str, List[str]] = {c: [] for c in CATEGORY_COUNTS}
    for row in items:
        cat = row.get("category")
        text = (row.get("text") or "").strip()
        if cat not in CATEGORY_COUNTS or not text:
            continue
        by_cat[cat].append(text)
    out: List[Dict[str, Any]] = []
    for cat in CATEGORY_ORDER:
        want = CATEGORY_COUNTS[cat]
        texts = by_cat[cat][:want]
        prefix = ID_PREFIX[cat]
        for i, text in enumerate(texts, start=1):
            out.append({"id": f"{prefix}_{i:03d}", "category": cat, "text": text})
    return out


def _counts_ok(items: List[Dict[str, Any]]) -> bool:
    got: Dict[str, int] = {c: 0 for c in CATEGORY_COUNTS}
    for row in items:
        c = row.get("category")
        if c in got:
            got[c] += 1
    return all(got[c] == CATEGORY_COUNTS[c] for c in CATEGORY_COUNTS)


async def generate_prompts_via_llm() -> List[Dict[str, Any]]:
    api_key, base_url, model = _llm_config()
    if not api_key:
        raise ValueError("Set GROQ_API_KEY (or legacy OPENAI_API_KEY) for LLM prompts")

    counts_line = ", ".join(f"{k}: {v}" for k, v in CATEGORY_COUNTS.items())
    total = sum(CATEGORY_COUNTS.values())
    user_msg = (
        f"Generate exactly these counts (total {total}): {counts_line}. "
        f'Return JSON: {{"prompts":[{{"category":"domain_vocabulary","text":"..."}},...]}}'
    )

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.9,
        "max_tokens": 12000,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_msg},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        body = r.json()

    content = body["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    raw = parsed.get("prompts") or parsed.get("data") or []
    if not isinstance(raw, list):
        raise ValueError("LLM response missing prompts array")

    normalized = _assign_ids(raw)
    if len(normalized) != sum(CATEGORY_COUNTS.values()):
        raise ValueError(
            f"Expected {sum(CATEGORY_COUNTS.values())} prompts after normalization, got {len(normalized)}"
        )
    if not _counts_ok(normalized):
        raise ValueError("Category counts mismatch after LLM generation")
    return normalized


def load_cache() -> List[Dict[str, Any]] | None:
    if not CACHE_FILE.is_file():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        prompts = data.get("prompts")
        if isinstance(prompts, list) and len(prompts) == sum(CATEGORY_COUNTS.values()) and _counts_ok(prompts):
            return prompts
    except (json.JSONDecodeError, OSError):
        pass
    return None


def save_cache(prompts: List[Dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"prompts": prompts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def get_llm_prompts(*, force_refresh: bool) -> List[Dict[str, Any]]:
    if not force_refresh:
        cached = load_cache()
        if cached is not None:
            return cached
    try:
        prompts = await generate_prompts_via_llm()
        save_cache(prompts)
        return prompts
    except Exception:
        raise
