"""FastAPI application for MetaGaAP 2.

Exposes the REST + WebSocket API that the React front-end talks to (see
``frontend/src/api.ts`` and SPEC.md section 5) and, when a built UI is present,
serves it as static files so ``python -m metagaap2`` is a single self-contained
local web app.

Responsibilities
----------------
* Environment / capability reporting (:func:`engines`) - which compute engines
  and external tools this machine has, plus platform and default-engine hints.
* A server-side file picker (:func:`browse`) so the desktop-style UI can pick
  reads / references without a native file dialog.
* Job lifecycle - create (:func:`create_job`), list (:func:`list_jobs`), fetch
  (:func:`get_job`) and cancel (:func:`cancel_job`) runs, delegating all
  background execution to :mod:`metagaap2.jobs`.
* Live progress over a WebSocket (:func:`job_events`) that re-broadcasts the
  :class:`~metagaap2.models.WSEvent` stream from the job manager.
* Result downloads (:func:`download`) restricted to files inside a job's own run
  directory (path-traversal is rejected).

Nothing here uses ``shell=True`` and no heavy bioinformatics libraries are
imported at module load, keeping start-up fast and cross-platform (Windows /
Linux / macOS).
"""

from __future__ import annotations

import asyncio
import platform
import string
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, tools
from .engines import default_engine_key, detect_all
from .jobs import manager
from .models import (
    EngineKey,
    Job,
    RunConfig,
    ServerInfo,
    WSEvent,
)

__all__ = ["app"]


# --------------------------------------------------------------------------- #
# Application object
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Bind the running event loop to the job manager at startup.

    The pipeline runs on worker threads and hands :class:`WSEvent` objects back
    to the server loop via ``loop.call_soon_threadsafe``. Capturing the loop
    here - inside the running server - guarantees those handoffs target a live
    loop, so WebSocket subscribers receive live progress (not just replayed
    history).
    """
    manager.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(
    title="MetaGaAP 2",
    version=__version__,
    summary="Cross-platform, Java-free quasispecies / meta-barcode pipeline.",
    lifespan=_lifespan,
)

# Permissive CORS for local development only. The app is meant to run on
# ``localhost``; we allow the usual loopback origins (any port) so a separately
# served Vite dev front-end can talk to this backend, without opening the API to
# arbitrary remote sites.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Health & capabilities
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe: ``{"status": "ok", "version": <package version>}``."""
    return {"status": "ok", "version": __version__}


@app.get("/api/engines", response_model=ServerInfo)
def engines() -> ServerInfo:
    """Report this machine's platform, engines and detected external tools.

    Drives the front-end's engine picker and tool status panel: it lists every
    engine's capabilities (:func:`metagaap2.engines.detect_all`), the best
    default engine for this machine (:func:`metagaap2.engines.default_engine_key`)
    and the discovered native binaries (:func:`metagaap2.tools.detect_tools`).
    """
    return ServerInfo(
        version=__version__,
        platform=platform.platform(),
        python=platform.python_version(),
        default_engine=default_engine_key(),
        engines=detect_all(),
        tools=tools.detect_tools(),
    )


# --------------------------------------------------------------------------- #
# Server-side file picker
# --------------------------------------------------------------------------- #
def _list_roots() -> dict[str, object]:
    """Return the filesystem roots as a listing with no parent.

    On Windows this enumerates the available drive letters (``C:\\`` ...); on
    POSIX systems there is a single root, ``/``.
    """
    entries: list[dict[str, object]] = []
    if platform.system() == "Windows":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            if drive.exists():
                entries.append(
                    {"name": f"{letter}:\\", "path": str(drive), "is_dir": True}
                )
    else:
        entries.append({"name": "/", "path": "/", "is_dir": True})
    return {"path": "", "parent": None, "entries": entries}


@app.get("/api/fs")
def browse(path: Optional[str] = None) -> dict[str, object]:
    """List a directory for the in-app file picker.

    With no ``path`` (or an empty one) the filesystem roots are returned
    (drive letters on Windows, ``/`` elsewhere). Otherwise the directory's
    immediate children are returned, directories first then files, each sorted
    case-insensitively. Entries that cannot be inspected (permission errors,
    broken links) are silently skipped so a single bad child never breaks the
    listing.

    Raises
    ------
    HTTPException
        404 when ``path`` does not exist; 400 when it is not a directory.
    """
    if not path:
        return _list_roots()

    target = Path(path)
    try:
        target = target.expanduser()
    except (RuntimeError, ValueError):
        pass

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    entries: list[dict[str, object]] = []
    try:
        children = list(target.iterdir())
    except (OSError, PermissionError) as exc:
        raise HTTPException(
            status_code=403, detail=f"Cannot read directory: {exc}"
        ) from exc

    for child in children:
        try:
            is_dir = child.is_dir()
        except OSError:
            # Unreadable entry (e.g. a broken symlink or denied path); skip it.
            continue
        entries.append({"name": child.name, "path": str(child), "is_dir": is_dir})

    # Directories first, then files, each alphabetical (case-insensitive).
    entries.sort(key=lambda e: (not e["is_dir"], str(e["name"]).lower()))

    parent = target.parent
    parent_str: Optional[str] = None if parent == target else str(parent)

    return {"path": str(target), "parent": parent_str, "entries": entries}


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #
@app.post("/api/jobs", response_model=Job)
def create_job(config: RunConfig) -> Job:
    """Create a job from a :class:`RunConfig` and start it in the background.

    Validation of ``config`` is handled by FastAPI / pydantic (a malformed body
    yields a 422 automatically). The created job is returned immediately in its
    ``queued``/``running`` state; progress streams over the WebSocket.
    """
    job = manager.create(config)
    manager.start(job)
    return job


@app.get("/api/jobs", response_model=list[Job])
def list_jobs() -> list[Job]:
    """Return every job known to the manager, newest activity first."""
    return manager.list()


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    """Return a single job by id, or 404 if it is unknown."""
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@app.post("/api/jobs/{job_id}/cancel", response_model=Job)
def cancel_job(job_id: str) -> Job:
    """Request cancellation of a running job and return its current snapshot.

    Cancellation is co-operative: the job manager flags the job and the
    orchestrator stops cleanly at the next stage boundary. Returns 404 for an
    unknown job.
    """
    job = manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


# --------------------------------------------------------------------------- #
# Result downloads (sandboxed to the job's run directory)
# --------------------------------------------------------------------------- #
@app.get("/api/jobs/{job_id}/download")
def download(job_id: str, path: str) -> FileResponse:
    """Stream a result file that lives inside the job's run directory.

    The requested ``path`` is resolved and checked to be contained within the
    job's ``run_dir`` so directory-traversal (``..``) and absolute paths
    pointing elsewhere are rejected with 403.

    Raises
    ------
    HTTPException
        404 when the job (or its run directory, or the file) is missing;
        403 when ``path`` escapes the run directory.
    """
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if not job.run_dir:
        raise HTTPException(
            status_code=404, detail="Job has no run directory yet."
        )

    run_dir = Path(job.run_dir).resolve()
    try:
        target = Path(path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid path: {exc}") from exc

    # Containment check: target must be the run dir itself or a descendant.
    if target != run_dir and run_dir not in target.parents:
        raise HTTPException(
            status_code=403, detail="Path is outside the job run directory."
        )
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    return FileResponse(path=str(target), filename=target.name)


# --------------------------------------------------------------------------- #
# Live progress over WebSocket
# --------------------------------------------------------------------------- #
@app.websocket("/ws/jobs/{job_id}")
async def job_events(websocket: WebSocket, job_id: str) -> None:
    """Stream a job's :class:`WSEvent` envelopes to a connected client.

    Accepts the socket, then forwards every event yielded by
    ``manager.subscribe(job_id)`` as JSON. The stream ends (and the socket is
    closed) when a terminal ``done`` event is seen, when the subscription
    iterator is exhausted, or when the client disconnects. Unknown job ids are
    refused with a WebSocket close before any data is sent.
    """
    await websocket.accept()

    if manager.get(job_id) is None:
        # 1008 = policy violation; tells the client this id is not valid.
        await websocket.close(code=1008, reason="Job not found")
        return

    try:
        async for event in manager.subscribe(job_id):
            payload = _event_payload(event)
            await websocket.send_json(payload)
            if _is_terminal(event):
                break
    except WebSocketDisconnect:
        # Client went away mid-stream; nothing to clean up here.
        return
    except Exception:  # noqa: BLE001 - never let a stream error crash the worker.
        # Best-effort: try to close cleanly; ignore if already gone.
        pass

    try:
        await websocket.close()
    except RuntimeError:
        # Socket already closed (e.g. client disconnected).
        pass


def _event_payload(event: WSEvent) -> dict[str, object]:
    """Serialise a :class:`WSEvent` to a JSON-ready dict for the socket."""
    return event.model_dump(mode="json")


def _is_terminal(event: WSEvent) -> bool:
    """True when ``event`` marks the end of a job's stream (a ``done`` event)."""
    return event.type.value == "done"


# --------------------------------------------------------------------------- #
# Built front-end (served when present)
# --------------------------------------------------------------------------- #
# When a production build of the React UI has been copied into
# ``metagaap2/webui`` it is mounted at the site root so the single command
# ``python -m metagaap2`` serves both the API and the UI. ``html=True`` makes the
# mount fall back to ``index.html`` for client-side routes. The mount is added
# last so it never shadows the ``/api`` and ``/ws`` routes above.
_WEBUI_DIR = Path(__file__).resolve().parent / "webui"
if _WEBUI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEBUI_DIR), html=True), name="webui")
