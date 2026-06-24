"""Tests for :mod:`metagaap2.vcf` - the minimal VCF reader/writer.

Covers the write/read round-trip, multi-allelic ALT splitting, the ``is_snp``
property, header/contig emission, tolerance of missing optional columns, and
contig grouping/sorting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from metagaap2.vcf import (
    Variant,
    read_vcf,
    variants_by_contig,
    write_vcf,
)


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #
def test_write_read_round_trip(tmp_path: Path) -> None:
    """Variants survive a write -> read cycle unchanged in the fields we model."""
    variants = [
        Variant(chrom="chr1", pos=100, ref="A", alts=["G"], qual=37.0, info={"DP": "50", "AF": "0.30"}),
        Variant(chrom="chr1", pos=250, ref="C", alts=["T"], qual=None, info={}, filter="PASS"),
        Variant(chrom="chr2", pos=10, ref="GG", alts=["G"], qual=12.5, info={"INDEL": ""}),
    ]
    out = tmp_path / "round_trip.vcf"

    written = write_vcf(variants, out, reference_name="ref.fa")
    assert written == 3

    loaded = read_vcf(out)
    assert len(loaded) == 3

    assert loaded[0].chrom == "chr1"
    assert loaded[0].pos == 100
    assert loaded[0].ref == "A"
    assert loaded[0].alts == ["G"]
    assert loaded[0].qual == 37.0
    assert loaded[0].info == {"DP": "50", "AF": "0.30"}
    assert loaded[0].filter == "PASS"

    # QUAL "." round-trips to None.
    assert loaded[1].qual is None

    # A bare INFO flag round-trips to an empty-string value.
    assert loaded[2].info == {"INDEL": ""}
    assert loaded[2].qual == 12.5


def test_output_has_required_headers(tmp_path: Path) -> None:
    """The writer emits ##fileformat and a #CHROM header line."""
    out = tmp_path / "headers.vcf"
    write_vcf([Variant(chrom="c", pos=1, ref="A", alts=["T"])], out)
    text = out.read_text(encoding="utf-8")

    assert text.startswith("##fileformat=VCFv4.2")
    header_lines = [ln for ln in text.splitlines() if ln.startswith("#CHROM")]
    assert len(header_lines) == 1
    assert header_lines[0].split("\t")[:8] == [
        "#CHROM",
        "POS",
        "ID",
        "REF",
        "ALT",
        "QUAL",
        "FILTER",
        "INFO",
    ]


# --------------------------------------------------------------------------- #
# Multi-allelic splitting
# --------------------------------------------------------------------------- #
def test_multi_allelic_split_on_read(tmp_path: Path) -> None:
    """A comma-separated ALT field is split into a list of alleles on read."""
    out = tmp_path / "multi.vcf"
    out.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr1\t500\t.\tA\tG,T,C\t60\tPASS\tDP=99\n",
        encoding="utf-8",
    )

    loaded = read_vcf(out)
    assert len(loaded) == 1
    assert loaded[0].alts == ["G", "T", "C"]


def test_multi_allelic_round_trip(tmp_path: Path) -> None:
    """Multi-allelic alts are joined with commas on write and split back on read."""
    out = tmp_path / "multi_rt.vcf"
    write_vcf([Variant(chrom="chr1", pos=7, ref="A", alts=["G", "T"])], out)

    body = [ln for ln in out.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    assert len(body) == 1
    assert body[0].split("\t")[4] == "G,T"

    loaded = read_vcf(out)
    assert loaded[0].alts == ["G", "T"]


# --------------------------------------------------------------------------- #
# is_snp property
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("ref", "alts", "expected"),
    [
        ("A", ["G"], True),
        ("A", ["G", "T"], True),
        ("AT", ["G"], False),  # MNP / multi-base ref
        ("A", ["GT"], False),  # insertion
        ("GG", ["G"], False),  # deletion
        ("A", [], False),  # no concrete alt
        ("A", ["."], False),  # missing alt only
    ],
)
def test_is_snp(ref: str, alts: list[str], expected: bool) -> None:
    var = Variant(chrom="c", pos=1, ref=ref, alts=alts)
    assert var.is_snp is expected


# --------------------------------------------------------------------------- #
# Contig + sample columns
# --------------------------------------------------------------------------- #
def test_write_contig_lines(tmp_path: Path) -> None:
    out = tmp_path / "contigs.vcf"
    write_vcf(
        [Variant(chrom="chr1", pos=1, ref="A", alts=["T"])],
        out,
        contigs={"chr1": 1000, "chr2": 2000},
    )
    text = out.read_text(encoding="utf-8")
    assert "##contig=<ID=chr1,length=1000>" in text
    assert "##contig=<ID=chr2,length=2000>" in text


def test_write_with_sample_column(tmp_path: Path) -> None:
    """When a sample is named, FORMAT + sample columns appear and rows still parse."""
    out = tmp_path / "sample.vcf"
    write_vcf(
        [Variant(chrom="chr1", pos=1, ref="A", alts=["T"], qual=20.0)],
        out,
        sample="S1",
    )
    text = out.read_text(encoding="utf-8")
    header = [ln for ln in text.splitlines() if ln.startswith("#CHROM")][0]
    assert header.split("\t")[-2:] == ["FORMAT", "S1"]

    # Sample columns are ignored on read; the core record is still recovered.
    loaded = read_vcf(out)
    assert len(loaded) == 1
    assert loaded[0].alts == ["T"]
    assert loaded[0].qual == 20.0


# --------------------------------------------------------------------------- #
# Tolerance of missing / malformed columns
# --------------------------------------------------------------------------- #
def test_read_tolerates_missing_optional_columns(tmp_path: Path) -> None:
    """Records with only the five mandatory columns still load with sane defaults."""
    out = tmp_path / "minimal.vcf"
    out.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\n"
        "chr1\t42\t.\tA\tG\n",
        encoding="utf-8",
    )
    loaded = read_vcf(out)
    assert len(loaded) == 1
    v = loaded[0]
    assert (v.chrom, v.pos, v.ref, v.alts) == ("chr1", 42, "A", ["G"])
    assert v.qual is None
    assert v.filter == "PASS"
    assert v.info == {}


def test_read_skips_blank_and_malformed_lines(tmp_path: Path) -> None:
    """Blank lines, short rows and non-integer POS are skipped, not fatal."""
    out = tmp_path / "messy.vcf"
    out.write_text(
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\n"
        "\n"
        "chr1\tNOT_A_NUMBER\t.\tA\tG\n"
        "chr1\t10\n"  # too few columns
        "chr1\t20\t.\tA\tT\n",
        encoding="utf-8",
    )
    loaded = read_vcf(out)
    assert len(loaded) == 1
    assert loaded[0].pos == 20


# --------------------------------------------------------------------------- #
# Grouping
# --------------------------------------------------------------------------- #
def test_variants_by_contig_sorted() -> None:
    variants = [
        Variant(chrom="chr2", pos=300, ref="A", alts=["G"]),
        Variant(chrom="chr1", pos=200, ref="A", alts=["G"]),
        Variant(chrom="chr1", pos=50, ref="A", alts=["G"]),
        Variant(chrom="chr2", pos=10, ref="A", alts=["G"]),
    ]
    grouped = variants_by_contig(variants)

    assert set(grouped) == {"chr1", "chr2"}
    assert [v.pos for v in grouped["chr1"]] == [50, 200]
    assert [v.pos for v in grouped["chr2"]] == [10, 300]


def test_variants_by_contig_empty() -> None:
    assert variants_by_contig([]) == {}
