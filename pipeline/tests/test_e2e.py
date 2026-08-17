"""End-to-end smoke tests (stub stage)."""

from arca_pipeline import orchestrate


def test_import():
    assert callable(orchestrate.runner.run_pipeline)