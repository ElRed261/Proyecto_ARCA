"""A16 — round 23: the per-hour observer, the Table 1860 gate and day order.

S4: opening a saved day must show that hour's observer (the window used to
paint only the name remembered for the station).
S5: with iX 2, 3, 5 or 6 the group 7wwW1W2 is omitted, so the field shows the
identification figure `7`, stays disabled and keeps whatever was stored.
S3: the picker lists the days 1, 2, 3 ... 10, 11, not as text.
"""

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QWidget

from oms_core.services import synoptic as synoptic_service
from oms_core.services.document import load_day_document
from oms_ui.observation_picker import ObservationPickerDialog

STATION = "78486"
FECHA = "2024-04-28"


class _Stub(QDialog):
    """Non-blocking stand-in for the review and draft-guard dialogs.

    Closing a dirty page opens the draft guard modally; without this stub the
    test teardown blocks forever waiting for a click.
    """

    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent")
        if parent is None:
            parent = next(
                (arg for arg in args if isinstance(arg, QWidget)), None
            )
        super().__init__(parent)
        self.review = args[0] if args else {}

    def exec(self):
        return QDialog.DialogCode.Accepted


@pytest.fixture
def page(fresh_db, qtbot, monkeypatch):
    import pathlib

    import oms_ui.pages.synoptic as synoptic_ui

    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _Stub)
    page = synoptic_ui.SynopticPage(
        fresh_db, config_dir=pathlib.Path("/tmp"), role="admin"
    )
    qtbot.addWidget(page)
    page.set_station(STATION)

    class _Guard(_Stub):
        def exec(self):
            return synoptic_ui.DraftGuardDialog.DISCARD

    page._draft_guard_class = _Guard  # pytest-qt closes widgets at teardown
    return page


# ------------------------------------------------- S4: observador por hora


def test_the_loaded_day_shows_each_hours_observer(page, fresh_db):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z",
                               {"nombre_observador": "YASSER GALAN"})
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "12Z",
                               {"nombre_observador": "EDGAR ACOSTA"})
    page.fecha_edit.setDate(QDate(2024, 4, 28))
    page.select_hour("06Z")
    assert page.observer_edit.text() == "YASSER GALAN"
    page.select_hour("12Z")
    assert page.observer_edit.text() == "EDGAR ACOSTA"


def test_an_hour_without_observer_falls_back_to_the_remembered_name(page):
    synoptic_service.remember_observer(page._conn, STATION, "MARTA PEREZ")
    page.fecha_edit.setDate(QDate(2024, 4, 28))
    page.select_hour("09Z")
    assert page.observer_edit.text() == "MARTA PEREZ"


# ------------------------------------------- S5: Tabla 1860 y la cifra «7»


@pytest.mark.parametrize("ix", ["2", "3", "5", "6"])
def test_an_omitted_group_shows_only_the_seven(page, ix):
    page.select_hour("06Z")
    page.field("meteo_4_irixhvv").setText(f"3{ix}566")
    field = page.field("meteo_4_6")
    assert field.text() == "7"
    assert not field.isEnabled()


@pytest.mark.parametrize("ix", ["1", "4", "7"])
def test_an_included_group_stays_editable(page, ix):
    page.select_hour("06Z")
    page.field("meteo_4_irixhvv").setText(f"3{ix}566")
    field = page.field("meteo_4_6")
    assert field.isEnabled()
    field.setText("70311")
    assert field.text() == "70311"


def test_the_stored_group_survives_a_save_with_the_gate_closed(page, fresh_db):
    """Showing "7" must never destroy what the observer had written."""
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", {
        "meteo_4_irixhvv": "32566", "meteo_4_6": "70311",
        "nombre_observador": "YASSER GALAN",
    })
    page.fecha_edit.setDate(QDate(2024, 4, 28))
    page.select_hour("06Z")
    assert page.field("meteo_4_6").text() == "7"     # display only
    page.save_clicked()
    stored = load_day_document(fresh_db, STATION, FECHA).horas.get("06Z") or {}
    assert stored.get("meteo_4_6") == "70311"        # kept, not overwritten


def test_an_empty_day_never_stores_an_invented_six_group(page, fresh_db):
    page.fecha_edit.setDate(QDate(2024, 4, 28))
    page.select_hour("06Z")
    page.field("meteo_4_irixhvv").setText("32566")
    page.save_clicked()
    stored = load_day_document(fresh_db, STATION, FECHA).horas.get("06Z") or {}
    assert stored.get("meteo_4_6") in ("", None)


# ------------------------------------------------ S3: días en orden numérico


def test_the_picker_lists_the_days_in_numeric_order(fresh_db, qtbot):
    for day in (1, 2, 10, 11, 20, 3):
        synoptic_service.save_hour(fresh_db, STATION, f"2024-04-{day:02d}",
                                   "06Z", {"meteo_4_1": "50602"})
    dialog = ObservationPickerDialog(fresh_db, station=STATION)
    qtbot.addWidget(dialog)
    month = dialog.tree.topLevelItem(0).child(0)
    days = [month.child(i).text(0).split(" ")[0] for i in range(month.childCount())]
    assert days == ["01", "02", "03", "10", "11", "20"]
