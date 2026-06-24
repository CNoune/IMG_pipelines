"""Safe, cross-platform external-command execution.

Replaces the original pipeline's ``subprocess.Popen([cmd], shell=True)`` calls
(which were shell-injection prone and broke on paths with spaces) with list-arg
execution, explicit return-code checking, optional output redirection to a file,
and shell-free pipelines.

Nothing here uses ``shell=True``.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Optional, Union

LogSink = Callable[[str], None]
StrPath = Union[str, Path]


class ToolNotFound(RuntimeError):
    """Raised when a required executable is not on PATH."""


class CommandError(RuntimeError):
    """Raised when a command exits non-zero."""

    def __init__(self, args: Sequence[str], returncode: int, stderr_tail: str):
        self.cmd = list(args)
        self.returncode = returncode
        self.stderr_tail = stderr_tail
        pretty = " ".join(str(a) for a in args)
        super().__init__(
            f"Command failed (exit {returncode}): {pretty}\n--- stderr tail ---\n{stderr_tail}"
        )


def which(name: str) -> Optional[str]:
    """Locate an executable on PATH, returning its absolute path or None."""
    return shutil.which(name)


def require(name: str) -> str:
    """Return the path to ``name`` or raise :class:`ToolNotFound`."""
    path = which(name)
    if path is None:
        raise ToolNotFound(f"Required tool not found on PATH: {name!r}")
    return path


def _as_str_args(args: Sequence[StrPath]) -> list[str]:
    return [str(a) for a in args]


def _tail(text: str, n: int = 40) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def run(
    args: Sequence[StrPath],
    *,
    cwd: Optional[StrPath] = None,
    stdout_path: Optional[StrPath] = None,
    stdin_path: Optional[StrPath] = None,
    append: bool = False,
    env: Optional[dict[str, str]] = None,
    log: Optional[LogSink] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a single command without a shell.

    Parameters
    ----------
    args:
        Command and arguments as a list. Path objects are stringified.
    stdout_path:
        If given, stdout is redirected to this file (the safe equivalent of
        ``> file``). Otherwise stdout is captured and returned.
    stdin_path:
        If given, the file is fed to stdin (the safe equivalent of ``< file``).
    append:
        Open ``stdout_path`` in append mode.
    log:
        Optional callback receiving each captured stderr line (live logging).
    check:
        Raise :class:`CommandError` on non-zero exit (default True).
    """
    str_args = _as_str_args(args)
    logger = logging.getLogger("metagaap2.runner")
    logger.debug("run: %s", " ".join(str_args))
    if log:
        log("$ " + " ".join(str_args))

    stdout_f = None
    stdin_f = None
    try:
        if stdout_path is not None:
            Path(stdout_path).parent.mkdir(parents=True, exist_ok=True)
            stdout_f = open(stdout_path, "ab" if append else "wb")
        if stdin_path is not None:
            stdin_f = open(stdin_path, "rb")

        proc = subprocess.run(
            str_args,
            cwd=str(cwd) if cwd else None,
            stdout=stdout_f if stdout_f else subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin_f if stdin_f else None,
            env=env,
            text=True if stdout_f is None else False,
        )
    finally:
        if stdout_f:
            stdout_f.close()
        if stdin_f:
            stdin_f.close()

    stderr = proc.stderr if isinstance(proc.stderr, str) else (proc.stderr or b"").decode(errors="replace")
    if stderr and log:
        for line in stderr.splitlines():
            log(line)

    if check and proc.returncode != 0:
        raise CommandError(str_args, proc.returncode, _tail(stderr))
    return proc


def run_pipe(
    stages: Sequence[Sequence[StrPath]],
    *,
    cwd: Optional[StrPath] = None,
    stdout_path: Optional[StrPath] = None,
    env: Optional[dict[str, str]] = None,
    log: Optional[LogSink] = None,
    check: bool = True,
) -> int:
    """Run a shell-free pipeline: ``stages[0] | stages[1] | ... > stdout_path``.

    Each stage is a list-arg command. Implements the pipe in Python so no shell
    is involved (e.g. ``minimap2 ... | samtools sort -o out.bam``).
    """
    str_stages = [_as_str_args(s) for s in stages]
    logger = logging.getLogger("metagaap2.runner")
    pretty = " | ".join(" ".join(s) for s in str_stages)
    logger.debug("pipe: %s", pretty)
    if log:
        log("$ " + pretty)

    procs: list[subprocess.Popen] = []
    final_out = None
    # Per-stage stderr captured concurrently. Verbose tools (minimap2, bwa-mem2,
    # samtools, bcftools) can emit far more than the OS pipe buffer (~64 KB) to
    # stderr; if we wait() before draining, the writer blocks on a full pipe and
    # we deadlock. So a reader thread per process drains stderr in parallel with
    # the wait below.
    stderr_bufs: dict[int, bytes] = {}
    threads: list[threading.Thread] = []

    def _drain(idx: int, stream) -> None:
        try:
            stderr_bufs[idx] = stream.read() if stream else b""
        except (OSError, ValueError):
            stderr_bufs[idx] = b""

    try:
        if stdout_path is not None:
            Path(stdout_path).parent.mkdir(parents=True, exist_ok=True)
            final_out = open(stdout_path, "wb")

        prev_stdout = None
        for i, stage in enumerate(str_stages):
            is_last = i == len(str_stages) - 1
            proc = subprocess.Popen(
                stage,
                cwd=str(cwd) if cwd else None,
                stdin=prev_stdout,
                stdout=(final_out if (is_last and final_out) else subprocess.PIPE),
                stderr=subprocess.PIPE,
                env=env,
            )
            if prev_stdout is not None:
                prev_stdout.close()  # allow upstream to receive SIGPIPE
            prev_stdout = proc.stdout
            procs.append(proc)

        # Start draining every stage's stderr before we wait on anything.
        for idx, proc in enumerate(procs):
            thread = threading.Thread(target=_drain, args=(idx, proc.stderr), daemon=True)
            thread.start()
            threads.append(thread)

        # Drain the last stage's stdout if it wasn't redirected to a file, so the
        # final process never blocks writing to a full pipe either.
        last = procs[-1]
        if final_out is None and last.stdout is not None:
            last.stdout.read()

        returncodes = [p.wait() for p in procs]
        for thread in threads:
            thread.join()
    finally:
        if final_out:
            final_out.close()

    # Surface stderr from every stage (drained above).
    for idx, stage in enumerate(str_stages):
        err = stderr_bufs.get(idx, b"").decode(errors="replace")
        if err and log:
            for line in err.splitlines():
                log(line)

    failed = [(rc, idx) for idx, rc in enumerate(returncodes) if rc != 0]
    if check and failed:
        rc, idx = failed[0]
        tail = _tail(stderr_bufs.get(idx, b"").decode(errors="replace"))
        raise CommandError(str_stages[idx], rc, tail)
    return returncodes[-1]


def tool_version(name: str, version_args: Sequence[str] = ("--version",)) -> Optional[str]:
    """Best-effort single-line version string for a tool, or None if unavailable."""
    path = which(name)
    if path is None:
        return None
    for flag in (list(version_args), ["--version"], ["-v"], ["version"]):
        try:
            proc = subprocess.run(
                [path, *flag], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15
            )
            out = (proc.stdout or "").strip()
            if out:
                return out.splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError):
            continue
    return path
