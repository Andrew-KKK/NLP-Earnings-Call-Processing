"""Page routes for landing and dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from config import get_settings
from services.case_registry import discover_cases, find_case
from services.insights_composer import (
    build_headline_payload,
    compose_headline,
    compose_rule_list,
)
from services.precomputed_loader import load_case_bundle
from services.risk_labels import radar_axes

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/")
def landing(request: Request):
    cases = discover_cases()
    bundles = []
    for c in cases:
        if c.all_files_exist():
            try:
                bundle = load_case_bundle(c)
                bundles.append(_card(bundle, c.source))
            except Exception:
                continue
    return TEMPLATES.TemplateResponse(
        request,
        "index.html",
        {
            "precomputed_cases": [b for b in bundles if b["source"] == "precomputed"],
            "uploaded_cases": [b for b in bundles if b["source"] == "upload"],
        },
    )


def _card(bundle, source: str) -> dict:
    return {
        "slug": bundle.slug,
        "display_name": bundle.display_name,
        "source": source,
        "transparency": bundle.transparency,
        "tone_pill": bundle.tone_pill,
    }


@router.get("/case/{slug}")
def dashboard(request: Request, slug: str):
    info = find_case(slug)
    if info is None:
        raise HTTPException(status_code=404, detail="case not found")
    bundle = load_case_bundle(info)
    tone_shift_row = (bundle.raw.get("tone_shift", {}).get("tone_shift_results") or [{}])[0]
    rule_list = compose_rule_list(
        scores=bundle.scores,
        qna_rows=bundle.qna_rows,
        tone_shift_flag=bool(tone_shift_row.get("tone_shift_flag")),
        negative_score_shift=float(tone_shift_row.get("negative_score_shift") or 0.0),
    )
    settings = get_settings()
    headline = compose_headline(
        build_headline_payload(
            slug=bundle.slug,
            scores=bundle.scores,
            tone_shift_flag=bool(tone_shift_row.get("tone_shift_flag")),
            qna_rows=bundle.qna_rows,
        ),
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
    )

    radar = radar_axes(bundle.scores)
    return TEMPLATES.TemplateResponse(
        request,
        "dashboard.html",
        {
            "bundle": bundle,
            "radar_json": json.dumps(radar, ensure_ascii=False),
            "headline": headline,
            "worth_tracking": rule_list["worth_tracking"],
            "disclosure_risks": rule_list["disclosure_risks"],
        },
    )
