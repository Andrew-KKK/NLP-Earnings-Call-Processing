"""Gemini-based fallback for 恩泓's Azure-OpenAI Q&A extraction (spec §8.6)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位專業的金融數據萃取專家。
請從法說會逐字稿中，精準找出「提問 (Question)」與「回答 (Answer)」配對。

【嚴格規則】：
1. 100% 複製原文，不可摘要。
2. Question 絕不可包含回答；Answer 絕不可為空。
3. 過濾 Operator/串場句（如 "The first question is..."）。
4. 當語氣轉為「給予解答的陳述句」（如 "We expect...", "Let me answer...", "我們預期..."），
   即為回答的起點，必須在此切斷。

僅以下列 JSON 格式回應，不附加其他文字：
{"qna_list": [{"question": "...", "answer": "..."}, ...]}"""


def _GenerativeModel(model: str, api_key: str):
    """Indirection so tests can monkey-patch without importing google.generativeai."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, system_instruction=SYSTEM_PROMPT)


def extract_qna_from_chunk(
    chunk_text: str,
    *,
    api_key: str,
    model: str,
    max_retries: int = 3,
) -> list[dict[str, str]]:
    """Return a list of {question, answer} dicts with the same shape 恩泓 produces."""
    client = _GenerativeModel(model, api_key)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.generate_content(
                chunk_text,
                generation_config={"response_mime_type": "application/json"},
            )
            data = json.loads(resp.text)
            pairs = data.get("qna_list", []) or []
            return [p for p in pairs if _is_valid_pair(p)]
        except Exception as exc:  # noqa: BLE001 — broad on purpose, retried
            last_err = exc
            log.warning("Gemini extraction attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2**attempt)
    if last_err:
        log.error("Gemini extraction failed after %d retries: %s", max_retries, last_err)
    return []


def _is_valid_pair(pair: Any) -> bool:
    if not isinstance(pair, dict):
        return False
    q = (pair.get("question") or "").strip()
    a = (pair.get("answer") or "").strip()
    return bool(q) and bool(a)
