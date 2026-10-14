"""Shared pytest fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_arca_dir(tmp_path):
    """Scratch directory mimicking the pipeline's working tree (raw/, parsed/, rejected/)."""
    raw = tmp_path / "raw"
    parsed = tmp_path / "parsed"
    rejected = tmp_path / "rejected"
    for d in (raw, parsed, rejected):
        d.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def fixture_xlsm_path():
    """Path to the real golden fixture workbook (Estación Central 01/03/2026)."""
    return Path(__file__).parent / "fixtures" / "estacion_central_01032026.xlsm"