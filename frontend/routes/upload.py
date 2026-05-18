"""Upload endpoint + SSE progress channel."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import StreamingResponse

router = APIRouter()


from services.case_registry import discover_cases
from services.docx_loader import docx_to_text
from services.job_store import JobStatus, get_job_store
from services.slug import make_slug
from services.upload_processor import process_upload as _process_upload


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    full_docx: UploadFile = File(...),
    qna_docx: UploadFile | None = File(None),
    case_name: str = Form(""),
) -> dict[str, str]:
    tmpdir = Path(tempfile.mkdtemp(prefix="upload_"))
    full_path = tmpdir / (full_docx.filename or "full.docx")
    full_path.write_bytes(await full_docx.read())
    full_text = docx_to_text(full_path)
    qna_text: str | None = None
    if qna_docx is not None and qna_docx.filename:
        qna_path = tmpdir / qna_docx.filename
        qna_path.write_bytes(await qna_docx.read())
        qna_text = docx_to_text(qna_path)

    raw_name = case_name or (full_docx.filename or "")
    taken = {c.slug for c in discover_cases()}
    slug = make_slug(raw_name, taken=taken)

    store = get_job_store()
    job = store.create(slug=slug)
    background.add_task(
        _run_pipeline_async,
        job_id=job.id,
        full_text=full_text,
        qna_text=qna_text,
        slug=slug,
    )
    return {"job_id": job.id, "slug": slug}


async def _run_pipeline_async(*, job_id: str, full_text: str, qna_text: str | None, slug: str) -> None:
    await _process_upload(
        job_id=job_id,
        store=get_job_store(),
        full_text=full_text,
        qna_text=qna_text,
        slug=slug,
    )


@router.get("/sse/job/{job_id}")
async def sse_job(job_id: str) -> StreamingResponse:
    store = get_job_store()
    job = store.get(job_id)
    if job is None:
        return StreamingResponse(iter([f"event: error\ndata: not_found\n\n"]), media_type="text/event-stream")

    async def emit():
        # Replay current status first
        yield f"data: {json.dumps({'status': job.status.value, 'step': job.step})}\n\n"
        async for evt in store.events(job_id):
            yield f"data: {json.dumps(evt)}\n\n"

    return StreamingResponse(emit(), media_type="text/event-stream")
