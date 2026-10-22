"""A19 — a CLI edit typed just before a context change must not be lost.

The three CLI views are cached across days (``SynopticPage._cli_views``) and
autosave on a 700 ms debounce. Changing the day, the station or navigating
reloaded the same widgets with the other day's data, so an edit that had not
fired its timer yet was written against the wrong day or dropped entirely —
exactly the "lleno un dato del 5074 y no se guarda" the owner hit.
"""

import pathlib

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QWidget

from oms_core.services import cli as cli_service

STATION = "78486"
DAY_A = "2024-04-28"
DAY_B = "2024-04-29"


class _Stub(QDialog):
    """Non-blocking stand-in for the review and draft-guard dialogs."""

    def __init__(self, *args, **kwargs):
        parent = kwargs.get("parent")
        if parent is None:
            parent = next((a for a in args if isinstance(a, QWidget)), None)
        super().__init__(parent)
        self.review = args[0] if args else {}

    def exec(self):
        return QDialog.DialogCode.Accepted


@pytest.fixture
def page(fresh_db, qtbot, monkeypatch):
    import oms_ui.pages.synoptic as synoptic_ui

    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _Stub)
    page = synoptic_ui.SynopticPage(
        fresh_db, config_dir=pathlib.Path("/tmp"), role="admin"
    )
    qtbot.addWidget(page)
    page.set_station(STATION)
    page.fecha_edit.setDate(QDate(2024, 4, 28))

    class _Guard(_Stub):
        def exec(self):
            return synoptic_ui.DraftGuardDialog.DISCARD

    page._draft_guard_class = _Guard
    return page


def _open(page, module_key):
    page._open_cli(module_key)
    return page._cli_views[module_key]


def test_a_5074_edit_survives_changing_the_day(page, fresh_db):
    view = _open(page, "cli5074")
    view.fields["hourly.2.lect_bar"].setText("1012.3")
    page.fecha_edit.setDate(QDate(2024, 4, 29))  # before the 700 ms debounce

    stored = cli_service.load_cli(fresh_db, STATION, DAY_A, "cli5074")
    assert stored["hourly"]["2"]["lect_bar"] == "1012.3"
    assert cli_service.load_cli(fresh_db, STATION, DAY_B, "cli5074") is None


def test_a_3074_edit_survives_changing_the_day(page, fresh_db):
    view = _open(page, "cli3074")
    view.row_inputs[2]["pres_alti"].setText("1012.7")
    page.fecha_edit.setDate(QDate(2024, 4, 29))

    stored = cli_service.load_cli(fresh_db, STATION, DAY_A, "cli3074")
    rows = stored.get("horas") if isinstance(stored.get("horas"), dict) else stored
    assert rows["2"]["pres_alti"] == "1012.7"
    assert cli_service.load_cli(fresh_db, STATION, DAY_B, "cli3074") is None


def test_a_4074_edit_survives_changing_the_day(page, fresh_db):
    view = _open(page, "cli4074")
    view.row_inputs[1]["observador"].setText("YG")
    page.fecha_edit.setDate(QDate(2024, 4, 29))

    stored = cli_service.load_cli(fresh_db, STATION, DAY_A, "cli4074")
    rows = stored.get("horas") if isinstance(stored.get("horas"), dict) else stored
    assert rows["1"]["observador"] == "YG"


def test_a_5074_edit_survives_navigating_with_the_arrows(page, fresh_db):
    view = _open(page, "cli5074")
    view.fields["subsuelo.d5"].setText("24.1")
    page.navigate_to_day(1)

    assert page.fecha_iso == DAY_B
    stored = cli_service.load_cli(fresh_db, STATION, DAY_A, "cli5074")
    assert stored["subsuelo"]["d5"] == "24.1"


def test_no_pending_timer_is_left_behind_after_the_flush(page):
    view = _open(page, "cli5074")
    view.fields["iniciales_obs"].setText("YG")
    page.fecha_edit.setDate(QDate(2024, 4, 29))
    assert view._autosave_timer.isActive() is False


def test_the_flush_does_not_create_empty_days(page, fresh_db):
    """Flushing an untouched view must not write a blank sheet."""
    _open(page, "cli5074")
    page.fecha_edit.setDate(QDate(2024, 4, 29))
    assert cli_service.load_cli(fresh_db, STATION, DAY_A, "cli5074") is None


# ------------------------------------- the 5074 is stored whole (decision A)


def test_the_5074_block_is_never_cleaned(fresh_db):
    """Owner round 24: EVERY value of the 5074 must be stored, so the block is
    persisted exactly as the window produced it — no field filtering."""
    from oms_core.services import document_map as dm

    block = {
        "iniciales_obs": "YG",
        "observaciones_manuales": "// sin novedad",
        "hourly": {"2": {"lect_bar": "1012.1", "correc_temp": "0.0"}},
        "subsuelo": {"d5": "24.1", "d100": "INAP"},
        "evaporimetros": {"piche": "0", "tanque_c": "3.2"},
        "fenomenos": [{"hora": "14", "fenomeno": "niebla"}],
    }
    assert dm.clean_cli_block("cli5074", block) == block

    cli_service.save_cli(fresh_db, STATION, DAY_A, "cli5074", block)
    assert cli_service.load_cli(fresh_db, STATION, DAY_A, "cli5074") == block


# ----------------------------------------- Auditoría right after Sinóptico


def test_audit_sits_immediately_after_synoptic():
    """Owner round 25: the auditor works next to the observation it marks."""
    from oms_ui.main_window import _RAIL_MODULE_IDS, NAV_ENTRIES

    entries = [entry[0] for entry in NAV_ENTRIES]
    assert entries[:3] == ["dashboard", "synoptic", "audit"]
    assert list(_RAIL_MODULE_IDS)[:2] == ["synoptic", "audit"]
    # the rail lists the same modules as the nav, in the same order
    assert list(_RAIL_MODULE_IDS) == [e for e in entries if e != "dashboard"]
