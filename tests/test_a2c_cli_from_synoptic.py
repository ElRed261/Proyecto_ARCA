"""A2c — the CLI 3074 view derives from the synoptic hour (rule R3).

The owner's model: ``temp_seco``/``temp_humedo`` ARE ``ts``/``th``; correcting
them in the form must show up in the CLI. The old build copied them once, only
into empty rows, which is how the corpus ended up with disagreeing values.
"""



from oms_core.services import cli as cli_service
from oms_core.services import synoptic as synoptic_service

STATION = "78486"
FECHA = "2025-10-26"
HOUR_06Z = {
    "ts": "24.1",
    "th": "22.0",
    "pres_est": "1001.6",
    "p3": "1000.0",
    "meteo_4_1": "50602",
    "meteo_4_irixhvv": "32466",
    "meteo_4_6": "76366",
    "nombre_observador": "YASSER GALAN",
}


def _save_synoptic(conn):
    synoptic_service.save_hour(conn, STATION, FECHA, "06Z", HOUR_06Z)


def test_legacy_flat_cli_block_is_normalised():
    """Old documents keep the rows at the top level; Neo expects 'horas'."""
    flat = {**cli_service._normalize_cli_block({"2": {"viento_vel": "3.6"}})}
    assert flat["horas"]["2"]["viento_vel"] == "3.6"


def test_a_current_block_passes_through():
    wrapped = {"horas": {"2": {"viento_vel": "3.6"}}}
    assert cli_service._normalize_cli_block(wrapped) == wrapped


def test_the_cli_row_shows_the_synoptic_temperatures(fresh_db):
    _save_synoptic(fresh_db)
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli3074",
                         {"horas": {"2": {"viento_vel": "3.6"}}})
    doc = cli_service.load_cli3074(fresh_db, STATION, FECHA)
    row = doc["horas"]["2"]
    assert row["temp_seco"] == "24.1"      # ts
    assert row["temp_humedo"] == "22.0"    # th
    assert row["pres_est"] == "1001.6"


def test_the_cli_row_shows_the_derived_values(fresh_db):
    _save_synoptic(fresh_db)
    doc = cli_service.load_cli3074(fresh_db, STATION, FECHA)
    row = doc["horas"]["2"]
    assert row["visibilidad"]            # from IrIXHVV
    assert row["tend_dif"]               # from pres_est/p3
    assert row["tend_car"]
    assert row["hum_hr"]                 # psychrometric from ts/th
    assert row["hum_tvap"]
    assert row["hum_ptor"]
    assert row["pres_nmm"]


def test_the_wind_direction_comes_from_nddff(fresh_db):
    _save_synoptic(fresh_db)
    doc = cli_service.load_cli3074(fresh_db, STATION, FECHA)
    # Nddff "50602": dd = "06" -> 60 degrees
    assert doc["horas"]["2"]["viento_dir"] == "60"


def test_manual_cli_values_are_preserved(fresh_db):
    _save_synoptic(fresh_db)
    cli_service.save_cli(
        fresh_db, STATION, FECHA, "cli3074",
        {"horas": {"2": {"viento_vel": "3.6", "pres_alti": "1012.3",
                         "fenomenos": {"granizo": True}}}},
    )
    row = cli_service.load_cli3074(fresh_db, STATION, FECHA)["horas"]["2"]
    assert row["viento_vel"] == "3.6"     # typed, never derived
    assert row["pres_alti"] == "1012.3"   # altimeter, typed
    assert row["fenomenos"]["granizo"] is True


def test_a_day_without_synoptic_data_keeps_the_stored_row(fresh_db):
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli3074",
                         {"horas": {"2": {"viento_vel": "2.0"}}})
    doc = cli_service.load_cli3074(fresh_db, STATION, FECHA)
    assert doc["horas"]["2"]["viento_vel"] == "2.0"
    assert "temp_seco" not in doc["horas"]["2"]
