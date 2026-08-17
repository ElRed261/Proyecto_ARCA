"""Tests for the transform layer's pure core (stub stage)."""

from arca_pipeline.transform import excel_to_json


def test_import():
    assert callable(excel_to_json.parse_excel)