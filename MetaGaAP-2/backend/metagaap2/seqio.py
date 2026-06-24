"""Cross-platform sequence IO helpers for MetaGaAP 2.

Thin, portable wrappers over ``dnaio`` (FASTQ/FASTA streaming, transparent
gzip via ``xopen``), ``pyfastx`` (indexed random access where it helps) and
Biopython (fallback FASTA parsing). These helpers are used by every engine and
by the pipeline orchestrator, replacing the assorted ``awk``/``grep``/FASTX
one-liners of the original Java-based pipeline with a single dependency-light,
Windows/Linux/macOS-safe surface.

Design notes
------------
* Every public function accepts ``str`` or :class:`pathlib.Path`.
* Compression is detected from the ``.gz`` suffix and handled transparently by
  ``xopen``/``dnaio`` (and by ``gzip`` in the few hand-rolled readers).
* Empty and missing-but-empty files are handled gracefully: iterators simply
  yield nothing and counters return ``0`` rather than raising.
* ``pyfastx`` is used only for genuinely indexed access (random extraction);
  because it writes a sidecar ``.fxi`` index next to the input, a streaming
  fallback is provided for cases where indexing is undesirable or fails.

Nothing here imports ``pysam``, ``mappy`` or ``edlib`` (no Windows wheels).
"""

from __future__ import annotations

import gzip
import io
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union

import dnaio

StrPath = Union[str, Path]

__all__ = [
    "open_fastq",
    "iter_fastq",
    "read_fasta",
    "iter_fasta",
    "write_fasta",
    "modal_read_length",
    "count_reads",
    "extract_records",
]


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _is_gzip(path: Path) -> bool:
    """True if ``path`` looks gzip-compressed (by suffix)."""
    return path.suffix.lower() == ".gz"


def _open_text(path: Path) -> io.TextIOBase:
    """Open a (possibly gzipped) file for UTF-8 text reading.

    Used by the hand-rolled FASTA reader so we never depend on a third-party
    library being importable just to stream plain text records.
    """
    if _is_gzip(path):
        return gzip.open(path, mode="rt", encoding="utf-8", newline="")
    return open(path, mode="rt", encoding="utf-8", newline="")


def _first_token(header: str) -> str:
    """Return the record id: the header up to the first whitespace."""
    return header.split(None, 1)[0] if header else header


# --------------------------------------------------------------------------- #
# FASTQ
# --------------------------------------------------------------------------- #
@contextmanager
def open_fastq(path: StrPath):
    """Context manager yielding a ``dnaio`` reader over a FASTQ/FASTA file.

    Each iterated record exposes ``.name``, ``.sequence`` and ``.qualities``
    (the latter is ``None`` for FASTA input). Gzip is handled transparently.

    Example
    -------
    >>> with open_fastq("reads.fastq.gz") as reader:
    ...     for record in reader:
    ...         print(record.name, len(record.sequence))
    """
    path = Path(path)
    reader = dnaio.open(str(path))
    try:
        yield reader
    finally:
        reader.close()


def iter_fastq(path: StrPath) -> Iterator[tuple[str, str, Optional[str]]]:
    """Iterate a FASTQ file as ``(name, sequence, qualities)`` tuples.

    ``dnaio`` handles gzip transparently via ``xopen``. ``qualities`` is
    ``None`` when the source carries no quality string (e.g. FASTA). Empty
    files yield nothing.
    """
    path = Path(path)
    with dnaio.open(str(path)) as reader:
        for record in reader:
            yield record.name, record.sequence, record.qualities


def count_reads(fastq_path: StrPath) -> int:
    """Return the number of reads in a FASTQ (or FASTA) file.

    Empty or header-less files return ``0``.
    """
    path = Path(fastq_path)
    total = 0
    with dnaio.open(str(path)) as reader:
        for _ in reader:
            total += 1
    return total


def modal_read_length(fastq_path: StrPath, *, sample_n: int = 5000) -> int:
    """Return the most common read length over the first ``sample_n`` reads.

    Pure-Python replacement for the original ``awk`` length-histogram
    one-liner used to default the haplotype window size. Sampling the head of
    the file keeps this O(sample_n) on large inputs while remaining
    representative for fixed-length amplicon data.

    Returns ``0`` for empty files. ``sample_n <= 0`` scans the whole file.
    """
    path = Path(fastq_path)
    lengths: Counter[int] = Counter()
    seen = 0
    with dnaio.open(str(path)) as reader:
        for record in reader:
            seq = record.sequence
            if seq:
                lengths[len(seq)] += 1
            seen += 1
            if sample_n and seen >= sample_n:
                break
    if not lengths:
        return 0
    # most_common breaks ties by insertion order; prefer the longer length on a
    # tie for determinism and because amplicon reads cluster at full length.
    best_count = max(lengths.values())
    return max(length for length, count in lengths.items() if count == best_count)


# --------------------------------------------------------------------------- #
# FASTA
# --------------------------------------------------------------------------- #
def iter_fasta(path: StrPath) -> Iterator[tuple[str, str]]:
    """Iterate a FASTA file as ``(id, sequence)`` tuples.

    The ``id`` is the header token up to the first whitespace. Multi-line
    sequence blocks are concatenated. Gzip (``.gz``) is handled transparently.
    Empty files yield nothing.
    """
    path = Path(path)
    header: Optional[str] = None
    chunks: list[str] = []
    with _open_text(path) as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    yield _first_token(header), "".join(chunks)
                header = line[1:].strip()
                chunks = []
            else:
                chunks.append(line.strip())
        if header is not None:
            yield _first_token(header), "".join(chunks)


def read_fasta(path: StrPath) -> dict[str, str]:
    """Read a FASTA file fully into an ``{id: sequence}`` dictionary.

    Suitable for references and haplotype databases that fit comfortably in
    memory. On duplicate ids the last record wins. Empty files yield ``{}``.
    """
    return {seq_id: seq for seq_id, seq in iter_fasta(path)}


def write_fasta(
    records: Iterable[tuple[str, str]],
    path: StrPath,
    *,
    wrap: Optional[int] = 70,
) -> int:
    """Write ``(id, sequence)`` records to a FASTA file; return the count.

    Parameters
    ----------
    records:
        Iterable of ``(id, sequence)`` pairs.
    path:
        Output path. ``.gz`` outputs are written gzip-compressed. Parent
        directories are created as needed.
    wrap:
        Wrap sequence lines at this width. ``None`` or a value ``< 1`` writes
        each sequence on a single line.

    Returns
    -------
    int
        Number of records written.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    opener = (
        (lambda: gzip.open(out, mode="wt", encoding="utf-8", newline="\n"))
        if _is_gzip(out)
        else (lambda: open(out, mode="wt", encoding="utf-8", newline="\n"))
    )
    with opener() as handle:
        for seq_id, sequence in records:
            handle.write(f">{seq_id}\n")
            sequence = sequence or ""
            if wrap and wrap >= 1:
                for i in range(0, len(sequence), wrap):
                    handle.write(sequence[i : i + wrap])
                    handle.write("\n")
                if not sequence:
                    handle.write("\n")
            else:
                handle.write(sequence)
                handle.write("\n")
            count += 1
    return count


def extract_records(
    fasta_path: StrPath,
    ids: Iterable[str],
    out_path: StrPath,
) -> int:
    """Write only the FASTA records whose id is in ``ids`` to ``out_path``.

    Pure-Python replacement for the original ``SeqExtract`` step. Tries
    ``pyfastx`` indexed random access first (efficient for extracting a small
    subset from a large, plain-text, seekable FASTA); falls back to a single
    streaming pass for gzip input or when indexing is unavailable.

    Matching is by exact id (header token up to first whitespace). Returns the
    number of records written. Requested ids that are absent are skipped.
    """
    src = Path(fasta_path)
    want = set(ids)
    if not want:
        # Still create an (empty) output so downstream paths exist.
        write_fasta(iter([]), out_path)
        return 0

    # Indexed path: only worthwhile for plain (non-gzip) FASTA that pyfastx can
    # seek into. pyfastx writes a sidecar .fxi index next to the input.
    if not _is_gzip(src):
        try:
            import pyfastx  # type: ignore[import-not-found]

            fa = pyfastx.Fasta(str(src), build_index=True)
            try:
                available = set(fa.keys())
                ordered = [i for i in want if i in available]

                def _indexed() -> Iterator[tuple[str, str]]:
                    for seq_id in ordered:
                        yield seq_id, str(fa[seq_id].seq)

                return write_fasta(_indexed(), out_path)
            finally:
                # pyfastx Fasta has no explicit close in all versions; drop ref.
                del fa
        except Exception:  # noqa: BLE001 - any pyfastx failure -> safe fallback
            pass

    # Streaming fallback: one pass, write matches in file order.
    def _streamed() -> Iterator[tuple[str, str]]:
        for seq_id, sequence in iter_fasta(src):
            if seq_id in want:
                yield seq_id, sequence

    return write_fasta(_streamed(), out_path)
