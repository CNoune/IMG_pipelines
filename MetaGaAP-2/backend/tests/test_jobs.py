"""Tests for the async job manager's event delivery.

Guards the regression found in review: a WebSocket subscriber that connects
*before* a run starts must receive the live event stream, not just the replayed
history. The original code captured a non-running event loop on a threadpool
worker, so ``call_soon_threadsafe`` scheduled onto a dead loop and no live event
was ever delivered.
"""

from __future__ import annotations

import asyncio

from metagaap2 import jobs
from metagaap2.models import (
    JobState,
    RunConfig,
    Sample,
    WSEvent,
    WSEventType,
)


def _fake_execute(job, *, emit, is_cancelled):  # noqa: ANN001 - test helper
    """Stand-in for pipeline.execute_job that emits a known event sequence."""
    job.state = JobState.RUNNING
    emit(WSEvent(type=WSEventType.STATE, job_id=job.id, state=JobState.RUNNING, progress=0.0))
    for i in range(3):
        emit(WSEvent(type=WSEventType.LOG, job_id=job.id, line=f"line {i}"))
    job.state = JobState.COMPLETED
    job.progress = 1.0
    emit(
        WSEvent(
            type=WSEventType.DONE,
            job_id=job.id,
            state=JobState.COMPLETED,
            progress=1.0,
        )
    )


def _config() -> RunConfig:
    return RunConfig(
        run_name="t",
        work_dir=".",
        reference="ref.fa",
        samples=[Sample(name="s1", r1="r1.fq")],
    )


def test_live_events_reach_a_presubscribed_consumer(monkeypatch):
    """A subscriber attached before start() receives every live event."""
    monkeypatch.setattr(jobs, "execute_job", _fake_execute)
    mgr = jobs.JobManager()

    async def run() -> list[WSEvent]:
        mgr.bind_loop(asyncio.get_running_loop())
        job = mgr.create(_config())
        received: list[WSEvent] = []

        async def consume() -> None:
            async for ev in mgr.subscribe(job.id):
                received.append(ev)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)  # let the subscriber attach before the run
        mgr.start(job)
        await asyncio.wait_for(task, timeout=5)
        return received

    received = asyncio.run(run())
    types = [e.type for e in received]
    assert WSEventType.STATE in types
    assert sum(1 for e in received if e.type is WSEventType.LOG) == 3
    assert received[-1].type is WSEventType.DONE
    assert received[-1].state is JobState.COMPLETED


def test_late_subscriber_replays_history(monkeypatch):
    """A subscriber that connects after completion still sees the full record."""
    monkeypatch.setattr(jobs, "execute_job", _fake_execute)
    mgr = jobs.JobManager()

    async def run() -> list[WSEvent]:
        mgr.bind_loop(asyncio.get_running_loop())
        job = mgr.create(_config())
        mgr.start(job)
        # Wait for the worker thread to finish producing events.
        runtime = mgr._runtime(job.id)  # noqa: SLF001 - white-box wait
        for _ in range(200):
            if runtime is not None and runtime.finished.is_set():
                break
            await asyncio.sleep(0.01)
        received: list[WSEvent] = []
        async for ev in mgr.subscribe(job.id):
            received.append(ev)
        return received

    received = asyncio.run(run())
    assert sum(1 for e in received if e.type is WSEventType.LOG) == 3
    assert any(e.type is WSEventType.DONE for e in received)
