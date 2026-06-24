"""Data contract for MetaGaAP 2.

Pydantic v2 models and enums shared across the pipeline engine and the HTTP
API. This module is the authoritative Python-side schema; ``frontend/src/types.ts``
mirrors it for the UI. Keep the two in sync.

Nothing here imports heavy bioinformatics libraries, so it is safe to import
from anywhere (server, tests, engines).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class EngineKey(str, Enum):
    """Which compute engine runs the per-sample stages."""

    PORTABLE = "portable"  # pure-Python, pip-only, all platforms incl. Windows
    NATIVE = "native"  # external binaries (minimap2/samtools/bcftools/...)


class Aligner(str, Enum):
    BUILTIN = "builtin"  # portable: k-mer index + parasail
    MINIMAP2 = "minimap2"  # native
    BWA_MEM2 = "bwa_mem2"  # native


class VariantCaller(str, Enum):
    BUILTIN = "builtin"  # portable: frequency pileup caller
    BCFTOOLS = "bcftools"  # native
    LOFREQ = "lofreq"  # native, low-frequency / quasispecies


class ReferenceMode(str, Enum):
    SINGLE = "single"  # one shared reference -> merged database across samples
    MULTIPLE = "multiple"  # per-sample reference -> independent databases


class StageName(str, Enum):
    TRIM = "trim"
    ALIGN_CALL = "align_call"  # map to reference + call variants
    HAPLOTYPES = "haplotypes"  # build combinatorial database
    CONFIRM = "confirm"  # map reads back + count + extract confirmed seqs
    MERGE = "merge"  # multi-sample single-reference merge + re-map


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
class ReadGroup(BaseModel):
    """Read-group metadata (replaces the picard AddOrReplaceReadGroups step)."""

    sample: str = Field(..., description="RGSM - sample name")
    library: str = Field("lib1", description="RGLB - library name")
    platform: str = Field("ILLUMINA", description="RGPL - e.g. ILLUMINA, IONTORRENT")
    unit: str = Field("unit1", description="RGPU - sequencing unit")
    id: Optional[str] = Field(None, description="RGID - defaults to sample.unit")

    def rg_id(self) -> str:
        return self.id or f"{self.sample}.{self.unit}"


class Sample(BaseModel):
    """A single sample to process."""

    name: str = Field(..., description="Unique sample identifier")
    r1: str = Field(..., description="Path to forward / single-end FASTQ")
    r2: Optional[str] = Field(None, description="Path to reverse FASTQ (paired-end)")
    reference: Optional[str] = Field(
        None,
        description="Per-sample reference FASTA. Required when reference_mode=multiple; "
        "for single mode the run-level reference is used.",
    )
    read_group: Optional[ReadGroup] = None

    @property
    def paired(self) -> bool:
        return bool(self.r2)


class QCParams(BaseModel):
    """Quality-control / trimming parameters (cutadapt or fastp)."""

    enabled: bool = True
    min_quality: int = Field(20, ge=0, le=60, description="Quality trim threshold (Q)")
    min_length: int = Field(30, ge=1, description="Discard reads shorter than this after trimming")
    trim_front: int = Field(0, ge=0, description="Fixed bases to cut from the 5' end")
    trim_tail: int = Field(0, ge=0, description="Fixed bases to cut from the 3' end")
    adapter_fwd: Optional[str] = Field(None, description="Optional 3' adapter for R1")
    adapter_rev: Optional[str] = Field(None, description="Optional 3' adapter for R2")
    detect_adapters: bool = Field(True, description="Auto-detect adapters where supported")


class VariantParams(BaseModel):
    caller: VariantCaller = VariantCaller.BUILTIN
    min_base_quality: int = Field(20, ge=0, le=60)
    min_mapping_quality: int = Field(20, ge=0, le=60)
    min_depth: int = Field(10, ge=1, description="Minimum site depth to consider a variant")
    min_alt_fraction: float = Field(
        0.02, ge=0.0, le=1.0, description="Minimum ALT allele fraction (quasispecies-sensitive)"
    )
    ploidy: int = Field(2, ge=1, description="Ploidy for bcftools call (ignored by freq caller)")


class HaplotypeParams(BaseModel):
    """Combinatorial haplotype database parameters (biostar175929 replacement)."""

    window: Optional[int] = Field(
        None,
        ge=1,
        description="Sliding-window size in bp. If null, defaults to the modal read length.",
    )
    max_haplotypes_per_window: int = Field(
        1024, ge=1, description="Safety cap on combinations emitted per window"
    )
    max_variants_per_window: int = Field(
        12, ge=1, description="Skip windows with more variant sites than this (combinatorial blow-up guard)"
    )
    step: Optional[int] = Field(
        None, ge=1, description="Window step in bp. If null, defaults to window (non-overlapping)."
    )


class ConfirmParams(BaseModel):
    min_mapped_reads: int = Field(
        2, ge=1, description="Keep haplotypes recruiting at least this many reads (original used >1)"
    )
    min_identity: float = Field(
        0.90, ge=0.0, le=1.0, description="Minimum read-to-haplotype identity for portable assignment"
    )


class RunConfig(BaseModel):
    """Everything required to execute a run. Posted to /api/jobs."""

    run_name: str = Field(..., description="Run label; names the output directory")
    work_dir: str = Field(..., description="Parent directory for run outputs")
    engine: EngineKey = EngineKey.PORTABLE
    aligner: Aligner = Aligner.BUILTIN
    threads: int = Field(4, ge=1)
    reference_mode: ReferenceMode = ReferenceMode.SINGLE
    reference: Optional[str] = Field(
        None, description="Shared reference FASTA (required when reference_mode=single)"
    )
    merge_single_reference: bool = Field(
        True, description="In single-reference multi-sample runs, merge per-sample databases"
    )
    samples: list[Sample] = Field(..., min_length=1)
    qc: QCParams = Field(default_factory=QCParams)
    variants: VariantParams = Field(default_factory=VariantParams)
    haplotypes: HaplotypeParams = Field(default_factory=HaplotypeParams)
    confirm: ConfirmParams = Field(default_factory=ConfirmParams)


# --------------------------------------------------------------------------- #
# Outputs / status
# --------------------------------------------------------------------------- #
class StageResult(BaseModel):
    name: StageName
    status: StageStatus = StageStatus.PENDING
    started_at: Optional[str] = None  # ISO 8601
    ended_at: Optional[str] = None
    message: Optional[str] = None
    log_path: Optional[str] = None
    outputs: dict[str, str] = Field(default_factory=dict)  # label -> path


class SampleResult(BaseModel):
    sample: str
    stages: list[StageResult] = Field(default_factory=list)
    confirmed_fasta: Optional[str] = None
    stats_csv: Optional[str] = None
    counts_csv: Optional[str] = None
    n_confirmed: int = 0
    n_haplotypes: int = 0


class Job(BaseModel):
    id: str
    config: RunConfig
    state: JobState = JobState.QUEUED
    progress: float = Field(0.0, ge=0.0, le=1.0)
    current_stage: Optional[StageName] = None
    samples: list[SampleResult] = Field(default_factory=list)
    run_dir: Optional[str] = None
    created_at: str  # ISO 8601
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Capability / environment reporting
# --------------------------------------------------------------------------- #
class ToolInfo(BaseModel):
    name: str
    found: bool
    path: Optional[str] = None
    version: Optional[str] = None


class EngineCapabilities(BaseModel):
    key: EngineKey
    label: str
    available: bool
    aligners: list[Aligner] = Field(default_factory=list)
    callers: list[VariantCaller] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list, description="Missing tools (native engine)")
    note: Optional[str] = None


class ServerInfo(BaseModel):
    version: str
    platform: str  # e.g. "Windows-11", "Linux", "Darwin"
    python: str
    default_engine: EngineKey
    engines: list[EngineCapabilities] = Field(default_factory=list)
    tools: list[ToolInfo] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# WebSocket event envelope
# --------------------------------------------------------------------------- #
class WSEventType(str, Enum):
    STATE = "state"  # job state / progress changed
    STAGE = "stage"  # a stage updated
    LOG = "log"  # a log line
    DONE = "done"  # terminal


class WSEvent(BaseModel):
    type: WSEventType
    job_id: str
    state: Optional[JobState] = None
    progress: Optional[float] = None
    sample: Optional[str] = None
    stage: Optional[StageResult] = None
    line: Optional[str] = None
