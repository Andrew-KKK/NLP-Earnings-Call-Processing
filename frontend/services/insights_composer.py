"""Investment-insights panel composition (spec §8.4)."""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

HEADLINE_SYSTEM_PROMPT = """你是金融分析師。給定法說會 Q&A 的分析結果（透明度分數、風險旗標、情緒落差），
請以繁體中文寫 2-3 句重點摘要：
  1. 整體透明度評價（高 / 中 / 低 + 一句佐證）
  2. 最需追蹤的一題（題號 + 一句原因）
  3. 是否有語氣轉變或揭露風險（若無則略過）
不得編造資料中未出現的細節。"""


def _HeadlineModel(model: str, api_key: str):
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name=model, system_instruction=HEADLINE_SYSTEM_PROMPT)


def compose_headline(payload: dict, *, api_key: str, model: str) -> str:
    """LLM-written 2-3 sentence summary in Traditional Chinese. Empty if no key."""
    if not api_key:
        return ""
    try:
        client = _HeadlineModel(model, api_key)
        resp = client.generate_content(json.dumps(payload, ensure_ascii=False))
        return (resp.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("Insights headline failed: %s", exc)
        return ""


def build_headline_payload(*, slug: str, scores: dict, tone_shift_flag: bool, qna_rows: list) -> dict:
    """Build the compact JSON payload the LLM receives."""
    worst = None
    for row in sorted(qna_rows, key=lambda r: r.get("composite_score", 100)):
        if row["risk_label"] in {"evasive", "tone_shift", "vague"}:
            worst = {
                "index": row["index"],
                "topic": row.get("topic", ""),
                "label": row["risk_label_zh"],
                "score": row["composite_score"],
            }
            break
    flagged = sum(1 for r in qna_rows if r["risk_label"] in {"evasive", "tone_shift"})
    return {
        "company": slug,
        "transparency": int(round(float(scores.get("綜合透明度", 0.0)))),
        "tone_shift_flag": bool(tone_shift_flag),
        "worst_qna": worst,
        "flagged_count": flagged,
    }


def compose_rule_list(
    *,
    scores: dict[str, float],
    qna_rows: list[dict[str, Any]],
    tone_shift_flag: bool,
    negative_score_shift: float,
) -> dict[str, list]:
    """Return the deterministic part of the insights panel."""
    worth_tracking: list[dict[str, str]] = []
    for row in qna_rows:
        if row["risk_label"] in {"evasive", "tone_shift"}:
            worth_tracking.append(
                {
                    "index": row["index"],
                    "bullet": f"第 {row['index']} 題 · {row.get('topic', '')} · {row['risk_label_zh']}",
                }
            )

    disclosure: list[str] = []
    transparency = float(scores.get("綜合透明度", 0.0))
    if transparency < 50:
        disclosure.append(f"整體透明度偏低 ({transparency:.0f}/100)")
    if tone_shift_flag:
        disclosure.append(f"Q&A 階段語氣較簡報轉趨保守 (Δ {negative_score_shift:+.2f})")
    n_downplay = sum(1 for row in qna_rows if row.get("_signals", {}).get("risk_downplay_flag"))
    if n_downplay > 0:
        disclosure.append(f"{n_downplay} 題出現負面議題弱化訊號")

    return {"worth_tracking": worth_tracking, "disclosure_risks": disclosure}
