"""In-memory job store used by the upload flow + SSE progress route."""

from __future__ import annotations

import asyncio
import enum
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    slug: str
    status: JobStatus = JobStatus.PENDING
    step: str = "queued"
    error: str | None = None
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue, repr=False)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(self, *, slug: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, slug=slug)
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, *, status: JobStatus, step: str, error: str | None = None) -> None:
        job = self._jobs[job_id]
        job.status = status
        job.step = step
        job.error = error
        job._queue.put_nowait({"status": status.value, "step": step, "error": error})

    async def events(self, job_id: str) -> AsyncIterator[dict]:
        job = self._jobs[job_id]
        while True:
            evt = await job._queue.get()
            yield evt
            if evt["status"] in {JobStatus.DONE.value, JobStatus.FAILED.value}:
                return


_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
