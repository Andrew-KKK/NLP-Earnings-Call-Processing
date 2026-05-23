"""Per-Q&A risk-label, composite score, topic and tone-pill derivation (spec §8)."""

from __future__ import annotations

from enum import Enum
from typing import Mapping


class RiskLabel(str, Enum):
    DIRECT = "direct"
    VAGUE = "vague"
    EVASIVE = "evasive"
    TONE_SHIFT = "tone_shift"

    @property
    def zh(self) -> str:
        return {
            "direct": "直接回答",
            "vague": "模糊回答",
            "evasive": "迴避回答",
            "tone_shift": "語氣轉變",
        }[self.value]

    @property
    def palette_class(self) -> str:
        # Matches Tailwind class names defined in templates/base.html
        return {
            "direct": "risk-direct",
            "vague": "risk-vague",
            "evasive": "risk-evasive",
            "tone_shift": "risk-tone",
        }[self.value]


def derive_risk_label(signals: Mapping[str, object]) -> RiskLabel:
    """Apply the cascade defined in spec §8.1. First match wins."""
    if signals.get("topic_mismatch_flag") or signals.get("risk_downplay_flag"):
        return RiskLabel.EVASIVE
    if signals.get("negative_question_soft_answer_flag") or signals.get("tone_gap_label", "aligned") != "aligned":
        return RiskLabel.TONE_SHIFT
    overlap = float(signals.get("overlap_ratio", 1.0) or 0.0)
    if overlap < 0.4:
        return RiskLabel.VAGUE
    return RiskLabel.DIRECT


def composite_score(
    *,
    overlap_ratio: float,
    topic_mismatch_flag: bool,
    risk_downplay_flag: bool,
    negative_question_soft_answer_flag: bool,
) -> int:
    """Per-Q&A composite score 0-100 (spec §8.2)."""
    addressed = float(overlap_ratio or 0.0) * 40
    transparency = 40 if not (topic_mismatch_flag or risk_downplay_flag) else 10
    tone = 20 if not negative_question_soft_answer_flag else 5
    return int(round(addressed + transparency + tone))


def derive_topic(question_key_phrases: list[str], question_text: str) -> str:
    """Short 2-6 char topic tag (spec §8.3). Deterministic; no LLM call."""
    phrases = [p.strip() for p in (question_key_phrases or []) if p and p.strip()]
    if phrases:
        return "、".join(phrases[:2])
    text = (question_text or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return text + "…"
    return text[:8] + "…"


def tone_pill(tone_shift_flag: bool) -> dict[str, str]:
    """Hero pill text + CSS variant key (spec §8.5)."""
    if tone_shift_flag:
        return {"text": "⚠ 語氣轉趨保守", "variant": "shifted"}
    return {"text": "● 語氣平穩", "variant": "stable"}


def radar_axes(scores: Mapping[str, float]) -> dict[str, float]:
    """Five radar axes, all oriented higher = better (0-100, outer = more transparent).

    The 浩誠 scoring module emits 迴避度 / 語氣落差 as "higher = worse" axes
    (more evasion / bigger tone gap). The composite 綜合透明度 already folds them
    in as ``100 − score`` (see 浩誠_回答品質評分/metrics.py:composite_transparency_score);
    here we apply the same flip for the radar so a transparent call reads as a
    large, even pentagon instead of being pinched on those two spokes. Renamed
    to 坦誠度 / 語氣穩定 to match the now-positive direction.

    Missing badness axes default to 50 (→ 50 after flip = neutral), never to a
    falsely-perfect 100.
    """
    def _clip(x: float) -> float:
        return max(0.0, min(100.0, x))

    return {
        "直接性": _clip(float(scores.get("直接性", 0.0))),
        "具體性": _clip(float(scores.get("具體性", 0.0))),
        "坦誠度": _clip(100.0 - float(scores.get("迴避度", 50.0))),
        "語氣穩定": _clip(100.0 - float(scores.get("語氣落差", 50.0))),
        "一致性": _clip(float(scores.get("一致性", 0.0))),
    }
