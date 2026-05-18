"""HTMX swap targets."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from services.case_registry import find_case
from services.precomputed_loader import load_case_bundle

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/api/case/{slug}/qna")
def qna_partial(request: Request, slug: str):
    info = find_case(slug)
    if info is None:
        raise HTTPException(status_code=404)
    bundle = load_case_bundle(info)
    return TEMPLATES.TemplateResponse(
        request,
        "partials/qna_table.html",
        {"qna_rows": bundle.qna_rows},
    )
