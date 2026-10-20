"""A9 — the schema 2 contract is checked by a schema, not by hand.

`jsonschema` replaces a growing pile of isinstance checks and names the exact
path that broke, so an imported file is either accepted or rejected with
evidence.
"""

import pytest

from oms_core.services import document_schema as schema

STATION = "78486"


def _doc(**overrides):
    doc = {
        "schema": 2,
        "meta": {"estacion": STATION, "fecha": "2025-10-26"},
        "synop": {
            "06Z": {
                "observador": "YASSER GALAN",
                "datos": {"ts": "24.1", "pres_est": "1001.6"},
                "grupos": {"Nddff": "50602", "9spspsp_17": "98658"},
            }
        },
        "cli": {"3074": {"2": {"viento_vel": "3.6"}}},
    }
    doc.update(overrides)
    return doc


def test_a_good_document_passes():
    schema.validate_document_schema(_doc())


def test_the_observer_is_mandatory_in_every_hour():
    doc = _doc()
    del doc["synop"]["06Z"]["observador"]
    with pytest.raises(schema.DocumentSchemaError) as exc:
        schema.validate_document_schema(doc)
    assert "observador" in str(exc.value)


def test_an_empty_observer_is_accepted():
    doc = _doc()
    doc["synop"]["06Z"]["observador"] = ""
    schema.validate_document_schema(doc)


def test_the_station_and_the_iso_date_are_required():
    with pytest.raises(schema.DocumentSchemaError) as exc:
        schema.validate_document_schema(_doc(meta={"fecha": "2025-10-26"}))
    assert "estacion" in str(exc.value)

    with pytest.raises(schema.DocumentSchemaError) as exc:
        schema.validate_document_schema(_doc(meta={"estacion": STATION, "fecha": "26102025"}))
    assert "meta/fecha" in str(exc.value)


def test_an_unknown_hour_is_rejected():
    doc = _doc()
    doc["synop"]["07Z"] = {"observador": ""}
    with pytest.raises(schema.DocumentSchemaError) as exc:
        schema.validate_document_schema(doc)
    assert "07Z" in str(exc.value) or "synop" in str(exc.value)


def test_an_unknown_group_is_rejected():
    doc = _doc()
    doc["synop"]["06Z"]["grupos"]["no_existe"] = "00000"
    with pytest.raises(schema.DocumentSchemaError) as exc:
        schema.validate_document_schema(doc)
    assert "no_existe" in str(exc.value)


def test_a_group_longer_than_five_characters_is_rejected():
    doc = _doc()
    doc["synop"]["06Z"]["grupos"]["Nddff"] = "123456"
    with pytest.raises(schema.DocumentSchemaError):
        schema.validate_document_schema(doc)


def test_the_schema_requires_one_of_the_two_containers():
    doc = _doc()
    del doc["synop"]
    with pytest.raises(schema.DocumentSchemaError):
        schema.validate_document_schema(doc)


def test_is_schema_two():
    assert schema.is_schema_two({"schema": 2}) is True
    assert schema.is_schema_two({"schema": 1}) is False
    assert schema.is_schema_two({}) is False
    assert schema.is_schema_two("no soy un dict") is False
