import asyncio

import pytest

from services.job_store import JobStore, JobStatus


def test_create_and_get():
    store = JobStore()
    job = store.create(slug="tsmc")
    assert job.slug == "tsmc"
    assert job.status == JobStatus.PENDING
    fetched = store.get(job.id)
    assert fetched is job


def test_update_status_and_emit():
    store = JobStore()
    job = store.create(slug="x")
    events: list[dict] = []

    async def consume():
        async for evt in store.events(job.id):
            events.append(evt)
            if evt["status"] == JobStatus.DONE.value:
                break

    async def driver():
        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0)
        store.update(job.id, status=JobStatus.RUNNING, step="translating")
        store.update(job.id, status=JobStatus.RUNNING, step="extracting_qna")
        store.update(job.id, status=JobStatus.DONE, step="done")
        await consumer

    asyncio.run(driver())
    assert [e["step"] for e in events] == ["translating", "extracting_qna", "done"]
