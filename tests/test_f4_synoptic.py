"""F4 — synoptic observation service tests.

Oracle facts under test (read-only oracle: OLD/frontend SynopticPage +
OLD src-tauri storage.rs):

- hour model: 17 base keys for all hours, +t_max/t_min/t_max_24h/t_min_24h
  for EVEN hours only (00Z, 06Z, 12Z, 18Z);
- hourCompletion is an orientation heuristic (done = non-empty expected keys);
- server-side validar_grupos_synop: max 5 chars, only digits and '/', with
  the exact oracle error message shape ("el grupo 'X' en hora YYZ", nothing
  is written on failure);
- draft bound to station+fecha with a validity check;
- observer name remembered per station (app_config KV);
- structured save errors carry {field, hour, detail} (parseFieldError
  contract) so the UI can highlight the guilty field and switch hour.
"""

import json

import pytest

from oms_core.db.repositories import observations as observations_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import synoptic

HOURS = synoptic.HOURS
EVEN = synoptic.EVEN_HOURS
ODD = synoptic.ODD_HOURS


# ---------------------------------------------------------------- hour model


def test_hour_lists_match_the_oracle():
    assert EVEN == ("00Z", "06Z", "12Z", "18Z")
    assert ODD == ("03Z", "09Z", "15Z", "21Z")
    assert HOURS == ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z")
    assert len(synoptic.BASE_DATA_KEYS) == 17
    for key in ("ts", "th", "pres_est", "p3", "p24", "viento_dir", "viento_vel",
                "visibilidad", "ll", "meteo_2_1", "meteo_4_irixhvv", "meteo_4_1",
                "meteo_4_6", "meteo_6_2", "meteo_8_1", "extra_8ns_1", "extra_8ns_2"):
        assert key in synoptic.BASE_DATA_KEYS
    assert synoptic.EVEN_EXTRA_KEYS == ("t_max", "t_min", "t_max_24h", "t_min_24h")
    assert synoptic.HOUR_META == ("station_id", "fecha", "correc_alt", "nombre_observador")


def test_hour_completion_honest_denominator():
    even_data = {key: "1" for key in synoptic.BASE_DATA_KEYS}
    even_data["t_max"] = "25.0"
    c = synoptic.hour_completion(even_data, "06Z")
    assert c["total"] == 21  # 17 base + 4 even-only
    assert c["done"] == 18

    odd_data = {key: "x" for key in synoptic.BASE_DATA_KEYS}
    odd_data["t_max"] = "25.0"  # ignored for odd hours (not expected)
    c = synoptic.hour_completion(odd_data, "09Z")
    assert c["total"] == 17
    assert c["done"] == 17


def test_hour_completion_counts_only_non_empty_and_handles_garbage():
    data = {"ts": "23.2", "th": "   ", "pres_est": None, "t_max": "25.0"}
    c = synoptic.hour_completion(data, "06Z")
    assert c["done"] == 2  # ts + t_max
    assert c["ratio"] == pytest.approx(2 / 21)
    assert synoptic.hour_completion(None, "06Z")["done"] == 0
    assert synoptic.hour_completion("nope", "09Z")["done"] == 0


def test_parse_field_error_portfolio():
    assert synoptic.parse_field_error(
        "el grupo 'meteo_4_6' en hora 06Z excede 5 caracteres"
    ) == {"field": "meteo_4_6", "hour": "06Z"}
    assert synoptic.parse_field_error("etapa validate (x): blabla") is None
    assert synoptic.parse_field_error("") is None
    assert synoptic.parse_field_error(None) is None
    assert synoptic.parse_field_error(6) is None


# ---------------------------------------------------------------- save_hour


@pytest.fixture()
def station(fresh_db):
    """Seed stations exist in a migrated DB; 78485 (Las américas) has ch=2.0."""
    row = fresh_db.execute(
        "SELECT COUNT(*) FROM stations WHERE id = '78485'"
    ).fetchone()
    assert row[0] == 1
    return "78485"


def _hour_data(counter=0.0, **extra):
    data = {"ts": "23.2", "th": "22.3", "pres_est": "1025.3", "p3": "1022.3",
            "p24": "1024.1", "viento_dir": "180", "viento_vel": "12",
            "visibilidad": "55", "ll": "", "meteo_2_1": "08030",
            "meteo_4_irixhvv": "32566", "meteo_4_1": "50102",
            "meteo_4_6": "72221", "meteo_6_2": "06000", "meteo_8_1": "",
            "extra_8ns_1": "81819", "extra_8ns_2": "85180",
            # even-hour extras present (the UI sends them, possibly empty)
            "t_max": "", "t_min": "", "t_max_24h": "", "t_min_24h": ""}
    data.update({k: v for k, v in extra.items()})
    if counter:
        data["pres_est"] = f"{1025.3 + counter:.1f}"  # keep唯一 per call
    return data


def test_save_hour_transactional_path_writes_row_and_diario_doc(fresh_db, station):
    synoptic.save_hour(fresh_db, station, "2025-12-08", "06Z",
                       _hour_data(), observer="Andry emiliano")

    rows = observations_repo.get_day(fresh_db, station, "2025-12-08")
    assert len(rows) == 1
    row = rows[0]
    assert row.hora == "06Z"
    assert row.observador == "Andry emiliano"
    assert row.p_est == pytest.approx(1025.3)
    assert row.v_dir_deg == pytest.approx(180.0)
    assert row.v_vel == pytest.approx(12.0)
    # derived values landed as REALs (p_nmm/rocio/t_vapor/hr)
    assert row.p_nmm is not None and row.p_nmm > 1000.0

    doc_text = summaries_repo.get_summary_doc(
        fresh_db, station, 2025, 12, "diario", day=8
    )
    assert doc_text is not None
    doc = json.loads(doc_text)
    assert doc["meta"]["estacion"] == station
    assert doc["meta"]["fecha"] == "2025-12-08"  # ISO, one format everywhere
    # R3 (docs/ARQUITECTURA_DATOS.md): the observer belongs to the hour
    assert "observador" not in doc["meta"]
    hora_entry = doc["synop"]["06Z"]
    assert hora_entry["observador"] == "Andry emiliano"
    assert hora_entry["datos"]["pres_est"] == "1025.3"
    assert "Tmax" not in hora_entry["datos"]  # empty values are not stored (R2)
    assert hora_entry["grupos"]["IrIXHVV"] == "32566"
    assert hora_entry["grupos"]["Nddff"] == "50102"
    # R2: nothing derived is persisted; it is recomputed on read instead
    assert "calculado" not in hora_entry
    assert "correc_alt" not in hora_entry["datos"]
    assert "visibilidad" not in hora_entry["datos"]
    recomputed = synoptic._recalc_derived(
        {"pres_est": "1025.3", "ts": "23.2", "th": "22.9"}, station, "", "2.0")
    assert recomputed["pres_nmm"]
    assert recomputed["humedad_relativa"]


def test_save_hour_second_hour_updates_same_doc_and_keeps_first(fresh_db, station):
    synoptic.save_hour(fresh_db, station, "2025-12-08", "06Z", _hour_data())
    synoptic.save_hour(fresh_db, station, "2025-12-08", "09Z",
                       _hour_data(ts="24.1", th="22.9"))

    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, station, 2025, 12, "diario", day=8))
    assert set(doc["synop"]) == {"06Z", "09Z"}
    assert doc["synop"]["09Z"]["datos"]["ts"] == "24.1"
    assert doc["synop"]["06Z"]["datos"]["ts"] == "23.2"
    assert len(observations_repo.get_day(fresh_db, station, "2025-12-08")) == 2


def test_save_hour_rejects_group_over_5_and_writes_nothing(fresh_db, station):
    data = _hour_data()
    data["meteo_4_6"] = "123456"
    with pytest.raises(synoptic.SaveError) as excinfo:
        synoptic.save_hour(fresh_db, station, "2025-12-08", "06Z", data)

    err = excinfo.value
    assert err.field == "meteo_4_6"
    assert err.hour == "06Z"
    assert "el grupo 'meteo_4_6' en hora 06Z excede 5 caracteres (123456)." in str(err)
    # byte-exact oracle tail: the Rust literal carries a newline + 21 spaces
    assert str(err).endswith("Ejemplos válidos: 32466, 120//, /////\n                     ")
    assert observations_repo.count(fresh_db) == 0
    assert summaries_repo.count_docs(fresh_db) == 0


def test_save_hour_rejects_invalid_group_character_with_position(fresh_db, station):
    data = _hour_data()
    data["meteo_6_2"] = "0600A"
    with pytest.raises(synoptic.SaveError) as excinfo:
        synoptic.save_hour(fresh_db, station, "2025-12-08", "06Z", data)
    assert "el grupo 'meteo_6_2' en hora 06Z contiene un carácter inválido" in str(excinfo.value)
    assert "posición 5" in str(excinfo.value)
    assert observations_repo.count(fresh_db) == 0


def test_save_hour_rejects_unknown_station_and_bad_date(fresh_db, station):
    data = _hour_data()
    with pytest.raises(synoptic.SaveError, match="Código de estación inválido"):
        synoptic.save_hour(fresh_db, "", "2025-12-08", "06Z", data)
    with pytest.raises(synoptic.SaveError, match="caracteres no permitidos"):
        synoptic.save_hour(fresh_db, "NO OK!", "2025-12-08", "06Z", data)
    with pytest.raises(synoptic.SaveError, match="Se espera YYYY-MM-DD"):
        synoptic.save_hour(fresh_db, station, "2025/12/08", "06Z", data)
    with pytest.raises(synoptic.SaveError, match="calendario real"):
        synoptic.save_hour(fresh_db, station, "2025-02-30", "06Z", data)
    with pytest.raises(synoptic.SaveError, match="hora sinóptica"):
        synoptic.save_hour(fresh_db, station, "2025-12-08", "13Z", data)
    assert observations_repo.count(fresh_db) == 0


def test_save_uses_iso_year_calendar(fresh_db, station):
    # Leap-year date must be accepted (rule 9.2: real calendar validation).
    synoptic.save_hour(fresh_db, station, "2024-02-29", "06Z", _hour_data())
    rows = observations_repo.get_day(fresh_db, station, "2024-02-29")
    assert rows and rows[0].hora == "06Z"


# ---------------------------------------------------------------- observer


def test_observer_kv_roundtrip(fresh_db):
    assert synoptic.observer_for(fresh_db, "78485") == ""
    synoptic.remember_observer(fresh_db, "78485", "Ana Durán ")
    assert synoptic.observer_for(fresh_db, "78485") == "Ana Durán"
    assert synoptic.observer_for(fresh_db, "78486") == ""
    synoptic.remember_observer(fresh_db, "78486", "   ")
    assert synoptic.observer_for(fresh_db, "78486") == ""  # empty never stored


# ---------------------------------------------------------------- draft


def test_draft_roundtrip_and_validity(fresh_db, tmp_path):
    config_dir = tmp_path / "config"
    draft = synoptic.bind_draft({"06Z": {"ts": "23.2"}}, "06Z", {}, "78485", "2025-12-08")
    loaded = synoptic.save_draft(config_dir, draft)
    assert loaded is True

    assert synoptic.load_draft(config_dir, "78485", "2025-12-08") == draft
    assert synoptic.load_draft(config_dir, "78486", "2025-12-08") is None
    assert synoptic.load_draft(config_dir, "78485", "2025-12-09") is None


def test_draft_rejects_unbound_payload(tmp_path):
    with pytest.raises(ValueError):
        synoptic.save_draft(tmp_path, {"06Z": {"ts": "23.2"}})  # not bound


def test_draft_corrupt_file_is_ignored(tmp_path):
    config_dir = tmp_path
    (config_dir / "synoptic_draft.json").write_text("{not json", encoding="utf-8")
    assert synoptic.load_draft(config_dir, "78485", "2025-12-08") is None


def test_draft_clear(tmp_path):
    config_dir = tmp_path
    synoptic.save_draft(config_dir, synoptic.bind_draft({}, "06Z", {}, "S", "F"))
    synoptic.clear_draft(config_dir)
    assert synoptic.load_draft(config_dir, "S", "F") is None


# ---------------------------------------------------------------- review


def test_pre_save_review_lists_partials_and_empties():
    day = {
        "06Z": {"ts": "23.2"},          # partial: 1/21
        "09Z": dict.fromkeys(synoptic.BASE_DATA_KEYS, "1"),  # complete odd hour
        "12Z": {},                       # empty
        "15Z": {},
        "18Z": {},
        "21Z": {},
        "00Z": {},
        "03Z": {},
    }
    review = synoptic.pre_save_review(day)
    assert review["partial"] == [{"hora": "06Z", "done": 1, "total": 21}]
    assert review["empty_count"] == 6


def test_pre_save_review_all_complete_is_clean():
    odd_complete = dict.fromkeys(synoptic.BASE_DATA_KEYS, "1")
    even_complete = dict(odd_complete, **dict.fromkeys(synoptic.EVEN_EXTRA_KEYS, "1"))
    day = {
        "06Z": even_complete, "09Z": odd_complete, "12Z": even_complete,
        "15Z": odd_complete, "18Z": even_complete, "21Z": odd_complete,
        "00Z": even_complete, "03Z": odd_complete,
    }
    review = synoptic.pre_save_review(day)
    assert review["partial"] == []
    assert review["empty_count"] == 0


# ---------------------------------------------------------------- load_day (day navigation)


def test_load_day_roundtrips_saved_hour_fields(fresh_db, station):
    """Oracle get_observation: a stored day returns flat lowercase hour data."""
    synoptic.save_hour(fresh_db, station, "2025-12-08", "06Z",
                       _hour_data(), observer="Andry emiliano")
    synoptic.save_hour(fresh_db, station, "2025-12-08", "09Z",
                       _hour_data(ts="24.1", th="22.9"))

    loaded = synoptic.load_day(fresh_db, station, "2025-12-08")
    assert loaded is not None
    assert set(loaded) == set(HOURS)  # every hour present, empty or filled
    entry = loaded["06Z"]
    assert entry["ts"] == "23.2"
    assert entry["pres_est"] == "1025.3"
    assert entry["meteo_4_irixhvv"] == "32566"
    assert entry["meteo_2_1"] == "08030"
    assert entry["extra_8ns_1"] == "81819"
    assert "t_max" not in entry  # empty values are not values (R2)
    assert entry["nombre_observador"] == "Andry emiliano"
    assert loaded["09Z"]["ts"] == "24.1"
    assert not [k for k in loaded["15Z"] if k != "nombre_observador"]  # empty hour


def test_load_day_returns_none_when_no_document(fresh_db, station):
    assert synoptic.load_day(fresh_db, station, "2025-12-07") is None


def test_load_day_rejects_bad_fecha(fresh_db, station):
    with pytest.raises(synoptic.SaveError):
        synoptic.load_day(fresh_db, station, "2025-13-99")
