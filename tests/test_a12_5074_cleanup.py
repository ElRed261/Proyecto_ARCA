"""A12 — the 5074 no longer carries the daily extremes block.

The owner asked to drop everything from TEMPERATURA °C down to RECORRIDO DEL
VIENTO: it duplicated what the synoptic form and the 4074 already hold.
"""

from oms_ui.pages.cli5074 import Cli5074View, get_initial_state

REMOVED_FIELDS = (
    "temp_max", "temp_min",
    "rafaga_dir", "rafaga_vel", "rafaga_hora",
    "hum_max", "hum_min",
    "pres_max", "pres_min",
    "insolac", "radiac", "lluvia", "evap_tanque_a",
    "punto_rocio", "recorrido_viento",
)


def test_the_document_has_no_daily_section():
    state = get_initial_state()
    assert "daily" not in state
    for field in REMOVED_FIELDS:
        assert field not in state


def test_the_remaining_sections_survive():
    state = get_initial_state()
    for section in ("hourly", "subsuelo", "evaporimetros",
                    "iniciales_obs", "observaciones_manuales", "fenomenos"):
        assert section in state, section


def test_the_view_does_not_build_the_removed_fields(qtbot, fresh_db):
    view = Cli5074View(fresh_db, station="78486", fecha="2024-04-28")
    qtbot.addWidget(view)
    assert not [key for key in view.fields if key.startswith("daily.")]


def test_the_hourly_and_subsuelo_fields_still_exist(qtbot, fresh_db):
    view = Cli5074View(fresh_db, station="78486", fecha="2024-04-28")
    qtbot.addWidget(view)
    assert any(key.startswith("hourly.") for key in view.fields)
    assert any(key.startswith("subsuelo.") for key in view.fields)
    assert "iniciales_obs" in view.fields
