"""A1 — the single mapping table (day document <-> form fields).

Every observation value is either observed (persisted) or derived (recomputed
on read). Before this table the reader and the writer each had their own list
and they disagreed: six ``datos`` keys never reached the form and the whole
``synop`` block was ignored on load.
"""

import pytest

import oms_calc
from oms_core.services import document_map as dm
from oms_core.services import synoptic as synoptic_service


def test_the_table_covers_the_44_group_fields():
    assert len(dm.SYNOP_FIELDS) == 44
    form_keys = [form for form, _synop in dm.SYNOP_FIELDS]
    synop_names = [synop for _form, synop in dm.SYNOP_FIELDS]
    assert len(set(form_keys)) == 44
    assert len(set(synop_names)) == 44


def test_the_44_form_keys_include_row_14():
    """Row 14 was missing from the legacy list: 7 lanes vanished on load."""
    form_keys = {form for form, _synop in dm.SYNOP_FIELDS}
    for col in range(7):
        assert f"meteo_14_{col}" in form_keys


def test_synop_names_match_the_calculation_boundary():
    """The table may only differ from the calc boundary in the spacing the
    owner asked to remove (``0CSDL DM DH`` -> ``0CSDLDMDH``)."""
    for form_key, synop_name in dm.SYNOP_FIELDS:
        assert oms_calc.to_synop_name(form_key).replace(" ", "") == synop_name, form_key


def test_legacy_spaced_group_name_is_read():
    assert dm.document_to_groups({"0CSDL DM DH": "01000"}, legacy=True) == {
        "meteo_6_2": "01000"
    }
    assert dm.document_to_groups({"0CSDLDMDH": "01000"}, legacy=True) == {
        "meteo_6_2": "01000"
    }


def test_legacy_field_keys_do_not_drift_from_the_table():
    """Same coverage, order aside: both lists must name the same 44 fields."""
    expected = {form for form, _synop in dm.SYNOP_FIELDS}
    assert set(synoptic_service._SYNOP_FIELD_KEYS) == expected
    assert len(synoptic_service._SYNOP_FIELD_KEYS) == 44


def test_datos_round_trip_keeps_form_keys():
    hour_data = {"ts": "28.2", "th": "24.1", "t_max": "30.1", "ll": "0.0"}
    doc = dm.datos_to_document(hour_data)
    assert doc == {"ts": "28.2", "th": "24.1", "Tmax": "30.1", "LL": "0.0"}
    assert dm.document_to_datos(doc) == hour_data


def test_empty_strings_in_the_document_are_not_values():
    """The legacy writer stored "" for unfilled fields; reading ignores them."""
    assert dm.document_to_datos({"ts": "24.1", "Tmax": "", "LL": None}) == {"ts": "24.1"}


def test_empty_values_are_not_written():
    assert dm.datos_to_document({"ts": "", "th": None, "pres_est": "1001.6"}) == {
        "pres_est": "1001.6"
    }


@pytest.mark.parametrize(
    "form_key", ["correc_alt", "visibilidad", "viento_dir", "viento_vel"]
)
def test_derived_datos_are_never_persisted(form_key):
    assert form_key not in dict(dm.OBSERVED_DATOS)
    assert dm.is_derived(form_key) is True


def test_observed_keys_are_not_derived():
    assert dm.is_derived("ts") is False
    assert dm.is_derived("meteo_4_1") is False  # a group field


def test_legacy_polluted_lanes_are_skipped():
    """Lanes 18..24 in the old files hold 555, 29uuu and UI labels."""
    grupos = {
        "9spspsp_1": "94082",
        "9spspsp_17": "98658",
        "9spspsp_18": "555",
        "9spspsp_19": "29097",
        "9spspsp_20": "Calculos de Estación",
    }
    legacy = dm.document_to_groups(grupos, legacy=True)
    assert legacy == {"meteo_10_2": "94082", "meteo_14_4": "98658"}


def test_a_schema_two_document_owns_all_24_lanes():
    grupos = {"9spspsp_18": "94123"}
    assert dm.document_to_groups(grupos, legacy=False) == {"meteo_14_5": "94123"}


@pytest.mark.parametrize("junk", ["900090", "9*0090", "29071=", "Calculos"])
def test_malformed_group_values_are_dropped(junk):
    assert dm.document_to_groups({"Nddff": junk}, legacy=False) == {}


def test_groups_round_trip_for_valid_codes():
    hour_data = {"meteo_4_1": "50602", "meteo_14_4": "98658"}
    doc = dm.groups_to_document(hour_data)
    assert doc == {"Nddff": "50602", "9spspsp_17": "98658"}
    assert dm.document_to_groups(doc, legacy=False) == hour_data


def test_cli_surfaces_keep_only_the_manual_entries():
    assert dm.OBSERVED_CLI3074 == ("viento_vel", "pres_alti", "fenomenos")
    assert dm.OBSERVED_CLI4074 == ("observador", "fenomenos")
