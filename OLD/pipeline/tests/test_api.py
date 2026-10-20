"""Tests for the Query/UI API layer."""

import json

import pandas as pd
import pytest
from sqlalchemy import create_engine

# ponytail: skip if fastapi not installed — syntax check only per task hard rule
fastapi = pytest.importorskip("fastapi", reason="fastapi not installed in venv")
from fastapi.testclient import TestClient

from arca_pipeline.api.main import app
from arca_pipeline.load import gold, silver

COLUMNS = [
    "station_code",
    "fecha",
    "hora",
    "ts",
    "th",
    "pres_est",
    "pres_nmm",
    "p3",
    "p24",
    "correc_alt",
    "Tmax",
    "Tmin",
    "LL",
    "temp_seco",
    "temp_humedo",
    "hum_ptor",
    "hum_tvap",
    "hum_hr",
    "viento_dir",
    "viento_vel",
    "visibilidad",
    "tend_car",
    "tend_dif",
    "source_sha256",
    "validated_at",
]


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/api_test.db")
    yield eng
    eng.dispose()


def _insert_sample(engine, sha256="a" * 64):
    rows = [
        {
            "station_code": "78486",
            "fecha": "2026-03-01",
            "hora": "06Z",
            "ts": 15.0,
            "source_sha256": sha256,
            "validated_at": "2026-03-01T06:00:00+00:00",
        },
        {
            "station_code": "78486",
            "fecha": "2026-03-01",
            "hora": "12Z",
            "ts": 20.0,
            "source_sha256": sha256,
            "validated_at": "2026-03-01T12:00:00+00:00",
        },
    ]
    df = pd.DataFrame(rows).reindex(columns=COLUMNS)
    return silver.upsert_observations(engine, df)


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_state_no_runs_yet(monkeypatch, tmp_path):
    # ponytail: isolate _PIPELINE_ROOT to empty dir so no last_run.json is found
    import arca_pipeline.api.main as api_main

    monkeypatch.setattr(api_main, "_PIPELINE_ROOT", tmp_path)
    client = TestClient(app)
    resp = client.get("/state")
    assert resp.status_code == 404
    # spec says {"status":"no runs yet"} — accept either detail wrapper or direct
    body = resp.json()
    if "detail" in body and isinstance(body["detail"], dict):
        assert body["detail"].get("status") == "no runs yet"
    else:
        assert body.get("status") == "no runs yet"


def test_state_with_run(monkeypatch, tmp_path):
    import arca_pipeline.api.main as api_main

    monkeypatch.setattr(api_main, "_PIPELINE_ROOT", tmp_path)
    state_dir = tmp_path / "data" / "state"
    state_dir.mkdir(parents=True)
    payload = {"started_at": "2026-03-01T00:00:00+00:00", "files_ingested": 1}
    (state_dir / "last_run.json").write_text(json.dumps(payload))
    client = TestClient(app)
    resp = client.get("/state")
    assert resp.status_code == 200
    assert resp.json()["files_ingested"] == 1


def test_observations_with_sqlite(monkeypatch, engine, tmp_path):
    import arca_pipeline.api.main as api_main
    from arca_pipeline.config import settings

    _insert_sample(engine)
    # ponytail: point settings to the temp sqlite file so api per-request engine sees same DB
    db_url = f"sqlite:///{tmp_path}/api_test.db"
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(api_main.settings, "database_url", db_url)

    client = TestClient(app)
    resp = client.get("/stations/78486/observations?from=2026-03-01&to=2026-03-02")
    assert resp.status_code == 200
    body = resp.json()
    assert body["station_code"] == "78486"
    assert body["count"] == 2
    assert len(body["observations"]) == 2
    # ordered by fecha,hora
    assert body["observations"][0]["hora"] == "06Z"
    assert body["observations"][1]["hora"] == "12Z"


def test_observations_filter_and_validation(monkeypatch, engine, tmp_path):
    import arca_pipeline.api.main as api_main
    from arca_pipeline.config import settings

    _insert_sample(engine)
    db_url = f"sqlite:///{tmp_path}/api_test.db"
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(api_main.settings, "database_url", db_url)

    client = TestClient(app)
    # outside range -> empty
    resp = client.get("/stations/78486/observations?from=2026-03-10&to=2026-03-11")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0

    # missing params -> 422
    resp = client.get("/stations/78486/observations?from=2026-03-01")
    assert resp.status_code == 422

    # invalid date format -> 422
    resp = client.get("/stations/78486/observations?from=not-a-date&to=2026-03-02")
    assert resp.status_code == 422


def test_kpis(monkeypatch, engine, tmp_path):
    import arca_pipeline.api.main as api_main
    from arca_pipeline.config import settings

    _insert_sample(engine)
    gold.build_monthly_kpis(engine, "78486", 2026, 3)
    db_url = f"sqlite:///{tmp_path}/api_test.db"
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(api_main.settings, "database_url", db_url)

    client = TestClient(app)
    resp = client.get("/stations/78486/kpis?year=2026&month=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["station_code"] == "78486"
    assert body["year"] == 2026
    assert body["month"] == 3
    assert body["avg_ts"] == 17.5

    resp = client.get("/stations/78486/kpis?year=2026&month=2")
    assert resp.status_code == 404


def test_rejected(monkeypatch, tmp_path):
    import arca_pipeline.api.main as api_main

    monkeypatch.setattr(api_main, "_PIPELINE_ROOT", tmp_path)
    rejected = tmp_path / "data" / "rejected"
    rejected.mkdir(parents=True)
    (rejected / "bad.xlsm.rejected.json").write_text(json.dumps({"reason": "parse_error: boom"}))
    (rejected / "other.xlsm.rejected.json").write_text(json.dumps({"errors": ["a", "b"]}))
    client = TestClient(app)
    resp = client.get("/rejected")
    assert resp.status_code == 200
    body = resp.json()
    # ponytail: support both plain list and wrapped dict
    if isinstance(body, dict):
        items = body.get("rejected", body.get("items", []))
        if "count" in body:
            assert body["count"] == 2
    else:
        items = body
    assert len(items) == 2
    filenames = {x["filename"] for x in items}
    assert "bad.xlsm.rejected.json" in filenames
    reasons = {x["reason"] for x in items}
    assert any("parse_error" in r for r in reasons)
