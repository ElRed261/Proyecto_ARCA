"""Tests for the load layer (silver UPSERT + gold KPIs)."""

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from arca_pipeline.load import gold, silver

COLUMNS = [
    "station_code", "fecha", "hora", "ts", "th", "pres_est", "pres_nmm",
    "p3", "p24", "correc_alt", "Tmax", "Tmin", "LL", "temp_seco",
    "temp_humedo", "hum_ptor", "hum_tvap", "hum_hr", "viento_dir",
    "viento_vel", "visibilidad", "tend_car", "tend_dif", "source_sha256",
    "validated_at",
]


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/test.db")
    yield eng
    eng.dispose()


def insert_sample(engine, sha256="a" * 64, ts_06=15.0, ts_12=20.0) -> int:
    """Upsert 2 silver rows (station 78486, 2026-03-01, horas 06Z/12Z)."""
    rows = [
        {
            "station_code": "78486", "fecha": "2026-03-01", "hora": "06Z",
            "ts": ts_06, "source_sha256": sha256,
            "validated_at": "2026-03-01T06:00:00+00:00",
        },
        {
            "station_code": "78486", "fecha": "2026-03-01", "hora": "12Z",
            "ts": ts_12, "source_sha256": sha256,
            "validated_at": "2026-03-01T12:00:00+00:00",
        },
    ]
    df = pd.DataFrame(rows).reindex(columns=COLUMNS)  # missing cols -> NaN -> NULL
    return silver.upsert_observations(engine, df)


def count_rows(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def test_upsert_inserts_rows(engine):
    assert insert_sample(engine) == 2
    assert count_rows(engine, "silver_observations") == 2


def test_upsert_idempotent_rerun(engine):
    insert_sample(engine)
    insert_sample(engine)
    assert count_rows(engine, "silver_observations") == 2


def test_upsert_updated_values(engine):
    insert_sample(engine, ts_06=15.0)
    insert_sample(engine, ts_06=99.0)
    with engine.connect() as conn:
        ts = conn.execute(
            text("SELECT ts FROM silver_observations WHERE hora = '06Z'")
        ).scalar()
    assert ts == 99.0
    assert count_rows(engine, "silver_observations") == 2


def test_upsert_new_sha256_adds_row(engine):
    insert_sample(engine, sha256="a" * 64)
    insert_sample(engine, sha256="b" * 64)
    assert count_rows(engine, "silver_observations") == 4


def test_build_monthly_kpis(engine):
    insert_sample(engine)
    kpis = gold.build_monthly_kpis(engine, "78486", 2026, 3)
    assert kpis["avg_ts"] == 17.5
    assert kpis["days_with_data"] == 1
    assert count_rows(engine, "gold_kpis_mensuales") == 1
    gold.build_monthly_kpis(engine, "78486", 2026, 3)
    assert count_rows(engine, "gold_kpis_mensuales") == 1