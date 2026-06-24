"""Native compute engine for MetaGaAP 2.

Wraps fast external bioinformatics binaries (``fastp``, ``minimap2``,
``bwa-mem2``/``bwa``, ``samtools``, ``bcftools``, ``lofreq``) when they are
present on ``PATH``. These tools have no pip wheels on native Windows, so this
engine is *optional* and auto-detected: on machines where the binaries are
missing the portable engine (:class:`~metagaap2.engines.portable.PortableEngine`)
remains available. On Windows the binaries are typically supplied via WSL or a
conda/bioconda environment.

Every external command is executed through :mod:`metagaap2.runner` with list
arguments; ``shell=True`` is never used and shell-free pipelines are built with
:func:`metagaap2.runner.run_pipe`. Caller-specific VCFs are normalised back into
the pipeline's uniform :class:`~metagaap2.vcf.Variant` shape via
:mod:`metagaap2.vcf`, so downstream stages never touch tool-specific FORMAT or
INFO columns.

Tool discovery is delegated entirely to :mod:`metagaap2.tools`, which is the
single source of truth for which logical tool resolves to which executable.

Nothing here imports ``pysam``, ``mappy`` or ``edlib`` (no Windows wheels).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from .. import seqio, vcf
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
from ..runner import CommandError, run, run_pipe, which
from ..tools import detect_tool
from .base import CallResult, CountResult, Engine, LogSink, TrimResult

__all__ = ["NativeEngine"]

#: Hint shown when the engine is unavailable - guides the user to bioconda.
_CONDA_NOTE = (
    "Install the native binaries via conda/bioconda "
    "(e.g. `conda install -c bioconda minimap2 bwa-mem2 samtools bcftools lofreq fastp`). "
    "On Windows use WSL or a conda environment."
)


def _resolve(name: str) -> str:
    """Return the resolved executable for a logical tool name.

    Uses :func:`metagaap2.tools.detect_tool` so platform-specific candidate
    binaries (e.g. ``bwa-mem2.avx2`` or a fallback to legacy ``bwa``) are honoured
    consistently with discovery/reporting. Raises :class:`FileNotFoundError` when
    nothing resolves, which should not happen once :meth:`NativeEngine.detect`
    has gated execution.
    """
    info = detect_tool(name)
    if not info.found or not info.path:
        raise FileNotFoundError(
            f"Native engine requires {name!r} but it was not found on PATH. {_CONDA_NOTE}"
        )
    return info.path


class NativeEngine(Engine):
    """Compute engine backed by external bioinformatics binaries."""

    key = EngineKey.NATIVE
    label = "Native (external tools)"
    supported_aligners = (Aligner.MINIMAP2, Aligner.BWA_MEM2)
    supported_callers = (VariantCaller.BCFTOOLS, VariantCaller.LOFREQ)

    # ------------------------------------------------------------------ #
    # Capability reporting
    # ------------------------------------------------------------------ #
    @classmethod
    def detect(cls) -> EngineCapabilities:
        """Report native-tool availability for this machine.

        The engine is available when an aligner (``minimap2`` *or* ``bwa-mem2``)
        and ``samtools`` are both present. Aligners and callers actually found are
        reported so the UI only offers honourable choices; everything missing for
        the full feature set is listed in ``missing``.
        """
        # Probe each logical tool the engine can use.
        names = ("minimap2", "bwa-mem2", "samtools", "bcftools", "lofreq", "fastp")
        infos = {name: detect_tool(name) for name in names}

        aligners: list[Aligner] = []
        if infos["minimap2"].found:
            aligners.append(Aligner.MINIMAP2)
        if infos["bwa-mem2"].found:
            aligners.append(Aligner.BWA_MEM2)

        callers: list[VariantCaller] = []
        if infos["bcftools"].found:
            callers.append(VariantCaller.BCFTOOLS)
        if infos["lofreq"].found:
            callers.append(VariantCaller.LOFREQ)

        have_aligner = bool(aligners)
        have_samtools = infos["samtools"].found
        available = have_aligner and have_samtools

        # Everything genuinely missing for the full native feature set.
        missing: list[str] = []
        if not have_aligner:
            missing.append("minimap2 or bwa-mem2")
        if not have_samtools:
            missing.append("samtools")
        if not callers:
            missing.append("bcftools or lofreq")
        if not infos["fastp"].found:
            missing.append("fastp (optional; trim falls back to cutadapt)")

        if available:
            note = _CONDA_NOTE if missing else None
        else:
            note = (
                "Native engine unavailable: needs an aligner (minimap2 or bwa-mem2) "
                f"and samtools. {_CONDA_NOTE}"
            )

        return EngineCapabilities(
            key=cls.key,
            label=cls.label,
            available=available,
            aligners=aligners,
            callers=callers,
            missing=missing,
            note=note,
        )

    # ------------------------------------------------------------------ #
    # Trim
    # ------------------------------------------------------------------ #
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
        """Quality/adapter trim with ``fastp`` (falls back to ``cutadapt``).

        When trimming is disabled the inputs are returned verbatim. ``fastp`` is
        preferred when present; if it is missing the cutadapt subprocess fallback
        is used so the native engine still functions on machines lacking fastp.
        """
        r1 = Path(r1)
        r2 = Path(r2) if r2 else None
        out_dir = Path(out_dir)

        if not params.enabled:
            return TrimResult(r1=r1, r2=r2, report=None)

        out_dir.mkdir(parents=True, exist_ok=True)
        paired = r2 is not None

        if which("fastp") is not None:
            return self._trim_fastp(
                r1=r1, r2=r2, params=params, out_dir=out_dir, sample=sample, log=log
            )
        return self._trim_cutadapt(
            r1=r1, r2=r2, params=params, out_dir=out_dir, sample=sample, paired=paired, log=log
        )

    def _trim_fastp(
        self,
        *,
        r1: Path,
        r2: Optional[Path],
        params: QCParams,
        out_dir: Path,
        sample: str,
        log: Optional[LogSink],
    ) -> TrimResult:
        fastp = _resolve("fastp")
        out_r1 = out_dir / f"{sample}_R1.fastq.gz"
        out_r2 = out_dir / f"{sample}_R2.fastq.gz" if r2 else None
        report_json = out_dir / f"{sample}_fastp.json"
        report_html = out_dir / f"{sample}_fastp.html"

        args: list[str] = [
            fastp,
            "-i", str(r1),
            "-o", str(out_r1),
            "-q", str(params.min_quality),
            "-l", str(params.min_length),
            "-w", str(self.threads),
            "-j", str(report_json),
            "-h", str(report_html),
        ]
        if r2 and out_r2:
            args += ["-I", str(r2), "-O", str(out_r2)]
        if params.trim_front > 0:
            args += ["--trim_front1", str(params.trim_front)]
            if r2:
                args += ["--trim_front2", str(params.trim_front)]
        if params.trim_tail > 0:
            args += ["--trim_tail1", str(params.trim_tail)]
            if r2:
                args += ["--trim_tail2", str(params.trim_tail)]
        # Adapters: explicit sequences take precedence; otherwise rely on
        # fastp's overlap-based auto-detection (on by default for PE; enable for SE).
        if params.adapter_fwd:
            args += ["--adapter_sequence", params.adapter_fwd]
        if params.adapter_rev and r2:
            args += ["--adapter_sequence_r2", params.adapter_rev]
        if params.detect_adapters and not r2:
            args.append("--detect_adapter_for_pe")  # harmless on SE; enables detection

        run(args, log=log)

        n_in = seqio.count_reads(r1)
        n_out = seqio.count_reads(out_r1)
        return TrimResult(
            r1=out_r1,
            r2=out_r2,
            report=report_json,
            n_reads_in=n_in,
            n_reads_out=n_out,
        )

    def _trim_cutadapt(
        self,
        *,
        r1: Path,
        r2: Optional[Path],
        params: QCParams,
        out_dir: Path,
        sample: str,
        paired: bool,
        log: Optional[LogSink],
    ) -> TrimResult:
        """Fallback trimmer using cutadapt as a pip-installed subprocess.

        Invoked as ``python -m cutadapt`` so it is cross-platform and does not
        depend on a console-script entry point being on PATH.
        """
        out_r1 = out_dir / f"{sample}_R1.fastq.gz"
        out_r2 = out_dir / f"{sample}_R2.fastq.gz" if paired else None

        args: list[str] = [
            sys.executable, "-m", "cutadapt",
            "-q", str(params.min_quality),
            "-m", str(params.min_length),
            "-j", str(self.threads),
        ]
        if params.trim_front > 0:
            args += ["-u", str(params.trim_front)]
        if params.trim_tail > 0:
            args += ["-u", f"-{params.trim_tail}"]
        if params.adapter_fwd:
            args += ["-a", params.adapter_fwd]
        if paired and params.adapter_rev:
            args += ["-A", params.adapter_rev]

        args += ["-o", str(out_r1)]
        if paired and out_r2:
            args += ["-p", str(out_r2), str(r1), str(r2)]
        else:
            args += [str(r1)]

        run(args, log=log)

        n_in = seqio.count_reads(r1)
        n_out = seqio.count_reads(out_r1)
        return TrimResult(
            r1=out_r1,
            r2=out_r2,
            report=None,
            n_reads_in=n_in,
            n_reads_out=n_out,
        )

    # ------------------------------------------------------------------ #
    # Align + call
    # ------------------------------------------------------------------ #
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
        """Map reads to ``reference`` and call variants, writing a VCF.

        Reads are mapped (with a read-group header) and piped straight into
        ``samtools sort`` to produce a coordinate-sorted, indexed BAM. Variants
        are then called with the configured caller and post-filtered by
        ``min_depth`` / ``min_alt_fraction``.
        """
        aligner = self.aligner or Aligner.MINIMAP2
        caller = params.caller
        self.validate(aligner=aligner, caller=caller)

        r1 = Path(r1)
        r2 = Path(r2) if r2 else None
        reference = Path(reference)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        sorted_bam = out_dir / f"{sample}.sorted.bam"
        self._map_to_bam(
            r1=r1,
            r2=r2,
            reference=reference,
            aligner=aligner,
            sorted_bam=sorted_bam,
            read_group=read_group,
            min_mapping_quality=None,  # filtering happens at call time
            log=log,
        )

        raw_vcf = out_dir / f"{sample}.raw.vcf"
        final_vcf = out_dir / f"{sample}.vcf"

        if caller == VariantCaller.BCFTOOLS:
            self._call_bcftools(
                reference=reference,
                sorted_bam=sorted_bam,
                params=params,
                raw_vcf=raw_vcf,
                log=log,
            )
        else:  # VariantCaller.LOFREQ
            self._call_lofreq(
                reference=reference,
                sorted_bam=sorted_bam,
                params=params,
                raw_vcf=raw_vcf,
                log=log,
            )

        n_variants = self._post_filter_vcf(
            raw_vcf=raw_vcf,
            final_vcf=final_vcf,
            reference=reference,
            params=params,
        )

        modal_len = seqio.modal_read_length(r1)

        return CallResult(
            vcf=final_vcf,
            modal_read_length=modal_len,
            n_variants=n_variants,
            bam=sorted_bam,
        )

    # -- mapping helper -------------------------------------------------- #
    def _read_group_string(self, read_group: ReadGroup) -> str:
        """Build the SAM ``@RG`` header line (tab-separated, escaped for args)."""
        return (
            f"@RG\\tID:{read_group.rg_id()}"
            f"\\tSM:{read_group.sample}"
            f"\\tLB:{read_group.library}"
            f"\\tPL:{read_group.platform}"
            f"\\tPU:{read_group.unit}"
        )

    def _index_reference_bwa(self, reference: Path, *, log: Optional[LogSink]) -> None:
        """Ensure a bwa-mem2 (or bwa) index exists next to ``reference``."""
        bwa = _resolve("bwa-mem2")
        # bwa-mem2 writes <ref>.bwt.2bit.64 etc; legacy bwa writes <ref>.bwt.
        sentinels = (
            reference.with_suffix(reference.suffix + ".bwt.2bit.64"),
            reference.with_suffix(reference.suffix + ".bwt"),
        )
        if any(s.exists() for s in sentinels):
            return
        run([bwa, "index", str(reference)], log=log)

    def _map_to_bam(
        self,
        *,
        r1: Path,
        r2: Optional[Path],
        reference: Path,
        aligner: Aligner,
        sorted_bam: Path,
        read_group: Optional[ReadGroup],
        min_mapping_quality: Optional[int],
        log: Optional[LogSink],
    ) -> None:
        """Map reads and pipe SAM straight into ``samtools sort`` -> indexed BAM."""
        samtools = _resolve("samtools")
        rg = self._read_group_string(read_group) if read_group else None

        if aligner == Aligner.MINIMAP2:
            minimap2 = _resolve("minimap2")
            map_cmd: list[str] = [minimap2, "-ax", "sr", "-t", str(self.threads)]
            if rg:
                map_cmd += ["-R", rg]
            map_cmd.append(str(reference))
            map_cmd.append(str(r1))
            if r2:
                map_cmd.append(str(r2))
        else:  # Aligner.BWA_MEM2
            self._index_reference_bwa(reference, log=log)
            bwa = _resolve("bwa-mem2")
            map_cmd = [bwa, "mem", "-t", str(self.threads)]
            if rg:
                map_cmd += ["-R", rg]
            map_cmd.append(str(reference))
            map_cmd.append(str(r1))
            if r2:
                map_cmd.append(str(r2))

        sort_cmd: list[str] = [samtools, "sort", "-@", str(self.threads)]
        if min_mapping_quality is not None:
            # Drop low-MAPQ alignments at sort time when requested.
            view_cmd = [
                samtools, "view", "-b", "-q", str(min_mapping_quality), "-"
            ]
            run_pipe(
                [map_cmd, view_cmd, sort_cmd + ["-o", str(sorted_bam), "-"]],
                log=log,
            )
        else:
            run_pipe(
                [map_cmd, sort_cmd + ["-o", str(sorted_bam), "-"]],
                log=log,
            )

        run([samtools, "index", str(sorted_bam)], log=log)

    # -- bcftools -------------------------------------------------------- #
    def _call_bcftools(
        self,
        *,
        reference: Path,
        sorted_bam: Path,
        params: VariantParams,
        raw_vcf: Path,
        log: Optional[LogSink],
    ) -> None:
        """``bcftools mpileup | bcftools call`` into an uncompressed VCF."""
        bcftools = _resolve("bcftools")
        samtools = _resolve("samtools")
        # Ensure a faidx index for the reference (mpileup needs it).
        if not reference.with_suffix(reference.suffix + ".fai").exists():
            run([samtools, "faidx", str(reference)], log=log)

        mpileup = [
            bcftools, "mpileup",
            "-f", str(reference),
            "-q", str(params.min_mapping_quality),
            "-Q", str(params.min_base_quality),
            "-a", "FORMAT/AD,FORMAT/DP,INFO/AD",
            "-Ou",
            str(sorted_bam),
        ]
        call = [
            bcftools, "call",
            "-mv",
            "--ploidy", str(params.ploidy),
            "-Ov",
            "-o", str(raw_vcf),
        ]
        run_pipe([mpileup, call], log=log)

    # -- lofreq ---------------------------------------------------------- #
    def _call_lofreq(
        self,
        *,
        reference: Path,
        sorted_bam: Path,
        params: VariantParams,
        raw_vcf: Path,
        log: Optional[LogSink],
    ) -> None:
        """``lofreq call`` into an uncompressed VCF.

        Insertion/deletion quality is added with ``lofreq indelqual`` so indels
        are callable; the dindel model is used as it needs no external training.
        """
        lofreq = _resolve("lofreq")
        samtools = _resolve("samtools")
        if not reference.with_suffix(reference.suffix + ".fai").exists():
            run([samtools, "faidx", str(reference)], log=log)

        # Add indel qualities, then call SNVs and indels.
        iq_bam = sorted_bam.with_suffix(".indelqual.bam")
        try:
            run(
                [
                    lofreq, "indelqual", "--dindel",
                    "-f", str(reference),
                    "-o", str(iq_bam),
                    str(sorted_bam),
                ],
                log=log,
            )
            run([samtools, "index", str(iq_bam)], log=log)
            call_bam = iq_bam
        except CommandError:
            # indelqual is best-effort; fall back to SNV-only calling.
            call_bam = sorted_bam

        call_args: list[str] = [
            lofreq, "call",
            "-f", str(reference),
            "-q", str(params.min_base_quality),
            "-Q", str(params.min_base_quality),
            "-m", str(params.min_mapping_quality),
        ]
        if call_bam == iq_bam:
            # Indel qualities were added; ask lofreq to emit indels too.
            call_args.append("--call-indels")
        call_args += ["-o", str(raw_vcf), str(call_bam)]
        run(call_args, log=log)

    # -- post-filter ----------------------------------------------------- #
    @staticmethod
    def _depth_of(var: vcf.Variant) -> Optional[int]:
        """Best-effort site depth from a caller's INFO column."""
        info = var.info
        if "DP" in info:
            try:
                return int(info["DP"])
            except ValueError:
                pass
        # bcftools/lofreq DP4: ref-fwd,ref-rev,alt-fwd,alt-rev.
        if "DP4" in info:
            try:
                return sum(int(x) for x in info["DP4"].split(","))
            except ValueError:
                pass
        return None

    @staticmethod
    def _alt_fraction_of(var: vcf.Variant) -> Optional[float]:
        """Best-effort ALT allele fraction from a caller's INFO column."""
        info = var.info
        if "AF" in info:
            # AF may be multi-allelic (comma-separated); take the max.
            try:
                fractions = [float(x) for x in info["AF"].split(",") if x]
                if fractions:
                    return max(fractions)
            except ValueError:
                pass
        # Derive from DP4 when AF is absent (bcftools mpileup output).
        if "DP4" in info:
            try:
                parts = [int(x) for x in info["DP4"].split(",")]
                if len(parts) == 4:
                    total = sum(parts)
                    alt = parts[2] + parts[3]
                    if total > 0:
                        return alt / total
            except ValueError:
                pass
        return None

    def _post_filter_vcf(
        self,
        *,
        raw_vcf: Path,
        final_vcf: Path,
        reference: Path,
        params: VariantParams,
    ) -> int:
        """Filter the raw VCF by depth / ALT fraction and write the final VCF.

        Records whose depth or ALT fraction cannot be determined are *kept*
        (conservative) so callers that do not emit DP/AF do not silently lose all
        variants. Returns the number of variants retained.
        """
        variants = vcf.read_vcf(raw_vcf)
        kept: list[vcf.Variant] = []
        for var in variants:
            depth = self._depth_of(var)
            if depth is not None and depth < params.min_depth:
                continue
            frac = self._alt_fraction_of(var)
            if frac is not None and frac < params.min_alt_fraction:
                continue
            kept.append(var)

        # Carry contig lengths through when available from the reference index.
        contigs = self._reference_contigs(reference)
        vcf.write_vcf(
            kept,
            final_vcf,
            reference_name=reference.name,
            contigs=contigs or None,
        )
        return len(kept)

    @staticmethod
    def _reference_contigs(reference: Path) -> dict[str, int]:
        """Read contig lengths from a ``.fai`` index if present, else from FASTA."""
        fai = reference.with_suffix(reference.suffix + ".fai")
        contigs: dict[str, int] = {}
        if fai.exists():
            try:
                for line in fai.read_text(encoding="utf-8").splitlines():
                    cols = line.split("\t")
                    if len(cols) >= 2:
                        contigs[cols[0]] = int(cols[1])
                return contigs
            except (OSError, ValueError):
                contigs = {}
        # Fall back to reading the FASTA itself.
        try:
            for seq_id, seq in seqio.iter_fasta(reference):
                contigs[seq_id] = len(seq)
        except OSError:
            pass
        return contigs

    # ------------------------------------------------------------------ #
    # Map + count (confirm)
    # ------------------------------------------------------------------ #
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
        """Map reads to ``target_fasta`` and count reads recruited per sequence.

        Reads are mapped, sorted and indexed, then ``samtools idxstats`` gives the
        per-sequence mapped/unmapped read tallies. A stats CSV is written with the
        header ``Sequences,Sequence_Length,Mapped_Reads,Unmapped_Reads``.
        """
        aligner = self.aligner or Aligner.MINIMAP2
        r1 = Path(r1)
        r2 = Path(r2) if r2 else None
        target_fasta = Path(target_fasta)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        sorted_bam = out_dir / f"{sample}.confirm.sorted.bam"
        # No read-group needed for counting; map straight to a sorted, indexed BAM.
        self._map_to_bam(
            r1=r1,
            r2=r2,
            reference=target_fasta,
            aligner=aligner,
            sorted_bam=sorted_bam,
            read_group=None,
            min_mapping_quality=None,
            log=log,
        )

        samtools = _resolve("samtools")
        proc = run([samtools, "idxstats", str(sorted_bam)], log=log)
        idxstats_text = proc.stdout if isinstance(proc.stdout, str) else (
            (proc.stdout or b"").decode(errors="replace")
        )

        counts: dict[str, int] = {}
        rows: list[tuple[str, int, int, int]] = []
        for line in idxstats_text.splitlines():
            if not line.strip():
                continue
            cols = line.split("\t")
            if len(cols) < 4:
                continue
            seq = cols[0]
            if seq == "*":
                # The unmapped-reads catch-all row; not a target sequence.
                continue
            try:
                length = int(cols[1])
                mapped = int(cols[2])
                unmapped = int(cols[3])
            except ValueError:
                continue
            counts[seq] = mapped
            rows.append((seq, length, mapped, unmapped))

        stats_csv = out_dir / f"{sample}_stats.csv"
        self._write_stats_csv(stats_csv, rows)

        return CountResult(counts=counts, stats_csv=stats_csv, bam=sorted_bam)

    @staticmethod
    def _write_stats_csv(path: Path, rows: list[tuple[str, int, int, int]]) -> None:
        """Write the per-sequence recruitment stats CSV."""
        import csv

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["Sequences", "Sequence_Length", "Mapped_Reads", "Unmapped_Reads"]
            )
            for seq, length, mapped, unmapped in rows:
                writer.writerow([seq, length, mapped, unmapped])
