"""Tests for the transform core (extracted from miscelaneos/scratch/excel_to_json.py).

Golden values below were confirmed against the real fixture with a live run
of parse_excel (openpyxl 3.1.5): estacion 78486, fecha 01032026, 8 Z-hours,
06Z datos.ts == "24.4", 06Z synop.YYGGiw == "01061", cli3074["2"] pres_est
== "1014.2" and tend_car == "6".
"""

import pytest

from arca_pipeline.transform.excel_to_json import parse_excel


def test_parse_excel_fixture_golden(fixture_xlsm_path):
    result = parse_excel(fixture_xlsm_path)

    assert result["meta"]["estacion"] == "78486"
    assert result["meta"]["fecha"] == "01032026"

    assert list(result["horas"].keys()) == ["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"]
    assert result["horas"]["06Z"]["datos"]["ts"] == "24.4"
    assert result["horas"]["06Z"]["synop"]["YYGGiw"] == "01061"

    assert result["cli3074"]["2"]["pres_est"] == "1014.2"
    assert result["cli3074"]["2"]["tend_car"] == "6"


def test_parse_excel_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_excel("/nonexistent/path/no_such_file.xlsm")


def test_parse_excel_override_station_and_date(fixture_xlsm_path):
    result = parse_excel(fixture_xlsm_path, station="99999", date="2026-03-01")

    assert result["meta"]["estacion"] == "99999"
    assert result["meta"]["fecha"] == "01032026"
    assert result["meta"]["ultima_actualizacion"] == ""