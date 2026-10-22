"""F4 — CLI 3074/4074/5074 service tests (fenómenos + rowUpdate port).

Oracle facts echoed here from OLD/frontend/src/test/cliFenomenos.test.js and
the three CLI pages (exact field lists), plus the merge semantics of
OLD src-tauri modules/cli/mod.rs (cli key saved into the same daily
document without touching horas/meta).
"""

import json

import pytest

from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import cli as cli_service
from oms_core.services import synoptic

STATION = "78485"


# ------------------------------------------------- rowUpdate (fenómenos)


def _base_rows():
    return {
        2: {
            "pres_est": "1012.0",
            "fenomenos": {"tiempo_presente": "", "granizo": False, "trueno": False},
        },
    }


def test_toggle_check_true_stores_boolean_without_formatter():
    rows = cli_service.apply_cli_field_update(_base_rows(), 2, "fenomenos.granizo", True)
    assert rows[2]["fenomenos"]["granizo"] is True


def test_uncheck_returns_false():
    rows = cli_service.apply_cli_field_update(_base_rows(), 2, "fenomenos.granizo", True)
    rows = cli_service.apply_cli_field_update(rows, 2, "fenomenos.granizo", False)
    assert rows[2]["fenomenos"]["granizo"] is False


def test_toggling_one_check_preserves_siblings():
    rows = cli_service.apply_cli_field_update(_base_rows(), 2, "fenomenos.trueno", True)
    fen = rows[2]["fenomenos"]
    assert fen["granizo"] is False
    assert fen["trueno"] is True
    assert fen["tiempo_presente"] == ""


def test_input_map_is_never_mutated():
    base = _base_rows()
    before = json.dumps(base)
    cli_service.apply_cli_field_update(base, 2, "fenomenos.granizo", True)
    assert json.dumps(base) == before


def test_tiempo_presente_goes_through_the_normal_path():
    rows = cli_service.apply_cli_field_update(_base_rows(), 2, "fenomenos.tiempo_presente", "02")
    assert rows[2]["fenomenos"]["tiempo_presente"] == "02"


def test_numeric_fields_are_formatted_to_one_decimal():
    rows = cli_service.apply_cli_field_update(_base_rows(), 2, "pres_est", "1012.05")
    assert rows[2]["pres_est"] == "1012.1"
    # non-decimal types pass through untouched (oracle: enforceOneDecimal(true, ..) is true)
    assert cli_service.enforce_one_decimal(True, "pres_est") is True


def test_missing_row_is_created_with_default_fenomenos():
    rows = cli_service.apply_cli_field_update({}, 5, "fenomenos.niebla", True)
    assert rows[5]["fenomenos"]["niebla"] is True


def test_3074_field_lists_match_the_oracle():
    assert cli_service.DECIMAL_FIELDS_3074 == [
        "pres_est", "pres_nmm", "pres_alti", "tend_dif",
        "temp_seco", "temp_humedo", "hum_ptor", "hum_tvap",
        "viento_vel", "visibilidad",
    ]
    assert cli_service.CEIL_FIELDS_3074 == ["hum_hr"]
    assert cli_service.DECIMAL_FIELDS_4074 == ["lluvia_6h", "temp_max", "temp_min"]
    assert "rafaga_vel" in cli_service.DECIMAL_FIELDS_5074
    assert cli_service.CEIL_FIELDS_5074 == ["hum_max", "hum_min"]
    # the ten fenómenos booleans of the 3074 sheet (exact keys)
    assert list(cli_service.DEFAULT_FENOMENOS) == [
        "granizo", "ventarron", "neblina", "trueno", "relampago",
        "rocio", "polvo", "calima", "niebla", "tornado",
    ]
    assert all(value is False for value in cli_service.DEFAULT_FENOMENOS.values())


def test_one_decimal_ceil_semantics():
    # 3074/5074 humidity fields round UP to integers (oracle hum_ptor/hum_max/hum_min/hum_hr)
    assert cli_service.enforce_one_decimal("84.2", "hum_hr", ceil_fields=["hum_hr"]) == "85"
    assert cli_service.enforce_one_decimal("23.05", "temp_max", decimal_fields=["temp_max"]) == "23.1"
    # negative values round away-with-floor (oracle Math.floor on negatives)
    assert cli_service.enforce_one_decimal("-10.02", "temp_min", decimal_fields=["temp_min"]) == "-10.1"
    # already-one-decimal strings pass through untouched
    assert cli_service.enforce_one_decimal("1012.3", "pres_est", decimal_fields=["pres_est"]) == "1012.3"


# ------------------------------------------------- cli save merged into the doc


def test_save_cli3074_merges_into_the_daily_document_without_touching_horas(fresh_db):
    synoptic.save_hour(fresh_db, STATION, "2026-02-10", "06Z",
                       {"ts": "23.2", "th": "22.3", "pres_est": "1015.3"})

    cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli3074",
                         {"2": {"pres_est": "1015.0"}})

    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2026, 2, "diario", day=10))
    # schema 2 nests the CLI blocks under 'cli' (they used to sit at the root)
    assert doc["schema"] == 2
    assert doc["cli"]["3074"]["2"]["pres_est"] == "1015.0"
    assert doc["synop"]["06Z"]["datos"]["ts"] == "23.2"  # horas untouched
    assert doc["meta"]["estacion"] == STATION
    # and the reader finds it in either shape
    assert cli_service.load_cli(fresh_db, STATION, "2026-02-10", "cli3074") == {
        "2": {"pres_est": "1015.0"}}


def test_save_cli_preserves_sibling_cli_keys(fresh_db):
    cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli4074", {"nubosidad": {"3": "5"}})
    cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli5074", {"daily": {"lluvia": "1.2"}})

    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2026, 2, "diario", day=10))
    assert "4074" in doc["cli"] and "5074" in doc["cli"]


def test_save_cli_replaces_previous_value_for_the_same_key(fresh_db):
    cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli4074", {"v": 1})
    cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli4074", {"v": 2})
    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2026, 2, "diario", day=10))
    assert doc["cli"]["4074"] == {"v": 2}


def test_save_cli_validates_inputs(fresh_db):
    with pytest.raises(synoptic.SaveError, match="Código de estación inválido"):
        cli_service.save_cli(fresh_db, "", "2026-02-10", "cli3074", {})
    with pytest.raises(synoptic.SaveError, match="Se espera YYYY-MM-DD"):
        cli_service.save_cli(fresh_db, STATION, "10-02-26", "cli3074", {})
    with pytest.raises(ValueError, match="cli_key"):
        cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli9999", {})


# ------------------------------------------------- cli load


def test_load_cli_returns_stored_value_or_none(fresh_db):
    assert cli_service.load_cli(fresh_db, STATION, "2026-02-10", "cli3074") is None
    cli_service.save_cli(fresh_db, STATION, "2026-02-10", "cli3074",
                         {"1": {"temp_seco": "24.0"}})
    assert cli_service.load_cli(fresh_db, STATION, "2026-02-10", "cli3074") == \
        {"1": {"temp_seco": "24.0"}}
