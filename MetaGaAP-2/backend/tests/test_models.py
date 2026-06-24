"""Tests for :mod:`metagaap2.models` - the pydantic v2 data contract.

Covers:
  * a JSON round-trip of a :class:`RunConfig` carrying one :class:`Sample`
    (``model_dump_json`` -> ``model_validate_json``),
  * the documented defaults (engine = portable, caller = builtin, aligner =
    builtin, reference_mode = single),
  * field-level validation, in particular that :class:`QCParams` rejects
    ``min_length = 0`` (constraint ``ge=1``),
  * that :class:`RunConfig` requires at least one sample (``min_length=1``),
  * the :class:`Sample` and :class:`ReadGroup` helper behaviour.

Needs only ``pydantic`` - no bioinformatics libraries are imported.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from metagaap2.models import (
    Aligner,
    EngineKey,
    QCParams,
    ReadGroup,
    ReferenceMode,
    RunConfig,
    Sample,
    VariantCaller,
)


# --------------------------------------------------------------------------- #
# JSON round-trip
# --------------------------------------------------------------------------- #
def test_run_config_json_round_trip() -> None:
    """A ``RunConfig`` with one sample survives a JSON dump/validate cycle."""
    cfg = RunConfig(
        run_name="run01",
        work_dir="/data/runs",
        reference="/data/ref.fasta",
        samples=[
            Sample(
                name="sampleA",
                r1="/data/sampleA_R1.fastq.gz",
                r2="/data/sampleA_R2.fastq.gz",
                read_group=ReadGroup(sample="sampleA"),
            )
        ],
    )

    payload = cfg.model_dump_json()
    restored = RunConfig.model_validate_json(payload)

    assert restored == cfg
    assert restored.run_name == "run01"
    assert len(restored.samples) == 1
    assert restored.samples[0].name == "sampleA"
    assert restored.samples[0].paired is True
    assert restored.samples[0].read_group is not None
    assert restored.samples[0].read_group.rg_id() == "sampleA.unit1"


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #
def test_run_config_defaults() -> None:
    """The documented engine/caller/aligner defaults hold."""
    cfg = RunConfig(
        run_name="run01",
        work_dir="/data/runs",
        samples=[Sample(name="s1", r1="/data/s1.fastq.gz")],
    )

    assert cfg.engine is EngineKey.PORTABLE
    assert cfg.aligner is Aligner.BUILTIN
    assert cfg.reference_mode is ReferenceMode.SINGLE
    assert cfg.variants.caller is VariantCaller.BUILTIN
    assert cfg.threads == 4
    assert cfg.merge_single_reference is True

    # Nested defaults are populated via default_factory.
    assert cfg.qc.enabled is True
    assert cfg.qc.min_quality == 20
    assert cfg.qc.min_length == 30


def test_sample_defaults_single_end() -> None:
    """A single-end sample reports ``paired`` False and no reverse read."""
    sample = Sample(name="s1", r1="/data/s1.fastq.gz")
    assert sample.r2 is None
    assert sample.paired is False
    assert sample.reference is None
    assert sample.read_group is None


def test_read_group_defaults_and_rg_id() -> None:
    """``ReadGroup`` defaults match the contract and ``rg_id`` derives an ID."""
    rg = ReadGroup(sample="s1")
    assert rg.library == "lib1"
    assert rg.platform == "ILLUMINA"
    assert rg.unit == "unit1"
    assert rg.id is None
    assert rg.rg_id() == "s1.unit1"

    explicit = ReadGroup(sample="s1", id="RGX")
    assert explicit.rg_id() == "RGX"


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_qc_params_rejects_zero_min_length() -> None:
    """``QCParams.min_length`` has constraint ``ge=1`` so 0 is rejected."""
    with pytest.raises(ValidationError):
        QCParams(min_length=0)


def test_qc_params_accepts_min_length_one() -> None:
    """The boundary value ``min_length=1`` is accepted."""
    assert QCParams(min_length=1).min_length == 1


def test_run_config_requires_at_least_one_sample() -> None:
    """``RunConfig.samples`` enforces ``min_length=1``."""
    with pytest.raises(ValidationError):
        RunConfig(run_name="run01", work_dir="/data/runs", samples=[])


def test_qc_params_rejects_out_of_range_quality() -> None:
    """``min_quality`` is bounded to 0..60 inclusive."""
    with pytest.raises(ValidationError):
        QCParams(min_quality=61)
    with pytest.raises(ValidationError):
        QCParams(min_quality=-1)


def test_enum_serialises_to_string_value() -> None:
    """String enums serialise to their plain string values in JSON."""
    cfg = RunConfig(
        run_name="run01",
        work_dir="/data/runs",
        samples=[Sample(name="s1", r1="/data/s1.fastq.gz")],
    )
    dumped = cfg.model_dump()
    assert dumped["engine"] == "portable"
    assert dumped["aligner"] == "builtin"
    assert dumped["variants"]["caller"] == "builtin"
