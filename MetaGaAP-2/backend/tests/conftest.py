"""Shared pytest fixtures for the MetaGaAP 2 backend test suite.

Deliberately minimal: the individual test modules are largely self-contained and
rely only on ``pytest`` built-ins (``tmp_path``) plus ``pydantic``. Common
helpers are collected here so they can be reused as the suite grows.

Tests must pass with only ``pytest`` and ``pydantic`` installed - nothing here
imports bioinformatics libraries.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the ``backend`` directory (which contains the ``metagaap2`` package) is
# importable regardless of where pytest is invoked from. ``conftest.py`` lives in
# ``backend/tests`` so its parent is the package root.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture()
def minimal_run_config_dict(tmp_path: Path) -> dict:
    """A minimal, valid ``RunConfig`` payload as a plain dict.

    Useful for tests that want to exercise validation without depending on the
    model class directly. Paths point inside ``tmp_path`` so nothing touches the
    real filesystem outside the test sandbox.
    """
    return {
        "run_name": "demo",
        "work_dir": str(tmp_path),
        "samples": [
            {"name": "s1", "r1": str(tmp_path / "s1_R1.fastq.gz")},
        ],
    }
