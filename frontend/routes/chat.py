"""Gemini chat SSE proxy."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from config import get_settings
from services.case_registry import find_case
from services.chat_service import build_context, stream_chat as _stream_chat
from services.precomputed_loader import load_case_bundle

router = APIRouter()


def _sse_event(payload: str) -> str:
    """Encode arbitrary text (possibly containing newlines) as one SSE event.

    SSE is line-bounded: each ``data:`` line is one segment, and the spec
    rejoins consecutive ``data:`` lines with ``\\n``. A naive ``f"data: {x}\\n\\n"``
    drops everything after the first newline in ``x``, which corrupted Gemini
    chunks that contained markdown (newlines between bullets/headings).

    The spec also strips a single trailing ``\\n`` from the data buffer before
    dispatch, so we append one extra empty ``data:`` line whenever the payload
    ends in ``\\n``. This preserves paragraph breaks that fall on chunk
    boundaries.
    """
    lines = payload.split("\n")
    if not payload or payload.endswith("\n"):
        lines.append("")
    return "".join(f"data: {line}\n" for line in lines) + "\n"


@router.get("/chat/stream")
async def chat_stream(
    case: str = Query(...),
    msg: str = Query(...),
    history: str = Query("[]"),
):
    info = find_case(case)
    if info is None:
        raise HTTPException(status_code=404, detail="case not found")
    bundle = load_case_bundle(info)
    ctx = build_context(bundle)

    try:
        parsed_history = json.loads(history) or []
    except json.JSONDecodeError:
        parsed_history = []

    settings = get_settings()

    async def emit():
        async for piece in _stream_chat(
            context=ctx,
            history=parsed_history,
            user_msg=msg,
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        ):
            if piece:
                yield _sse_event(piece)
        yield "event: done\ndata: 1\n\n"

    return StreamingResponse(emit(), media_type="text/event-stream")
