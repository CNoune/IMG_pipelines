"""In-memory async job manager for MetaGaAP 2.

This module bridges the synchronous, thread-bound pipeline orchestrator
(:func:`metagaap2.pipeline.execute_job`) to the asynchronous FastAPI layer
(REST + WebSocket). It owns the lifecycle of every :class:`~metagaap2.models.Job`
for the life of the server process:

* :meth:`JobManager.create`     - build a queued job from a
  :class:`~metagaap2.models.RunConfig` (assigns the id, timestamps it, and seeds
  one :class:`~metagaap2.models.SampleResult` skeleton per sample so the UI has
  something to render before the run starts),
* :meth:`JobManager.start`      - run the pipeline on a background worker thread,
  forwarding every :class:`~metagaap2.models.WSEvent` emitted by the orchestrator
  onto a per-job :class:`asyncio.Queue` in a thread-safe way,
* :meth:`JobManager.subscribe`  - an async generator a WebSocket handler awaits;
  it replays the (bounded) event history for late subscribers and then yields
  live events until the job reaches a terminal state, and
* :meth:`JobManager.cancel`     - request cooperative cancellation via a per-job
  :class:`threading.Event` that the orchestrator polls between stages.

The orchestrator runs on a worker thread, so it must never touch the event loop
directly. The emit callback installed by :meth:`JobManager.start` captures the
running loop and hands each event back to it with
``loop.call_soon_threadsafe(queue.put_nowait, event)``; the queue is created and
drained on the loop's thread. A bounded history is kept per job so a client that
connects after the run has already produced output still sees the earlier
events, and so that a client connecting after completion receives the full
record and a terminal sentinel.

A single module-level :data:`manager` instance is shared by the server.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from .models import (
    Job,
    JobState,
    RunConfig,
    SampleResult,
    WSEvent,
    WSEventType,
)
from .pipeline import execute_job

__all__ = ["JobManager", "manager"]

#: Maximum number of WebSocket events retained per job for late-subscriber replay.
_HISTORY_LIMIT = 2000


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 form."""
    return datetime.now(timezone.utc).isoformat()


class _JobRuntime:
    """Per-job runtime state that lives only in memory (never serialised).

    Holds the event-streaming machinery for one job: the asyncio queues feeding
    each live subscriber, the bounded replay history, the worker thread, the
    cancellation flag and the loop the queues belong to.
    """

    def __init__(self, job: Job) -> None:
        self.job = job
        #: Live subscriber queues. Each subscriber gets its own queue so a slow
        #: consumer cannot starve the others.
        self.subscribers: set[asyncio.Queue[Optional[WSEvent]]] = set()
        #: Bounded replay history so late subscribers can catch up.
        self.history: deque[WSEvent] = deque(maxlen=_HISTORY_LIMIT)
        #: True once a terminal (DONE) event has been observed.
        self.finished = threading.Event()
        #: Set by :meth:`JobManager.cancel`; polled by the orchestrator.
        self.cancel_flag = threading.Event()
        #: The worker thread running the pipeline (None until started).
        self.thread: Optional[threading.Thread] = None
        #: The event loop the queues belong to (captured in ``start``).
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        #: Guards subscriber-set + history mutations across threads.
        self.lock = threading.Lock()


class JobManager:
    """In-memory registry and background runner for pipeline jobs.

    Thread-safe for the operations the server performs: jobs are created and
    inspected on the event-loop thread, executed on worker threads, and their
    events are streamed back to the loop thread-safely.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._runtimes: dict[str, _JobRuntime] = {}
        self._lock = threading.Lock()
        #: The server's *running* event loop, bound once at application startup
        #: so worker threads can hand events back to it thread-safely. Never a
        #: freshly-created, non-running loop. See :meth:`bind_loop`.
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the event loop the FastAPI server runs on.

        Called once from the application startup hook (which executes on the
        loop thread). Worker threads use this loop with
        ``call_soon_threadsafe`` to deliver events to live WebSocket
        subscribers, so it must be the actual running loop.
        """
        self._loop = loop

    # -- creation / lookup --------------------------------------------------- #
    def create(self, config: RunConfig) -> Job:
        """Create and register a queued :class:`Job` from ``config``.

        Assigns a fresh ``uuid4().hex`` id, stamps ``created_at`` with the
        current UTC time, and seeds one :class:`SampleResult` skeleton per
        configured sample so the UI can render the sample list immediately.
        """
        job = Job(
            id=uuid4().hex,
            config=config,
            state=JobState.QUEUED,
            created_at=_now_iso(),
            samples=[SampleResult(sample=s.name) for s in config.samples],
        )
        runtime = _JobRuntime(job)
        with self._lock:
            self._jobs[job.id] = job
            self._runtimes[job.id] = runtime
        return job

    def list(self) -> list[Job]:
        """Return all known jobs, newest first (by creation time)."""
        with self._lock:
            jobs = list(self._jobs.values())
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def get(self, job_id: str) -> Optional[Job]:
        """Return the job with ``job_id``, or ``None`` if unknown."""
        with self._lock:
            return self._jobs.get(job_id)

    def _runtime(self, job_id: str) -> Optional[_JobRuntime]:
        with self._lock:
            return self._runtimes.get(job_id)

    # -- execution ----------------------------------------------------------- #
    def start(self, job: Job) -> None:
        """Run ``job`` on a background worker thread.

        Captures the currently-running event loop so the worker thread can push
        events back onto it thread-safely, then spawns the worker. The pipeline
        orchestrator (:func:`execute_job`) appends its own authoritative
        per-sample results as it runs, so the queued-time skeleton is cleared
        first to avoid duplicate sample entries. Calling this on a job that has
        already been started is a no-op.
        """
        runtime = self._runtime(job.id)
        if runtime is None:
            raise KeyError(f"Unknown job {job.id!r}; create it before starting.")

        with runtime.lock:
            if runtime.thread is not None:
                return  # already started
            # Use the server's running loop (bound at startup via ``bind_loop``)
            # so the worker thread can deliver events thread-safely. For sync
            # FastAPI routes ``start`` runs on a threadpool worker, so there is
            # NO running loop here to capture - and a fresh, non-running loop
            # would silently swallow every event. If the loop has not been bound
            # yet (tests / embedded use), the first subscriber binds it lazily
            # in ``subscribe`` before any live event needs delivering.
            runtime.loop = self._loop
            # The orchestrator re-populates ``samples`` itself; drop the skeleton.
            job.samples = []
            thread = threading.Thread(
                target=self._run,
                args=(runtime,),
                name=f"metagaap2-job-{job.id[:8]}",
                daemon=True,
            )
            runtime.thread = thread
        thread.start()

    def _run(self, runtime: _JobRuntime) -> None:
        """Worker-thread body: execute the pipeline and stream its events.

        Runs entirely off the event loop. Every emitted event is recorded in the
        bounded history and forwarded to each live subscriber queue via
        ``loop.call_soon_threadsafe``. A final sentinel (``None``) is pushed to
        every subscriber so :meth:`subscribe` can finish cleanly.
        """
        job = runtime.job

        def emit(event: WSEvent) -> None:
            self._dispatch(runtime, event)
            if event.type is WSEventType.DONE:
                runtime.finished.set()

        try:
            execute_job(job, emit=emit, is_cancelled=runtime.cancel_flag.is_set)
        except Exception as exc:  # noqa: BLE001 - execute_job is contractually
            # exception-safe, but guard the thread regardless so a stray failure
            # never leaves subscribers hanging.
            job.state = JobState.FAILED
            job.error = job.error or str(exc)
            job.ended_at = job.ended_at or _now_iso()
            self._dispatch(
                runtime,
                WSEvent(
                    type=WSEventType.DONE,
                    job_id=job.id,
                    state=job.state,
                    progress=job.progress,
                ),
            )
        finally:
            runtime.finished.set()
            self._close_subscribers(runtime)

    # -- event fan-out (called from the worker thread) ----------------------- #
    def _dispatch(self, runtime: _JobRuntime, event: WSEvent) -> None:
        """Record ``event`` in history and forward it to live subscribers.

        Safe to call from the worker thread: the subscriber queues are driven on
        the loop thread, so each ``put_nowait`` is scheduled with
        ``call_soon_threadsafe``.
        """
        loop = runtime.loop
        with runtime.lock:
            runtime.history.append(event)
            queues = list(runtime.subscribers)
        if loop is None:
            return
        for queue in queues:
            loop.call_soon_threadsafe(self._safe_put, queue, event)

    def _close_subscribers(self, runtime: _JobRuntime) -> None:
        """Push the terminal sentinel to every live subscriber queue."""
        loop = runtime.loop
        with runtime.lock:
            queues = list(runtime.subscribers)
        if loop is None:
            return
        for queue in queues:
            loop.call_soon_threadsafe(self._safe_put, queue, None)

    @staticmethod
    def _safe_put(queue: "asyncio.Queue[Optional[WSEvent]]", item: Optional[WSEvent]) -> None:
        """Best-effort enqueue on the loop thread (drop if a queue is full)."""
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:  # pragma: no cover - queues are unbounded
            pass

    # -- subscription (consumed by the WebSocket handler) -------------------- #
    async def subscribe(self, job_id: str) -> AsyncIterator[WSEvent]:
        """Yield :class:`WSEvent` envelopes for ``job_id``.

        Replays the bounded event history first (so a late subscriber sees what
        it missed), then yields live events as they arrive. The generator
        finishes once the job has reached a terminal state and the terminal
        ``DONE`` event has been delivered.

        Unknown ``job_id`` yields nothing and returns immediately.
        """
        runtime = self._runtime(job_id)
        if runtime is None:
            return

        # ``subscribe`` runs inside the server's running loop. Bind it now if the
        # startup hook hasn't already, so events dispatched from the worker
        # thread while this subscriber is connected are delivered (not just
        # replayed from history).
        running_loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = running_loop
        if runtime.loop is None:
            runtime.loop = running_loop

        queue: "asyncio.Queue[Optional[WSEvent]]" = asyncio.Queue()
        with runtime.lock:
            replay = list(runtime.history)
            already_finished = runtime.finished.is_set()
            runtime.subscribers.add(queue)

        try:
            # 1) Replay everything recorded so far.
            for event in replay:
                yield event

            # 2) If the job had already finished before we subscribed, the
            #    sentinel that closes live subscribers was sent before we joined,
            #    so the history above is the complete record - stop here.
            if already_finished:
                return

            # 3) Stream live events until the terminal sentinel arrives.
            while True:
                event = await queue.get()
                if event is None:  # terminal sentinel
                    return
                yield event
        finally:
            with runtime.lock:
                runtime.subscribers.discard(queue)

    # -- cancellation -------------------------------------------------------- #
    def cancel(self, job_id: str) -> Optional[Job]:
        """Request cooperative cancellation of ``job_id``.

        Sets the per-job :class:`threading.Event` the orchestrator polls between
        stages. Returns the job (with its current state) or ``None`` if unknown.
        A job that has already finished is returned unchanged.
        """
        runtime = self._runtime(job_id)
        if runtime is None:
            return None
        runtime.cancel_flag.set()
        if runtime.job.state is JobState.QUEUED:
            # Never started: flip it straight to cancelled so the UI reflects it.
            runtime.job.state = JobState.CANCELLED
            runtime.job.ended_at = _now_iso()
        return runtime.job


#: Process-wide singleton shared by the FastAPI server.
manager = JobManager()
