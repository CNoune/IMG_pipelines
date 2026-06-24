"""Engine abstraction for MetaGaAP 2.

An *engine* provides the platform-specific compute stages. Two implementations
exist: :class:`~metagaap2.engines.portable.PortableEngine` (pure Python, runs
everywhere incl. native Windows) and
:class:`~metagaap2.engines.native.NativeEngine` (external binaries).

Stages that are engine-independent (combinatorial haplotype generation,
de-duplication, confirmed-sequence extraction, merging) live outside the engine
in :mod:`metagaap2.haplotypes`, :mod:`metagaap2.dedup` and
:mod:`metagaap2.pipeline`.

The engine therefore exposes only the three platform-sensitive operations:

* :meth:`Engine.trim`            - QC/adapter/quality trimming
* :meth:`Engine.align_and_call`  - map reads to a reference + call variants -> VCF
* :meth:`Engine.map_and_count`   - map reads to a FASTA + count reads per sequence

All paths are :class:`pathlib.Path`. ``log`` is an optional callable taking a
single string (a log line) so callers can stream progress.
"""

from __future__ import annotations

import abc
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models import (
    Aligner,
    ConfirmParams,
    EngineCapabilities,
    EngineKey,
    QCParams,
    ReadGroup,
    VariantCaller,
    VariantParams,
)

LogSink = Callable[[str], None]


# --------------------------------------------------------------------------- #
# Stage result objects (returned by engine methods)
# --------------------------------------------------------------------------- #
@dataclass
class TrimResult:
    r1: Path
    r2: Optional[Path] = None
    report: Optional[Path] = None
    n_reads_in: Optional[int] = None
    n_reads_out: Optional[int] = None


@dataclass
class CallResult:
    vcf: Path
    modal_read_length: int  # used to default the haplotype window size
    n_variants: int = 0
    bam: Optional[Path] = None  # native engine only


@dataclass
class CountResult:
    """Per-sequence read recruitment against a FASTA (the confirm step)."""

    counts: dict[str, int] = field(default_factory=dict)  # sequence id -> mapped reads
    stats_csv: Optional[Path] = None
    bam: Optional[Path] = None  # native engine only


# --------------------------------------------------------------------------- #
# Engine interface
# --------------------------------------------------------------------------- #
class Engine(abc.ABC):
    """Abstract compute engine. Subclasses must be cheap to construct."""

    key: EngineKey
    label: str
    supported_aligners: tuple[Aligner, ...] = ()
    supported_callers: tuple[VariantCaller, ...] = ()

    def __init__(self, *, aligner: Optional[Aligner] = None, threads: int = 4) -> None:
        self.aligner = aligner
        self.threads = threads

    # -- capability reporting ------------------------------------------------ #
    @classmethod
    @abc.abstractmethod
    def detect(cls) -> EngineCapabilities:
        """Return availability + supported aligners/callers for this machine."""

    # -- stages -------------------------------------------------------------- #
    @abc.abstractmethod
    def trim(
        self,
        *,
        r1: Path,
        r2: Optional[Path],
        params: QCParams,
        out_dir: Path,
        sample: str,
        log: Optional[LogSink] = None,
    ) -> TrimResult:
        """Quality/adapter trim. If ``params.enabled`` is False, return inputs verbatim."""

    @abc.abstractmethod
    def align_and_call(
        self,
        *,
        r1: Path,
        r2: Optional[Path],
        reference: Path,
        read_group: ReadGroup,
        params: VariantParams,
        out_dir: Path,
        sample: str,
        log: Optional[LogSink] = None,
    ) -> CallResult:
        """Map reads to ``reference`` and call variants, writing a VCF."""

    @abc.abstractmethod
    def map_and_count(
        self,
        *,
        r1: Path,
        r2: Optional[Path],
        target_fasta: Path,
        params: ConfirmParams,
        out_dir: Path,
        sample: str,
        log: Optional[LogSink] = None,
    ) -> CountResult:
        """Map reads to ``target_fasta`` and return reads recruited per sequence."""

    # -- helpers ------------------------------------------------------------- #
    def validate(self, *, aligner: Aligner, caller: VariantCaller) -> None:
        """Raise ValueError if this engine cannot honour the requested options."""
        if self.supported_aligners and aligner not in self.supported_aligners:
            raise ValueError(
                f"Engine {self.key.value!r} does not support aligner {aligner.value!r}; "
                f"supported: {[a.value for a in self.supported_aligners]}"
            )
        if self.supported_callers and caller not in self.supported_callers:
            raise ValueError(
                f"Engine {self.key.value!r} does not support caller {caller.value!r}; "
                f"supported: {[c.value for c in self.supported_callers]}"
            )
