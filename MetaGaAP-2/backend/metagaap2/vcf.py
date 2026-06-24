"""Minimal, dependency-free VCF v4.2 reader/writer for MetaGaAP 2.

This module is deliberately tiny and engine-independent: every variant source in
the pipeline emits through it so that downstream code (:mod:`metagaap2.haplotypes`)
reads a single uniform shape regardless of provenance.

Three producers feed through here:

* the portable frequency pileup caller (pure Python), and
* the native ``bcftools``/``lofreq`` path (whose VCFs are re-read into
  :class:`Variant` objects so the rest of the pipeline never touches sample
  columns or caller-specific INFO fields it does not understand).

Only the columns the pipeline actually needs are modelled. Multi-allelic ALT
fields are split into a list on read; sample/FORMAT columns are ignored. The
writer produces a valid minimal VCF (``##fileformat`` + optional ``##contig``
lines + ``#CHROM`` header + one data row per :class:`Variant`).

No third-party dependencies: this is plain text parsing so it works identically
on Windows, Linux and macOS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "Variant",
    "read_vcf",
    "write_vcf",
    "variants_by_contig",
]

StrPath = Union[str, Path]

#: The mandatory eight-column VCF header (sample columns are appended only when
#: a sample name is supplied to :func:`write_vcf`).
_FIXED_COLUMNS: tuple[str, ...] = (
    "#CHROM",
    "POS",
    "ID",
    "REF",
    "ALT",
    "QUAL",
    "FILTER",
    "INFO",
)

_MISSING = "."


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Variant:
    """A single VCF record.

    Attributes
    ----------
    chrom:
        Contig / reference sequence name (the ``CHROM`` column).
    pos:
        1-based position of the variant on ``chrom``.
    ref:
        Reference allele.
    alts:
        Alternate alleles. A multi-allelic record (e.g. ``A,T``) is stored as a
        list (``["A", "T"]``).
    qual:
        Phred-scaled quality, or ``None`` when the source recorded ``"."``.
    info:
        Parsed ``INFO`` column as a mapping. Flag-style entries (no ``=``) map to
        the empty string.
    filter:
        The ``FILTER`` column; defaults to ``"PASS"``.
    """

    chrom: str
    pos: int
    ref: str
    alts: list[str]
    qual: Optional[float] = None
    info: dict[str, str] = field(default_factory=dict)
    filter: str = "PASS"

    @property
    def is_snp(self) -> bool:
        """True when this is a simple single-nucleotide variant.

        A SNP has a single-base reference allele and at least one alternate
        allele, every alternate also being a single base. Indels, MNPs and
        records with no concrete alternate allele return False.
        """
        if len(self.ref) != 1:
            return False
        concrete = [a for a in self.alts if a and a != _MISSING]
        if not concrete:
            return False
        return all(len(a) == 1 for a in concrete)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #
def _parse_info(field_text: str) -> dict[str, str]:
    """Parse a VCF ``INFO`` column into a mapping.

    ``key=value`` pairs become ``{key: value}``; bare flags map to ``""``.
    A missing INFO (``"."`` or empty) yields an empty dict.
    """
    info: dict[str, str] = {}
    if not field_text or field_text == _MISSING:
        return info
    for item in field_text.split(";"):
        if not item:
            continue
        if "=" in item:
            key, _, value = item.partition("=")
            info[key] = value
        else:
            info[item] = ""
    return info


def _parse_qual(field_text: str) -> Optional[float]:
    """Parse the ``QUAL`` column, tolerating ``"."`` and malformed values."""
    if not field_text or field_text == _MISSING:
        return None
    try:
        return float(field_text)
    except ValueError:
        return None


def _parse_alts(field_text: str) -> list[str]:
    """Split a (possibly multi-allelic) ``ALT`` column into a list of alleles.

    A missing ALT (``"."``) yields an empty list.
    """
    if not field_text or field_text == _MISSING:
        return []
    return [a for a in field_text.split(",") if a]


def read_vcf(path: StrPath) -> list[Variant]:
    """Parse a text VCF file into a list of :class:`Variant` objects.

    Header (``##``) and column-header (``#CHROM``) lines are skipped, multi-allelic
    ALT fields are split, and any sample / FORMAT columns are ignored. Missing
    optional columns (ID, QUAL, FILTER, INFO) are tolerated: a record only needs
    the first five fields (CHROM, POS, ID, REF, ALT). Blank lines and lines with
    too few fields or a non-integer POS are silently skipped so that partial or
    slightly malformed files still load.

    Parameters
    ----------
    path:
        Path to a VCF file (text; not bgzipped).

    Returns
    -------
    list[Variant]
        Variants in file order.
    """
    variants: list[Variant] = []
    vcf_path = Path(path)
    with vcf_path.open("r", encoding="utf-8", newline="") as handle:
        for raw in handle:
            line = raw.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            # A record needs at least CHROM, POS, ID, REF, ALT.
            if len(cols) < 5:
                continue
            chrom = cols[0]
            try:
                pos = int(cols[1])
            except ValueError:
                continue
            ref = cols[3]
            alts = _parse_alts(cols[4])
            qual = _parse_qual(cols[5]) if len(cols) > 5 else None
            filt = cols[6] if len(cols) > 6 and cols[6] not in ("", _MISSING) else "PASS"
            info = _parse_info(cols[7]) if len(cols) > 7 else {}
            variants.append(
                Variant(
                    chrom=chrom,
                    pos=pos,
                    ref=ref,
                    alts=alts,
                    qual=qual,
                    info=info,
                    filter=filt,
                )
            )
    return variants


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def _format_qual(qual: Optional[float]) -> str:
    """Render a QUAL value, collapsing integral floats to plain integers."""
    if qual is None:
        return _MISSING
    if qual == int(qual):
        return str(int(qual))
    return repr(qual)


def _format_info(info: dict[str, str]) -> str:
    """Render an INFO mapping back to the VCF ``key=value;flag`` form."""
    if not info:
        return _MISSING
    parts: list[str] = []
    for key, value in info.items():
        if value == "":
            parts.append(key)
        else:
            parts.append(f"{key}={value}")
    return ";".join(parts)


def write_vcf(
    variants: list[Variant],
    path: StrPath,
    *,
    reference_name: Optional[str] = None,
    sample: Optional[str] = None,
    contigs: Optional[dict[str, int]] = None,
) -> int:
    """Write ``variants`` to ``path`` as a valid minimal VCF v4.2 file.

    The output always carries a ``##fileformat=VCFv4.2`` line and a ``#CHROM``
    header. ``##contig`` lines are emitted when ``contigs`` is supplied, and a
    ``##reference`` line when ``reference_name`` is given. ALT alleles are joined
    with commas; an empty ``alts`` list is written as ``"."``.

    Parameters
    ----------
    variants:
        Records to write, in the order given.
    path:
        Destination file. Parent directories are created as needed.
    reference_name:
        Optional value for a ``##reference`` header line.
    sample:
        When given, a single sample column is added to the ``#CHROM`` header
        (with ``FORMAT``) so the file is well-formed for tools that expect a
        sample; data rows then carry a placeholder ``GT`` of ``.``.
    contigs:
        Optional mapping of contig name to length, emitted as ``##contig`` lines.

    Returns
    -------
    int
        The number of variant records written.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = ["##fileformat=VCFv4.2"]
    if reference_name is not None:
        lines.append(f"##reference={reference_name}")
    if contigs:
        for name, length in contigs.items():
            lines.append(f"##contig=<ID={name},length={length}>")

    columns = list(_FIXED_COLUMNS)
    if sample is not None:
        columns.append("FORMAT")
        columns.append(sample)
    lines.append("\t".join(columns))

    count = 0
    for var in variants:
        alt_text = ",".join(var.alts) if var.alts else _MISSING
        filt = var.filter if var.filter not in ("", None) else _MISSING
        row = [
            var.chrom,
            str(var.pos),
            _MISSING,  # ID
            var.ref,
            alt_text,
            _format_qual(var.qual),
            filt,
            _format_info(var.info),
        ]
        if sample is not None:
            row.append("GT")
            row.append(_MISSING)
        lines.append("\t".join(row))
        count += 1

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


# --------------------------------------------------------------------------- #
# Grouping
# --------------------------------------------------------------------------- #
def variants_by_contig(variants: list[Variant]) -> dict[str, list[Variant]]:
    """Group variants by contig, each contig's list sorted ascending by position.

    Insertion order of contigs follows first appearance in ``variants``.

    Parameters
    ----------
    variants:
        Variants to group.

    Returns
    -------
    dict[str, list[Variant]]
        Mapping of contig name to its position-sorted variants.
    """
    grouped: dict[str, list[Variant]] = {}
    for var in variants:
        grouped.setdefault(var.chrom, []).append(var)
    for records in grouped.values():
        records.sort(key=lambda v: v.pos)
    return grouped
