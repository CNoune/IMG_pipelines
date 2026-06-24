"""Combinatorial haplotype database construction for MetaGaAP 2.

This module is a pure-Python, cross-platform reimplementation of the original
pipeline's ``biostar175929.jar`` step. Given a reference FASTA and a VCF of
called variants, it builds a database of every plausible allele combination
within a sliding window the size of a sequencing read.

Method
------
For each reference contig a window of ``window`` bp slides along the sequence in
steps of ``step`` bp (default: ``step == window``, i.e. non-overlapping windows
that tile the contig). For every window:

* the variant sites whose 1-based ``POS`` falls inside the window are collected;
* windows carrying more than ``max_variants_per_window`` sites are skipped
  entirely (a guard against combinatorial blow-up);
* the cartesian product of allele choices is enumerated, each site offering
  ``[REF] + ALTs``. The all-``REF`` combination reproduces the wild-type window,
  so wild-type is always represented;
* chosen alleles are applied to the window substring from the **rightmost** to
  the **leftmost** position, so that length-changing edits (indels) never
  corrupt the offsets of edits still to be applied;
* at most ``max_haplotypes_per_window`` combinations are emitted per window
  (``itertools.islice`` over the product).

Sequences are de-duplicated across the whole database by checksum, and the
surviving records are renamed ``>{sample}_{i}`` (``i`` from 1).

The generator core (:func:`generate_window_haplotypes`) is a pure function and
is unit-tested directly. Only the orchestrator (:func:`build_haplotype_database`)
touches the filesystem, via :mod:`metagaap2.seqio` and :mod:`metagaap2.vcf`.

The algorithm is exact for substitutions (SNPs/MNPs). Indels are handled
best-effort and length-aware: an allele simply replaces the reference span it
covers within the window, clamped to the window's right edge.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Union

from .models import HaplotypeParams
from .seqio import iter_fasta, write_fasta
from .vcf import Variant, read_vcf, variants_by_contig

__all__ = [
    "generate_window_haplotypes",
    "build_haplotype_database",
]

StrPath = Union[str, Path]

_MISSING = "."


# --------------------------------------------------------------------------- #
# Pure combinatorial core
# --------------------------------------------------------------------------- #
def generate_window_haplotypes(
    ref_window: str,
    sites: list[tuple[int, list[str]]],
    *,
    max_variants: int,
    max_haplotypes: int,
) -> Iterator[str]:
    """Enumerate haplotype sequences for a single reference window.

    This is a pure function: it performs no IO and depends only on its
    arguments. It is the scientific heart of the module and is tested directly.

    Parameters
    ----------
    ref_window:
        The reference substring covered by the window.
    sites:
        Variant sites inside the window, each as
        ``(offset_in_window_0based, [allele, ...])`` where ``allele[0]`` is the
        reference allele at that site and the remainder are the alternates. The
        reference allele may be multi-base (an MNP or the anchor of a deletion);
        its length determines how much of ``ref_window`` a chosen allele
        replaces. Offsets are interpreted relative to the start of
        ``ref_window``.
    max_variants:
        If the number of sites exceeds this, no haplotypes are emitted (the
        window is skipped) - a guard against combinatorial blow-up.
    max_haplotypes:
        Cap on the number of distinct combinations emitted (``itertools.islice``
        over the cartesian product of per-site allele choices).

    Yields
    ------
    str
        Haplotype sequences. The first combination (all reference alleles)
        reproduces ``ref_window`` unchanged, so wild-type is always represented.
        Sequences are de-duplicated within this window.

    Notes
    -----
    Alleles are applied from the rightmost to the leftmost site so that
    length-changing edits (indels) do not shift the offsets of edits that have
    not yet been applied. A reference span that runs past the window's right
    edge is clamped to that edge (best-effort indel handling).

    Limitation (overlapping spans): when one site's reference span covers the
    offset of another site (e.g. a 2-base deletion anchored at offset *o* plus a
    SNP at offset *o+1*), choosing the multi-base reference allele of the
    spanning site overwrites the overlapped edit, so that particular allele
    combination collapses onto another and is not represented. This under-counts
    the haplotype space near overlapping indels but never corrupts a sequence;
    it is acceptable for the substitution-dominated barcoding use case and is
    locked by a regression test. Callers needing exactness near indels should
    pre-merge overlapping sites upstream.
    """
    # Guard: skip windows that are too dense with variation.
    if len(sites) > max_variants:
        return

    # No variants: the window is pure wild-type.
    if not sites:
        if max_haplotypes >= 1:
            yield ref_window
        return

    # Apply edits right-to-left so earlier (smaller) offsets stay valid even
    # when a later allele changes the sequence length. Sort a copy; do not
    # mutate the caller's list.
    ordered = sorted(sites, key=lambda s: s[0], reverse=True)

    # Per-site allele choices, in the same right-to-left order as ``ordered``.
    choice_lists: list[list[str]] = [alleles for _offset, alleles in ordered]

    window_len = len(ref_window)
    seen: set[str] = set()
    emitted = 0

    for combo in itertools.islice(
        itertools.product(*choice_lists), max_haplotypes
    ):
        # ``combo`` pairs with ``ordered`` (right-to-left). Apply each chosen
        # allele in turn; because we move right-to-left, ``offset`` for the next
        # (more leftward) edit is unaffected by length changes already made.
        seq = ref_window
        for (offset, alleles), chosen in zip(ordered, combo):
            ref_allele = alleles[0]
            # Length of reference span this site replaces, clamped to the
            # window's right edge so indels anchored near the end stay in-bounds.
            span = len(ref_allele) if ref_allele and ref_allele != _MISSING else 0
            start = offset
            end = min(offset + span, window_len)
            # A missing/"." alt is treated as "no sequence" (a deletion of the
            # reference span); a concrete allele replaces the span verbatim.
            replacement = "" if chosen in ("", _MISSING) else chosen
            seq = seq[:start] + replacement + seq[end:]

        if seq not in seen:
            seen.add(seq)
            emitted += 1
            yield seq


# --------------------------------------------------------------------------- #
# Window helpers
# --------------------------------------------------------------------------- #
def _sites_in_window(
    variants: Sequence[Variant],
    start: int,
    window_len: int,
) -> list[tuple[int, list[str]]]:
    """Build the ``sites`` list for the window ``[start, start + window_len)``.

    ``variants`` are 1-based VCF records (assumed pre-sorted by ``pos``). A
    variant is inside the window when its 0-based reference position
    (``pos - 1``) lies within ``[start, start + window_len)``. The returned
    offset is that position relative to ``start``. Each site's allele list is
    ``[ref, *concrete_alts]`` with any ``"."`` placeholder alternates dropped;
    sites whose alternates are all placeholders contribute nothing new and are
    omitted (they would only re-emit the reference).
    """
    sites: list[tuple[int, list[str]]] = []
    win_end = start + window_len
    for var in variants:
        pos0 = var.pos - 1
        if pos0 < start:
            continue
        if pos0 >= win_end:
            # Variants are position-sorted, so nothing further can fall inside.
            break
        concrete_alts = [a for a in var.alts if a and a != _MISSING]
        if not concrete_alts:
            continue
        offset = pos0 - start
        sites.append((offset, [var.ref, *concrete_alts]))
    return sites


# --------------------------------------------------------------------------- #
# Database builder
# --------------------------------------------------------------------------- #
def _checksum(sequence: str) -> bytes:
    """Return the SHA-1 digest of ``sequence`` upper-cased.

    Upper-casing makes de-duplication case-insensitive; the raw digest bytes are
    used as the set member (smaller and faster to compare than the hex string).
    """
    return hashlib.sha1(sequence.upper().encode("ascii", errors="replace")).digest()


def build_haplotype_database(
    reference_fasta: StrPath,
    vcf_path: StrPath,
    out_fasta: StrPath,
    params: HaplotypeParams,
    *,
    sample: str,
    default_window: int,
) -> int:
    """Build a combinatorial haplotype database from a reference and a VCF.

    Reads every reference contig and the variants called against it, slides a
    window across each contig, enumerates allele combinations per window via
    :func:`generate_window_haplotypes`, de-duplicates the emitted sequences
    across the whole database by checksum, and writes the unique records to
    ``out_fasta`` renamed ``>{sample}_{i}`` (``i`` from 1).

    Parameters
    ----------
    reference_fasta:
        Path to the reference FASTA (one or more contigs; gzip supported).
    vcf_path:
        Path to the VCF of called variants. A missing or empty VCF yields a
        database of the plain reference windows (wild-type only).
    out_fasta:
        Destination FASTA. Parent directories are created as needed.
    params:
        :class:`~metagaap2.models.HaplotypeParams` controlling window size,
        step, the per-window variant cap and the per-window haplotype cap.
    sample:
        Sample name used to rename output records (``>{sample}_{i}``).
    default_window:
        Window size used when ``params.window`` is ``None`` (typically the modal
        read length). Must be at least 1.

    Returns
    -------
    int
        The number of unique haplotype records written.

    Notes
    -----
    Unaltered reference windows are always included, so the wild-type sequence
    of every region is represented even where no variants were called.
    """
    out_path = Path(out_fasta)

    window = params.window if params.window is not None else default_window
    if window < 1:
        window = 1
    step = params.step if params.step is not None else window
    if step < 1:
        step = 1

    grouped = variants_by_contig(read_vcf(vcf_path)) if Path(vcf_path).exists() else {}

    seen: set[bytes] = set()

    def _records() -> Iterator[tuple[str, str]]:
        index = 0
        for contig_id, contig_seq in iter_fasta(reference_fasta):
            if not contig_seq:
                continue
            contig_vars = grouped.get(contig_id, [])
            contig_len = len(contig_seq)
            start = 0
            while start < contig_len:
                ref_window = contig_seq[start : start + window]
                if not ref_window:
                    break
                sites = _sites_in_window(contig_vars, start, len(ref_window))
                for hap in generate_window_haplotypes(
                    ref_window,
                    sites,
                    max_variants=params.max_variants_per_window,
                    max_haplotypes=params.max_haplotypes_per_window,
                ):
                    digest = _checksum(hap)
                    if digest in seen:
                        continue
                    seen.add(digest)
                    index += 1
                    yield f"{sample}_{index}", hap
                start += step

    return write_fasta(_records(), out_path)
