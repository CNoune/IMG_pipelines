"""Tests for :mod:`metagaap2.runner` - safe, shell-free command execution.

Covers:
  * :func:`run` redirecting stdout to a file (the safe ``> file`` equivalent),
  * :func:`run` raising :class:`CommandError` on a non-zero exit,
  * :func:`run` capturing stdout in-memory when no ``stdout_path`` is given,
  * :func:`run` honouring ``check=False`` (no raise on failure),
  * :func:`which` locating a real executable on PATH,
  * :func:`require` raising :class:`ToolNotFound` for a missing tool.

Every external command is the current Python interpreter (``sys.executable``)
so the tests are fully cross-platform and need no bioinformatics tooling.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from metagaap2.runner import (
    CommandError,
    ToolNotFound,
    require,
    run,
    which,
)


# --------------------------------------------------------------------------- #
# run() - stdout redirection to a file
# --------------------------------------------------------------------------- #
def test_run_captures_stdout_to_file(tmp_path: Path) -> None:
    """``stdout_path`` redirects a command's stdout to a file on disk."""
    out = tmp_path / "out.txt"
    proc = run(
        [sys.executable, "-c", "print('hi')"],
        stdout_path=out,
    )
    assert proc.returncode == 0
    assert out.exists()
    # print() adds a trailing newline; tolerate platform line endings.
    assert out.read_text().strip() == "hi"


def test_run_creates_parent_dir_for_stdout(tmp_path: Path) -> None:
    """A missing parent directory for ``stdout_path`` is created automatically."""
    out = tmp_path / "nested" / "deeper" / "out.txt"
    run([sys.executable, "-c", "print('nested')"], stdout_path=out)
    assert out.read_text().strip() == "nested"


def test_run_append_mode(tmp_path: Path) -> None:
    """``append=True`` adds to an existing file rather than truncating it."""
    out = tmp_path / "log.txt"
    run([sys.executable, "-c", "print('first')"], stdout_path=out)
    run([sys.executable, "-c", "print('second')"], stdout_path=out, append=True)
    contents = out.read_text().splitlines()
    assert contents == ["first", "second"]


# --------------------------------------------------------------------------- #
# run() - in-memory capture (no stdout_path)
# --------------------------------------------------------------------------- #
def test_run_captures_stdout_in_memory() -> None:
    """Without ``stdout_path`` stdout is captured as text on the result."""
    proc = run([sys.executable, "-c", "print('captured')"])
    assert proc.returncode == 0
    assert proc.stdout is not None
    assert "captured" in proc.stdout


# --------------------------------------------------------------------------- #
# run() - non-zero exit handling
# --------------------------------------------------------------------------- #
def test_run_raises_command_error_on_nonzero_exit() -> None:
    """A non-zero exit raises :class:`CommandError` carrying the return code."""
    with pytest.raises(CommandError) as excinfo:
        run([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert excinfo.value.returncode == 3
    assert excinfo.value.cmd[0] == sys.executable


def test_run_check_false_does_not_raise() -> None:
    """``check=False`` suppresses the exception and returns the failed process."""
    proc = run([sys.executable, "-c", "import sys; sys.exit(3)"], check=False)
    assert proc.returncode == 3


def test_command_error_includes_stderr_tail() -> None:
    """The stderr tail is surfaced on the raised :class:`CommandError`."""
    with pytest.raises(CommandError) as excinfo:
        run(
            [
                sys.executable,
                "-c",
                "import sys; sys.stderr.write('boom\\n'); sys.exit(1)",
            ]
        )
    assert "boom" in excinfo.value.stderr_tail


# --------------------------------------------------------------------------- #
# which() / require()
# --------------------------------------------------------------------------- #
def test_which_finds_executable() -> None:
    """``which`` locates the running Python interpreter by its base name."""
    name = Path(sys.executable).name
    found = which(name)
    assert found is not None
    assert Path(found).name == name


def test_which_returns_none_for_missing_tool() -> None:
    """``which`` returns ``None`` for a tool that does not exist on PATH."""
    assert which("definitely-not-a-real-tool-xyz-123") is None


def test_require_returns_path_for_existing_tool() -> None:
    """``require`` returns the resolved path for a tool that exists."""
    name = Path(sys.executable).name
    assert Path(require(name)).name == name


def test_require_raises_tool_not_found_for_missing() -> None:
    """``require`` raises :class:`ToolNotFound` when a tool is absent."""
    with pytest.raises(ToolNotFound):
        require("definitely-not-a-real-tool-xyz-123")
