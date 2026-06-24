"""Tests for :mod:`metagaap2.haplotypes` - combinatorial haplotype generation.

Covers the pure generator core (a two-SNP window yielding all four
combinations including wild-type; the ``max_variants`` skip; the
``max_haplotypes`` cap; correct application of a length-changing indel allele)
and the database builder round-trip (record count + ``>{sample}_{i}`` renaming)
on a tiny reference + VCF in ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from metagaap2.haplotypes import (
    build_haplotype_database,
    generate_window_haplotypes,
)
from metagaap2.models import HaplotypeParams
from metagaap2.seqio import read_fasta


# --------------------------------------------------------------------------- #
# Overlapping deletion + SNP: documented best-effort (lossy) behaviour, locked.
# --------------------------------------------------------------------------- #
def test_overlapping_deletion_and_snp_is_lossy_but_safe() -> None:
    """A deletion whose REF span covers a SNP collapses some combinations.

    Reference 'ACGT' with a 2-base deletion at offset 1 (REF 'CG' -> 'C') and a
    SNP at offset 2 (REF 'G' -> 'A'): the deletion's REF span (offsets 1-2)
    overlaps the SNP, so picking the deletion site's REF allele rewrites the SNP.
    The result is a safe (never corrupt) but under-counted set. This locks the
    documented limitation so any change to the policy is deliberate.
    """
    haps = set(
        generate_window_haplotypes(
            "ACGT",
            [(1, ["CG", "C"]), (2, ["G", "A"])],
            max_variants=12,
            max_haplotypes=1024,
        )
    )
    assert haps == {"ACGT", "ACT"}


# --------------------------------------------------------------------------- #
# (1) Two-SNP window -> 4 distinct haplotypes including wild-type
# --------------------------------------------------------------------------- #
def test_two_snp_window_yields_four_haplotypes() -> None:
    """Two biallelic SNP sites give 2 x 2 = 4 distinct sequences, incl. wild-type."""
    ref_window = "ACGTACGT"
    # Site at offset 1 (REF C -> ALT T); site at offset 5 (REF C -> ALT A).
    sites = [
        (1, ["C", "T"]),
        (5, ["C", "A"]),
    ]
    haps = list(
        generate_window_haplotypes(
            ref_window, sites, max_variants=10, max_haplotypes=1024
        )
    )

    assert len(haps) == 4
    assert len(set(haps)) == 4
    # Wild-type is always represented (all-REF combination).
    assert ref_window in haps
    # The four expected combinations.
    assert set(haps) == {
        "ACGTACGT",  # ref/ref
        "ATGTACGT",  # alt/ref  (offset 1 -> T)
        "ACGTAAGT",  # ref/alt  (offset 5 -> A)
        "ATGTAAGT",  # alt/alt
    }


def test_no_variants_yields_only_wild_type() -> None:
    """A window with no sites emits exactly the unaltered reference window."""
    haps = list(
        generate_window_haplotypes(
            "ACGTACGT", [], max_variants=10, max_haplotypes=1024
        )
    )
    assert haps == ["ACGTACGT"]


def test_multi_allelic_site_expands_alts() -> None:
    """A site offering REF + two ALTs contributes three choices."""
    haps = list(
        generate_window_haplotypes(
            "ACGT", [(0, ["A", "G", "T"])], max_variants=10, max_haplotypes=1024
        )
    )
    assert set(haps) == {"ACGT", "GCGT", "TCGT"}


# --------------------------------------------------------------------------- #
# (2) max_variants skip
# --------------------------------------------------------------------------- #
def test_max_variants_skips_dense_window() -> None:
    """A window with more sites than ``max_variants`` emits nothing."""
    sites = [
        (0, ["A", "G"]),
        (1, ["C", "T"]),
        (2, ["G", "A"]),
    ]
    haps = list(
        generate_window_haplotypes(
            "ACGT", sites, max_variants=2, max_haplotypes=1024
        )
    )
    assert haps == []


def test_at_variant_limit_is_not_skipped() -> None:
    """Exactly ``max_variants`` sites are allowed (skip is strictly greater-than)."""
    sites = [
        (0, ["A", "G"]),
        (2, ["G", "A"]),
    ]
    haps = list(
        generate_window_haplotypes(
            "ACGT", sites, max_variants=2, max_haplotypes=1024
        )
    )
    assert len(haps) == 4


# --------------------------------------------------------------------------- #
# (3) max_haplotypes cap
# --------------------------------------------------------------------------- #
def test_max_haplotypes_caps_emitted_combinations() -> None:
    """The number emitted is capped by ``max_haplotypes`` (islice over product)."""
    # Three biallelic sites -> 8 possible combinations; cap at 3.
    sites = [
        (0, ["A", "G"]),
        (1, ["C", "T"]),
        (2, ["G", "A"]),
    ]
    haps = list(
        generate_window_haplotypes(
            "ACGT", sites, max_variants=10, max_haplotypes=3
        )
    )
    assert len(haps) == 3
    # The first emitted combination is the all-REF wild-type.
    assert "ACGT" in haps


# --------------------------------------------------------------------------- #
# (4) length-changing (indel) allele applied correctly
# --------------------------------------------------------------------------- #
def test_insertion_allele_lengthens_sequence() -> None:
    """An insertion ALT (longer than its REF) is spliced in length-aware."""
    # REF window "ACGT"; at offset 1 the single-base REF "C" -> "CTT" (insertion).
    haps = list(
        generate_window_haplotypes(
            "ACGT", [(1, ["C", "CTT"])], max_variants=10, max_haplotypes=1024
        )
    )
    assert set(haps) == {"ACGT", "ACTTGT"}


def test_deletion_allele_shortens_sequence() -> None:
    """A deletion (REF spans 2 bp, ALT is 1 bp) removes the right base."""
    # REF window "ACGT"; at offset 1 the 2-base REF "CG" -> "C" (deletes the G).
    haps = list(
        generate_window_haplotypes(
            "ACGT", [(1, ["CG", "C"])], max_variants=10, max_haplotypes=1024
        )
    )
    assert set(haps) == {"ACGT", "ACT"}


def test_indel_and_snp_apply_independently_right_to_left() -> None:
    """A leftward insertion and a rightward SNP both apply without corrupting offsets.

    Applying right-to-left is essential here: the insertion at offset 1 changes
    the sequence length, but because the offset-6 SNP is applied first (it is
    further right), the insertion's offset is still valid when it is applied.
    """
    ref_window = "ACGTACGT"
    sites = [
        (1, ["C", "CTT"]),  # insertion near the left
        (6, ["G", "A"]),  # SNP near the right
    ]
    haps = list(
        generate_window_haplotypes(
            ref_window, sites, max_variants=10, max_haplotypes=1024
        )
    )
    assert set(haps) == {
        "ACGTACGT",  # ref / ref
        "ACTTGTACGT",  # ins / ref
        "ACGTACAT",  # ref / snp  (offset 6 G -> A)
        "ACTTGTACAT",  # ins / snp
    }


def test_indel_clamped_to_window_right_edge() -> None:
    """An allele whose REF span runs past the window end is clamped, not out of bounds.

    The window is "ACG" (3 bp) but the site at offset 2 declares a 2-base REF
    "GT" that overruns the right edge by one base. The replaced span is clamped
    to ``window[2:3]`` ("G"). The REF choice writes the full 2-base allele back
    ("ACGT"); the ALT choice "G" writes a single base ("ACG"). No index error is
    raised and both sequences stay well-formed.
    """
    haps = list(
        generate_window_haplotypes(
            "ACG", [(2, ["GT", "G"])], max_variants=10, max_haplotypes=1024
        )
    )
    assert haps == ["ACGT", "ACG"]


# --------------------------------------------------------------------------- #
# (5) build_haplotype_database round-trip on a tiny ref + VCF
# --------------------------------------------------------------------------- #
def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_build_database_round_trip(tmp_path: Path) -> None:
    """End-to-end: tiny ref + VCF -> unique records renamed ``>{sample}_{i}``."""
    ref = tmp_path / "ref.fasta"
    _write(ref, ">contig1\nACGTACGT\n")

    vcf = tmp_path / "calls.vcf"
    # Two SNPs inside a single 8 bp window: pos 2 (C->T) and pos 6 (C->A).
    _write(
        vcf,
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "contig1\t2\t.\tC\tT\t50\tPASS\t.\n"
        "contig1\t6\t.\tC\tA\t50\tPASS\t.\n",
    )

    out = tmp_path / "haplotypes" / "S1_db.fasta"
    params = HaplotypeParams(window=8, step=8)

    n = build_haplotype_database(
        ref, vcf, out, params, sample="S1", default_window=8
    )

    # 2 x 2 = 4 distinct haplotypes, including wild-type.
    assert n == 4
    assert out.exists()

    records = read_fasta(out)
    assert len(records) == 4
    # Records are renamed >S1_1 .. >S1_4 (i from 1).
    assert set(records) == {"S1_1", "S1_2", "S1_3", "S1_4"}
    # Wild-type window must be present.
    assert "ACGTACGT" in records.values()
    # Both alternate alleles appear among the emitted sequences.
    assert "ATGTACGT" in records.values()
    assert "ACGTAAGT" in records.values()
    assert "ATGTAAGT" in records.values()


def test_build_database_default_window(tmp_path: Path) -> None:
    """``params.window is None`` falls back to ``default_window``."""
    ref = tmp_path / "ref.fasta"
    _write(ref, ">c\nACGTACGTAC\n")  # 10 bp
    vcf = tmp_path / "empty.vcf"
    _write(vcf, "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n")

    out = tmp_path / "db.fasta"
    params = HaplotypeParams(window=None, step=None)

    # default_window 5, non-overlapping step -> two wild-type windows.
    n = build_haplotype_database(
        ref, vcf, out, params, sample="WT", default_window=5
    )
    records = read_fasta(out)
    assert n == 2
    assert set(records) == {"WT_1", "WT_2"}
    assert set(records.values()) == {"ACGTA", "CGTAC"}


def test_build_database_missing_vcf_yields_reference_windows(tmp_path: Path) -> None:
    """A non-existent VCF yields only the plain reference windows (wild-type)."""
    ref = tmp_path / "ref.fasta"
    _write(ref, ">c\nACGTACGT\n")
    out = tmp_path / "db.fasta"
    params = HaplotypeParams(window=8, step=8)

    n = build_haplotype_database(
        ref,
        tmp_path / "does_not_exist.vcf",
        out,
        params,
        sample="X",
        default_window=8,
    )
    records = read_fasta(out)
    assert n == 1
    assert records == {"X_1": "ACGTACGT"}


def test_build_database_dedupes_across_windows(tmp_path: Path) -> None:
    """Identical sequences emitted from different windows are written only once."""
    ref = tmp_path / "ref.fasta"
    # Two identical 4 bp halves -> non-overlapping windows produce the same seq.
    _write(ref, ">c\nACGTACGT\n")
    vcf = tmp_path / "empty.vcf"
    _write(vcf, "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\n")

    out = tmp_path / "db.fasta"
    params = HaplotypeParams(window=4, step=4)

    n = build_haplotype_database(
        ref, vcf, out, params, sample="D", default_window=4
    )
    records = read_fasta(out)
    assert n == 1
    assert records == {"D_1": "ACGT"}
