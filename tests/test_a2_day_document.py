"""A2 — one object carries the whole day: synoptic hours + the three CLIs.

The owner's requirement: opening 26/10/2025 must hydrate the synoptic grid
AND the CLI views from a single read, with no lost fields.
"""



from oms_core.services import cli as cli_service
from oms_core.services import document as doc_service
from oms_core.services import synoptic as synoptic_service

STATION = "78486"
FECHA = "2025-10-26"


def _legacy_doc() -> dict:
    return {
        "meta": {"estacion": STATION, "fecha": "26102025"},
        "horas": {
            "06Z": {
                "observador": "YASSER GALAN",
                "datos": {"ts": "24.1", "th": "22.0", "Tmax": "30.1", "LL": "0.0"},
                "synop": {
                    "Nddff": "50602",
                    "0CSDL DM DH": "01000",
                    "9spspsp_17": "98658",
                    "9spspsp_18": "555",
                    "9spspsp_19": "29097",
                    "9spspsp_20": "Calculos de Estación",
                },
            },
            "21Z": {"observador": "", "datos": {"ts": "27.5"}, "synop": {}},
        },
        "cli3074": {"2": {"viento_vel": "3.6", "hum_hr": "77", "fenomenos": {"granizo": True}}},
        "cli4074": {"2": {"observador": "YG", "temp_max": "30.1"}},
    }


def _schema2_doc() -> dict:
    return {
        "schema": 2,
        "meta": {"estacion": STATION, "fecha": FECHA},
        "synop": {
            "06Z": {
                "observador": "EDGAR ACOSTA",
                "datos": {"ts": "28.2"},
                "grupos": {"Nddff": "80602", "9spspsp_18": "94123"},
            }
        },
        "cli": {"3074": {"2": {"viento_vel": "4.1", "pres_alti": "1012.0"}}},
    }


# ------------------------------------------------------------- schema 1


def test_legacy_day_maps_datos_with_the_capitalisation():
    day = doc_service.day_document_from_stored(_legacy_doc(), STATION, FECHA)
    hour = day.hour("06Z")
    assert hour["ts"] == "24.1"
    assert hour["th"] == "22.0"
    assert hour["t_max"] == "30.1"   # stored as Tmax
    assert hour["ll"] == "0.0"       # stored as LL


def test_legacy_day_maps_groups_and_drops_the_pollution():
    day = doc_service.day_document_from_stored(_legacy_doc(), STATION, FECHA)
    hour = day.hour("06Z")
    assert hour["meteo_4_1"] == "50602"
    assert hour["meteo_6_2"] == "01000"          # stored as "0CSDL DM DH"
    assert hour["meteo_14_4"] == "98658"         # 9spspsp_17
    assert "meteo_14_5" not in hour              # 9spspsp_18 was "555"
    assert "meteo_14_6" not in hour              # 9spspsp_19 was 29uuu
    assert "meteo_16_0" not in hour              # 9spspsp_20 was a label


def test_every_hour_carries_the_observer_even_when_empty():
    day = doc_service.day_document_from_stored(_legacy_doc(), STATION, FECHA)
    assert day.observer("06Z") == "YASSER GALAN"
    assert day.observer("21Z") == ""
    assert set(day.observers()) == set(doc_service.HOURS)
    for hora in doc_service.HOURS:
        assert "nombre_observador" in day.hour(hora)


def test_legacy_day_carries_the_cli_blocks():
    day = doc_service.day_document_from_stored(
        _legacy_doc(), STATION, FECHA,
        {"cli3074": {"2": {"viento_vel": "3.6"}}, "cli4074": {"2": {"observador": "YG"}}},
    )
    assert day.cli["cli3074"]["2"]["viento_vel"] == "3.6"
    assert day.cli["cli4074"]["2"]["observador"] == "YG"


# ------------------------------------------------------------- schema 2


def test_schema_two_day_owns_all_24_lanes():
    day = doc_service.day_document_from_stored(_schema2_doc(), STATION, FECHA)
    hour = day.hour("06Z")
    assert hour["ts"] == "28.2"
    assert hour["meteo_4_1"] == "80602"
    assert hour["meteo_14_5"] == "94123"          # lane 18 is real in schema 2
    assert day.schema == 2


def test_schema_two_reads_the_cli_block_from_the_nested_object():
    doc = _schema2_doc()
    day = doc_service.day_document_from_stored(
        doc, STATION, FECHA, {"cli3074": doc["cli"]["3074"]}
    )
    assert day.cli["cli3074"]["2"]["pres_alti"] == "1012.0"


# --------------------------------------------------------------- loader


def test_an_empty_day_has_eight_hours_and_three_clis():
    day = doc_service.empty_day_document(STATION, FECHA)
    assert set(day.horas) == set(doc_service.HOURS)
    assert all(day.hour(h)["nombre_observador"] == "" for h in doc_service.HOURS)
    assert day.cli == {"cli3074": {}, "cli4074": {}, "cli5074": {}}


def test_load_day_document_reads_the_stored_day(fresh_db):
    doc = _legacy_doc()
    synoptic_service.save_hour(
        fresh_db, STATION, FECHA, "06Z",
        {"ts": "24.1", "nombre_observador": "YASSER GALAN", "meteo_4_1": "50602"},
    )
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli3074", {"2": {"viento_vel": "3.6"}})
    day = doc_service.load_day_document(fresh_db, STATION, FECHA)
    assert day is not None
    assert day.hour("06Z")["ts"] == "24.1"
    assert day.hour("06Z")["meteo_4_1"] == "50602"
    assert day.observer("06Z") == "YASSER GALAN"
    assert day.cli["cli3074"]["2"]["viento_vel"] == "3.6"
    assert doc  # the fixture document stays as reference for the mapping


def test_load_day_document_returns_none_without_a_document(fresh_db):
    assert doc_service.load_day_document(fresh_db, STATION, FECHA) is None
