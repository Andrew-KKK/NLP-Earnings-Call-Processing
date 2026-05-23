"""Orchestrates the upload pipeline: docx → 恩泓 → (haocheng → jincing → yining).

Downstream adapters all use process-global os.chdir to satisfy upstream module
expectations (config.ini in CWD, data/ relative to CWD). Running them
concurrently via asyncio.gather caused a chdir race that corrupted file lookups
and (on team-source SystemExit) brought down uvicorn. They now run sequentially.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from adapters import (
    enhong_adapter,
    haocheng_adapter,
    jincing_adapter,
    mengcheng_adapter,
    yining_adapter,
)
from config import get_settings
from services.job_store import JobStatus, JobStore

log = logging.getLogger(__name__)


def _safe_str(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or f"{type(exc).__name__}"


async def _run_stage(
    *,
    name: str,
    step_label: str,
    coro_factory: Callable[[], Awaitable[None]],
    status: dict[str, dict],
    set_step: Callable[[str], None],
) -> None:
    """Run one downstream stage, capturing any failure into status[name].

    Catches BaseException (not just Exception) because team-source modules
    raise SystemExit on missing inputs, which would otherwise terminate the
    server process. CancelledError/KeyboardInterrupt are re-raised so the event
    loop can shut down cleanly when uvicorn is stopped.
    """
    set_step(step_label)
    try:
        await coro_factory()
        status[name] = {"ok": True}
    except (asyncio.CancelledError, KeyboardInterrupt):
        raise
    except BaseException as exc:  # noqa: BLE001 — including SystemExit on purpose
        log.exception("%s adapter failed", name)
        status[name] = {"ok": False, "error": _safe_str(exc)}


async def process_upload(
    *,
    job_id: str,
    store: JobStore,
    full_text: str,
    qna_text: str | None,
    slug: str,
) -> None:
    settings = get_settings()
    case_dir = settings.cache_dir_resolved() / slug
    case_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, dict] = {}

    def _set(step: str) -> None:
        store.update(job_id, status=JobStatus.RUNNING, step=step)

    try:
        # Auto-detect raw ASR and run 孟諴 preprocessing first if so.
        # `is_raw_asr` is cheap (linear scan); the LLM call only fires when needed.
        if mengcheng_adapter.is_raw_asr(full_text):
            _set("preprocessing")
            log.info("Raw ASR detected for slug=%s; running 孟諴 preprocessing.", slug)
            full_text, qna_text = await asyncio.to_thread(mengcheng_adapter.run, full_text)
            status["mengcheng"] = {"ok": True, "applied": True}
        else:
            status["mengcheng"] = {"ok": True, "applied": False, "reason": "input already clean"}

        _set("translating")
        full_json, qna_json = await asyncio.to_thread(
            enhong_adapter.run,
            full_text=full_text, qna_text=qna_text, out_dir=case_dir, slug=slug,
        )
        status["enhong"] = {"ok": True}

        # Sequential — the four downstream adapters share os.chdir state.
        await _run_stage(
            name="haocheng", step_label="scoring", status=status, set_step=_set,
            coro_factory=lambda: asyncio.to_thread(
                haocheng_adapter.run,
                qna_json=qna_json, full_json=full_json, out_dir=case_dir,
            ),
        )
        await _run_stage(
            name="jincing_sentiment", step_label="sentiment", status=status, set_step=_set,
            coro_factory=lambda: asyncio.to_thread(
                jincing_adapter.run_sentiment,
                qna_json=qna_json, full_json=full_json, out_dir=case_dir, slug=slug,
            ),
        )
        await _run_stage(
            name="jincing_keyphrase", step_label="keyphrase", status=status, set_step=_set,
            coro_factory=lambda: asyncio.to_thread(
                jincing_adapter.run_keyphrase,
                qna_json=qna_json, full_json=full_json, out_dir=case_dir, slug=slug,
            ),
        )
        await _run_stage(
            name="yining", step_label="summary", status=status, set_step=_set,
            coro_factory=lambda: asyncio.to_thread(
                yining_adapter.run,
                qna_json=qna_json, full_json=full_json, out_dir=case_dir, slug=slug,
            ),
        )

        (case_dir / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        store.update(job_id, status=JobStatus.DONE, step="done")

    except (asyncio.CancelledError, KeyboardInterrupt):
        raise
    except BaseException as exc:  # noqa: BLE001 — including SystemExit from enhong adapter
        log.exception("Upload pipeline failed for slug=%s", slug)
        store.update(job_id, status=JobStatus.FAILED, step="failed", error=_safe_str(exc))
        (case_dir / "status.json").write_text(
            json.dumps({**status, "_fatal": _safe_str(exc)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
