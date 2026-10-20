"""A6 — the JSON tree is a faithful export of the database, and it round-trips.

SQLite is the truth; the Documents tree is the transport that Drive carries.
Exporting must write the schema 2 document, and importing it back must yield
the same document, or the two layers drift apart.
"""

import json

from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import document as doc_service
from oms_core.services import export as export_service
from oms_core.services import synoptic as synoptic_service

STATION = "78486"
FECHA = "2025-10-26"
HOUR = {
    "ts": "24.1", "th": "22.0", "pres_est": "1001.6", "p3": "1000.0",
    "meteo_4_1": "50602", "meteo_6_2": "01000", "nombre_observador": "YASSER GALAN",
}


def _saved_day(conn):
    synoptic_service.save_hour(conn, STATION, FECHA, "06Z", HOUR)
    synoptic_service.save_hour(conn, STATION, FECHA, "21Z",
                               {**HOUR, "ts": "27.5", "nombre_observador": "EDGAR ACOSTA"})
    return summaries_repo.get_summary_doc(conn, STATION, 2025, 10, "diario", day=26)


# ------------------------------------------------------------------ path


def test_the_path_follows_the_station_year_month_convention(tmp_path):
    path = export_service.day_path(tmp_path, STATION, 2025, 10, 26)
    assert path == tmp_path / "synop" / STATION / "2025" / "10" / "7848626102025.json"


# ---------------------------------------------------------------- export


def test_export_writes_the_schema_two_document(fresh_db, tmp_path):
    _saved_day(fresh_db)
    path = export_service.export_day(fresh_db, STATION, FECHA, tmp_path)
    assert path is not None and path.exists()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema"] == 2
    assert document["horas"]["06Z"]["observador"] == "YASSER GALAN"
    assert document["horas"]["06Z"]["datos"]["ts"] == "24.1"
    assert "calculado" not in document["horas"]["06Z"]


def test_export_returns_none_for_a_missing_day(fresh_db, tmp_path):
    assert export_service.export_day(fresh_db, STATION, "2025-01-01", tmp_path) is None


def test_export_all_counts_what_it_writes(fresh_db, tmp_path):
    _saved_day(fresh_db)
    report = export_service.export_all(fresh_db, tmp_path)
    assert report.written == 1
    assert report.errors == []
    assert (tmp_path / "synop" / STATION / "2025" / "10").is_dir()


# ------------------------------------------------------------ round trip


def test_a_day_round_trips_through_the_tree(fresh_db, tmp_path):
    original = _saved_day(fresh_db)
    path = export_service.export_day(fresh_db, STATION, FECHA, tmp_path)

    # wipe the day and bring it back from the file we just wrote
    fresh_db.execute(
        "DELETE FROM summary_logs WHERE station_id=? AND year=? AND month=? AND day=?",
        (STATION, 2025, 10, 26))
    fresh_db.commit()
    assert doc_service.load_day_document(fresh_db, STATION, FECHA) is None

    assert export_service.import_day_file(fresh_db, path) is True
    restored = summaries_repo.get_summary_doc(
        fresh_db, STATION, 2025, 10, "diario", day=26)
    assert json.loads(restored) == json.loads(original)


def test_importing_a_legacy_file_still_migrates_it(fresh_db, tmp_path):
    legacy = {
        "meta": {"estacion": STATION, "fecha": "26102025"},
        "horas": {"06Z": {"observador": "X", "datos": {"ts": "20.0"},
                          "synop": {"9spspsp_18": "555"}}},
    }
    path = tmp_path / "viejo.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert export_service.import_day_file(fresh_db, path) is True
    day = doc_service.load_day_document(fresh_db, STATION, FECHA)
    assert day is not None and day.schema == 2
    assert "meteo_14_5" not in day.hour("06Z")  # the polluted lane is gone


def test_a_dry_run_import_writes_nothing(fresh_db, tmp_path):
    _saved_day(fresh_db)
    path = export_service.export_day(fresh_db, STATION, FECHA, tmp_path)
    fresh_db.execute("DELETE FROM summary_logs")
    fresh_db.commit()
    assert export_service.import_day_file(fresh_db, path, dry_run=True) is True
    assert summaries_repo.get_summary_doc(
        fresh_db, STATION, 2025, 10, "diario", day=26) is None
