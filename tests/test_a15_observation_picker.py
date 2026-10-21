"""A15 — "Cargar Observación": the archive is browsed inside the app.

The owner replaced the file explorer: the window lists the stations by NAME
(only when the session can see more than one), then year -> month -> day under
monochrome icons, and returns the chosen ``(station, ISO date)``.
"""

import pytest
from PySide6.QtWidgets import QDialog, QLabel

from oms_core.services import synoptic as synoptic_service
from oms_ui.observation_picker import (
    ObservationPickerDialog,
    day_label,
    month_name,
)

STATION = "78486"


@pytest.fixture
def seeded(fresh_db):
    """Two days of 2024 and one of 2023 for the same station."""
    for fecha in ("2024-04-28", "2024-04-30", "2023-10-14"):
        synoptic_service.save_hour(fresh_db, STATION, fecha, "06Z",
                                   {"meteo_4_1": "50602"})
    return fresh_db


def test_the_month_and_day_labels_are_human_readable():
    assert month_name("04") == "abril"
    assert month_name("4") == "abril"
    assert day_label("2024-04-28") == "28 · dom"


def test_the_dialog_lists_the_stations_by_name(seeded, qtbot):
    dialog = ObservationPickerDialog(seeded, station=STATION)
    qtbot.addWidget(dialog)
    assert dialog.station_list.count() >= 1
    first = dialog.station_list.item(0)
    card = dialog.station_list.itemWidget(first)
    assert isinstance(card, QLabel)
    assert card.text().split("<br>")[0].count("784") == 0, "el nombre va primero"


def test_a_single_station_session_hides_the_list(seeded, qtbot):
    dialog = ObservationPickerDialog(seeded, station=STATION, show_stations=False)
    qtbot.addWidget(dialog)
    assert not hasattr(dialog, "station_list")
    assert dialog.tree.topLevelItemCount() == 2  # 2024 and 2023


def test_the_tree_walks_year_month_day(seeded, qtbot):
    dialog = ObservationPickerDialog(seeded, station=STATION)
    qtbot.addWidget(dialog)
    years = [dialog.tree.topLevelItem(i).text(0) for i in range(dialog.tree.topLevelItemCount())]
    assert years[0].startswith("2024"), "el año más nuevo primero"
    year = dialog.tree.topLevelItem(0)
    month = year.child(0)
    assert month.text(0).startswith("abril")
    assert month.childCount() == 2
    assert [month.child(i).text(0) for i in range(2)] == ["28 · dom", "30 · mar"]


def test_choosing_a_day_returns_the_padded_iso_date(seeded, qtbot):
    dialog = ObservationPickerDialog(seeded, station=STATION)
    qtbot.addWidget(dialog)
    day = dialog.tree.topLevelItem(1).child(0).child(0)  # 2023-10-14
    dialog.tree.setCurrentItem(day)
    assert dialog.load_btn.isEnabled()
    dialog._accept_selection()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selection() == (STATION, "2023-10-14")


def test_a_year_or_month_node_cannot_be_loaded(seeded, qtbot):
    dialog = ObservationPickerDialog(seeded, station=STATION)
    qtbot.addWidget(dialog)
    dialog.tree.setCurrentItem(dialog.tree.topLevelItem(0))
    assert not dialog.load_btn.isEnabled()


def test_a_station_without_days_says_so(fresh_db, qtbot):
    dialog = ObservationPickerDialog(fresh_db, station=STATION)
    qtbot.addWidget(dialog)
    assert dialog.empty_label.isVisible() is False  # not shown until displayed
    dialog.show()
    assert dialog.tree.topLevelItemCount() == 0
    assert dialog.empty_label.isVisible() is True
