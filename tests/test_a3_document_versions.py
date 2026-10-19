"""A3 — the save path stores only observed values, and every write is a version.

Rules R2 (nothing derived is persisted), R3 (the observer belongs to the hour,
never to the day) and the version trail that makes a later correction
reviewable (rule R4).
"""

import json

from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import cli as cli_service
from oms_core.services import synoptic as synoptic_service
from oms_core.services import versions as versions_service

STATION = "78486"
FECHA = "2025-10-26"

HOUR = {
    "ts": "24.1",
    "th": "22.0",
    "pres_est": "1001.6",
    "p3": "1000.0",
    "viento_dir": "180",
    "viento_vel": "12.0",
    "correc_alt": "5.5",
    "visibilidad": "160",
    "meteo_4_1": "50602",
    "meteo_6_2": "01000",
    "nombre_observador": "YASSER GALAN",
}


def _doc(conn) -> dict:
    text = summaries_repo.get_summary_doc(conn, STATION, 2025, 10, "diario", day=26)
    return json.loads(text)


# --------------------------------------------------------- stored shape


def test_derived_values_are_not_stored(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR)
    hora = _doc(fresh_db)["horas"]["06Z"]
    assert "calculado" not in hora
    assert "correc_alt" not in hora["datos"]
    assert "visibilidad" not in hora["datos"]


def test_observed_values_are_stored(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR)
    datos = _doc(fresh_db)["horas"]["06Z"]["datos"]
    assert datos["ts"] == "24.1"
    assert datos["pres_est"] == "1001.6"


def test_the_observer_is_stored_per_hour_not_in_meta(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR)
    doc = _doc(fresh_db)
    assert "observador" not in doc["meta"]
    assert doc["horas"]["06Z"]["observador"] == "YASSER GALAN"


def test_an_empty_observer_is_still_written(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "09Z", {"ts": "25.0"})
    assert _doc(fresh_db)["horas"]["09Z"]["observador"] == ""


def test_the_group_name_is_written_joined(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR)
    synop = _doc(fresh_db)["horas"]["06Z"]["synop"]
    assert synop["0CSDLDMDH"] == "01000"      # owner's spelling, no spaces
    assert "0CSDL DM DH" not in synop


# ------------------------------------------------------------- versions


def test_a_synoptic_save_records_a_version(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR, actor="tester")
    history = versions_service.list_versions(fresh_db, STATION, 2025, 10, 26)
    assert len(history) == 1
    assert history[0]["actor"] == "tester"
    assert history[0]["sha256_antes"] is None       # first write
    assert history[0]["sha256_despues"]
    assert "synoptic 06Z" in history[0]["resumen_cambio"]


def test_a_second_save_keeps_the_chain(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR, actor="tester")
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z",
                               {**HOUR, "ts": "24.9"}, actor="tester")
    history = versions_service.list_versions(fresh_db, STATION, 2025, 10, 26)
    assert len(history) == 2
    assert history[0]["sha256_antes"] == history[1]["sha256_despues"]
    assert history[0]["sha256_despues"] != history[1]["sha256_despues"]


def test_a_cli_save_records_its_own_version(fresh_db):
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli3074",
                         {"horas": {"2": {"viento_vel": "3.6"}}}, actor="tester")
    history = versions_service.list_versions(fresh_db, STATION, 2025, 10, 26)
    assert len(history) == 1
    assert "cli cli3074" in history[0]["resumen_cambio"]


def test_versions_count_helper(fresh_db):
    assert versions_service.count(fresh_db, STATION, 2025, 10, 26) == 0
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", HOUR)
    assert versions_service.count(fresh_db, STATION, 2025, 10, 26) == 1


def test_the_migration_creates_the_table(fresh_db):
    row = fresh_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='document_versions'"
    ).fetchone()
    assert row is not None
