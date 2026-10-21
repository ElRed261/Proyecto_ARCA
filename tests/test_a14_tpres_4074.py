"""A14 — T.PRES. always reads two digits; the 4074 zeroes only where asked.

The T.PRES. column of the CLI 3074 is a two-digit field. When the value comes
from the group ``7wwW1W2`` it is its second and third digits, and a
single-digit ``ww`` still reads padded (``71`` -> ``01``) instead of falling
through to the cloud-cover comparison.

The CLI 4074 keeps the grey "0" placeholder only on the rows the owner marked;
the rest of the sheet stays visually blank.
"""

import pytest

import oms_calc
from oms_core.services import cli as cli_service
from oms_core.services import synoptic as synoptic_service

STATION = "78486"
FECHA = "2024-04-28"


# ------------------------------------------------------- T.PRES. de dos dígitos


def test_the_boundary_pads_a_single_digit_ww():
    assert oms_calc.calc_tiempo_presente("71", "", "") == "01"
    assert oms_calc.calc_tiempo_presente("79", "", "") == "09"
    assert oms_calc.calc_tiempo_presente("70205", "", "") == "02"
    assert oms_calc.calc_tiempo_presente("7", "", "") == ""


def test_every_derived_tpres_has_two_digits_or_none(fresh_db):
    for group in ("71", "70205", "701", "70311"):
        synoptic_service.save_hour(fresh_db, STATION, FECHA, "12Z",
                                   {"meteo_4_1": "50602", "meteo_4_6": group})
        value = cli_service.load_cli3074(
            fresh_db, STATION, FECHA)["horas"]["8"]["tiempo_presente"]
        assert value in ("", None) or (len(value) == 2 and value.isdigit()), group


def test_the_single_digit_group_reaches_the_sheet_as_01(fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "09Z",
                               {"meteo_4_1": "30100"})
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "12Z",
                               {"meteo_4_1": "50602", "meteo_4_6": "71"})
    row = cli_service.load_cli3074(fresh_db, STATION, FECHA)["horas"]["8"]
    assert row["tiempo_presente"] == "01"


def test_the_group_digits_win_over_the_cloud_comparison(fresh_db):
    """70205 says ww=02: the cloud cover changing must not override it."""
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "09Z",
                               {"meteo_4_1": "30100"})
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "12Z",
                               {"meteo_4_1": "50602", "meteo_4_6": "70205"})
    assert cli_service.load_cli3074(
        fresh_db, STATION, FECHA)["horas"]["8"]["tiempo_presente"] == "02"


# ------------------------------------------------- 4074: ceros sólo donde van


def test_the_4074_zeroes_only_the_rows_the_owner_marked():
    from oms_ui.pages.cli4074 import ZERO_PLACEHOLDER_ROWS

    assert ZERO_PLACEHOLDER_ROWS == frozenset({2, 5, 8, 11, 14, 15, 16, 17, 20, 23})
    # the fourteen blank rows the owner listed are exactly the rest
    blank = {1, 3, 4, 6, 7, 9, 10, 12, 13, 18, 19, 21, 22, 24}
    assert set(range(1, 25)) - ZERO_PLACEHOLDER_ROWS == blank


@pytest.mark.parametrize("row,expected", [
    (1, ""), (2, "0"), (3, ""), (4, ""), (5, "0"), (6, ""), (7, ""), (8, "0"),
    (9, ""), (10, ""), (11, "0"), (12, ""), (13, ""), (14, "0"), (15, "0"),
    (16, "0"), (17, "0"), (18, ""), (19, ""), (20, "0"), (21, ""), (22, ""),
    (23, "0"), (24, ""),
])
def test_the_sheet_placeholders_per_row(qtbot, fresh_db, row, expected):
    from oms_ui.pages.cli4074 import Cli4074View

    page = Cli4074View(fresh_db, station=STATION, fecha=FECHA)
    qtbot.addWidget(page)
    for field, widget in page.row_inputs[row].items():
        if field == "observador":
            assert widget.placeholderText() == ""
        else:
            assert widget.placeholderText() == expected, (row, field)
