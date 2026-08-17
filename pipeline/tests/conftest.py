"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def tmp_arca_dir(tmp_path):
    """Scratch directory mimicking the pipeline's working tree (raw/, parsed/, rejected/).

    The fixture providing a real .xlsm sample is added here once the transform
    core is extracted from miscelaneos/scratch/excel_to_json.py.
    """
    raw = tmp_path / "raw"
    parsed = tmp_path / "parsed"
    rejected = tmp_path / "rejected"
    for d in (raw, parsed, rejected):
        d.mkdir(parents=True)
    return tmp_path