"""External-tool detection for the native engine.

The native engine (:mod:`metagaap2.engines.native`) shells out to bioinformatics
binaries that are *not* available as pip wheels on Windows (minimap2, bwa-mem2,
samtools, bcftools, lofreq, fastp). This module discovers which of those tools
are installed on the current machine and reports their version strings.

It is the single source of truth for tool discovery used both by the native
engine (to decide whether it can run) and by the ``GET /api/engines`` endpoint
(to populate :class:`~metagaap2.models.ServerInfo.tools`).

Discovery is deliberately cheap and side-effect-free: each logical tool maps to
an ordered tuple of candidate executable names, and the first one found on PATH
(via :func:`metagaap2.runner.which`) wins. Version probing is best-effort and
never raises.

Nothing here uses ``shell=True``; all probing goes through :mod:`metagaap2.runner`.
"""

from __future__ import annotations

from collections.abc import Iterable

from . import runner
from .models import ToolInfo

__all__ = ["TOOLS", "detect_tool", "detect_tools", "have"]


# --------------------------------------------------------------------------- #
# Tool catalogue
# --------------------------------------------------------------------------- #
# Logical name -> ordered candidate executable names. The first candidate that
# resolves on PATH is used. Ordering encodes preference: where a tool ships
# under several names across platforms / package managers, the most common /
# preferred binary name comes first.
TOOLS: dict[str, tuple[str, ...]] = {
    "minimap2": ("minimap2",),
    # bwa-mem2 is the modern, faster successor to classic bwa; fall back to the
    # legacy "bwa" binary when bwa-mem2 is not present.
    "bwa-mem2": ("bwa-mem2", "bwa-mem2.avx2", "bwa-mem2.sse42", "bwa"),
    "bwa": ("bwa",),
    "samtools": ("samtools",),
    "bcftools": ("bcftools",),
    "lofreq": ("lofreq",),
    "fastp": ("fastp",),
}


# --------------------------------------------------------------------------- #
# Per-tool version-probe flags
# --------------------------------------------------------------------------- #
# Most tools answer to ``--version``; a few htslib-family tools print their
# version banner on ``--version`` too, but samtools/bcftools historically also
# accept it, so the runner's default fallbacks cover the rest. lofreq uses the
# "version" subcommand.
_VERSION_ARGS: dict[str, tuple[str, ...]] = {
    "minimap2": ("--version",),
    "bwa-mem2": ("version",),
    "bwa": ("version",),
    "samtools": ("--version",),
    "bcftools": ("--version",),
    "lofreq": ("version",),
    "fastp": ("--version",),
}


def _candidates(name: str) -> tuple[str, ...]:
    """Return the candidate executable names for a logical tool name.

    Unknown names are treated as their own single candidate so callers can probe
    arbitrary binaries without first registering them in :data:`TOOLS`.
    """
    return TOOLS.get(name, (name,))


def detect_tool(name: str) -> ToolInfo:
    """Detect a single logical tool and return a :class:`ToolInfo`.

    The first candidate executable for ``name`` that resolves on PATH wins. When
    none are found, a ``found=False`` record is returned (never raises). Version
    detection is best-effort and silently degrades to ``None``.
    """
    for candidate in _candidates(name):
        path = runner.which(candidate)
        if path is None:
            continue
        version_args = _VERSION_ARGS.get(name, _VERSION_ARGS.get(candidate, ("--version",)))
        version = runner.tool_version(candidate, version_args)
        # ``tool_version`` falls back to returning the path when no version
        # banner could be parsed; treat a bare path as "no version available".
        if version == path:
            version = None
        return ToolInfo(name=name, found=True, path=path, version=version)
    return ToolInfo(name=name, found=False, path=None, version=None)


def detect_tools(names: Iterable[str] | None = None) -> list[ToolInfo]:
    """Detect several tools at once.

    Parameters
    ----------
    names:
        Logical tool names to probe. When ``None`` (the default), every tool in
        :data:`TOOLS` is detected, preserving insertion order.
    """
    if names is None:
        names = TOOLS.keys()
    return [detect_tool(name) for name in names]


def have(name: str) -> bool:
    """Return ``True`` if any candidate executable for ``name`` is on PATH."""
    return any(runner.which(candidate) is not None for candidate in _candidates(name))
