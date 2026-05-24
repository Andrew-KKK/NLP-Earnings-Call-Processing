"""Load a CaseInfo's JSON outputs and assemble the dashboard view-model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.case_registry import CaseInfo
from services.risk_labels import composite_score, derive_risk_label, derive_topic, tone_pill


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# Placeholder sentence-ids the summary engine emits when it produces nothing
# real (e.g. ["S1"]) — treat as empty rather than rendering them.
_SUMMARY_PLACEHOLDER_RE = re.compile(r"^[A-Za-z]\d*$")


def _clean_summary(payload: Any) -> list[str]:
    """Extract display-ready summary sentences, dropping blanks/placeholders."""
    if not isinstance(payload, dict):
        return []
    out: list[str] = []
    for item in payload.get("summary") or []:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s or _SUMMARY_PLACEHOLDER_RE.match(s):
            continue
        out.append(s)
    return out


@dataclass
class CaseBundle:
    slug: str
    display_name: str
    source: str
    scores: dict[str, float]
    tone_pill: dict[str, str]
    qna_rows: list[dict[str, Any]]
    full_summary: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def transparency(self) -> float:
        return float(self.scores.get("綜合透明度", 0.0))


def load_case_bundle(info: CaseInfo) -> CaseBundle:
    qna_payload = _read_json(info.qna_json) or {"qna_list": []}
    scores_payload = _read_json(info.scores_json) or {"scores": {}}
    sent_payload = _read_json(info.sentiment_dir / "qna_sentiment_summary.json") or {"qna_results": []}
    kp_payload = _read_json(info.keyphrase_dir / "qna_keyphrase_summary.json") or {"qna_results": []}
    tone_shift = _read_json(info.sentiment_dir / "company_tone_shift_summary.json") or {"tone_shift_results": [{}]}
    pii_payload = _read_json(info.pii_summary_json) or {"summary": []}
    full_summary_payload = _read_json(info.full_summary_json)
    full_summary = _clean_summary(full_summary_payload)

    sent_by_pair = {int(float(r["pair_id"])): r for r in sent_payload.get("qna_results", []) if r.get("pair_id") is not None}
    kp_by_pair = {int(float(r["pair_id"])): r for r in kp_payload.get("qna_results", []) if r.get("pair_id") is not None}

    qna_rows: list[dict[str, Any]] = []
    for idx, pair in enumerate(qna_payload.get("qna_list", []), start=1):
        sent = sent_by_pair.get(idx, {})
        kp = kp_by_pair.get(idx, {})
        signals = {
            "topic_mismatch_flag": bool(kp.get("topic_mismatch_flag")),
            "risk_downplay_flag": bool(sent.get("risk_downplay_flag")),
            "negative_question_soft_answer_flag": bool(sent.get("negative_question_soft_answer_flag")),
            "tone_gap_label": sent.get("tone_gap_label", "aligned"),
            "overlap_ratio": float(kp.get("overlap_ratio") or 0.0),
        }
        label = derive_risk_label(signals)
        qna_rows.append(
            {
                "index": idx,
                "question": pair.get("question", ""),
                "answer": pair.get("answer", ""),
                "question_translated": pair.get("question_translated", ""),
                "answer_translated": pair.get("answer_translated", ""),
                "topic": derive_topic(kp.get("question_key_phrases") or [], pair.get("question_translated", "")),
                "risk_label": label.value,
                "risk_label_zh": label.zh,
                "risk_label_class": label.palette_class,
                "composite_score": composite_score(
                    overlap_ratio=signals["overlap_ratio"],
                    topic_mismatch_flag=signals["topic_mismatch_flag"],
                    risk_downplay_flag=signals["risk_downplay_flag"],
                    negative_question_soft_answer_flag=signals["negative_question_soft_answer_flag"],
                ),
                "_signals": signals,
            }
        )

    scores = dict(scores_payload.get("scores", {}))
    tone_shift_row = (tone_shift.get("tone_shift_results") or [{}])[0]
    pill = tone_pill(bool(tone_shift_row.get("tone_shift_flag")))

    return CaseBundle(
        slug=info.slug,
        display_name=info.display_name,
        source=info.source,
        scores=scores,
        tone_pill=pill,
        qna_rows=qna_rows,
        full_summary=full_summary,
        raw={
            "qna": qna_payload,
            "sentiment": sent_payload,
            "keyphrase": kp_payload,
            "tone_shift": tone_shift,
            "pii": pii_payload,
        },
    )
