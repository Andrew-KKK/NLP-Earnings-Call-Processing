"""Gemini chat service: per-case context builder + streaming proxy."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from services.precomputed_loader import CaseBundle

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位專業的金融分析助手，正在協助使用者解讀一場法說會的 Q&A 與分析結果。
規則：
1. 回答必須以繁體中文。
2. 引用 Q&A 時要附上題號（例：「第 2 題」）。
3. 解釋風險標籤時，引用底層訊號（如 overlap_ratio、tone_gap_label）。
4. 如使用者提出與本案件無關的問題，禮貌拒答並請對方換題。
5. 不得編造資料中未出現的細節。"""


def build_context(bundle: CaseBundle) -> str:
    """Compose the per-case context bundle for Gemini."""
    payload = {
        "company": bundle.slug,
        "transparency_scores": bundle.scores,
        "tone_pill": bundle.tone_pill,
        "qna": [
            {
                "index": row["index"],
                "question": row["question_translated"] or row["question"],
                "answer": row["answer_translated"] or row["answer"],
                "topic": row["topic"],
                "risk_label": row["risk_label_zh"],
                "composite_score": row["composite_score"],
                "signals": row["_signals"],
            }
            for row in bundle.qna_rows
        ],
        "summary_bullets": (bundle.raw.get("pii") or {}).get("summary", []),
    }
    return SYSTEM_PROMPT + "\n\n<case_data>\n" + json.dumps(payload, ensure_ascii=False) + "\n</case_data>"


def _ChatModel(model: str, api_key: str, *, system_instruction: str | None = None):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, system_instruction=system_instruction)


async def stream_chat(
    *,
    context: str,
    history: list[dict],
    user_msg: str,
    api_key: str,
    model: str,
) -> AsyncIterator[str]:
    """Yield text chunks from Gemini. Each chunk is forwarded to the SSE response."""
    if not api_key:
        yield "(未啟用 LLM 對話)"
        return

    client = _ChatModel(model, api_key, system_instruction=context)
    contents = list(history) + [{"role": "user", "parts": [user_msg]}]

    try:
        resp = client.generate_content(contents, stream=True)
        for chunk in resp:
            try:
                text = chunk.text or ""
            except (ValueError, AttributeError):
                # A streamed chunk with no content Part (e.g. the final chunk
                # carrying only finish_reason=STOP) makes the `.text` quick
                # accessor raise ValueError. That's benign end-of-stream — skip
                # it rather than surfacing it as a chat error.
                continue
            if text:
                yield text
    except Exception as exc:  # noqa: BLE001
        log.warning("Chat streaming failed: %s", exc)
        yield f"(對話發生錯誤：{exc})"
