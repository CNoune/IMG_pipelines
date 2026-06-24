"""Checksum-based de-duplication of FASTA records.

This replaces the original pipeline's ``seguid``-based de-duplication and its
broken ``multiprocessing`` block (which dead-locked on Windows and silently
dropped records on large inputs). The implementation here is deliberately
simple, streaming, and cross-platform:

* All input FASTA files are read in order and concatenated logically.
* Each record's sequence is upper-cased and hashed with :func:`hashlib.sha1`.
* The first record bearing a given checksum is kept; later records whose
  checksum has already been seen are discarded.
* Only the set of seen checksums is held in memory, so memory use scales with
  the number of *unique* sequences, not the number of records.

Reading and writing go through :mod:`metagaap2.seqio` so the same
``dnaio``-backed, transparently-compressed IO is used everywhere in MetaGaAP 2.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Optional, Union

from .seqio import iter_fasta, write_fasta

__all__ = ["dedup_fasta"]

PathLike = Union[str, Path]


def _normalise_inputs(in_paths: Union[PathLike, Iterable[PathLike]]) -> list[Path]:
    """Coerce the ``in_paths`` argument into a concrete list of :class:`Path`.

    A single path (``str`` or :class:`Path`) is accepted as a convenience and is
    wrapped in a one-element list; any other iterable is materialised in order.
    """
    if isinstance(in_paths, (str, Path)):
        return [Path(in_paths)]
    return [Path(p) for p in in_paths]


def _checksum(sequence: str) -> bytes:
    """Return the SHA-1 digest of ``sequence`` after upper-casing.

    Upper-casing makes the comparison case-insensitive (soft-masked / lower-case
    bases are treated as identical to their upper-case counterparts). The raw
    ``bytes`` digest is used as the set member because it is smaller and faster
    to hash/compare than the hex string.
    """
    return hashlib.sha1(sequence.upper().encode("ascii", errors="replace")).digest()


def dedup_fasta(
    in_paths: Union[PathLike, Iterable[PathLike]],
    out_path: PathLike,
    *,
    rename_prefix: Optional[str] = None,
) -> tuple[int, int]:
    """De-duplicate FASTA records by sequence checksum.

    Records from every file in ``in_paths`` are streamed in order and written to
    ``out_path``. A record is kept only if the SHA-1 checksum of its
    upper-cased sequence has not been seen before; subsequent records sharing a
    checksum are dropped.

    Parameters
    ----------
    in_paths:
        A single FASTA path or an iterable of FASTA paths. Inputs are processed
        (and therefore concatenated) in the order given. Files may be
        transparently compressed (e.g. ``.gz``) per :mod:`metagaap2.seqio`.
    out_path:
        Destination FASTA file. Parent directories are created if required.
    rename_prefix:
        If given, every *kept* record is renamed to ``f"{rename_prefix}_{i}"``
        where ``i`` is a zero-based running index over kept records. The
        original record description, if any, is discarded. If ``None`` the
        original record name is preserved.

    Returns
    -------
    tuple[int, int]
        ``(n_in, n_out)`` - the total number of input records read and the
        number of unique records written.
    """
    inputs = _normalise_inputs(in_paths)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen: set[bytes] = set()
    counters = {"n_in": 0, "n_out": 0}

    def _unique_records() -> Iterator[tuple[str, str]]:
        for path in inputs:
            for name, sequence in iter_fasta(path):
                counters["n_in"] += 1
                digest = _checksum(sequence)
                if digest in seen:
                    continue
                seen.add(digest)
                out_name = (
                    f"{rename_prefix}_{counters['n_out']}"
                    if rename_prefix is not None
                    else name
                )
                counters["n_out"] += 1
                yield out_name, sequence

    write_fasta(_unique_records(), out)
    return counters["n_in"], counters["n_out"]
