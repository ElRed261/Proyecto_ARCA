"""A18 — the observer initials of every CLI hour (owner round 23, S6).

Each CLI keeps who wrote it: the 3074 and the 4074 per hour row, the 5074 once
for the whole sheet. The initials are their own field (not derived from the
OBS name) and they travel to the stored JSON.
"""

from oms_core.services import cli as cli_service
from oms_core.services import synoptic as synoptic_service

STATION = "78486"
FECHA = "2024-04-28"


def _page(qtbot, conn, view_name):
    from oms_ui.pages import cli3074 as ui3074
    from oms_ui.pages import cli4074 as ui4074
    from oms_ui.pages import cli5074 as ui5074

    if view_name == "3074":
        page = ui3074.Cli3074View(conn, station=STATION, fecha=FECHA)
    elif view_name == "4074":
        page = ui4074.Cli4074View(conn, station=STATION, fecha=FECHA)
    else:
        page = ui5074.Cli5074View(conn, station=STATION, fecha=FECHA)
    qtbot.addWidget(page)
    return page


def test_the_3074_keeps_the_initials_of_every_hour(fresh_db, qtbot):
    page = _page(qtbot, fresh_db, "3074")
    page.row_inputs[2]["observador"].setText("YG")
    page.row_inputs[5]["observador"].setText("EA")
    page.save_data() if hasattr(page, "save_data") else page.save()

    stored = cli_service.load_cli(fresh_db, STATION, FECHA, "cli3074")
    rows = stored.get("horas") if isinstance(stored.get("horas"), dict) else stored
    assert rows["2"]["observador"] == "YG"
    assert rows["5"]["observador"] == "EA"


def test_the_3074_paints_the_stored_initials(fresh_db, qtbot):
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli3074", {
        "horas": {"8": {"observador": "AC"}},
    })
    page = _page(qtbot, fresh_db, "3074")
    assert page.row_inputs[8]["observador"].text() == "AC"


def test_the_4074_keeps_its_observer_column(fresh_db, qtbot):
    page = _page(qtbot, fresh_db, "4074")
    page.row_inputs[1]["observador"].setText("YG")
    page.save_data()
    stored = cli_service.load_cli(fresh_db, STATION, FECHA, "cli4074")
    rows = stored.get("horas") if isinstance(stored.get("horas"), dict) else stored
    assert rows["1"]["observador"] == "YG"


def test_the_5074_has_one_initials_field_for_the_sheet(fresh_db, qtbot):
    page = _page(qtbot, fresh_db, "5074")
    assert "iniciales_obs" in page.fields
    page.fields["iniciales_obs"].setText("YG")
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli5074", page.state())
    stored = cli_service.load_cli(fresh_db, STATION, FECHA, "cli5074")
    assert stored["iniciales_obs"] == "YG"


def test_the_3074_initials_survive_a_day_save(fresh_db):
    """Saving the day must not clean them away (OBSERVED_CLI3074)."""
    cli_service.save_cli(fresh_db, STATION, FECHA, "cli3074", {
        "horas": {"2": {"viento_vel": "4", "observador": "YG"}},
    })
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z",
                               {"meteo_4_1": "50602"})
    stored = cli_service.load_cli(fresh_db, STATION, FECHA, "cli3074")
    rows = stored.get("horas") if isinstance(stored.get("horas"), dict) else stored
    assert rows["2"]["observador"] == "YG"
