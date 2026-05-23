"""Adapter for 孟諴: raw-ASR transcript preprocessing.

Wraps `孟諴＿前處理/main.py`. The canonical logic — prompt template, QNA marker,
and post-processing normalizer — lives upstream; this adapter loads it via
`importlib.util` so the Chinese folder name doesn't collide with FastAPI's
`app:main` module.

Public API:
    is_raw_asr(text)               -> bool
    run(raw_text)                  -> (cleaned_full_text, cleaned_qna_text)
"""

from __future__ import annotations

import importlib.util
import logging
import time
from types import ModuleType

from google import genai
from google.genai import errors as genai_errors

from adapters._shared import team_root
from config import get_settings

log = logging.getLogger(__name__)

MENGCHENG_ROOT = "孟諴＿前處理"  # NOTE: U+FF3F full-width underscore
_MOD: ModuleType | None = None

# Spare free-tier Gemini keys supplied by the project owner; used as fallback
# when the primary GEMINI_API_KEY is rate-limited. The primary key (from .env)
# is always tried first.
_FALLBACK_KEYS: tuple[str, ...] = (
    "AIzaSyCAvaKEKV1WglpXoiOJJeeQVottKdQUUy4",
    "AIzaSyA-xcpdSFMvy1vbDnMYfvENAR4pBf_2dUY",
)


def _load_upstream() -> ModuleType:
    """Load 孟諴＿前處理/main.py once under a unique module name."""
    global _MOD
    if _MOD is not None:
        return _MOD
    src = team_root(MENGCHENG_ROOT) / "main.py"
    if not src.is_file():
        raise FileNotFoundError(f"mengcheng main.py missing: {src}")
    spec = importlib.util.spec_from_file_location("mengcheng_preprocess", str(src))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build spec for {src}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MOD = mod
    return mod


# ----------------------------------------------------------------------------
# Heuristic
# ----------------------------------------------------------------------------
_SENTENCE_PUNCT = set(".!?。？！")


def is_raw_asr(text: str, *, threshold: float = 0.005) -> bool:
    """Cheap heuristic: raw ASR has almost no sentence-terminal punctuation.

    A polished transcript runs ~1–5% sentence punctuation; raw ASR is ~0%.
    Returns True when density is below `threshold` (default 0.5%).
    Empty/whitespace text returns False (let the pipeline error out normally).
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < 200:
        return False  # too short to judge reliably; assume clean
    hits = sum(1 for c in stripped if c in _SENTENCE_PUNCT)
    density = hits / len(stripped)
    return density < threshold


# ----------------------------------------------------------------------------
# Gemini call (mirrors mengcheng main.py's retry + split-on-marker flow)
# ----------------------------------------------------------------------------
def _is_quota_or_transient(e: BaseException) -> bool:
    code = getattr(e, "code", None)
    if code in (429, 503):
        return True
    msg = str(e).lower()
    return any(s in msg for s in ("quota", "exhaust", "rate", "limit", "503", "429"))


def _is_daily_quota(e: BaseException) -> bool:
    """Distinguish daily-quota (must rotate key) from per-minute (just wait)."""
    msg = str(e).lower()
    return "resource_exhausted" in msg or "exceeded your current quota" in msg or "perdayperproject" in msg.replace("_", "")


def _call_gemini_with_retry(prompt: str, *, primary_key: str, model: str) -> str:
    keys: list[str] = []
    seen: set[str] = set()
    for k in (primary_key, *_FALLBACK_KEYS):
        if k and k not in seen:
            keys.append(k)
            seen.add(k)

    last_err: BaseException | None = None
    for key_idx, key in enumerate(keys):
        client = genai.Client(api_key=key)
        log.info("mengcheng: trying Gemini key %d/%d", key_idx + 1, len(keys))
        for attempt in range(1, 6):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "temperature": 0.1,
                        "top_p": 0.95,
                        "max_output_tokens": 65000,
                    },
                )
                return (resp.text or "").strip()
            except (genai_errors.ServerError, genai_errors.APIError) as e:
                last_err = e
                if _is_daily_quota(e):
                    log.warning("mengcheng: key %d daily quota exhausted; rotating", key_idx + 1)
                    break  # rotate to next key
                if _is_quota_or_transient(e):
                    wait = 2 ** attempt
                    log.warning("mengcheng: transient on key %d (attempt %d/3): %s; retry in %ds",
                                key_idx + 1, attempt, e, wait)
                    time.sleep(wait)
                    continue
                raise
    raise RuntimeError(f"mengcheng Gemini failed across {len(keys)} keys; last error: {last_err}")


def run(raw_text: str) -> tuple[str, str]:
    """Clean a raw ASR transcript via Gemini + the upstream prompt.

    Returns (cleaned_full_text, cleaned_qna_text). Both are newline-separated
    one-turn-per-line text ready to feed the 恩泓 adapter as `full_text` and
    `qna_text`.
    """
    settings = get_settings()
    if not settings.has_gemini():
        raise RuntimeError("mengcheng preprocessing requires GEMINI_API_KEY in .env")

    mod = _load_upstream()
    prompt = mod.build_prompt(raw_text)
    cleaned = _call_gemini_with_retry(
        prompt, primary_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL
    )

    if not cleaned:
        raise RuntimeError("mengcheng preprocessing: Gemini returned empty response")
    if mod.QNA_MARKER not in cleaned:
        raise RuntimeError(
            f"mengcheng preprocessing: missing marker {mod.QNA_MARKER!r} in Gemini output; "
            f"head={cleaned[:200]!r}"
        )

    prep_part, _, qna_part = cleaned.partition(mod.QNA_MARKER)
    prep_part = prep_part.replace(mod.QNA_MARKER, "").strip()
    qna_part = qna_part.replace(mod.QNA_MARKER, "").strip()

    prep_lines = mod._normalize_speaker_prefixes(prep_part.splitlines())
    qna_lines = mod._normalize_speaker_prefixes(qna_part.splitlines())

    if not prep_lines:
        raise RuntimeError("mengcheng preprocessing: prepared-remarks section is empty after cleanup")
    if not qna_lines:
        raise RuntimeError("mengcheng preprocessing: Q&A section is empty after cleanup")

    full_text = "\n".join(prep_lines + qna_lines)
    qna_text = "\n".join(qna_lines)
    return full_text, qna_text
