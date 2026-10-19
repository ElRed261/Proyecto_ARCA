"""A5 — migrate the legacy (schema 1) documents the app produced.

Rule R1 keeps every observed value; rule R2 drops what must not be stored
(derived blocks and the polluted nine-lane slots).
"""

import json

from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import document as doc_service
from oms_core.services import legacy_migration as migration

STATION = "78486"
LEGACY = {
    "meta": {
        "estacion": STATION,
        "fecha": "26102025",
        "ultima_actualizacion": "2026-06-02 13:32:03",
    },
    "horas": {
        "06Z": {
            "observador": "YASSER GALAN",
            "datos": {"ts": "24.1", "th": "22.0", "Tmax": "30.1", "LL": "",
                      "correc_alt": "5.5", "visibilidad": "160"},
            "synop": {
                "Nddff": "50602",
                "0CSDL DM DH": "01000",
                "9spspsp_17": "98658",
                "9spspsp_18": "555",
                "9spspsp_19": "29097",
                "9spspsp_20": "Calculos de Estación",
            },
            "calculado": {"pres_nmm": "1007.1", "hr": "83"},
        },
        "21Z": {"datos": {"ts": "27.5"}, "synop": {}},
    },
    "cli3074": {"2": {"viento_vel": "3.6", "hum_hr": "77"}},
    "cli4074": {"2": {"observador": "YG"}},
}


def _write(tmp_path, name, doc):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


# ------------------------------------------------------------ the rewrite


def test_the_v2_document_keeps_observed_values_only():
    document, _dropped = migration.build_v2_document(
        LEGACY, station=STATION, fecha="2025-10-26")
    hour = document["synop"]["06Z"]
    assert document["schema"] == 2
    assert hour["observador"] == "YASSER GALAN"
    assert hour["datos"]["ts"] == "24.1"
    assert hour["datos"]["Tmax"] == "30.1"
    assert "LL" not in hour["datos"]           # empty string is not a value
    assert "correc_alt" not in hour["datos"]   # derived from the station
    assert "visibilidad" not in hour["datos"]  # derived from IrIXHVV
    assert "calculado" not in hour


def test_the_polluted_lanes_are_dropped_and_counted():
    document, dropped = migration.build_v2_document(
        LEGACY, station=STATION, fecha="2025-10-26")
    grupos = document["synop"]["06Z"]["grupos"]
    assert grupos["Nddff"] == "50602"
    assert grupos["0CSDLDMDH"] == "01000"     # joined spelling
    assert grupos["9spspsp_17"] == "98658"
    assert "9spspsp_18" not in grupos
    assert "9spspsp_19" not in grupos
    assert "9spspsp_20" not in grupos
    assert dropped == 3


def test_every_hour_carries_the_observer():
    document, _ = migration.build_v2_document(
        LEGACY, station=STATION, fecha="2025-10-26")
    assert document["synop"]["06Z"]["observador"] == "YASSER GALAN"
    assert document["synop"]["21Z"]["observador"] == ""


def test_cli_blocks_are_nested():
    document, _ = migration.build_v2_document(
        LEGACY, station=STATION, fecha="2025-10-26")
    assert document["cli"]["3074"]["2"]["viento_vel"] == "3.6"
    assert document["cli"]["4074"]["2"]["observador"] == "YG"


def test_the_updated_stamp_becomes_iso_with_offset():
    document, _ = migration.build_v2_document(
        LEGACY, station=STATION, fecha="2025-10-26")
    assert document["meta"]["actualizado"] == "2026-06-02T13:32:03-04:00"


# ------------------------------------------------------------- migration


def test_a_dry_run_writes_nothing(fresh_db, tmp_path):
    path = _write(tmp_path, "78486/2025/10/7848626102025.json", LEGACY)
    report = migration.migrate_root(fresh_db, tmp_path, dry_run=True)
    assert report.migrated == 1 and report.dry_run is True
    assert summaries_repo.get_summary_doc(
        fresh_db, STATION, 2025, 10, "diario", day=26) is None
    assert path.exists()


def test_a_real_run_stores_a_schema_two_document(fresh_db, tmp_path):
    _write(tmp_path, "78486/2025/10/7848626102025.json", LEGACY)
    report = migration.migrate_root(fresh_db, tmp_path, dry_run=False)
    assert report.migrated == 1
    assert report.lanes_dropped == 3
    text = summaries_repo.get_summary_doc(fresh_db, STATION, 2025, 10, "diario", day=26)
    assert json.loads(text)["schema"] == 2


def test_the_migrated_day_loads_complete(fresh_db, tmp_path):
    _write(tmp_path, "78486/2025/10/7848626102025.json", LEGACY)
    migration.migrate_root(fresh_db, tmp_path, dry_run=False)
    day = doc_service.load_day_document(fresh_db, STATION, "2025-10-26")
    assert day is not None and day.schema == 2
    assert day.hour("06Z")["ts"] == "24.1"
    assert day.hour("06Z")["meteo_4_1"] == "50602"
    assert day.cli["cli3074"]["2"]["viento_vel"] == "3.6"


def test_an_already_migrated_file_is_skipped(fresh_db, tmp_path):
    document, _ = migration.build_v2_document(
        LEGACY, station=STATION, fecha="2025-10-26")
    _write(tmp_path, "78486/2025/10/7848626102025.json", document)
    report = migration.migrate_root(fresh_db, tmp_path, dry_run=False)
    assert report.already_v2 == 1 and report.migrated == 0


def test_a_broken_file_is_reported_not_crashed(fresh_db, tmp_path):
    _write(tmp_path, "roto.json", {"meta": {}})
    report = migration.migrate_root(fresh_db, tmp_path, dry_run=False)
    assert report.seen == 1
    assert len(report.rejected) == 1
    assert "meta" in report.rejected[0][1]
