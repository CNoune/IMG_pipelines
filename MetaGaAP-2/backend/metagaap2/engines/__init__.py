"""Engine registry and discovery for MetaGaAP 2.

This package exposes the platform-sensitive compute engines and a small set of
helpers used by the server and pipeline to select one:

* :data:`ENGINES`             - registry mapping :class:`~metagaap2.models.EngineKey`
  to the concrete :class:`~metagaap2.engines.base.Engine` subclass.
* :func:`get_engine`          - construct an engine instance for a given key.
* :func:`detect_all`          - probe every engine's availability on this machine.
* :func:`default_engine_key`  - pick the best default for this machine (the
  native engine when its binaries are present, otherwise the always-available
  portable engine).

The two implementations are
:class:`~metagaap2.engines.portable.PortableEngine` (pure-Python, pip-only, runs
everywhere including native Windows) and
:class:`~metagaap2.engines.native.NativeEngine` (external bioinformatics
binaries, auto-detected). The :class:`~metagaap2.engines.base.Engine` ABC and the
stage result dataclasses (:class:`~metagaap2.engines.base.TrimResult`,
:class:`~metagaap2.engines.base.CallResult`,
:class:`~metagaap2.engines.base.CountResult`) are re-exported here for
convenience.
"""

from __future__ import annotations

from typing import Optional

from ..models import Aligner, EngineCapabilities, EngineKey
from .base import (
    CallResult,
    CountResult,
    Engine,
    LogSink,
    TrimResult,
)
from .native import NativeEngine
from .portable import PortableEngine

__all__ = [
    "Engine",
    "LogSink",
    "TrimResult",
    "CallResult",
    "CountResult",
    "PortableEngine",
    "NativeEngine",
    "ENGINES",
    "get_engine",
    "detect_all",
    "default_engine_key",
]


#: Registry of engine implementations keyed by :class:`EngineKey`.
ENGINES: dict[EngineKey, type[Engine]] = {
    EngineKey.PORTABLE: PortableEngine,
    EngineKey.NATIVE: NativeEngine,
}


def get_engine(
    key: EngineKey,
    *,
    aligner: Optional[Aligner] = None,
    threads: int = 4,
) -> Engine:
    """Construct an :class:`Engine` instance for ``key``.

    Parameters
    ----------
    key:
        Which engine to build (:attr:`EngineKey.PORTABLE` or
        :attr:`EngineKey.NATIVE`).
    aligner:
        Aligner the engine should use. ``None`` lets the engine pick its own
        default (the portable engine ignores this; the native engine defaults to
        minimap2).
    threads:
        Thread count passed to engines that support multi-threading.

    Returns
    -------
    Engine
        A freshly constructed engine instance.

    Raises
    ------
    KeyError
        If ``key`` is not a registered engine.
    """
    try:
        engine_cls = ENGINES[key]
    except KeyError as exc:
        valid = ", ".join(repr(k.value) for k in ENGINES)
        raise KeyError(
            f"Unknown engine key {key!r}; valid keys are: {valid}."
        ) from exc
    return engine_cls(aligner=aligner, threads=threads)


def detect_all() -> list[EngineCapabilities]:
    """Probe every registered engine and report its capabilities on this machine.

    Calls each engine class's :meth:`Engine.detect` classmethod. The result is
    ordered to match the :data:`ENGINES` registry insertion order (portable
    first, native second).
    """
    return [engine_cls.detect() for engine_cls in ENGINES.values()]


def default_engine_key() -> EngineKey:
    """Return the best default engine key for this machine.

    Prefers :attr:`EngineKey.NATIVE` when its required binaries are detected;
    otherwise falls back to the always-available :attr:`EngineKey.PORTABLE`
    engine.
    """
    if NativeEngine.detect().available:
        return EngineKey.NATIVE
    return EngineKey.PORTABLE
