"""F5 — core tests for the monthly summary service.

Covers generate_month over the imported legacy diarios (calendar-complete
table), the kind='mensual' vs kind='resumen' non-collision, history
list/load/delete, and the approved-corrections overlay (the ported
``*_cor.json`` workflow of the oracle) for both document shapes (legacy
``horarias`` docs and F4 ``horas`` docs with derived recalculation).
"""

import json
import sqlite3
from pathlib import Path

import pytest

from oms_core.db.repositories import audit as audit_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.importer.importer import Importer
from oms_core.services import summary as summary_service


def _import_fixtures(conn: sqlite3.Connection) -> None:
    base = Path(__file__).parent
    Importer(conn).import_root(base / "fixtures" / "importer" / "json")


@pytest.fixture()
def station_db(fresh_db):
    """Fresh DB with the importer fixtures loaded (EC 15/05, no-acc 07/05)."""
    _import_fixtures(fresh_db)
    return fresh_db


# ---------------------------------------------------------------------------
# generation from legacy diarios
# ---------------------------------------------------------------------------


def test_generate_month_shapes_and_verbatim_keys(fresh_db):
    _import_fixtures(fresh_db)
    doc = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)

    assert set(doc) == {"meta", "datos"}
    assert doc["meta"]["estacion"] == "Estación Central"
    assert doc["meta"]["periodo"] == "05/2025"
    assert doc["meta"]["total_dias"] == 31  # full calendar month
    assert doc["meta"]["generado"]  # non-empty timestamp

    kpis = doc["datos"][14]  # 2025-05-15 (index = day - 1)
    assert kpis["Dias"] == "2025-05-15"
    for key in summary_service.HEADERS:
        assert key in kpis  # the 21 verbatim oracle keys
    # the corpus day 15 carries a full dataset: exact values pinned
    assert kpis["Mayor temperatura máxima"] == 29.0
    assert kpis["Media presion en la estación"] is not None
    assert kpis["Lluvia"] == 5.0  # product decision: own-day rain


def test_generate_month_is_calendar_complete_with_null_days(fresh_db):
    _import_fixtures(fresh_db)
    doc = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    dias = [row["Dias"] for row in doc["datos"]]
    assert dias == [f"2025-05-{d:02d}" for d in range(1, 32)]
    # day 07 has real (all-NaN → null) data; day 10 has no diario at all
    empty = doc["datos"][9]
    assert empty["Dias"] == "2025-05-10"
    for key in summary_service.HEADERS[1:]:
        if key in ("Dirección del viento",):
            assert empty[key] is None
        elif key == "Velocidad máxima y direccion":
            assert empty[key] == "N/A"  # oracle algorithm on an empty day


def test_generate_month_all_null_month_is_stable(fresh_db):
    _import_fixtures(fresh_db)
    doc = summary_service.generate_month(fresh_db, "MDJB", 2025, 2)
    assert doc["meta"]["total_dias"] == 28
    assert all(row["Dias"].startswith("2025-02-") for row in doc["datos"])
    assert all(
        row[key] is None
        for row in doc["datos"]
        for key in summary_service.HEADERS[1:]
        if key != "Velocidad máxima y direccion"
    )


def test_mensual_kind_does_not_collide_with_imported_resumen(fresh_db, tmp_path):
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "importer" / "resumen" / (
        "resumen_78485_102025.json")
    legacy_text = fixture.read_text(encoding="utf-8")
    sha = __import__("hashlib").sha256(legacy_text.encode("utf-8")).hexdigest()
    summaries_repo.upsert_summary_doc(
        fresh_db, station_id="78485", year=2025, month=10,
        kind="resumen", data=legacy_text, sha256=sha, day=0,
    )
    doc = summary_service.generate_month(fresh_db, "78485", 2025, 10)

    # imported legacy summary untouched
    assert summaries_repo.get_summary_doc(fresh_db, "78485", 2025, 10, "resumen") == legacy_text
    # generated doc stored as its own kind
    mensual = summaries_repo.get_summary_doc(fresh_db, "78485", 2025, 10, "mensual")
    assert mensual is not None
    assert json.loads(mensual)["datos"][0]["Dias"] == "2025-10-01"
    assert doc["datos"][14]["Dias"] == "2025-10-15"
    # both kinds coexist in the same natural-key slot (day=0)
    kinds = {row["kind"] for row in summaries_repo.list_docs(fresh_db)}
    assert {"resumen", "mensual"} <= kinds


def test_generate_month_stores_sha_and_full_table(fresh_db):
    _import_fixtures(fresh_db)
    summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    row = fresh_db.execute(
        "SELECT sha256, data FROM summary_logs WHERE station_id = 'Estación Central'"
        " AND year = 2025 AND month = 5 AND kind = 'mensual' AND day = 0"
    ).fetchone()
    assert row["sha256"] is not None and len(row["sha256"]) == 64
    assert len(json.loads(row["data"])["datos"]) == 31


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


def test_history_list_load_delete_roundtrip(fresh_db):
    _import_fixtures(fresh_db)
    summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    summary_service.generate_month(fresh_db, "MDJB", 2025, 6)

    entries = summary_service.list_history(fresh_db)
    assert [(e["station"], e["period"]) for e in entries] == [
        ("MDJB", "06/2025"),
        ("Estación Central", "05/2025"),
    ]  # newest period first, mirroring the oracle sort by period desc
    assert all("total_dias" in e and "generado" in e for e in entries)

    loaded = summary_service.load_doc(fresh_db, "Estación Central", 2025, 5)
    assert loaded["meta"]["estacion"] == "Estación Central"
    assert len(loaded["datos"]) == 31

    other = summary_service.load_doc(fresh_db, "No existe", 2025, 1)
    assert other is None

    assert summary_service.delete_doc(fresh_db, "Estación Central", 2025, 5) is True
    assert summary_service.load_doc(fresh_db, "Estación Central", 2025, 5) is None
    assert summary_service.delete_doc(fresh_db, "Estación Central", 2025, 5) is False
    remaining = summary_service.list_history(fresh_db)
    assert [e["station"] for e in remaining] == ["MDJB"]


def test_history_ignores_diario_and_resumen_kinds(fresh_db):
    _import_fixtures(fresh_db)
    # resumen import? none in this fixture set; just check diario docs are not history
    entries = summary_service.list_history(fresh_db)
    assert entries == []


# ---------------------------------------------------------------------------
# approved-corrections overlay (the _cor.json workflow, ported)
# ---------------------------------------------------------------------------


def _propose_approved(conn, station, fecha, hora, campo, original, corrected):
    return audit_repo.propose_correction(
        conn,
        station_id=station,
        fecha=fecha,
        hora=hora,
        campo=campo,
        valor_original=original,
        valor_corregido=corrected,
        justificacion="test",
        corregido_por="tester",
        estado="aprobado",
    )


def test_correction_overlay_on_legacy_hour_row(fresh_db):
    _import_fixtures(fresh_db)

    before = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    base_mean = before["datos"][14]["Media presion en la estación"]

    # approved correction to pres_est at 12Z of the 15th (a legacy horarias row)
    _propose_approved(
        fresh_db, "Estación Central", "2025-05-15", "12Z", "pres_est", "1013.0", "1020.0"
    )
    after = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    corrected_mean = after["datos"][14]["Media presion en la estación"]

    assert corrected_mean != base_mean
    # the mean moved by (1020.0 - 1013.0) / 8 → up to 0.1 from half-up rounding
    assert abs((corrected_mean - base_mean) - round((1020.0 - 1013.0) / 8, 1)) <= 0.15


def test_correction_overlay_recomputes_derived_on_f4_doc(fresh_db):
    """On an F4-captured day (doc with 'horas'), correcting a raw input
    (ts) recomputes the derived fields through oms_calc."""
    from oms_core.services import synoptic as synoptic_service

    fresh_db.execute(
        "INSERT OR REPLACE INTO stations (id, name, provincia, latitud, longitud,"
        " elevacion, ch, is_active) VALUES ('TESTS', 'Test', '', 0, 0, 0, 1.0, 1)"
    )
    fresh_db.commit()
    synoptic_service.save_hour(
        fresh_db, "TESTS", "2025-05-20", "06Z",
        {"ts": "23.2", "th": "22.3", "pres_est": "1025.3", "p3": "1022.3",
         "p24": "1024.1", "viento_dir": "180", "viento_vel": "12",
         "visibilidad": "55", "ll": "0.0", "meteo_2_1": "08030",
         "meteo_4_irixhvv": "32566", "meteo_4_1": "50102", "meteo_4_6": "72221",
         "meteo_6_2": "06000", "meteo_8_1": "11222", "extra_8ns_1": "81819",
         "extra_8ns_2": "85180",
         "t_max": "25.1", "t_min": "18.3", "t_max_24h": "26.0", "t_min_24h": "17.9"},
        observer="tester",
    )

    before = summary_service.generate_month(fresh_db, "TESTS", 2025, 5)
    day20 = before["datos"][19]
    assert day20["Dias"] == "2025-05-20"
    assert day20["Menor temperatura minima"] == 18.3
    assert day20["Punto de rocio"] is not None

    _propose_approved(
        fresh_db, "TESTS", "2025-05-20", "06Z", "th", "22.3", "22.5"
    )
    after = summary_service.generate_month(fresh_db, "TESTS", 2025, 5)
    day20b = after["datos"][19]
    # °C rose → dew point/tension recomputed (higher than before)
    assert day20b["Punto de rocio"] != day20["Punto de rocio"]
    assert day20b["Punto de rocio"] > day20["Punto de rocio"]
    # an uncorrected column is untouched
    assert day20b["Menor temperatura minima"] == 18.3
    assert day20b["Mayor temperatura máxima"] == 25.1


def test_correction_overlay_does_not_touch_other_days(fresh_db):
    _import_fixtures(fresh_db)
    _propose_approved(
        fresh_db, "Estación Central", "2025-05-15", "12Z", "pres_est", "1013.0", "1020.0"
    )
    doc = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    day10 = doc["datos"][9]
    # the other days are unaffected by the correction
    assert day10["Media presion en la estación"] is None


def test_main_window_wires_the_summary_page(qtbot, fresh_db, tmp_path):
    from oms_ui.main_window import MainWindow

    _import_fixtures(fresh_db)
    window = MainWindow("admin", fresh_db)
    qtbot.addWidget(window)
    assert window._pages["summary"].station_combo.count() > 0
    page = window._pages["summary"]
    assert page.station_combo.count() > 0


def test_pending_corrections_are_not_applied(fresh_db):
    _import_fixtures(fresh_db)
    audit_repo.propose_correction(
        fresh_db,
        station_id="Estación Central",
        fecha="2025-05-15",
        hora="12Z",
        campo="pres_est",
        valor_original="1013.0",
        valor_corregido="1020.0",
        justificacion="test",
        corregido_por="tester",
        estado="pendiente",
    )
    before = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    doc = summary_service.generate_month(fresh_db, "Estación Central", 2025, 5)
    assert doc["datos"][14]["Media presion en la estación"] == before["datos"][14][
        "Media presion en la estación"]


# ---------------------------------------------------------------------------
# synop_adapter fidelity: cli4074/cli3074 blocks + horas-derived cloud rows
# (oracle adapt_synoptic_json; legacy horarias passthrough untouched)
# ---------------------------------------------------------------------------


def _store_diario(conn, station, year, month, day, doc):
    import hashlib

    conn.execute(
        "INSERT OR IGNORE INTO stations (id, name, provincia, latitud, longitud,"
        " elevacion, ch, is_active) VALUES (?, ?, '', 0, 0, 0, 0.0, 1)",
        (station, station),
    )
    conn.commit()
    text = json.dumps(doc, ensure_ascii=False)
    summaries_repo.upsert_summary_doc(
        conn, station_id=station, year=year, month=month,
        kind="diario", data=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), day=day,
    )


def _horas_entry(nddff=None, pres_est=None, tmax=None, tmin=None):
    entry = {"datos": {}, "synop": {}, "calculado": {}}
    if pres_est is not None:
        entry["datos"]["pres_est"] = pres_est
    if tmax is not None:
        entry["datos"]["Tmax"] = tmax
    if tmin is not None:
        entry["datos"]["Tmin"] = tmin
    if nddff is not None:
        entry["synop"]["Nddff"] = nddff
    return entry


def test_f4_pure_doc_derives_cloud_rows_from_synop_groups(fresh_db):
    """A horas-only day (no horarias, no cli blocks) gets its day/afternoon
    nubosidad split from the Nddff groups, per the oracle adapter mapping
    (AST rows 5/8/11 -> 09Z/12Z/15Z day; 14/17/20 -> 18Z/21Z/00Z afternoon)."""
    doc = {
        "meta": {"estacion": "SYNOP", "fecha": "10062025"},
        "horas": {
            "09Z": _horas_entry(nddff="50000"),
            "12Z": _horas_entry(nddff="51000"),
            "15Z": _horas_entry(nddff="52000"),
            "18Z": _horas_entry(nddff="20000"),
            "21Z": _horas_entry(nddff="21000"),
            "00Z": _horas_entry(nddff="22000"),
        },
    }
    _store_diario(fresh_db, "SYNOP", 2025, 6, 10, doc)
    kpis = summary_service.generate_month(fresh_db, "SYNOP", 2025, 6)["datos"][9]
    assert kpis["Dias"] == "2025-06-10"
    assert kpis["Nuvocidad dia"] == 5.0  # (5 + 5 + 5) / 3
    assert kpis["Nuvocidad noche"] == 2.0  # (2 + 2 + 2) / 3
    assert kpis["Media de nuvocidad"] == 3.5  # unrounded halves (F2-D10)


def test_cli4074_nubosidad_overrides_horas_nddff(fresh_db):
    """cli4074 rows win over the horas Nddff groups (oracle order)."""
    doc = {
        "meta": {"estacion": "SYNOP", "fecha": "11062025"},
        "horas": {
            "09Z": _horas_entry(nddff="50000"),
            "12Z": _horas_entry(nddff="51000"),
            "15Z": _horas_entry(nddff="52000"),
            "18Z": _horas_entry(nddff="20000"),
            "21Z": _horas_entry(nddff="21000"),
            "00Z": _horas_entry(nddff="22000"),
        },
        "cli4074": {"5": {"nubosidad": 1.0}, "8": {"nubosidad": 2.0}},
    }
    _store_diario(fresh_db, "SYNOP", 2025, 6, 11, doc)
    kpis = summary_service.generate_month(fresh_db, "SYNOP", 2025, 6)["datos"][10]
    # day bucket: cli 1.0 + cli 2.0 + Nddff 5 -> (1 + 2 + 5) / 3 -> 2.7 half-up
    assert kpis["Nuvocidad dia"] == 2.7
    assert kpis["Nuvocidad noche"] == 2.0  # untouched afternoon


def test_cli3074_fills_hourly_when_horas_empty(fresh_db):
    """cli3074 hourly inputs fill the gaps the horas block leaves empty."""
    doc = {
        "meta": {"estacion": "SYNOP", "fecha": "12062025"},
        "horas": {"06Z": _horas_entry()},
        "cli3074": {"2": {"pres_est": 1011.5, "viento_vel": 4.0}},
    }
    _store_diario(fresh_db, "SYNOP", 2025, 6, 12, doc)
    kpis = summary_service.generate_month(fresh_db, "SYNOP", 2025, 6)["datos"][11]
    assert kpis["Media presion en la estación"] == 1011.5
    assert kpis["Velocidad media del viento"] == 14.4  # 4.0 m/s -> km/h


def test_cli4074_temp_overrides_horas_tmax(fresh_db):
    """cli4074 temp_max wins over the horas even-hour Tmax (oracle order)."""
    doc = {
        "meta": {"estacion": "SYNOP", "fecha": "13062025"},
        "horas": {"06Z": _horas_entry(tmax=30.0, tmin=20.0)},
        "cli4074": {"2": {"temp_max": 31.5, "temp_min": 19.5}},
    }
    _store_diario(fresh_db, "SYNOP", 2025, 6, 13, doc)
    kpis = summary_service.generate_month(fresh_db, "SYNOP", 2025, 6)["datos"][12]
    assert kpis["Mayor temperatura máxima"] == 31.5
    assert kpis["Menor temperatura minima"] == 19.5


def test_legacy_correction_materializes_missing_hour_row(fresh_db):
    """An approved correction for an hour the doc never captured still lands:
    the overlay materializes the horarias row instead of dropping the fix."""
    doc = {"meta": {"estacion": "NUEVA", "fecha": "14062025"}}
    _store_diario(fresh_db, "NUEVA", 2025, 6, 14, doc)
    _propose_approved(
        fresh_db, "NUEVA", "2025-06-14", "12Z", "pres_est", "", "1015.0"
    )
    kpis = summary_service.generate_month(fresh_db, "NUEVA", 2025, 6)["datos"][13]
    assert kpis["Media presion en la estación"] == 1015.0
