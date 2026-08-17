"""Tests for the pandera silver contract."""

from arca_pipeline.validate import contracts


def test_import():
    assert contracts.SilverSchema is not None
    assert callable(contracts.validate_silver)