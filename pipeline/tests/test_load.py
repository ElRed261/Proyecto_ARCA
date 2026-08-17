"""Tests for the load layer (silver UPSERT + gold KPIs)."""

from arca_pipeline.load import gold, silver


def test_import():
    assert callable(silver.upsert_observations)
    assert callable(gold.build_monthly_kpis)

# Idempotency test (to add once upsert_observations exists):
# run upsert_observations(engine, df) twice on the same data and assert
# SELECT COUNT(*) only grows by len(df) on the FIRST run — a rerun must be a
# no-op because (station_code, fecha, hora, source_sha256) already exists.