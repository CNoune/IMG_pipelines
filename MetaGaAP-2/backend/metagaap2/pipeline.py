"""Engine-independent run orchestrator for MetaGaAP 2.

This module drives a whole run from a :class:`~metagaap2.models.Job`: it creates
the run directory (SPEC.md section 7), resolves the requested compute engine, and
walks every sample through the four per-sample stages

* :attr:`~metagaap2.models.StageName.TRIM`        - QC / adapter trimming,
* :attr:`~metagaap2.models.StageName.ALIGN_CALL`  - map to the reference + call
  variants -> VCF (and report the modal read length),
* :attr:`~metagaap2.models.StageName.HAPLOTYPES`  - build the combinatorial
  haplotype database (the ``biostar175929.jar`` replacement), and
* :attr:`~metagaap2.models.StageName.CONFIRM`     - re-map reads to the
  haplotype database, keep the haplotypes that recruit enough reads, and extract
  the confirmed sequences,

followed by the optional, run-level
:attr:`~metagaap2.models.StageName.MERGE` stage that (for a single shared
reference across multiple samples) de-duplicates the per-sample databases into a
merged database and re-confirms every sample against it.

Everything here is pure Python and platform agnostic; the platform-sensitive
work (trim / align+call / map+count) is delegated to the chosen
:class:`~metagaap2.engines.base.Engine`. Combinatorial haplotype generation,
de-duplication and confirmed-sequence extraction are engine independent and live
in :mod:`metagaap2.haplotypes`, :mod:`metagaap2.dedup` and :mod:`metagaap2.seqio`.

The single public entry point is :func:`execute_job`. It mutates the supplied
``Job`` in place (state, progress, current stage, per-sample stage results, run
directory, error and timestamps) and reports every change through an ``emit``
callback as :class:`~metagaap2.models.WSEvent` envelopes. It never raises: any
failure is captured onto the job (state ``FAILED``, ``job.error`` set, the active
stage marked ``FAILED``) and reported via ``emit`` before returning. This is the
contract :mod:`metagaap2.jobs` relies on to run jobs on a background thread.
"""

from __future__ import annotations

import csv
import json
import platform
import shutil
import sys
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import __version__
from .dedup import dedup_fasta
from .engines import get_engine
from .engines.base import Engine
from .haplotypes import build_haplotype_database
from .models import (
    Job,
    JobState,
    ReadGroup,
    ReferenceMode,
    RunConfig,
    Sample,
    SampleResult,
    StageName,
    StageResult,
    StageStatus,
    WSEvent,
    WSEventType,
)
from .seqio import extract_records

__all__ = ["EmitFn", "execute_job"]

#: Callback used to report job/stage/log/progress changes (see :mod:`metagaap2.jobs`).
EmitFn = Callable[[WSEvent], None]

#: A function the orchestrator polls between stages to honour cancellation.
CancelFn = Callable[[], bool]

#: Per-sample stages run for every sample, in execution order.
_PER_SAMPLE_STAGES: tuple[StageName, ...] = (
    StageName.TRIM,
    StageName.ALIGN_CALL,
    StageName.HAPLOTYPES,
    StageName.CONFIRM,
)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 form (seconds precision, ``Z`` suffix)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_run_dir(config: RunConfig) -> Path:
    """Create ``<work_dir>/<run_name>/`` plus its standard subdirectories.

    Returns the run directory. Sub-directories (``logs``, ``trimmed``,
    ``alignments``, ``variants``, ``haplotypes``, ``results``) mirror SPEC.md
    section 7 and are created up front so every stage can assume they exist.
    """
    run_dir = Path(config.work_dir) / config.run_name
    for sub in ("", "logs", "trimmed", "alignments", "variants", "haplotypes", "results"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_run_config(run_dir: Path, config: RunConfig) -> None:
    """Persist the exact :class:`RunConfig` used as ``run_config.json``."""
    target = run_dir / "run_config.json"
    target.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_manifest(run_dir: Path, job: Job) -> None:
    """Write the final job snapshot (stages, outputs, timings) as ``manifest.json``."""
    snapshot = {
        "metagaap2_version": __version__,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "job": job.model_dump(mode="json"),
    }
    target = run_dir / "manifest.json"
    target.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _resolve_reference(config: RunConfig, sample: Sample) -> Path:
    """Resolve the reference FASTA for ``sample``.

    Per-sample references apply in :attr:`ReferenceMode.MULTIPLE`; the shared
    run-level reference applies in :attr:`ReferenceMode.SINGLE`. Raises
    ``ValueError`` (in Australian English) when the required reference is absent.
    """
    if config.reference_mode is ReferenceMode.MULTIPLE:
        if not sample.reference:
            raise ValueError(
                f"Sample {sample.name!r} has no reference, but the run uses "
                "per-sample references (reference_mode=multiple)."
            )
        return Path(sample.reference)
    if not config.reference:
        raise ValueError(
            "A shared reference is required when reference_mode=single, "
            "but none was provided."
        )
    return Path(config.reference)


def _read_group_for(sample: Sample) -> ReadGroup:
    """Return the sample's read-group, defaulting to one named after the sample."""
    return sample.read_group or ReadGroup(sample=sample.name)


# --------------------------------------------------------------------------- #
# Orchestration state
# --------------------------------------------------------------------------- #
class _Progress:
    """Tracks completed-stage progress so ``job.progress`` stays in ``[0, 1]``."""

    def __init__(self, total_stages: int) -> None:
        self.total = max(total_stages, 1)
        self.completed = 0

    def advance(self) -> float:
        self.completed += 1
        return min(self.completed / self.total, 1.0)

    @property
    def fraction(self) -> float:
        return min(self.completed / self.total, 1.0)


class _Orchestrator:
    """Internal driver bound to a single :class:`Job` and its ``emit`` callback."""

    def __init__(self, job: Job, *, emit: EmitFn, is_cancelled: CancelFn) -> None:
        self.job = job
        self.emit = emit
        self.is_cancelled = is_cancelled
        self.config = job.config
        self.run_dir: Path = Path(job.config.work_dir) / job.config.run_name
        self.engine: Optional[Engine] = None
        self.progress = _Progress(self._count_total_stages())
        # Sample name -> its SampleResult, for quick lookup during MERGE.
        self._results: dict[str, SampleResult] = {}
        # Sample name -> path to its haplotype database FASTA (for MERGE).
        self._db_paths: dict[str, Path] = {}
        # Sample name -> resolved trimmed reads (r1, r2) for re-mapping in MERGE.
        self._trimmed_reads: dict[str, tuple[Path, Optional[Path]]] = {}

    # -- progress / events --------------------------------------------------- #
    def _count_total_stages(self) -> int:
        """Total number of stages this run will attempt (drives progress)."""
        total = len(self.config.samples) * len(_PER_SAMPLE_STAGES)
        if self._merge_enabled():
            total += 1
        return total

    def _merge_enabled(self) -> bool:
        """True when the run should perform the multi-sample MERGE stage."""
        return (
            self.config.reference_mode is ReferenceMode.SINGLE
            and len(self.config.samples) > 1
            and self.config.merge_single_reference
        )

    def _emit_state(self) -> None:
        self.emit(
            WSEvent(
                type=WSEventType.STATE,
                job_id=self.job.id,
                state=self.job.state,
                progress=self.job.progress,
            )
        )

    def _emit_stage(self, sample: Optional[str], stage: StageResult) -> None:
        self.emit(
            WSEvent(
                type=WSEventType.STAGE,
                job_id=self.job.id,
                sample=sample,
                stage=stage,
                progress=self.job.progress,
            )
        )

    def _emit_log(self, sample: Optional[str], line: str) -> None:
        self.emit(
            WSEvent(
                type=WSEventType.LOG,
                job_id=self.job.id,
                sample=sample,
                line=line,
            )
        )

    # -- stage lifecycle ----------------------------------------------------- #
    def _start_stage(
        self,
        result: SampleResult,
        name: StageName,
        *,
        sample: str,
        log_name: str,
    ) -> tuple[StageResult, Path, Callable[[str], None]]:
        """Create + register a running :class:`StageResult` and a log sink.

        Returns the stage record, the path to its log file (under ``logs/``) and
        a ``log`` callback that appends each line to that file *and* forwards it
        to ``emit`` as a LOG event. The sink is what gets passed to the engine.
        """
        log_path = self.run_dir / "logs" / log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Truncate any stale log from a previous attempt.
        log_path.write_text("", encoding="utf-8")

        stage = StageResult(
            name=name,
            status=StageStatus.RUNNING,
            started_at=_now_iso(),
            log_path=str(log_path),
        )
        result.stages.append(stage)
        self.job.current_stage = name
        self._emit_stage(sample, stage)

        def _log(line: str) -> None:
            with log_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line.rstrip("\n") + "\n")
            self._emit_log(sample, line)

        return stage, log_path, _log

    def _finish_stage(
        self,
        sample: Optional[str],
        stage: StageResult,
        *,
        message: Optional[str] = None,
    ) -> None:
        """Mark a stage DONE, advance progress, and emit stage + state events."""
        stage.status = StageStatus.DONE
        stage.ended_at = _now_iso()
        if message:
            stage.message = message
        self.job.progress = self.progress.advance()
        self._emit_stage(sample, stage)
        self._emit_state()

    def _skip_stage(
        self,
        result: SampleResult,
        name: StageName,
        *,
        sample: str,
        message: str,
    ) -> None:
        """Record a SKIPPED stage (still counts towards progress)."""
        stage = StageResult(
            name=name,
            status=StageStatus.SKIPPED,
            started_at=_now_iso(),
            ended_at=_now_iso(),
            message=message,
        )
        result.stages.append(stage)
        self.job.progress = self.progress.advance()
        self._emit_stage(sample, stage)
        self._emit_state()

    # -- cancellation -------------------------------------------------------- #
    def _check_cancel(self) -> bool:
        """Return True (and flip the job to CANCELLED) if cancellation was asked."""
        if self.is_cancelled():
            self.job.state = JobState.CANCELLED
            self.job.ended_at = _now_iso()
            self._emit_state()
            return True
        return False

    # -- per-sample stages --------------------------------------------------- #
    def _run_sample(self, sample: Sample) -> bool:
        """Run TRIM -> ALIGN_CALL -> HAPLOTYPES -> CONFIRM for one sample.

        Returns False if the run was cancelled partway through (the caller then
        stops); True when the sample completed (or its stages were skipped).
        Cancellation is checked before every stage.
        """
        assert self.engine is not None
        result = SampleResult(sample=sample.name)
        self.job.samples.append(result)
        self._results[sample.name] = result

        reference = _resolve_reference(self.config, sample)
        read_group = _read_group_for(sample)

        r1 = Path(sample.r1)
        r2 = Path(sample.r2) if sample.r2 else None

        # ---- TRIM ---------------------------------------------------------- #
        if self._check_cancel():
            return False
        stage, _log_path, log = self._start_stage(
            result, StageName.TRIM, sample=sample.name, log_name=f"{sample.name}.trim.log"
        )
        trim = self.engine.trim(
            r1=r1,
            r2=r2,
            params=self.config.qc,
            out_dir=self.run_dir / "trimmed",
            sample=sample.name,
            log=log,
        )
        stage.outputs["r1"] = str(trim.r1)
        if trim.r2 is not None:
            stage.outputs["r2"] = str(trim.r2)
        if trim.report is not None:
            stage.outputs["report"] = str(trim.report)
        msg_parts = []
        if trim.n_reads_in is not None:
            msg_parts.append(f"{trim.n_reads_in} reads in")
        if trim.n_reads_out is not None:
            msg_parts.append(f"{trim.n_reads_out} reads out")
        self._finish_stage(
            sample.name, stage, message=", ".join(msg_parts) if msg_parts else None
        )
        trimmed_r1, trimmed_r2 = trim.r1, trim.r2
        self._trimmed_reads[sample.name] = (trimmed_r1, trimmed_r2)

        # ---- ALIGN_CALL ---------------------------------------------------- #
        if self._check_cancel():
            return False
        stage, _log_path, log = self._start_stage(
            result,
            StageName.ALIGN_CALL,
            sample=sample.name,
            log_name=f"{sample.name}.align_call.log",
        )
        call = self.engine.align_and_call(
            r1=trimmed_r1,
            r2=trimmed_r2,
            reference=reference,
            read_group=read_group,
            params=self.config.variants,
            out_dir=self.run_dir / "alignments",
            sample=sample.name,
            log=log,
        )
        # Engines write the VCF alongside the alignment; relocate it under
        # variants/ so the run directory matches SPEC.md section 7 (the BAM, if
        # any, stays in alignments/).
        produced_vcf = Path(call.vcf)
        vcf_path = self.run_dir / "variants" / f"{sample.name}.vcf"
        if produced_vcf.resolve() != vcf_path.resolve():
            vcf_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(produced_vcf), str(vcf_path))
        stage.outputs["vcf"] = str(vcf_path)
        if call.bam is not None:
            stage.outputs["bam"] = str(call.bam)
        modal = call.modal_read_length if call.modal_read_length > 0 else 1
        self._finish_stage(
            sample.name,
            stage,
            message=f"{call.n_variants} variants, modal read length {modal} bp",
        )

        # ---- HAPLOTYPES ---------------------------------------------------- #
        if self._check_cancel():
            return False
        stage, _log_path, log = self._start_stage(
            result,
            StageName.HAPLOTYPES,
            sample=sample.name,
            log_name=f"{sample.name}.haplotypes.log",
        )
        db_path = self.run_dir / "haplotypes" / f"{sample.name}_db.fasta"
        log(
            f"Building combinatorial haplotype database for {sample.name!r} "
            f"(window default {modal} bp) from {vcf_path.name}."
        )
        n_haplotypes = build_haplotype_database(
            reference,
            vcf_path,
            db_path,
            self.config.haplotypes,
            sample=sample.name,
            default_window=modal,
        )
        log(f"Wrote {n_haplotypes} unique haplotypes to {db_path.name}.")
        result.n_haplotypes = n_haplotypes
        self._db_paths[sample.name] = db_path
        stage.outputs["database"] = str(db_path)
        self._finish_stage(
            sample.name, stage, message=f"{n_haplotypes} haplotypes generated"
        )

        # ---- CONFIRM ------------------------------------------------------- #
        if self._check_cancel():
            return False
        stage, _log_path, log = self._start_stage(
            result,
            StageName.CONFIRM,
            sample=sample.name,
            log_name=f"{sample.name}.confirm.log",
        )
        self._confirm_against(
            sample_name=sample.name,
            result=result,
            stage=stage,
            db_path=db_path,
            r1=trimmed_r1,
            r2=trimmed_r2,
            log=log,
        )
        self._finish_stage(
            sample.name,
            stage,
            message=f"{result.n_confirmed} of {result.n_haplotypes} haplotypes confirmed",
        )
        return True

    # -- confirm + extraction (shared by CONFIRM and MERGE) ------------------ #
    def _confirm_against(
        self,
        *,
        sample_name: str,
        result: SampleResult,
        stage: StageResult,
        db_path: Path,
        r1: Path,
        r2: Optional[Path],
        log: Callable[[str], None],
    ) -> None:
        """Map a sample's reads to ``db_path``, keep + extract confirmed haplotypes.

        Recruits reads per haplotype via ``engine.map_and_count``, keeps those
        with at least ``confirm.min_mapped_reads`` reads, extracts them to
        ``results/<sample>_confirmed.fasta``, and writes the per-haplotype counts
        to ``results/<sample>_counts.csv``. Updates ``result`` in place.
        """
        assert self.engine is not None
        results_dir = self.run_dir / "results"

        count = self.engine.map_and_count(
            r1=r1,
            r2=r2,
            target_fasta=db_path,
            params=self.config.confirm,
            out_dir=results_dir,
            sample=sample_name,
            log=log,
        )

        threshold = self.config.confirm.min_mapped_reads
        confirmed_ids = [
            seq_id
            for seq_id, n in count.counts.items()
            if n >= threshold
        ]
        # Stable, deterministic ordering: by descending count then id.
        confirmed_ids.sort(key=lambda i: (-count.counts.get(i, 0), i))

        confirmed_fasta = results_dir / f"{sample_name}_confirmed.fasta"
        n_written = extract_records(db_path, confirmed_ids, confirmed_fasta)
        log(
            f"Confirmed {n_written} haplotypes "
            f"(>= {threshold} mapped reads) for {sample_name!r}."
        )

        counts_csv = results_dir / f"{sample_name}_counts.csv"
        self._write_counts_csv(counts_csv, count.counts, threshold)

        result.n_confirmed = n_written
        result.confirmed_fasta = str(confirmed_fasta)
        result.counts_csv = str(counts_csv)
        if count.stats_csv is not None:
            result.stats_csv = str(count.stats_csv)

        stage.outputs["confirmed_fasta"] = str(confirmed_fasta)
        stage.outputs["counts_csv"] = str(counts_csv)
        stage.outputs["target_db"] = str(db_path)
        if count.stats_csv is not None:
            stage.outputs["stats_csv"] = str(count.stats_csv)

    @staticmethod
    def _write_counts_csv(
        path: Path,
        counts: dict[str, int],
        threshold: int,
    ) -> None:
        """Write a ``haplotype,mapped_reads,confirmed`` CSV sorted by count desc."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["haplotype", "mapped_reads", "confirmed"])
            for seq_id, n in ordered:
                writer.writerow([seq_id, n, "yes" if n >= threshold else "no"])

    # -- multi-sample merge -------------------------------------------------- #
    def _run_merge(self) -> bool:
        """Merge per-sample databases, de-duplicate, and re-confirm every sample.

        Mirrors the original pipeline's single-reference merge + remap: all
        per-sample haplotype databases are concatenated and de-duplicated by
        checksum into ``haplotypes/merged_db.fasta``, then each sample's trimmed
        reads are re-mapped against the merged database and its confirmed
        sequences re-extracted. Returns False if the run was cancelled.
        """
        assert self.engine is not None
        if self._check_cancel():
            return False

        # A synthetic SampleResult holds the MERGE stage so it surfaces in the UI.
        merge_result = SampleResult(sample="__merge__")
        self.job.samples.append(merge_result)
        stage, _log_path, log = self._start_stage(
            merge_result,
            StageName.MERGE,
            sample="__merge__",
            log_name="merge.log",
        )

        merged_db = self.run_dir / "haplotypes" / "merged_db.fasta"
        db_paths = [self._db_paths[s.name] for s in self.config.samples if s.name in self._db_paths]
        log(
            f"De-duplicating {len(db_paths)} per-sample databases into "
            f"{merged_db.name}."
        )
        n_in, n_out = dedup_fasta(db_paths, merged_db, rename_prefix="merged")
        log(f"Merged database: {n_in} records in, {n_out} unique records out.")
        stage.outputs["merged_db"] = str(merged_db)

        # Re-confirm every sample against the merged database.
        for sample in self.config.samples:
            if self._check_cancel():
                return False
            reads = self._trimmed_reads.get(sample.name)
            result = self._results.get(sample.name)
            if reads is None or result is None:
                log(f"Skipping {sample.name!r}: no trimmed reads recorded.")
                continue
            r1, r2 = reads
            log(f"Re-mapping {sample.name!r} against the merged database.")
            self._confirm_against(
                sample_name=sample.name,
                result=result,
                stage=stage,
                db_path=merged_db,
                r1=r1,
                r2=r2,
                log=log,
            )

        self._finish_stage(
            "__merge__",
            stage,
            message=f"{n_out} merged haplotypes; {len(self.config.samples)} samples re-confirmed",
        )
        return True

    # -- driver -------------------------------------------------------------- #
    def run(self) -> None:
        """Execute the whole job, never raising; failures land on the job."""
        self.job.state = JobState.RUNNING
        self.job.started_at = _now_iso()
        self.job.progress = 0.0
        self._emit_state()

        active_sample: Optional[str] = None
        active_stage: Optional[StageResult] = None
        try:
            self.run_dir = _ensure_run_dir(self.config)
            self.job.run_dir = str(self.run_dir)
            _write_run_config(self.run_dir, self.config)

            self.engine = get_engine(
                self.config.engine,
                aligner=self.config.aligner,
                threads=self.config.threads,
            )
            self.engine.validate(aligner=self.config.aligner, caller=self.config.variants.caller)

            for sample in self.config.samples:
                active_sample = sample.name
                if not self._run_sample(sample):
                    # Cancelled inside the sample; state already set to CANCELLED.
                    # The manifest is still written by the finally block below.
                    return
                # The last appended stage is the one that just completed.
                active_stage = self._results[sample.name].stages[-1] if self._results[sample.name].stages else None

            if self._merge_enabled():
                if not self._run_merge():
                    # Cancelled during merge; manifest written by finally block.
                    return

            self.job.state = JobState.COMPLETED
            self.job.current_stage = None
            self.job.progress = 1.0
            self.job.ended_at = _now_iso()
            self._emit_state()
            self.emit(
                WSEvent(
                    type=WSEventType.DONE,
                    job_id=self.job.id,
                    state=self.job.state,
                    progress=self.job.progress,
                )
            )
        except Exception as exc:  # noqa: BLE001 - the contract is: never raise.
            self._handle_failure(exc, active_sample, active_stage)
        finally:
            # Always try to leave a manifest behind for inspection.
            try:
                _write_manifest(self.run_dir, self.job)
            except Exception:  # noqa: BLE001 - best-effort; do not mask outcome.
                pass

    def _handle_failure(
        self,
        exc: BaseException,
        active_sample: Optional[str],
        active_stage: Optional[StageResult],
    ) -> None:
        """Capture an exception onto the job and emit terminal failure events."""
        # Prefer the currently-running stage (the last running one on any sample).
        running = self._find_running_stage()
        if running is not None:
            stage_obj, sample_name = running
        else:
            stage_obj, sample_name = active_stage, active_sample

        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        self.job.state = JobState.FAILED
        self.job.error = str(exc) or detail
        self.job.ended_at = _now_iso()

        if stage_obj is not None:
            stage_obj.status = StageStatus.FAILED
            stage_obj.ended_at = _now_iso()
            stage_obj.message = detail
            self._emit_stage(sample_name, stage_obj)

        self._emit_log(sample_name, f"Run failed: {detail}")
        self._emit_state()
        self.emit(
            WSEvent(
                type=WSEventType.DONE,
                job_id=self.job.id,
                state=self.job.state,
                progress=self.job.progress,
            )
        )

    def _find_running_stage(self) -> Optional[tuple[StageResult, str]]:
        """Return the (stage, sample) pair still marked RUNNING, if any."""
        for result in self.job.samples:
            for stage in result.stages:
                if stage.status is StageStatus.RUNNING:
                    return stage, result.sample
        return None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def execute_job(
    job: Job,
    *,
    emit: EmitFn,
    is_cancelled: CancelFn,
) -> None:
    """Execute ``job`` end-to-end, mutating it in place and never raising.

    Drives the per-sample stages (TRIM -> ALIGN_CALL -> HAPLOTYPES -> CONFIRM)
    and the optional multi-sample MERGE stage, creating the run directory and
    writing ``run_config.json`` up front and ``manifest.json`` at the end (per
    SPEC.md section 7).

    Parameters
    ----------
    job:
        The job to run. Its ``state``, ``progress``, ``current_stage``,
        ``samples`` (per-stage results), ``run_dir``, ``error`` and timestamps
        are updated in place as the run proceeds.
    emit:
        Callback invoked with a :class:`~metagaap2.models.WSEvent` on every
        state, stage, log and progress change (consumed by :mod:`metagaap2.jobs`
        to broadcast over the WebSocket).
    is_cancelled:
        A zero-argument predicate polled between stages. When it returns ``True``
        the run stops cleanly: the job is set to ``CANCELLED`` and the function
        returns.

    Notes
    -----
    This function is exception-safe by contract: any failure sets the job state
    to ``FAILED``, records ``job.error``, marks the active stage ``FAILED`` and
    emits the appropriate events before returning. It never propagates.
    """
    _Orchestrator(job, emit=emit, is_cancelled=is_cancelled).run()
