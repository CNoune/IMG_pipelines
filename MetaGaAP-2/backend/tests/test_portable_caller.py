"""Tests for :mod:`metagaap2.engines.portable` - the pure-Python engine.

These exercise the two pure-Python compute stages on tiny synthetic data:

* ``align_and_call`` must call a known SNP carried by simulated reads against a
  small reference, and must *not* call sites that are uniformly reference.
* ``map_and_count`` must assign reads to the contig they were drawn from.

The heavy lifting depends on ``parasail`` and ``numpy`` wheels, so both are
``importorskip``-ed: on a machine without them the tests skip rather than fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("parasail")
pytest.importorskip("numpy")
pytest.importorskip("dnaio")

from metagaap2.engines.portable import PortableEngine  # noqa: E402
from metagaap2.models import (  # noqa: E402
    ConfirmParams,
    ReadGroup,
    VariantParams,
)
from metagaap2.vcf import read_vcf  # noqa: E402

# --------------------------------------------------------------------------- #
# Synthetic data
# --------------------------------------------------------------------------- #
# A 120 bp reference with no internal repeats so k-mer seeding is unambiguous.
_REFERENCE = (
    "ACGTTGCAACGTGCATTAGCCGGATCATGACTGACTTGCAACCTTGGAACCGGTTAACCGGT"
    "TACGATCGATCGTAGCTAGCATCGATCGTAGCTTACGATCAGCTAGCATGCATCGATGCATC"
)

# The SNP we plant: reference base at 0-based position 63 (an 'A') mutated to a
# 'C'. We pick a position comfortably inside the sequence so reads fully span it.
_SNP_POS0 = 63
_SNP_ALT = "C"


def _mutate(seq: str, pos0: int, base: str) -> str:
    return seq[:pos0] + base + seq[pos0 + 1 :]


def _write_fastq(path: Path, reads: list[tuple[str, str]]) -> None:
    """Write ``(name, sequence)`` reads to a plain FASTQ with all-high quality."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for name, seq in reads:
            handle.write(f"@{name}\n{seq}\n+\n{'I' * len(seq)}\n")


def _write_fasta(path: Path, records: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for name, seq in records:
            handle.write(f">{name}\n{seq}\n")


# --------------------------------------------------------------------------- #
# align_and_call
# --------------------------------------------------------------------------- #
def test_align_and_call_finds_planted_snp(tmp_path: Path) -> None:
    """A homogeneous A->G SNP carried by every read must be called."""
    ref_fa = tmp_path / "ref.fa"
    _write_fasta(ref_fa, [("contig1", _REFERENCE)])

    snp_base = _SNP_ALT
    assert _REFERENCE[_SNP_POS0] == "A"
    mutated = _mutate(_REFERENCE, _SNP_POS0, snp_base)

    # 40 reads, each an 80 bp window that fully spans the SNP site.
    reads: list[tuple[str, str]] = []
    read_len = 80
    start = _SNP_POS0 - 30
    for i in range(40):
        reads.append((f"read{i}", mutated[start : start + read_len]))
    r1 = tmp_path / "reads.fastq"
    _write_fastq(r1, reads)

    engine = PortableEngine()
    result = engine.align_and_call(
        r1=r1,
        r2=None,
        reference=ref_fa,
        read_group=ReadGroup(sample="S1"),
        params=VariantParams(min_depth=5, min_alt_fraction=0.2, min_base_quality=20),
        out_dir=tmp_path / "out",
        sample="S1",
    )

    assert result.vcf.exists()
    assert result.modal_read_length == read_len
    assert result.n_variants >= 1

    variants = read_vcf(result.vcf)
    snp_calls = [
        v
        for v in variants
        if v.chrom == "contig1" and v.pos == _SNP_POS0 + 1 and snp_base in v.alts
    ]
    assert snp_calls, f"Planted SNP not called. Got: {[(v.pos, v.ref, v.alts) for v in variants]}"

    call = snp_calls[0]
    assert call.ref == "A"
    assert call.alts == [snp_base]
    # The SNP is fixed in every read, so AF should be close to 1.0.
    assert float(call.info["AF"]) > 0.9
    assert int(call.info["DP"]) >= 5


def test_align_and_call_no_false_positive_on_clean_reads(tmp_path: Path) -> None:
    """Reads identical to the reference must yield no variant calls."""
    ref_fa = tmp_path / "ref.fa"
    _write_fasta(ref_fa, [("contig1", _REFERENCE)])

    reads = [(f"read{i}", _REFERENCE[10:90]) for i in range(30)]
    r1 = tmp_path / "clean.fastq"
    _write_fastq(r1, reads)

    engine = PortableEngine()
    result = engine.align_and_call(
        r1=r1,
        r2=None,
        reference=ref_fa,
        read_group=ReadGroup(sample="S1"),
        params=VariantParams(min_depth=5, min_alt_fraction=0.1),
        out_dir=tmp_path / "out",
        sample="S1",
    )
    assert result.n_variants == 0
    assert read_vcf(result.vcf) == []


def test_align_and_call_low_frequency_variant(tmp_path: Path) -> None:
    """A minority allele above min_alt_fraction is called (quasispecies case)."""
    ref_fa = tmp_path / "ref.fa"
    _write_fasta(ref_fa, [("contig1", _REFERENCE)])

    mutated = _mutate(_REFERENCE, _SNP_POS0, _SNP_ALT)
    window_start = _SNP_POS0 - 30
    read_len = 80
    reads: list[tuple[str, str]] = []
    # 90 reference reads + 10 mutant reads -> ~10% ALT fraction.
    for i in range(90):
        reads.append((f"ref{i}", _REFERENCE[window_start : window_start + read_len]))
    for i in range(10):
        reads.append((f"mut{i}", mutated[window_start : window_start + read_len]))
    r1 = tmp_path / "mixed.fastq"
    _write_fastq(r1, reads)

    engine = PortableEngine()
    result = engine.align_and_call(
        r1=r1,
        r2=None,
        reference=ref_fa,
        read_group=ReadGroup(sample="S1"),
        params=VariantParams(min_depth=10, min_alt_fraction=0.05),
        out_dir=tmp_path / "out",
        sample="S1",
    )
    variants = read_vcf(result.vcf)
    snp = [v for v in variants if v.pos == _SNP_POS0 + 1 and _SNP_ALT in v.alts]
    assert snp, "Low-frequency SNP not called"
    af = float(snp[0].info["AF"])
    assert 0.05 <= af <= 0.2


# --------------------------------------------------------------------------- #
# map_and_count
# --------------------------------------------------------------------------- #
def test_map_and_count_assigns_to_correct_contig(tmp_path: Path) -> None:
    """Reads drawn from each target are recruited to that target."""
    contig_a = _REFERENCE
    contig_b = (
        "TTTTGGGGCCCCAAAATTTTGGGGCCCCAAAAGCGCGCGCATATATATCGCGCGCGTATATA"
        "GCATGCATGCATGCATTAGCTAGCTAGCTAGCATCGATCGGATCGGATCGGCATCGATCGGA"
    )
    targets_fa = tmp_path / "targets.fa"
    _write_fasta(targets_fa, [("A", contig_a), ("B", contig_b)])

    reads: list[tuple[str, str]] = []
    for i in range(20):
        reads.append((f"a{i}", contig_a[5 + i : 5 + i + 70]))
    for i in range(15):
        reads.append((f"b{i}", contig_b[5 + i : 5 + i + 70]))
    r1 = tmp_path / "reads.fastq"
    _write_fastq(r1, reads)

    engine = PortableEngine()
    result = engine.map_and_count(
        r1=r1,
        r2=None,
        target_fasta=targets_fa,
        params=ConfirmParams(min_identity=0.9, min_mapped_reads=1),
        out_dir=tmp_path / "out",
        sample="S1",
    )

    assert result.counts["A"] == 20
    assert result.counts["B"] == 15
    assert result.stats_csv is not None and result.stats_csv.exists()

    csv_text = result.stats_csv.read_text(encoding="utf-8")
    assert csv_text.splitlines()[0] == "Sequence,Length,Mapped_Reads"
    assert f"A,{len(contig_a)},20" in csv_text
    assert f"B,{len(contig_b)},15" in csv_text


def test_map_and_count_reverse_complement_reads(tmp_path: Path) -> None:
    """Reverse-complement reads are still assigned to their source contig."""
    from metagaap2.engines.portable import _revcomp

    targets_fa = tmp_path / "targets.fa"
    _write_fasta(targets_fa, [("A", _REFERENCE)])

    reads = [(f"rc{i}", _revcomp(_REFERENCE[5 + i : 5 + i + 70])) for i in range(12)]
    r1 = tmp_path / "rc.fastq"
    _write_fastq(r1, reads)

    engine = PortableEngine()
    result = engine.map_and_count(
        r1=r1,
        r2=None,
        target_fasta=targets_fa,
        params=ConfirmParams(min_identity=0.9, min_mapped_reads=1),
        out_dir=tmp_path / "out",
        sample="S1",
    )
    assert result.counts["A"] == 12


def test_map_and_count_unmatched_reads_not_counted(tmp_path: Path) -> None:
    """Reads sharing no k-mers with any target are dropped."""
    targets_fa = tmp_path / "targets.fa"
    _write_fasta(targets_fa, [("A", _REFERENCE)])

    junk = "N" * 70  # all-ambiguous -> no valid k-mers
    foreign = "AAAAAAAAAACCCCCCCCCCGGGGGGGGGGTTTTTTTTTTACACACACACGTGTGTGTGT"
    reads = [("junk", junk), ("foreign", foreign)]
    r1 = tmp_path / "nomatch.fastq"
    _write_fastq(r1, reads)

    engine = PortableEngine()
    result = engine.map_and_count(
        r1=r1,
        r2=None,
        target_fasta=targets_fa,
        params=ConfirmParams(min_identity=0.95, min_mapped_reads=1),
        out_dir=tmp_path / "out",
        sample="S1",
    )
    assert result.counts["A"] == 0


# --------------------------------------------------------------------------- #
# detect / capabilities
# --------------------------------------------------------------------------- #
def test_detect_reports_available() -> None:
    caps = PortableEngine.detect()
    assert caps.available is True
    assert caps.key.value == "portable"
    from metagaap2.models import Aligner, VariantCaller

    assert Aligner.BUILTIN in caps.aligners
    assert VariantCaller.BUILTIN in caps.callers
