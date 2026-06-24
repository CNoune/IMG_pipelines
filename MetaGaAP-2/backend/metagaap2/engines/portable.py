"""Pure-Python, pip-only compute engine for MetaGaAP 2.

:class:`PortableEngine` implements the three platform-sensitive pipeline stages
without any external bioinformatics binaries, so it runs identically on native
Windows, Linux and macOS with a plain ``pip install``:

* :meth:`PortableEngine.trim`           - quality / adapter trimming via ``cutadapt``
  (invoked as ``[sys.executable, "-m", "cutadapt", ...]`` so it is always the
  pip-installed, cross-platform build).
* :meth:`PortableEngine.align_and_call` - a k-mer seed index plus ``parasail``
  semi-global SIMD alignment drives a frequency pileup caller that writes a VCF.
* :meth:`PortableEngine.map_and_count`  - k-mer pseudo-assignment of reads to the
  sequences of a target FASTA, with optional ``parasail`` identity verification.

Design intent
-------------
The alignment and counting routines build an exact k-mer index of the reference
(or targets) in NumPy-friendly Python dictionaries, seed each read by shared
k-mers, vote for the best ``(contig, diagonal)`` and then run a single banded
semi-global ``parasail`` alignment of the read against the relevant reference
window. This is deliberately tuned for **barcoding / amplicon scale** references
(genes, amplicons, haplotype panels - tens to a few thousand bp), which is the
regime MetaGaAP targets; it is not a whole-genome aligner.

Nothing here uses ``shell=True``; the only subprocess is ``cutadapt`` run through
:mod:`metagaap2.runner`. ``pysam``, ``mappy`` and ``edlib`` are never imported
(no Windows wheels). All paths are :class:`pathlib.Path`.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

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
from ..runner import run
from .base import CallResult, CountResult, Engine, LogSink, TrimResult

# --------------------------------------------------------------------------- #
# Tuning constants
# --------------------------------------------------------------------------- #
#: k-mer length for the seed index. Long enough to be reasonably specific on
#: amplicon-scale references, short enough to seed short / error-rich reads.
_KMER: int = 15

#: parasail affine gap penalties and match/mismatch scores. Modest values that
#: tolerate sequencing error while still penalising real indels.
_MATCH: int = 2
_MISMATCH: int = -3
_GAP_OPEN: int = 5
_GAP_EXTEND: int = 2

#: Padding (bp) added either side of the seeded reference window before the
#: semi-global alignment, to absorb read overhang and small indels.
_WINDOW_PAD: int = 30

#: Column indices into the per-position pileup matrix.
_BASE_TO_COL: dict[str, int] = {"A": 0, "C": 1, "G": 2, "T": 3}
_COL_TO_BASE: tuple[str, ...] = ("A", "C", "G", "T")
_DEL_COL: int = 4  # deletion observations
_N_COLS: int = 5  # A, C, G, T, deletion


def _log(log: Optional[LogSink], message: str) -> None:
    """Emit ``message`` to ``log`` if a sink was provided."""
    if log is not None:
        log(message)


def _revcomp(seq: str) -> str:
    """Return the reverse complement of ``seq`` (unknown bases -> ``N``)."""
    table = str.maketrans("ACGTNacgtn", "TGCANtgcan")
    return seq.translate(table)[::-1]


def _kmerise(seq: str, k: int = _KMER) -> list[tuple[str, int]]:
    """Yield ``(kmer, position)`` pairs for every length-``k`` window of ``seq``.

    k-mers containing any non-ACGT character are skipped so ambiguous bases do
    not pollute the seed index.
    """
    out: list[tuple[str, int]] = []
    upper = seq.upper()
    n = len(upper)
    if n < k:
        return out
    valid = set("ACGT")
    for i in range(n - k + 1):
        kmer = upper[i : i + k]
        if valid.issuperset(kmer):
            out.append((kmer, i))
    return out


class _ReferenceIndex:
    """An exact k-mer index over a set of reference sequences.

    Maps each k-mer to the list of ``(seq_id, position)`` occurrences. Used to
    seed reads against the correct contig and diagonal before alignment.
    """

    def __init__(self, sequences: dict[str, str], k: int = _KMER) -> None:
        self.k = k
        self.sequences: dict[str, str] = {sid: s.upper() for sid, s in sequences.items()}
        self.index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for seq_id, seq in self.sequences.items():
            for kmer, pos in _kmerise(seq, k):
                self.index[kmer].append((seq_id, pos))

    def seed(self, read: str) -> Optional[tuple[str, int, int]]:
        """Seed ``read`` against the index.

        Votes over shared k-mers for the best ``(seq_id, diagonal)`` where the
        diagonal is ``ref_pos - read_pos``. Returns ``(seq_id, ref_start,
        votes)`` for the winning placement, or ``None`` when no k-mer matches.
        """
        votes: Counter[tuple[str, int]] = Counter()
        for kmer, read_pos in _kmerise(read, self.k):
            hits = self.index.get(kmer)
            if not hits:
                continue
            for seq_id, ref_pos in hits:
                votes[(seq_id, ref_pos - read_pos)] += 1
        if not votes:
            return None
        (seq_id, diagonal), n_votes = votes.most_common(1)[0]
        ref_start = max(0, diagonal)
        return seq_id, ref_start, n_votes

    def best_target(self, read: str) -> Optional[tuple[str, int]]:
        """Return ``(seq_id, shared_kmer_count)`` for the target sharing the most
        distinct k-mer hits with ``read``, or ``None`` if nothing matches."""
        per_target: Counter[str] = Counter()
        for kmer, _ in _kmerise(read, self.k):
            hits = self.index.get(kmer)
            if not hits:
                continue
            seen: set[str] = set()
            for seq_id, _pos in hits:
                if seq_id not in seen:
                    seen.add(seq_id)
                    per_target[seq_id] += 1
        if not per_target:
            return None
        return per_target.most_common(1)[0]


def _import_parasail():
    """Import and return the ``parasail`` module, with a helpful error message."""
    try:
        import parasail  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only without the wheel
        raise RuntimeError(
            "The portable engine requires the 'parasail' package "
            "(pip install parasail). It was not importable."
        ) from exc
    return parasail


def _parse_cigar(decode: object) -> list[tuple[int, str]]:
    """Parse a parasail CIGAR ``decode`` string into ``(length, op)`` tuples.

    parasail returns the decoded CIGAR either as ``str`` or ``bytes`` depending
    on the build; both are handled. Ops are ``=`` (match), ``X`` (mismatch),
    ``M`` (match-or-mismatch), ``I`` (insertion to reference) and ``D``
    (deletion from reference).
    """
    text = decode.decode("ascii") if isinstance(decode, (bytes, bytearray)) else str(decode)
    ops: list[tuple[int, str]] = []
    num = ""
    for ch in text:
        if ch.isdigit():
            num += ch
        else:
            ops.append((int(num) if num else 0, ch))
            num = ""
    return ops


def _split_cigar_core(
    ops: list[tuple[int, str]],
) -> tuple[int, int, list[tuple[int, str]]]:
    """Strip leading/trailing end-gaps from a semi-global CIGAR.

    A semi-global (``sg_*``) alignment of a short read against a longer reference
    region pads the CIGAR with ``D`` (and occasionally ``I``) operations at the
    ends to span the parts of the reference the read does not cover (e.g.
    ``30D80=14D``). Those flank ops are *not* real deletions/insertions and must
    not be counted as variant observations.

    Returns ``(ref_offset, read_offset, core_ops)`` where ``ref_offset`` /
    ``read_offset`` are the reference / read bases consumed by leading flank ops
    (used to advance the cursors to the first genuinely aligned column), and
    ``core_ops`` is the CIGAR with leading and trailing flank ``D``/``I`` ops
    removed so it begins and ends on a match/mismatch column.
    """
    if not ops:
        return 0, 0, []
    start = 0
    ref_offset = 0
    read_offset = 0
    while start < len(ops) and ops[start][1] in ("D", "I"):
        length, op = ops[start]
        if op == "D":
            ref_offset += length
        else:  # "I"
            read_offset += length
        start += 1
    end = len(ops)
    while end > start and ops[end - 1][1] in ("D", "I"):
        end -= 1
    return ref_offset, read_offset, ops[start:end]


def _qual_at(qualities: Optional[str], idx: int) -> Optional[int]:
    """Return the Phred quality at read index ``idx`` (Sanger/Phred+33), or None."""
    if qualities is None or idx < 0 or idx >= len(qualities):
        return None
    return ord(qualities[idx]) - 33


class PortableEngine(Engine):
    """Pure-Python engine; the cross-platform default (no external binaries)."""

    key = EngineKey.PORTABLE
    label = "Portable (pure-Python)"
    supported_aligners = (Aligner.BUILTIN,)
    supported_callers = (VariantCaller.BUILTIN,)

    # ----------------------------------------------------------------------- #
    # Capability reporting
    # ----------------------------------------------------------------------- #
    @classmethod
    def detect(cls) -> EngineCapabilities:
        """Report the portable engine as always available (pip-only).

        The portable engine ships entirely in pip wheels, so it is available on
        every supported platform. We do a best-effort check that ``cutadapt`` is
        importable for the trim stage and note it if missing, but the engine
        itself remains available (trimming can be disabled).
        """
        missing: list[str] = []
        try:
            import cutadapt  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            missing.append("cutadapt")
        note = "Pure-Python engine; no external binaries required."
        if missing:
            note += " cutadapt not importable - trimming will be unavailable."
        return EngineCapabilities(
            key=cls.key,
            label=cls.label,
            available=True,
            aligners=list(cls.supported_aligners),
            callers=list(cls.supported_callers),
            missing=missing,
            note=note,
        )

    # ----------------------------------------------------------------------- #
    # Stage 1: trim
    # ----------------------------------------------------------------------- #
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
        """Quality/adapter trim with ``cutadapt``.

        When ``params.enabled`` is False the inputs are returned verbatim.
        Otherwise ``cutadapt`` is invoked as a subprocess
        (``[sys.executable, "-m", "cutadapt", ...]``) so the pip-installed,
        cross-platform build is always used. Outputs are gzip-compressed FASTQ
        in ``out_dir``.
        """
        r1 = Path(r1)
        r2 = Path(r2) if r2 is not None else None
        if not params.enabled:
            _log(log, "Trimming disabled; passing reads through unchanged.")
            return TrimResult(r1=r1, r2=r2)

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paired = r2 is not None

        out_r1 = out_dir / f"{sample}_R1.trimmed.fastq.gz"
        out_r2 = out_dir / f"{sample}_R2.trimmed.fastq.gz" if paired else None
        report = out_dir / f"{sample}.cutadapt.txt"

        cmd: list[str] = [
            sys.executable,
            "-m",
            "cutadapt",
            "-q",
            str(params.min_quality),
            "-m",
            str(params.min_length),
        ]

        # Fixed-length trimming. cutadapt's -u takes positive counts off the 5'
        # end and negative counts off the 3' end; -U is the R2 equivalent.
        if params.trim_front:
            cmd += ["-u", str(params.trim_front)]
        if params.trim_tail:
            cmd += ["-u", f"-{params.trim_tail}"]
        if paired:
            if params.trim_front:
                cmd += ["-U", str(params.trim_front)]
            if params.trim_tail:
                cmd += ["-U", f"-{params.trim_tail}"]

        # Adapters (3' adapter on each mate).
        if params.adapter_fwd:
            cmd += ["-a", params.adapter_fwd]
        if paired and params.adapter_rev:
            cmd += ["-A", params.adapter_rev]

        cmd += ["-o", str(out_r1)]
        if paired:
            cmd += ["-p", str(out_r2)]
        cmd += [str(r1)]
        if paired:
            cmd += [str(r2)]

        _log(log, f"Trimming sample {sample!r} with cutadapt.")
        proc = run(cmd, log=log)
        # cutadapt writes its report to stdout; persist it for the run record.
        report.write_text(proc.stdout or "", encoding="utf-8")

        n_in = seqio.count_reads(r1)
        n_out = seqio.count_reads(out_r1)
        return TrimResult(
            r1=out_r1,
            r2=out_r2,
            report=report,
            n_reads_in=n_in,
            n_reads_out=n_out,
        )

    # ----------------------------------------------------------------------- #
    # Stage 2: align + call (pure Python, no external aligner)
    # ----------------------------------------------------------------------- #
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

        Pure Python: builds a k-mer index of the reference, seeds each read by
        shared k-mers to vote for the best ``(contig, diagonal)``, runs a
        semi-global ``parasail`` alignment of the read against the seeded
        reference window, and walks the CIGAR to accumulate per-position base
        counts (A, C, G, T, deletion + coverage) in NumPy arrays. A variant is
        called wherever depth >= ``min_depth`` and an ALT fraction >=
        ``min_alt_fraction`` (with ``AF`` and ``DP`` recorded in INFO). Read
        qualities, when present, gate observations via ``min_base_quality``.

        This is tuned for barcoding-scale (gene / amplicon) references.
        """
        reference = Path(reference)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        parasail = _import_parasail()
        matrix = parasail.matrix_create("ACGT", _MATCH, _MISMATCH)

        refs = seqio.read_fasta(reference)
        if not refs:
            raise ValueError(f"Reference FASTA contained no sequences: {reference}")
        index = _ReferenceIndex(refs, k=_KMER)

        # Per-position pileup matrices: one (length x 5) int array per contig,
        # plus a coverage vector per contig.
        pileups: dict[str, np.ndarray] = {
            sid: np.zeros((len(seq), _N_COLS), dtype=np.int64) for sid, seq in refs.items()
        }
        coverage: dict[str, np.ndarray] = {
            sid: np.zeros(len(seq), dtype=np.int64) for sid, seq in refs.items()
        }

        read_files = [p for p in (r1, r2) if p is not None]
        reads_for_modal = Path(r1)
        n_aligned = 0
        n_total = 0

        for read_file in read_files:
            for _name, seq, quals in seqio.iter_fastq(read_file):
                n_total += 1
                if not seq:
                    continue
                placed = self._align_read(
                    seq=seq,
                    quals=quals,
                    index=index,
                    parasail=parasail,
                    matrix=matrix,
                    min_base_quality=params.min_base_quality,
                    pileups=pileups,
                    coverage=coverage,
                )
                if placed:
                    n_aligned += 1

        _log(
            log,
            f"Aligned {n_aligned}/{n_total} reads to {len(refs)} reference sequence(s).",
        )

        variants = self._call_variants(refs=refs, pileups=pileups, coverage=coverage, params=params)

        out_vcf = out_dir / f"{sample}.vcf"
        contigs = {sid: len(seq) for sid, seq in refs.items()}
        vcf.write_vcf(
            variants,
            out_vcf,
            reference_name=reference.name,
            sample=sample,
            contigs=contigs,
        )
        _log(log, f"Called {len(variants)} variant(s); wrote {out_vcf.name}.")

        modal = seqio.modal_read_length(reads_for_modal)
        return CallResult(vcf=out_vcf, modal_read_length=modal, n_variants=len(variants))

    def _align_read(
        self,
        *,
        seq: str,
        quals: Optional[str],
        index: _ReferenceIndex,
        parasail,  # noqa: ANN001 - module type, kept loose to avoid hard import
        matrix,  # noqa: ANN001
        min_base_quality: int,
        pileups: dict[str, np.ndarray],
        coverage: dict[str, np.ndarray],
    ) -> bool:
        """Seed, align (best of forward/reverse-complement) and tally one read.

        Returns True if the read was placed and contributed to the pileup.
        """
        seq_u = seq.upper()
        fwd_seed = index.seed(seq_u)
        rc_seq = _revcomp(seq_u)
        rc_seed = index.seed(rc_seq)

        # Pick the orientation with the stronger seed support.
        fwd_votes = fwd_seed[2] if fwd_seed else 0
        rc_votes = rc_seed[2] if rc_seed else 0
        if fwd_votes == 0 and rc_votes == 0:
            return False
        if rc_votes > fwd_votes:
            chosen_seq, chosen_quals, seed = rc_seq, (quals[::-1] if quals else None), rc_seed
        else:
            chosen_seq, chosen_quals, seed = seq_u, quals, fwd_seed

        assert seed is not None
        seq_id, ref_start, _votes = seed
        ref_seq = index.sequences[seq_id]

        # Carve a padded window of the reference around the seeded start.
        win_start = max(0, ref_start - _WINDOW_PAD)
        win_end = min(len(ref_seq), ref_start + len(chosen_seq) + _WINDOW_PAD)
        window = ref_seq[win_start:win_end]
        if not window:
            return False

        result = parasail.sg_trace_striped_16(
            chosen_seq, window, _GAP_OPEN, _GAP_EXTEND, matrix
        )
        cigar = result.cigar
        raw_ops = _parse_cigar(cigar.decode)
        ref_offset, read_offset, ops = _split_cigar_core(raw_ops)
        if not ops:
            return False

        # Walk the core CIGAR, accumulating per-reference-position observations.
        # Leading reference/read end-gaps (semi-global flanks) are skipped via the
        # offsets so the read aligns to the correct contig coordinate.
        ref_pos = win_start + cigar.beg_ref + ref_offset  # 0-based into the full contig
        read_pos = cigar.beg_query + read_offset
        pile = pileups[seq_id]
        cov = coverage[seq_id]
        contig_len = len(ref_seq)

        for length, op in ops:
            if op in ("=", "X", "M"):
                for _ in range(length):
                    if 0 <= ref_pos < contig_len and read_pos < len(chosen_seq):
                        base = chosen_seq[read_pos]
                        col = _BASE_TO_COL.get(base)
                        q = _qual_at(chosen_quals, read_pos)
                        if col is not None and (q is None or q >= min_base_quality):
                            pile[ref_pos, col] += 1
                            cov[ref_pos] += 1
                    ref_pos += 1
                    read_pos += 1
            elif op == "D":
                # Deletion from the read relative to the reference.
                for _ in range(length):
                    if 0 <= ref_pos < contig_len:
                        pile[ref_pos, _DEL_COL] += 1
                        cov[ref_pos] += 1
                    ref_pos += 1
            elif op == "I":
                # Insertion in the read; consumes read bases only. The builtin
                # caller does not emit insertions, so advance past them.
                read_pos += length
            # Any other op (e.g. soft clip 'S') consumes nothing here.
        return True

    @staticmethod
    def _call_variants(
        *,
        refs: dict[str, str],
        pileups: dict[str, np.ndarray],
        coverage: dict[str, np.ndarray],
        params: VariantParams,
    ) -> list[vcf.Variant]:
        """Frequency pileup caller.

        For each reference position with depth >= ``min_depth``, emit a
        :class:`~metagaap2.vcf.Variant` for every ALT allele (substitution or
        deletion) whose fraction of the depth is >= ``min_alt_fraction``. ``AF``
        (highest qualifying ALT fraction) and ``DP`` (depth) are stored in INFO.
        """
        variants: list[vcf.Variant] = []
        for seq_id, ref_seq in refs.items():
            pile = pileups[seq_id]
            cov = coverage[seq_id]
            ref_upper = ref_seq.upper()
            for pos in range(len(ref_upper)):
                depth = int(cov[pos])
                if depth < params.min_depth:
                    continue
                ref_base = ref_upper[pos]
                ref_col = _BASE_TO_COL.get(ref_base)

                alts: list[str] = []
                best_af = 0.0
                # Substitution alleles.
                for col in range(4):
                    if col == ref_col:
                        continue
                    count = int(pile[pos, col])
                    if count <= 0:
                        continue
                    af = count / depth
                    if af >= params.min_alt_fraction:
                        alts.append(_COL_TO_BASE[col])
                        best_af = max(best_af, af)
                # Deletion allele (represented as ref-base anchor -> empty is not
                # valid VCF, so we emit the upstream-anchored form REF=Xb ALT=X).
                del_count = int(pile[pos, _DEL_COL])
                if del_count > 0:
                    del_af = del_count / depth
                    if del_af >= params.min_alt_fraction and pos > 0:
                        anchor = ref_upper[pos - 1]
                        variants.append(
                            vcf.Variant(
                                chrom=seq_id,
                                pos=pos,  # 1-based position of the anchor (pos-1) + 1
                                ref=f"{anchor}{ref_base}",
                                alts=[anchor],
                                info={
                                    "AF": f"{del_af:.4f}",
                                    "DP": str(depth),
                                    "TYPE": "del",
                                },
                            )
                        )
                        best_af = max(best_af, del_af)

                if alts:
                    variants.append(
                        vcf.Variant(
                            chrom=seq_id,
                            pos=pos + 1,  # VCF is 1-based
                            ref=ref_base,
                            alts=alts,
                            info={"AF": f"{best_af:.4f}", "DP": str(depth)},
                        )
                    )
        variants.sort(key=lambda v: (v.chrom, v.pos))
        return variants

    # ----------------------------------------------------------------------- #
    # Stage 3: map + count
    # ----------------------------------------------------------------------- #
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

        Builds a k-mer index of the targets; each read is assigned to the target
        sharing the most distinct k-mers. When ``params.min_identity`` > 0 the
        assignment is verified with a ``parasail`` semi-global alignment and only
        counted if the read-to-target identity meets the threshold. Writes a
        stats CSV (``Sequence,Length,Mapped_Reads``).
        """
        target_fasta = Path(target_fasta)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        targets = seqio.read_fasta(target_fasta)
        counts: dict[str, int] = {sid: 0 for sid in targets}
        if not targets:
            stats_csv = self._write_stats_csv(out_dir, sample, targets, counts)
            _log(log, "Target FASTA was empty; no reads counted.")
            return CountResult(counts=counts, stats_csv=stats_csv)

        index = _ReferenceIndex(targets, k=_KMER)

        verify = params.min_identity > 0.0
        parasail = None
        matrix = None
        if verify:
            parasail = _import_parasail()
            matrix = parasail.matrix_create("ACGT", _MATCH, _MISMATCH)

        read_files = [p for p in (r1, r2) if p is not None]
        n_assigned = 0
        n_total = 0
        for read_file in read_files:
            for _name, seq, _quals in seqio.iter_fastq(read_file):
                n_total += 1
                if not seq:
                    continue
                target_id = self._assign_read(
                    seq=seq,
                    index=index,
                    targets=targets,
                    verify=verify,
                    parasail=parasail,
                    matrix=matrix,
                    min_identity=params.min_identity,
                )
                if target_id is not None:
                    counts[target_id] += 1
                    n_assigned += 1

        stats_csv = self._write_stats_csv(out_dir, sample, targets, counts)
        _log(
            log,
            f"Assigned {n_assigned}/{n_total} reads across {len(targets)} target(s); "
            f"wrote {stats_csv.name}.",
        )
        return CountResult(counts=counts, stats_csv=stats_csv)

    @staticmethod
    def _assign_read(
        *,
        seq: str,
        index: _ReferenceIndex,
        targets: dict[str, str],
        verify: bool,
        parasail,  # noqa: ANN001
        matrix,  # noqa: ANN001
        min_identity: float,
    ) -> Optional[str]:
        """Assign a single read to its best target (forward or reverse strand)."""
        seq_u = seq.upper()
        rc_seq = _revcomp(seq_u)

        fwd = index.best_target(seq_u)
        rc = index.best_target(rc_seq)
        fwd_kmers = fwd[1] if fwd else 0
        rc_kmers = rc[1] if rc else 0
        if fwd_kmers == 0 and rc_kmers == 0:
            return None
        if rc_kmers > fwd_kmers:
            best, chosen = rc, rc_seq
        else:
            best, chosen = fwd, seq_u
        assert best is not None
        target_id = best[0]

        if not verify:
            return target_id

        identity = PortableEngine._semiglobal_identity(
            read=chosen,
            reference=targets[target_id].upper(),
            parasail=parasail,
            matrix=matrix,
        )
        if identity >= min_identity:
            return target_id
        return None

    @staticmethod
    def _semiglobal_identity(
        *,
        read: str,
        reference: str,
        parasail,  # noqa: ANN001
        matrix,  # noqa: ANN001
    ) -> float:
        """Fraction of aligned columns that are matches in a semi-global alignment.

        Identity is ``matches / aligned_length`` over the CIGAR, where
        ``aligned_length`` counts every match, mismatch and indel column. Returns
        ``0.0`` for an empty alignment.
        """
        if not read or not reference:
            return 0.0
        result = parasail.sg_trace_striped_16(read, reference, _GAP_OPEN, _GAP_EXTEND, matrix)
        raw_ops = _parse_cigar(result.cigar.decode)
        # Strip semi-global reference end-gaps: only the spanned region counts, so
        # a read that is a clean substring of a longer target scores 1.0.
        _ref_off, _read_off, ops = _split_cigar_core(raw_ops)
        matches = 0
        aligned = 0
        for length, op in ops:
            if op == "=":
                matches += length
                aligned += length
            elif op in ("X", "M", "I", "D"):
                aligned += length
        if aligned == 0:
            return 0.0
        return matches / aligned

    @staticmethod
    def _write_stats_csv(
        out_dir: Path,
        sample: str,
        targets: dict[str, str],
        counts: dict[str, int],
    ) -> Path:
        """Write a ``Sequence,Length,Mapped_Reads`` CSV and return its path."""
        stats_csv = out_dir / f"{sample}.stats.csv"
        lines = ["Sequence,Length,Mapped_Reads"]
        for seq_id, seq in targets.items():
            lines.append(f"{seq_id},{len(seq)},{counts.get(seq_id, 0)}")
        stats_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return stats_csv
