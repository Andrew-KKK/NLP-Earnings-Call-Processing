"""Preview route: renders the dashboard with real TSMC data for design review.

This is a temporary scaffold so the user can see the visual design before the
full pre-computed loader + page route are implemented (Tasks 8-9, 23-24).
Replace with the proper /case/{slug} route once those tasks land.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from services.risk_labels import (
    composite_score,
    derive_risk_label,
    derive_topic,
    tone_pill,
)

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENHONG_DIR = PROJECT_ROOT / "恩泓_ 逐字稿翻譯和 Q&A 擷取"
HAOCHENG_DIR = PROJECT_ROOT / "浩誠_回答品質評分" / "output" / "batch_from_json"
JINCING_SENT_DIR = PROJECT_ROOT / "瑾慈：情緒分析&關鍵字擷取" / "sentiment_output"
JINCING_KP_DIR = PROJECT_ROOT / "瑾慈：情緒分析&關鍵字擷取" / "keyphrase_output"


@dataclass
class _Bundle:
    slug: str
    display_name: str
    scores: dict
    tone_pill: dict
    qna_rows: list

    @property
    def transparency(self) -> float:
        return float(self.scores.get("綜合透明度", 0.0))


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_bundle(slug: str) -> _Bundle:
    qna = _read(ENHONG_DIR / f"{slug}_extracted_qna_translation.json")
    scores_payload = _read(HAOCHENG_DIR / f"{slug}_scores.json")
    sent = _read(JINCING_SENT_DIR / slug / "qna_sentiment_summary.json")
    kp = _read(JINCING_KP_DIR / slug / "qna_keyphrase_summary.json")
    tone_shift = _read(JINCING_SENT_DIR / slug / "company_tone_shift_summary.json")

    sent_by_pair = {int(float(r["pair_id"])): r for r in sent.get("qna_results", []) if r.get("pair_id") is not None}
    kp_by_pair = {int(float(r["pair_id"])): r for r in kp.get("qna_results", []) if r.get("pair_id") is not None}

    rows: list[dict] = []
    for idx, pair in enumerate(qna.get("qna_list", []), start=1):
        s = sent_by_pair.get(idx, {})
        k = kp_by_pair.get(idx, {})
        signals = {
            "topic_mismatch_flag": bool(k.get("topic_mismatch_flag")),
            "risk_downplay_flag": bool(s.get("risk_downplay_flag")),
            "negative_question_soft_answer_flag": bool(s.get("negative_question_soft_answer_flag")),
            "tone_gap_label": s.get("tone_gap_label", "aligned"),
            "overlap_ratio": float(k.get("overlap_ratio") or 0.0),
        }
        label = derive_risk_label(signals)
        rows.append({
            "index": idx,
            "question": pair.get("question", ""),
            "answer": pair.get("answer", ""),
            "question_translated": pair.get("question_translated", ""),
            "answer_translated": pair.get("answer_translated", ""),
            "topic": derive_topic(k.get("question_key_phrases") or [], pair.get("question_translated", "")),
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
        })

    tone_row = (tone_shift.get("tone_shift_results") or [{}])[0]
    return _Bundle(
        slug=slug,
        display_name=slug.upper(),
        scores=scores_payload.get("scores", {}),
        tone_pill=tone_pill(bool(tone_row.get("tone_shift_flag"))),
        qna_rows=rows,
    )


def _rule_list(bundle: _Bundle, tone_shift_flag: bool, neg_shift: float) -> dict:
    worth = []
    for row in bundle.qna_rows:
        if row["risk_label"] in {"evasive", "tone_shift"}:
            worth.append({
                "index": row["index"],
                "bullet": f"第 {row['index']} 題 · {row['topic']} · {row['risk_label_zh']}",
            })
    disclosure = []
    t = bundle.transparency
    if t < 50:
        disclosure.append(f"整體透明度偏低 ({t:.0f}/100)")
    if tone_shift_flag:
        disclosure.append(f"Q&A 階段語氣較簡報轉趨保守 (Δ {neg_shift:+.2f})")
    n_dp = sum(1 for r in bundle.qna_rows if r["_signals"].get("risk_downplay_flag"))
    if n_dp:
        disclosure.append(f"{n_dp} 題出現負面議題弱化訊號")
    return {"worth_tracking": worth, "disclosure_risks": disclosure}


@router.get("/preview")
@router.get("/preview/{slug}")
def preview(request: Request, slug: str = "tsmc"):
    try:
        bundle = _build_bundle(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"case not found or incomplete: {exc}")

    tone_shift_payload = _read(JINCING_SENT_DIR / slug / "company_tone_shift_summary.json")
    tone_row = (tone_shift_payload.get("tone_shift_results") or [{}])[0]
    rule = _rule_list(bundle, bool(tone_row.get("tone_shift_flag")), float(tone_row.get("negative_score_shift") or 0.0))

    radar = {k: bundle.scores.get(k, 0) for k in ("直接性", "具體性", "迴避度", "語氣落差", "一致性")}

    headline = (
        f"{bundle.display_name} 本場法說會綜合透明度為 {bundle.transparency:.0f}/100，"
        + ("整體仍屬可讀。" if bundle.transparency >= 50 else "略低於可讀門檻。")
        + (f" 共 {len(rule['worth_tracking'])} 題出現迴避或語氣轉變訊號，建議優先追蹤。" if rule["worth_tracking"] else "")
    )

    return TEMPLATES.TemplateResponse(
        request,
        "preview.html",
        {
            "bundle": bundle,
            "radar_json": json.dumps(radar, ensure_ascii=False),
            "headline": headline,
            "worth_tracking": rule["worth_tracking"],
            "disclosure_risks": rule["disclosure_risks"],
        },
    )
