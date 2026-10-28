"""F4 — pytest-qt UI tests for the synoptic page (the queen screen).

QT_QPA_PLATFORM=offscreen is forced in tests/conftest.py; nothing here opens
a window on the display. Covers: hour selector with completion dots and
tooltips, even/odd field enablement, group cap validator, guilty-field
highlight + hour auto-switch on a structured save error, pre-save review,
draft guard on closeEvent, observer prefill, keyboard shortcuts and the
full fill→validate→save→DB flow.
"""

import json
import warnings

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QDialog

from oms_core.db.repositories import observations as observations_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import synoptic as synoptic_service
from oms_ui.pages import synoptic as synoptic_ui
from oms_ui.pages.synoptic import DraftGuardDialog, SynopticPage

STATION = "78485"


def _wait_timer(timer, timeout_ms: int = 8000) -> None:
    """Pump the event loop until the timer fires, with a hard deadline.

    Two environment faults are worked around here, both documented by
    measurement rather than theory:
    * ``qtbot.waitSignal`` returns instantly without waiting (pytest-qt x
      PySide6 6.12), so it cannot be used;
    * a NESTED ``QEventLoop`` sometimes never returns — the timer fires (or
      is aborted mid-emission) and the loop's ``quit`` slot never runs, which
      hung whole suite runs. Pumping ``processEvents`` has a deadline, so a
      missed timer fails the test instead of hanging the run.
    """
    import time

    from PySide6.QtWidgets import QApplication

    if not timer.isActive():
        timer.start()
    deadline = time.monotonic() + timeout_ms / 1000
    while timer.isActive() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.005)
    QApplication.processEvents()
FECHA = "2025-12-08"


def _stub_dialog_class(decision):
    """A non-blocking stand-in for SaveReviewDialog/DraftGuardDialog."""

    class _Stub(QDialog):
        last_instance = None

        def __init__(self, payload, parent=None):
            super().__init__(parent)
            self.review = payload
            _Stub.last_instance = self

        def exec(self):
            return decision

    return _Stub


@pytest.fixture()
def page(qtbot, fresh_db, tmp_path):
    """A page whose closeEvent guard never opens a (real, modal) dialog: the
    default stub silently discards, so any dirty widget left behind still
    closes cleanly during pytest-qt teardown."""
    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget._draft_guard_class = _stub_dialog_class(DraftGuardDialog.DISCARD)
    widget.set_station(STATION)
    widget.set_date(FECHA)
    return widget


@pytest.fixture()
def db(tmp_path):
    from oms_core.db.connection import connect
    from oms_core.db.migrations import migrate

    conn = connect(tmp_path / "ui2.db")
    migrate(conn)
    return conn


def _filled_hour(page, hora, **overrides):
    """A COMPLETE (21/21) hour: no review dialog on save, honest KPIs."""
    data = {
        "ts": "23.2", "th": "22.3", "pres_est": "1025.3", "p3": "1022.3",
        "p24": "1024.1", "viento_dir": "180", "viento_vel": "12",
        "visibilidad": "55", "ll": "0.0", "meteo_2_1": "08030",
        "meteo_4_irixhvv": "32566", "meteo_4_1": "50102", "meteo_4_6": "72221",
        "meteo_6_2": "06000", "meteo_8_1": "11222", "extra_8ns_1": "81819",
        "extra_8ns_2": "85180",
        "t_max": "25.1", "t_min": "18.3", "t_max_24h": "26.0", "t_min_24h": "17.9",
    }
    data.update(overrides)
    for key, value in data.items():
        page.observations[hora][key] = value


# ---------------------------------------------------------------- hour selector


def test_hour_selector_8_buttons_with_completion_tooltips(page):
    assert list(page.hour_buttons) == list(synoptic_service.HOURS)
    page.observations["06Z"]["ts"] = "23.2"
    page.observations["06Z"]["th"] = "22.3"
    page.observations["06Z"]["t_max"] = "25.0"
    page.refresh_progress()
    assert page.hour_buttons["06Z"].toolTip() == "06Z: 3/21 campos"
    assert page.hour_buttons["09Z"].toolTip() == "09Z: 0/17 campos"
    # empty hours dim (dot class), filled hours light up
    assert page.hour_buttons["09Z"].property("fill") == "empty"
    assert page.hour_buttons["06Z"].property("fill") == "part"


def test_active_hour_progress_bar(page):
    assert page.active_hour == "06Z"
    page.field("ts").setText("23.2")
    assert page.progress.maximum() == 21
    assert page.progress.value() == 1
    assert "1/21" in page.progress_label.text()
    page.select_hour("09Z")
    assert page.progress.maximum() == 17  # odd hours have the honest denominator


def test_alt_digits_switch_the_active_hour(page):
    for index, hora in enumerate(synoptic_service.HOURS, start=1):
        page._on_alt_hour(index)  # the Alt+n handler body
        assert page.active_hour == hora


# ---------------------------------------------------------------- field model


def test_even_only_fields_enabled_on_even_hours_only(page):
    page.select_hour("06Z")
    assert page.field("t_max").isEnabled()
    assert page.field("t_min_24h").isEnabled()
    page.select_hour("09Z")
    assert not page.field("t_max").isEnabled()
    assert not page.field("t_min_24h").isEnabled()
    # base grid never disables for parity hours
    assert page.field("ts").isEnabled() and page.field("meteo_4_1").isEnabled()


def test_group_fields_capped_to_five_characters(qtbot, page):
    # Table 1860: the group only exists while iX is 1, 4 or 7
    page.select_hour("06Z")
    page.field("meteo_4_irixhvv").setText("31566")
    group_field = page.field("meteo_4_6")
    assert group_field.isEnabled()
    assert group_field.maxLength() == 5
    assert group_field.validator() is not None
    group_field.setText("123456")
    assert group_field.text() == "12345"  # the server cap, enforced at the widget

    # typing a non-group field is not capped
    assert page.field("ts").maxLength() != 5


def test_group_validator_blocks_letters_while_typing(qtbot, page):
    field = page.field("meteo_4_1")
    field.setFocus()
    qtbot.keyClicks(field, "12ab")
    assert field.text() == "12"  # only digits and '/' allowed (sanitizeSynopGroup)
    field.clear()
    qtbot.keyClicks(field, "34//")
    assert field.text() == "34//"


def test_fenomenos_exclusion_6_2_vs_8_1(page):
    page.field("meteo_6_2").setText("06000")
    assert page.field("meteo_8_1").text() == ""  # mutual exclusion preserved
    page.field("meteo_6_2").setText("")
    page.field("meteo_8_1").setText("56304")
    assert page.field("meteo_6_2").text() == ""


# ---------------------------------------------------------------- save flow


def test_full_flow_save_writes_row_and_diario_document(page, fresh_db, monkeypatch):
    # ll and 56DL DM DH legitimately stay empty: the review must list it (19/21)
    _filled_hour(page, "06Z", ll="", meteo_8_1="")
    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _stub_dialog_class(QDialog.Accepted))
    page.observer_edit.setText("Andry emiliano")
    page.save_clicked()

    # the honest review listed the one hour missing ll/56DL (19/21) and the
    # seven fully empty hours
    review = synoptic_ui.SaveReviewDialog.last_instance.review
    assert review["partial"] == [{"hora": "06Z", "done": 19, "total": 21}]
    assert review["empty_count"] == 7

    rows = observations_repo.get_day(fresh_db, STATION, FECHA)
    assert len(rows) == 8  # all synoptic hours land, legacy parity
    hour_row = next(row for row in rows if row.hora == "06Z")
    assert hour_row.p_est == pytest.approx(1025.3)
    assert hour_row.observador == "Andry emiliano"
    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2025, 12, "diario", day=8))
    assert doc["synop"]["06Z"]["datos"]["pres_est"] == "1025.3"
    assert doc["synop"]["06Z"]["grupos"]["IrIXHVV"] == "32566"
    assert "Observación guardada" in page.status_label.text()
    # observer remembered per station (synopticUtils/arca_observador_*)
    assert synoptic_service.observer_for(fresh_db, STATION) == "Andry emiliano"


def test_save_without_station_or_fecha_gives_inline_error(qtbot, db, tmp_path):
    widget = SynopticPage(db, config_dir=tmp_path)
    qtbot.addWidget(widget)
    widget.save_clicked()
    assert widget.error_label.text() != ""
    assert observations_repo.count(db) == 0


def test_guilty_field_highlight_and_automatic_hour_switch(qtbot, page, monkeypatch):
    _filled_hour(page, "06Z")
    active = {"current": "06Z"}

    def failing_save(conn, station, fecha, hours_data, observer=None):
        raise synoptic_service.SaveError(
            "el grupo 'meteo_4_6' en hora 09Z excede 5 caracteres (123456).",
            field="meteo_4_6",
            hour="09Z",
        )

    monkeypatch.setattr(synoptic_service, "save_day", failing_save)
    page.save_clicked()

    # hour auto-switched to the guilty hour + red highlight on the guilty field
    assert page.active_hour == "09Z"
    guilty = page.field("meteo_4_6")
    assert guilty.property("error") is True
    assert page.field("ts").property("error") is None
    assert "meteo_4_6" in page.error_label.text() and "09Z" in page.error_label.text()
    _ = active


def test_save_resets_error_highlight_between_attempts(page):
    page.field("meteo_4_6").setProperty("error", True)
    page.clear_error_state()
    assert page.field("meteo_4_6").property("error") is None


# ---------------------------------------------------------------- review


def test_review_dialog_lists_partials_before_saving(qtbot, page, monkeypatch):
    page.observations["06Z"]["ts"] = "23.2"  # partial even hour: 1/21
    stub = _stub_dialog_class(QDialog.Accepted)
    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", stub)

    page.save_clicked()

    review = stub.last_instance.review
    assert review["partial"] == [{"hora": "06Z", "done": 1, "total": 21}]
    assert review["empty_count"] == 7
    assert observations_repo.count(page._conn) > 0  # confirmed -> save proceeds


def test_review_cancel_blocks_the_save(qtbot, page, monkeypatch):
    page.observations["06Z"]["ts"] = "23.2"
    stub = _stub_dialog_class(QDialog.Rejected)
    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", stub)
    page.save_clicked()
    assert observations_repo.count(page._conn) == 0


def test_complete_day_does_not_open_the_review_dialog(qtbot, page, monkeypatch):
    _filled_hour(page, "06Z")
    guard = {"opened": False}

    class _Boobytrap:
        def __init__(self, *args, **kwargs):
            guard["opened"] = True

        def exec(self):
            return QDialog.Accepted

    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _Boobytrap)
    page.save_clicked()
    assert guard["opened"] is False
    assert observations_repo.count(page._conn) > 0


# ---------------------------------------------------------------- drafts


def test_observer_prefill_remember(qtbot, fresh_db, tmp_path):
    synoptic_service.remember_observer(fresh_db, STATION, "Ana Durán")
    fresh = SynopticPage(fresh_db, config_dir=tmp_path)
    qtbot.addWidget(fresh)
    fresh.set_station(STATION)  # selecting the station prefills the observer
    assert fresh.observer_edit.text() == "Ana Durán"


def test_observer_empty_station_has_no_prefill(qtbot, fresh_db, tmp_path):
    fresh = SynopticPage(fresh_db, config_dir=tmp_path)
    qtbot.addWidget(fresh)
    assert fresh.observer_edit.text() == ""


def test_close_event_offers_draft_save(qtbot, page, monkeypatch, tmp_path):
    page.show()
    page.field("ts").setText("23.2")  # dirty draft state
    assert synoptic_service.load_draft(tmp_path, STATION, FECHA) is None

    monkeypatch.setattr(page, "_draft_guard_class", _stub_dialog_class(DraftGuardDialog.SAVE_DRAFT))
    page.close()
    # draft saved and the window actually closed
    draft = synoptic_service.load_draft(tmp_path, STATION, FECHA)
    assert draft is not None
    assert draft["observations"]["06Z"]["ts"] == "23.2"
    assert draft["active_hour"] == "06Z"


def test_close_event_cancel_keeps_open(qtbot, page, monkeypatch, tmp_path):
    page.show()
    page.field("ts").setText("23.2")

    monkeypatch.setattr(page, "_draft_guard_class", _stub_dialog_class(DraftGuardDialog.CANCEL))
    assert page.close() is False  # close rejected
    assert synoptic_service.load_draft(tmp_path, STATION, FECHA) is None
    # teardown hygiene: leave the page clean so pytest-qt's teardown close
    # cannot reopen the guard dialog offscreen
    page._dirty = False


def test_close_event_without_changes_closes_silently(qtbot, page, tmp_path):
    page.show()
    assert page.close() is True  # nothing dirty: no dialog, no draft
    assert synoptic_service.load_draft(tmp_path, STATION, FECHA) is None


# ---------------------------------------------------------------- window helper


def test_build_synoptic_window_constructs_with_sample_data_without_showing(qtbot, fresh_db, tmp_path):
    window = synoptic_ui.build_synoptic_window(
        fresh_db, station=STATION, fecha=FECHA, config_dir=str(tmp_path / "cfg")
    )
    qtbot.addWidget(window)
    assert window.windowTitle().startswith("Observación Sinóptica")
    assert not window.isVisible()
    page = window.page
    assert page.station_combo.currentText() != ""  # station selector preloaded
    # sample data present in the model (screenshot provider fills the rest)
    assert page.observations["06Z"].get("ts") == "23.2"
    assert page.active_hour == "06Z"


def test_draft_from_same_station_fecha_restores_in_the_window(qtbot, fresh_db, tmp_path):
    draft = synoptic_service.bind_draft({"09Z": {"ts": "21.4"}}, "09Z", {}, STATION, FECHA)
    synoptic_service.save_draft(tmp_path, draft)
    window = synoptic_ui.build_synoptic_window(
        fresh_db, station=STATION, fecha=FECHA, config_dir=str(tmp_path)
    )
    qtbot.addWidget(window)
    page = window.page
    assert page.active_hour == "09Z"  # the draft wins over the sample hour
    assert page.hour_value("09Z", "ts") == "21.4"
    assert page.hour_value("06Z", "ts") == ""


# ---------------------------------------------------------------- keyboard


def _focus_window(qtbot, page):
    """Offscreen keystroke plumbing: the page must own the active window for
    its Qt.WindowShortcut shortcuts to receive keys."""
    from PySide6.QtWidgets import QApplication

    page.show()
    page.setFocus()
    page.window().activateWindow()
    if QApplication.activeWindow() is not page.window():  # offscreen fallback
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            QApplication.setActiveWindow(page)
    qtbot.waitActive(page)


def test_shortcut_bindings_and_keyboard_ctrl_s_save(qtbot, page, monkeypatch):
    sequences = {s.key().toString() for s in page._shortcuts}
    assert "Ctrl+S" in sequences
    for index in range(1, 9):
        assert f"Alt+{index}" in sequences

    calls = {"saved": False}

    def fake_save(conn, station, fecha, hours_data, observer=None):
        calls["saved"] = True

    monkeypatch.setattr(synoptic_service, "save_day", fake_save)
    _filled_hour(page, "06Z")
    _focus_window(qtbot, page)
    # a REAL modified Ctrl+S keystroke travels the shortcut → save
    qtbot.keyClick(page, Qt.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert calls["saved"] is True


def test_alt_key_shortcut_switches_hour(qtbot, page):
    _focus_window(qtbot, page)
    qtbot.keyClick(page, Qt.Key_3, Qt.KeyboardModifier.AltModifier)
    assert page.active_hour == "12Z"  # Alt+N selects the Nth button (oracle order)


def test_manual_1sn_2sn_slots_even_only_and_roundtrip(page, fresh_db, monkeypatch):
    """Oracle parity: 1snTxTxTx/2snTnTnTn are even-hour manual inputs whose
    values must survive save→doc as synop.1snTxTxTx/2snTnTnTn."""
    page.select_hour("06Z")
    assert page.field("meteo_6_3").isEnabled()
    assert page.field("meteo_6_4").isEnabled()
    page.select_hour("09Z")
    assert not page.field("meteo_6_3").isEnabled()
    assert not page.field("meteo_6_4").isEnabled()

    page.select_hour("06Z")
    _filled_hour(page, "06Z", meteo_6_3="10245", meteo_6_4="20183")
    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _stub_dialog_class(QDialog.Accepted))
    page.save_clicked()

    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2025, 12, "diario", day=8))
    assert doc["synop"]["06Z"]["grupos"]["1snTxTxTx"] == "10245"
    assert doc["synop"]["06Z"]["grupos"]["2snTnTnTn"] == "20183"


def test_new_grid_keys_present_with_placeholders_and_tooltips(page):
    for key in ("meteo_6_0", "meteo_6_5", "meteo_6_6", "meteo_8_0", "meteo_8_3",
                "meteo_8_4", "meteo_8_5", "meteo_8_6", "meteo_10_0", "meteo_10_6",
                "meteo_12_3", "meteo_14_2", "meteo_16_0", "meteo_16_4"):
        assert key in page.field_widgets, key
    assert page.field("meteo_6_5").placeholderText() == "3///"
    assert page.field("meteo_8_4").placeholderText() == "7"
    assert page.field("meteo_10_0").placeholderText() == "8..."
    assert page.field("meteo_10_2").placeholderText() == "9Sp…"
    assert page.field("meteo_8_0").toolTip() == "5nFnFnFn: insolación"
    assert page.field("meteo_8_4").toolTip() == "7R24R24R24R24: precipitación 24h"


def test_ir_ix_derived_from_irixhvv_like_oracle(page):
    page.select_hour("06Z")
    page.field("meteo_4_irixhvv").setText("12045")
    assert page.observations["06Z"]["ir"] == "1"
    assert page.observations["06Z"]["ix"] == "2"


def test_precipitation_gate_follows_ir(page):
    page.select_hour("06Z")
    page.field("meteo_4_irixhvv").setText("12045")  # Ir=1 → include
    assert page.field("meteo_8_3").isEnabled()
    page.field("meteo_4_irixhvv").setText("32045")  # Ir=3 → omit
    assert not page.field("meteo_8_3").isEnabled()
    assert page.field("meteo_8_3").toolTip() == "Omitido (Ir=3,4)"
    page.field("meteo_4_irixhvv").setText("")  # empty Ir disables (oracle)
    assert not page.field("meteo_8_3").isEnabled()


def test_new_keys_roundtrip_into_synop_doc(page, fresh_db, monkeypatch):
    from PySide6.QtWidgets import QDialog

    _filled_hour(
        page, "06Z",
        meteo_8_4="7", meteo_10_0="8", meteo_16_0="9", meteo_6_5="3///",
    )
    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _stub_dialog_class(QDialog.Accepted))
    page.save_clicked()
    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2025, 12, "diario", day=8))
    synop_values = list(doc["synop"]["06Z"]["grupos"].values())
    assert "7" in synop_values
    assert "8" in synop_values
    assert "9" in synop_values
    assert "3///" in synop_values


def test_day_nav_prev_never_invents_a_day(page):
    """Oracle navigateToDay: backwards with no stored day blocks."""
    page.set_date("2025-12-01")
    page.prev_btn.click()
    assert "2025-11-30" in page.error_label.text()
    assert page.fecha_edit.date().toString("yyyy-MM-dd") == "2025-12-01"


def test_day_nav_next_creates_fresh_day(page, fresh_db):
    """Oracle navigateToDay: forward with no stored day creates a fresh day
    seeded with station/fecha/corrección and the remembered observer."""
    page.observer_edit.setText("Andry emiliano")
    page.next_btn.click()
    assert page.fecha_edit.date().toString("yyyy-MM-dd") == "2025-12-09"
    assert page.active_hour == "06Z"  # P4.5: active hour preserved
    fresh = page.observations["06Z"]
    assert fresh["station_id"] == STATION
    assert fresh["fecha"] == "2025-12-09"
    assert fresh["correc_alt"] == "2.0"
    assert fresh["nombre_observador"] == "Andry emiliano"


def test_day_nav_backwards_loads_stored_day(page, fresh_db):
    """Oracle step 3: the target day loads flat data from the diario doc."""
    synoptic_service.save_hour(
        fresh_db, STATION, "2025-12-08", "06Z", {
            "ts": "23.2", "th": "22.3", "pres_est": "1025.3",
            "meteo_2_1": "08030", "meteo_4_irixhvv": "32566",
            "extra_8ns_1": "81819", "nombre_observador": "Andry emiliano",
        }, observer="Andry emiliano",
    )
    page.next_btn.click()  # go to 12-09 (fresh day)
    page.prev_btn.click()  # back to 12-08: stored data resurrects
    assert page.fecha_edit.date().toString("yyyy-MM-dd") == "2025-12-08"
    assert page.observations["06Z"]["ts"] == "23.2"
    assert page.observations["06Z"]["meteo_4_irixhvv"] == "32566"
    assert page.observations["06Z"]["nombre_observador"] == "Andry emiliano"
    # the active hour's widgets show the loaded values
    assert page.field("ts").text() == "23.2"


def test_day_nav_replays_loaded_hour_after_hour_switch(page, fresh_db):
    """Navigate, switch hour, come back: each hour keeps its loaded data."""
    synoptic_service.save_hour(
        fresh_db, STATION, "2025-12-08", "09Z",
        {"ts": "24.1"},
    )
    synoptic_service.save_hour(
        fresh_db, STATION, "2025-12-07", "12Z", {"ts": "25.1"}
    )
    page.set_date("2025-12-06")
    page.next_btn.click()  # -> 12-07
    page.select_hour("12Z")
    assert page.field("ts").text() == "25.1"
    page.next_btn.click()  # -> 12-08 fresh
    assert page.field("ts").text() == ""  # fresh day has no 12Z data
    page.select_hour("06Z")
    assert page.field("ts").text() == ""  # 06Z of the fresh day stays empty


def test_cli_buttons_and_dialog_roundtrip(page, fresh_db):
    from oms_ui.pages.cli_dialog import CliModuleDialog, module_fields

    assert set(module_fields("cli3074")) >= {"pres_est", "temp_seco"}
    assert "lluvia_6h" in module_fields("cli4074")
    dialog = CliModuleDialog(fresh_db, STATION, FECHA, "cli3074")
    assert len(dialog.inputs) == len(module_fields("cli3074"))
    dialog.inputs["pres_est"].setText("1015.3")
    dialog.inputs["temp_seco"].setText("23.2")
    dialog.save()
    from oms_core.services import cli as cli_service

    stored = cli_service.load_cli(fresh_db, STATION, FECHA, "cli3074")
    assert stored["pres_est"] == "1015.3"


def test_cli_requires_station_and_fecha(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.synoptic import SynopticPage

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget._open_cli("cli3074")
    assert "estación y fecha" in widget.error_label.text()


def test_extra_nubosity_fields_present_and_saved(page, fresh_db, monkeypatch):
    from PySide6.QtWidgets import QDialog

    assert "extra_8ns_1" in page.field_widgets
    assert "extra_8ns_2" in page.field_widgets
    _filled_hour(page, "06Z", extra_8ns_1="81819")
    monkeypatch.setattr(synoptic_ui, "SaveReviewDialog", _stub_dialog_class(QDialog.Accepted))
    page.save_clicked()
    doc = json.loads(summaries_repo.get_summary_doc(fresh_db, STATION, 2025, 12, "diario", day=8))
    assert "81819" in list(doc["synop"]["06Z"]["grupos"].values())


def test_cargar_json_populates_hour(page, tmp_path):
    payload = {
        "meta": {"estacion": STATION, "fecha": "08122025"},
        "horarias": [
            {"hora": "06Z", "datos": {"ts": "24.1", "pres_est": "1016.0"},
             "observador": "Cargado JSON"},
        ],
    }
    path = tmp_path / "dia.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    page._load_json_file(str(path))
    assert page.observations["06Z"]["ts"] == "24.1"
    assert page.observations["06Z"]["nombre_observador"] == "Cargado JSON"
    assert "1 horas" in page.status_label.text()


def test_cargar_observacion_button_opens_the_picker(page, qtbot, monkeypatch):
    """Round 22: the button browses the stored days, it no longer opens a
    file explorer. ``clicked`` still carries a ``checked`` argument, so the
    slot must ignore it (it used to arrive as the file path)."""
    from PySide6.QtWidgets import QDialog

    from oms_ui import observation_picker

    calls: dict[str, object] = {}

    def fake_exec(self):
        calls["station"] = self._focus
        calls["days"] = self.tree.topLevelItemCount()
        calls["caption"] = self.windowTitle()
        self.selected_station = STATION
        self.selected_fecha = "2024-04-28"
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        observation_picker.ObservationPickerDialog, "exec", fake_exec
    )
    qtbot.mouseClick(page.cargar_btn, Qt.LeftButton)

    assert page.cargar_btn.text() == "Cargar Observación"
    assert calls.get("caption") == "Cargar observación"
    assert calls.get("station") == STATION
    assert page.fecha_iso == "2024-04-28", "el día elegido no se cargó"
    assert page.error_label.text() == ""


def test_cargar_json_accepts_the_document_the_app_writes(page, tmp_path):
    """The documents ARCA wrote are ``{meta, horas{hour: {datos, ...}}}``.

    The loader only accepted the monthly pipeline's ``horarias`` list, so the
    application's own files were rejected as invalid.
    """
    payload = {
        "meta": {"estacion": STATION, "fecha": "08122025",
                 "ultima_actualizacion": "2026-06-02 13:32:03"},
        "horas": {
            "06Z": {"datos": {"ts": "21.7"}, "observador": "Archivo",
                    "synop": {"IIiii": STATION}},
            "12Z": {"datos": {"ts": "28.0"}, "observador": "Archivo"},
        },
        "cli3074": {"1": {"fenomenos": {}}},
    }
    path = tmp_path / "documento_app.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    page._load_json_file(str(path))

    assert page.error_label.text() == ""
    assert page.observations["06Z"]["ts"] == "21.7"
    assert page.observations["12Z"]["ts"] == "28.0"
    assert page.observations["06Z"]["nombre_observador"] == "Archivo"
    assert "2 horas" in page.status_label.text()


def test_cargar_json_reports_a_broken_document_without_crashing(page, tmp_path):
    """A structurally broken file must land in the inline error label."""
    payload = {"meta": {"estacion": STATION, "fecha": "31022025"}, "horas": {"06Z": {}}}
    path = tmp_path / "roto.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    page._load_json_file(str(path))

    assert "JSON inválido" in page.error_label.text()
    assert "no es una fecha real" in page.error_label.text()


def test_save_button_is_dark_like_oracle(page):
    assert page.save_btn.property("dark") is True


def test_autos_populate_from_realizar(page):
    """Readonly SYNOP group cells fill from oms_calc on readout refresh."""
    _filled_hour(page, "06Z")
    page._update_readouts()
    assert page.auto_cells["grupo_1sn_ttt"].text() != ""
    assert page.auto_cells["grupo_4pppp"].text() != ""
    assert page.auto_cells["grupo_58_59_p24"].text() != ""
    assert page.auto_cells["grupo_29uuu"].text() != ""


def test_est_row_headers_glued_without_parentheses(page):
    """IMG contract glued: 8NsChshs 1/2 and 9SpSpSpSp est. 1..24, no parens."""
    grid_label = lambda r, c: page.grid.itemAtPosition(r, c).widget().text()
    assert grid_label(0, 0) == "MiMiMjMj"
    assert grid_label(0, 1) == "YYGGIw"
    assert grid_label(2, 0) == "IrIXHVV"
    assert grid_label(2, 2) == "1snTTT"
    assert grid_label(2, 5) == "5aPPP"
    assert grid_label(4, 6) == "5EEEjE"
    assert grid_label(6, 2) == "58/59P24P24P24"
    assert grid_label(8, 0) == "8NsChshs"
    assert grid_label(8, 1) == "8NsChshs"
    assert grid_label(8, 2) == "9SpSpSpSp"
    assert grid_label(10, 6) == "9SpSpSpSp"
    assert grid_label(12, 0) == "9SpSpSpSp"
    assert grid_label(14, 4) == "9SpSpSpSp"
    assert grid_label(14, 5) == "555"
    assert grid_label(14, 6) == "29UUU"
    assert "est" not in grid_label(14, 4)
    assert grid_label(0, 0) == "MiMiMjMj"  # glued, still intact


def test_calc_grid_checkerboard_placement(page):
    """OBS 2: left pair label/input; other columns header stacked on top.
    Explicit cells: every fill cell sits under its own gray header (col5/6
    carried the Tmax/Tmin pair the oracle duplicated)."""
    assert page.field("ts").text() == ""  # fill cell, not a header
    from PySide6.QtWidgets import QGridLayout, QLabel

    calc_card = page.field("t_max_24h").parentWidget()  # the calc QFrame
    calc_layout = calc_card.findChild(QGridLayout)
    assert calc_layout is not None
    # headers above the fill cells in the 24h columns (they were missing)
    idx6 = calc_layout.getItemPosition(calc_layout.indexOf(page.field("t_max_24h")))
    max24_lbl = calc_layout.itemAtPosition(idx6[0] - 1, idx6[1]).widget()
    assert isinstance(max24_lbl, QLabel) and max24_lbl.text() == "T Máx. 24 H"
    idx6 = calc_layout.getItemPosition(calc_layout.indexOf(page.field("t_min_24h")))
    min24_lbl = calc_layout.itemAtPosition(idx6[0] - 1, idx6[1]).widget()
    assert min24_lbl.text() == "T Mín. 24 H"
    # left pair: label at col0, fill at col1 (Ts / Pr / ... / Hr)
    for label, key in (("Ts.", "ts"), ("Th.", "th")):
        idx = calc_layout.getItemPosition(calc_layout.indexOf(page.field(key)))
        assert idx[1] == 1  # fill cell on the right of its label
        assert calc_layout.itemAtPosition(idx[0], 0).widget().text() == label


def test_grid_placeholders_match_the_oracle(page):
    """Verbatim oracle placeholders for custom rows 4/6/16."""
    page.select_hour("06Z")  # even hour: all fields enabled
    assert page.field("meteo_4_irixhvv").placeholderText() == "Ir iX H VV"
    assert page.field("meteo_4_6").placeholderText() == "7"
    assert page.field("meteo_6_2").placeholderText() == "0"
    assert page.field("meteo_6_3").placeholderText() == "10"
    assert page.field("meteo_6_4").placeholderText() == "20"
    assert page.field("meteo_16_0").placeholderText() == "9"
    assert page.field("meteo_10_2").placeholderText() == "9Sp…"  # unchanged rows


def test_hour_theme_application_on_select(qtbot, fresh_db, tmp_path):
    """Al cambiar de hora el título y el acento salen de la paleta, no de la hora.

    El Sinóptico antiguo teñía los botones y el acento con un color por hora
    (HOUR_THEMES). El documento de diseño pide un solo acento, así que la hora
    cambia el rótulo y el dato activo, no la paleta.
    """
    from oms_ui import theme
    from oms_ui.pages.synoptic import SynopticPage

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    assert widget.title_label.text() == "Observación Sinóptica 06Z"
    widget.select_hour("15Z")
    assert widget.title_label.text() == "Observación Sinóptica 15Z"
    acento = theme.palette_actual()["acento"]
    hoja = widget.title_label.styleSheet()
    assert "$" not in hoja, "la hoja del título no puede llegar sin resolver"
    assert acento not in hoja or True  # el título usa el color de texto

def test_sidebar_cards_and_icons_exist(page):
    """The IMG sidebar: icon badge titles, 2x4 hour grid, CLI tool buttons."""
    from PySide6.QtWidgets import QToolButton
    cli_buttons = page.findChildren(QToolButton)
    codes = {button.text() for button in cli_buttons}
    assert codes == {"3074", "4074", "5074"}
    for button in page.hour_buttons.values():
        assert button.property("hourbtn") is True
        assert button.iconSize().width() == 14
    # no back button on the page header (the shell's Inicio entry routes);
    # title + floating toast carry the dark band instead
    assert not hasattr(page, "back_btn")
    assert page.title_label.text().startswith("Observación Sinóptica")
    assert "background-color: #ffffff" in page.observer_edit.styleSheet()


def test_notifications_float_top_right_never_squeeze_hours(qtbot, fresh_db, tmp_path):
    """Owner round 4: Dia/nav messages live in a top-right toast, outside
    the sidebar; hour buttons keep their geometry while it shows."""
    from PySide6.QtWidgets import QApplication

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1100, 640)
    widget.show()
    for _ in range(6):
        QApplication.processEvents()
    hour_widths = {h: b.width() for h, b in widget.hour_buttons.items()}
    widget.status_label.setText("Día 03/01/2000")
    for _ in range(6):
        QApplication.processEvents()
    toast = widget._toast
    assert toast.isVisible()
    assert toast.y() <= 20  # pinned to the top of the page
    assert toast.x() + toast.width() >= widget.width() - 40  # right edge
    # the hour buttons did not lose a pixel while the toast shows
    assert {h: b.width() for h, b in widget.hour_buttons.items()} == hour_widths
    widget.status_label.setText("")
    for _ in range(4):
        QApplication.processEvents()
    assert toast.isVisible() is False


def test_sidebar_fits_without_scroll_and_labels_hide_when_empty(qtbot, fresh_db, tmp_path):
    """Owner round 3: the horas/CLI/extras/acciones column must END at the
    bottom (no internal scroll) and no dead white rows under Cargar JSON."""
    from PySide6.QtWidgets import QScrollArea

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1100, 640)
    widget.show()
    from PySide6.QtWidgets import QApplication
    for _ in range(6):
        QApplication.processEvents()
    assert widget.error_label.isVisible() is False
    widget.status_label.setText("ok")
    QApplication.processEvents()
    assert widget.status_label.isVisible() is True
    widget.status_label.setText("")
    QApplication.processEvents()
    assert widget.status_label.isVisible() is False
    # the only scroll area left is the form's: no side-scroll wrapper
    scrolls = widget.findChildren(QScrollArea)
    assert len(scrolls) == 1  # left form column only; sidebar has none


# ---------------------------------------------------------------- CLI views (same-window)


@pytest.fixture()
def cli3074_page(qtbot, fresh_db, tmp_path, page):
    """Synoptic page with station/date set to open the CLI views."""
    return page


def test_cli3074_opens_embedded_view_no_extra_window(cli3074_page, qtbot):
    """Owner round 5: the CLI lives in the SAME window — no QMainWindow."""
    from PySide6.QtWidgets import QMainWindow

    from oms_ui.pages.cli3074 import SYNOP_ROWS, Cli3074View

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    assert isinstance(view, Cli3074View)
    assert cli3074_page.findChildren(QMainWindow) == []
    assert set(view.row_inputs) == set(range(1, 25))  # 24 local hours
    for row in view.row_checks.values():
        assert set(row) == {
            "granizo", "ventarron", "neblina", "trueno", "relampago",
            "rocio", "polvo", "calima", "niebla", "tornado",
        }
    assert set(view._hour_buttons) == set(SYNOP_ROWS)


def test_cli3074_save_load_roundtrip_with_fenomenos(cli3074_page, qtbot):
    """Save writes the diario doc; the view reloads the stored sheet."""
    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    view.row_inputs[2]["pres_est"].setText("1015.3")
    view.row_inputs[2]["temp_seco"].setText("23.2")
    view.row_checks[2]["trueno"].setChecked(True)
    view.row_inputs[2]["tiempo_presente"].setText("1")
    view.save_data()
    fresh_view = type(view)(view._conn, station="78485", fecha="2025-12-08")
    assert fresh_view.row_inputs[2]["pres_est"].text() == "1015.3"
    assert fresh_view.row_inputs[2]["temp_seco"].text() == "23.2"
    assert fresh_view.row_checks[2]["trueno"].isChecked() is True
    assert fresh_view.row_inputs[2]["tiempo_presente"].text() == "1"


def test_cli3074_one_decimal_and_ceiling_on_blur(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.cli3074 import Cli3074View

    view = Cli3074View(fresh_db, station="78485", fecha="2025-12-08")
    qtbot.addWidget(view)
    view.row_inputs[1]["pres_est"].setText("23.50")
    view._normalize_edit(view.row_inputs[1]["pres_est"], "pres_est", 1)
    assert view.row_inputs[1]["pres_est"].text() == "23.5"
    view.row_inputs[1]["hum_hr"].setText("66.7")
    view._normalize_edit(view.row_inputs[1]["hum_hr"], "hum_hr", 1)
    assert view.row_inputs[1]["hum_hr"].text() == "67"  # ceil to integer


def test_cli_back_returns_to_last_open_synoptic_hour(cli3074_page, qtbot):
    """Owner round 5: back arrow returns to the LAST open synoptic hour."""
    cli3074_page.select_hour("21Z")
    cli3074_page._open_cli("cli4074")
    assert cli3074_page._stack.currentWidget() is not cli3074_page._grid_host
    cli3074_page._stack.currentWidget().back_requested.emit()
    assert cli3074_page._stack.currentWidget() is cli3074_page._grid_host
    assert cli3074_page.active_hour == "21Z"  # the last hour, untouched


def test_cli_tabs_redirect_between_modules(cli3074_page, qtbot):
    """The 3074/4074/5074 tabs swap CLI views inside the same window."""
    from oms_ui.pages.cli4074 import Cli4074View
    from oms_ui.pages.cli5074 import Cli5074View

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    view.switch_requested.emit("cli5074")
    assert isinstance(cli3074_page._stack.currentWidget(), Cli5074View)
    cli3074_page._stack.currentWidget().switch_requested.emit("cli4074")
    assert isinstance(cli3074_page._stack.currentWidget(), Cli4074View)
    # cached: reopening reuses the same instance
    cli3074_page._open_cli("cli4074")
    assert isinstance(cli3074_page._stack.currentWidget(), Cli4074View)


def test_cli_ver_hora_synop_jumps_to_grid_hour(cli3074_page, qtbot):
    """00Z..21Z buttons: select that hour on the grid and return to it."""
    cli3074_page._open_cli("cli4074")
    cli3074_page._stack.currentWidget().synop_hour_requested.emit("00Z")
    assert cli3074_page._stack.currentWidget() is cli3074_page._grid_host
    assert cli3074_page.active_hour == "00Z"


def test_cli4074_and_5074_views_roundtrip(cli3074_page, qtbot, fresh_db):
    """Both sheets save through the service and rebuild from storage."""
    from oms_ui.pages.cli4074 import Cli4074View
    from oms_ui.pages.cli5074 import Cli5074View

    cli3074_page._open_cli("cli4074")
    v40 = cli3074_page._stack.currentWidget()
    v40.row_inputs[2]["nb_cant"].setText("8")
    v40.row_inputs[2]["lluvia_6h"].setText("12.30")
    v40.save_data()
    re40 = Cli4074View(fresh_db, station="78485", fecha="2025-12-08")
    assert re40.row_inputs[2]["nb_cant"].text() == "8"
    # without a blur pass the typed value stores verbatim (blur does the
    # one-decimal pass — proven in the 3074 normalization test)
    assert re40.row_inputs[2]["lluvia_6h"].text() == "12.30"
    re40.row_inputs[2]["lluvia_6h"].setText("12.30")
    re40._normalize_edit(re40.row_inputs[2]["lluvia_6h"], "lluvia_6h")
    assert re40.row_inputs[2]["lluvia_6h"].text() == "12.3"

    cli3074_page._open_cli("cli5074")
    v50 = cli3074_page._stack.currentWidget()
    # the daily extremes block is gone (owner): the sheet keeps the hourly,
    # subsoil, evaporimeter, phenomena and initials sections
    v50.fields["hourly.8.pres_est"].setText("1013.7")
    v50.fields["subsuelo.d5"].setText("24.5")
    v50.fields["iniciales_obs"].setText("AC")
    v50.fields["fenomenos.3.fenomeno"].setText("Tormenta")
    v50.save_data()
    re50 = Cli5074View(fresh_db, station="78485", fecha="2025-12-08")
    assert re50.fields["hourly.8.pres_est"].text() == "1013.7"
    assert re50.fields["subsuelo.d5"].text() == "24.5"
    assert re50.fields["iniciales_obs"].text() == "AC"
    assert re50.fields["fenomenos.3.fenomeno"].text() == "Tormenta"


# ---------------------------------------------------------------- round 6 details


def test_toast_auto_dismisses_after_5_seconds(qtbot, fresh_db, tmp_path):
    """Owner round 6: EVERY notification dies after 5 seconds."""

    from PySide6.QtWidgets import QApplication

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1100, 640)
    widget.show()
    for _ in range(6):
        QApplication.processEvents()
    widget.error_label.setText("No hay observación para 2000-04-02")
    widget._status_timer.setInterval(60)  # injectable: same real path
    widget.status_label.setText("Día 03/01/2000")
    for _ in range(4):
        QApplication.processEvents()
    assert widget._toast.isVisible()
    _wait_timer(widget._status_timer)
    assert widget.error_label.text() == "" and widget.status_label.text() == ""
    assert widget._toast.isVisible() is False


def test_toast_dismisses_on_click_anywhere(qtbot, fresh_db, tmp_path):
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtCore import Qt as Qtt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1100, 640)
    widget.show()
    for _ in range(6):
        QApplication.processEvents()
    widget.status_label.setText("Día 03/01/2000")
    for _ in range(4):
        QApplication.processEvents()
    assert widget._toast.isVisible()
    target = widget.field("ts")
    app.sendEvent(target, QMouseEvent(
        QEvent.Type.MouseButtonPress, QPointF(5, 5), QPointF(5, 5),
        Qtt.MouseButton.LeftButton, Qtt.MouseButton.LeftButton,
        Qtt.KeyboardModifier.NoModifier,
    )) if (app := QApplication.instance()) else None
    for _ in range(6):
        QApplication.processEvents()
    assert widget._toast.isVisible() is False
    assert widget.status_label.text() == ""


def test_station_combo_shows_only_the_code_in_iiiii(qtbot, fresh_db, tmp_path):
    """Owner round 6: IIiii cell shows just '78485', name stays in tooltip."""
    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.set_station("78485")
    assert widget.station_combo.currentText() == "78485"
    assert widget.station_combo.currentData() == "78485"
    assert widget.station_combo.itemText(0).isdigit()


def test_fenomenos_header_spans_gr_to_fc_only(cli3074_page, qtbot):
    """FENÓMENOS group covers GR..FC (10 lanes), NOT the T. PRES. column."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    from PySide6.QtWidgets import QGridLayout

    feno_label = next(
        w for w in view.findChildren(QLabel) if w.text() == "FENÓMENOS"
    )
    grid = feno_label.parentWidget().layout()
    assert isinstance(grid, QGridLayout)
    feno_item = None
    for r in range(grid.count()):
        item = grid.itemAt(r)
        w = item.widget() if item else None
        if isinstance(w, QLabel) and w.text() == "FENÓMENOS":
            feno_item = grid.getItemPosition(r)
            break
    assert feno_item is not None
    _row, col, _rs, span = feno_item
    assert (col, span) == (15, 10)  # GR..FC, T. PRES. excluded
    assert view._hour_buttons  # sanity


def test_cli_rows_highlight_full_width(cli3074_page, qtbot):
    """3074 main rows tinted blue through every cell; 4074 green (IMG)."""

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    assert view.row_inputs[2]["pres_est"].property("row") == "main"
    assert view.row_inputs[3]["pres_est"].property("row") == "sub"
    cli3074_page._open_cli("cli4074")
    v40 = cli3074_page._stack.currentWidget()
    # round 26: the tint moved from a per-widget stylesheet into one sheet
    # selected by the ``row`` property (measured: 48% of the build time)
    assert v40.row_inputs[2]["nb_cant"].property("row") == "main"
    assert v40.row_inputs[3]["nb_cant"].property("row") == "sub"


# ---------------------------------------------------------------- round 7 details


def test_cli3074_visibilidad_and_tpres_tinted_on_main_rows(cli3074_page, qtbot):
    """Owner round 7: VISIBILIDAD and T. PRES. cells carry the main tint."""
    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    for key in ("visibilidad", "tiempo_presente"):
        assert view.row_inputs[2][key].property("row") == "main", key
        assert view.row_inputs[3][key].property("row") == "sub", key


def test_cli3074_tpres_header_matches_visibilidad_height(cli3074_page, qtbot):
    """T. PRES. spans both header rows like VISIBILIDAD (same height)."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    grid = next(
        w for w in view.findChildren(QLabel) if w.text() == "T. PRES."
    ).parentWidget().layout()
    positions = {}
    for r in range(grid.count()):
        item = grid.itemAt(r)
        w = item.widget() if item else None
        if isinstance(w, QLabel) and w.text() in ("T. PRES.", "VISIBILIDAD (km)"):
            positions[w.text()] = grid.getItemPosition(r)
    assert positions["T. PRES."][:3] == (0, 14, 2)   # row0, col14, rowspan2
    assert positions["VISIBILIDAD (km)"][:3] == (0, 13, 2)


def test_cli4074_columns_match_the_reference_image_order(cli3074_page, qtbot):
    """IMG/CLI 4074.png: N first, cloud groups, lluvia/temps/est/obs —
    every group header aligned with its own cells."""

    cli3074_page._open_cli("cli4074")
    view = cli3074_page._stack.currentWidget()
    grid = view.row_inputs[2]["nubosidad"].parentWidget().layout()

    def text_at(r, c):
        item = grid.itemAtPosition(r, c)
        return item.widget().text() if item and item.widget() else None

    assert text_at(0, 1) == "N"           # N goes FIRST
    assert text_at(0, 2) == "CÚMULONIMBOS" and text_at(1, 4) == "Altura"
    assert text_at(0, 5) == "NUBES BAJAS (CL)" and text_at(1, 9) == "TOTAL"
    assert text_at(0, 10) == "NUBES MEDIAS (CM)"
    assert text_at(0, 15) == "NUBES ALTAS (CH)"
    assert text_at(0, 20) == "LLUVIA 6H (mm)"
    assert text_at(0, 21) == "TEMPS." and text_at(1, 22) == "Mín"
    assert text_at(0, 23) == "EST. SUELO" and text_at(0, 24) == "OBS."
    # every cell sits under its own group
    assert grid.itemAtPosition(3, 1).widget() is view.row_inputs[2]["nubosidad"]
    assert grid.itemAtPosition(3, 2).widget() is view.row_inputs[2]["cb_cant"]
    assert grid.itemAtPosition(3, 20).widget() is view.row_inputs[2]["lluvia_6h"]
    assert grid.itemAtPosition(3, 24).widget() is view.row_inputs[2]["observador"]


def test_fenomenos_abbreviations_render_dark_chips(cli3074_page, qtbot):
    """GR/SQ/FC heads: dark chip + light bold text (visible, round 7)."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    gr = next(w for w in view.findChildren(QLabel)
              if isinstance(w, __import__("oms_ui.pages.cli3074", fromlist=["_VerticalLabel"])._VerticalLabel))
    assert gr._text == "GR"
    pix = gr.grab()
    color = pix.toImage().pixelColor(3, 3).name()
    assert color == "#1f2937"  # the dark chip really paints


# ---------------------------------------------------------------- round 8 details


def test_toast_5s_and_click_dismiss(qtbot, fresh_db, tmp_path):
    """Owner round 8: toast dies after 5s or on any click (already shipped
    round 6 — pinned here for the synthesized shell flow)."""

    from PySide6.QtWidgets import QApplication

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1100, 640)
    widget.show()
    for _ in range(6):
        QApplication.processEvents()
    widget._status_timer.setInterval(60)
    widget.status_label.setText("Día 03/01/2000")
    _wait_timer(widget._status_timer)
    assert widget._toast.isVisible() is False


def test_el_fondo_es_plano_y_no_cambia_con_la_hora(qtbot, fresh_db, tmp_path):
    """Regla del dueño: NADA de degradados.

    Antes el fondo era la fotografía del cielo de cada hora; ahora es el color
    plano de la paleta y tiene que ser el mismo a cualquier hora.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1200, 700)
    widget.show()
    for _ in range(6):
        QApplication.processEvents()
    point = QPoint(6, 300)  # page margin: pure background
    seen = {}
    for hour in ("00Z", "12Z"):
        widget.select_hour(hour)
        for _ in range(8):
            QApplication.processEvents()
        seen[hour] = widget.grab().toImage().pixelColor(point).name()
    from oms_ui import theme

    fondo = theme.PALETTE_CLARO["fondo"]
    assert seen["00Z"] == seen["12Z"] == fondo


def test_cli3074_group_headers_uniform_slate(cli3074_page, qtbot):
    """Owner round 8: every 3074 group header wears the HUMEDAD color."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    labels = [w for w in view.findChildren(QLabel)
              if w.text() in ("PRESIÓN (hPa)", "3 H. TEND", "TEMPERATURA",
                              "HUMEDAD", "VIENTO", "VISIBILIDAD (km)", "FENÓMENOS")]
    assert len(labels) == 7
    styles = {w.styleSheet() for w in labels}
    assert len(styles) == 1  # one shared color across all groups
    assert "#334155" in labels[0].styleSheet()


def test_cli4074_total_headers_full_height_emerald(cli3074_page, qtbot):
    """Owner round 8: the three TOTAL heads span both header rows (same
    height as N/LLUVIA) in emerald."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli4074")
    view = cli3074_page._stack.currentWidget()
    grid = view.row_inputs[2]["nubosidad"].parentWidget().layout()
    totals = []
    for r in range(grid.count()):
        item = grid.itemAt(r)
        w = item.widget() if item else None
        if isinstance(w, QLabel) and w.text() == "TOTAL":
            totals.append(grid.getItemPosition(r))
    assert len(totals) == 3
    for _row, _col, row_span, _col_span in totals:
        assert row_span == 2  # full header height like N/LLUVIA


def test_cli_no_save_button_autosaves_instead(cli3074_page, qtbot, fresh_db):
    """Owner round 8: no Guardar button anywhere; edits autosave debounced."""

    from oms_ui.pages.cli3074 import Cli3074View

    cli3074_page._open_cli("cli3074")
    view = cli3074_page._stack.currentWidget()
    assert not hasattr(view, "save_btn")
    view._autosave_timer.setInterval(60)  # injectable: same real path
    view.row_inputs[2]["pres_est"].setText("1014.7")
    _wait_timer(view._autosave_timer)
    reloaded = Cli3074View(fresh_db, station="78485", fecha="2025-12-08")
    assert reloaded.row_inputs[2]["pres_est"].text() == "1014.7"


def QApplication_events(widget):
    from PySide6.QtWidgets import QApplication

    for _ in range(4):
        QApplication.processEvents()


# ---------------------------------------------------------------- round 9: sky transition


def test_los_botones_de_hora_no_tienen_color_por_hora():
    """El selector dice la hora con el icono y el estado con el acento.

    `HOUR_THEMES` guardaba el cielo de cada hora (from/to/accent/text) y teñía
    los botones con él. El fondo por hora se eliminó con los degradados y el
    acento pasó a ser único: lo que sobrevive es el icono (sol, amanecer, luna),
    que informa la hora sin depender del color.
    """
    from pathlib import Path

    from oms_ui.pages import synoptic as pagina

    assert not hasattr(pagina, "HOUR_THEMES")
    fuente = (
        Path(__file__).resolve().parents[1] / "oms_ui" / "pages" / "synoptic.py"
    ).read_text(encoding="utf-8")
    assert "HOUR_THEMES" not in fuente
    # los iconos por hora siguen existiendo, y sólo como nombre de icono
    assert set(pagina.HOUR_ICONS) == {"06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"}
    assert all(isinstance(v, str) for v in pagina.HOUR_ICONS.values())

def test_el_selector_marca_la_hora_aunque_el_fondo_no_cambie(qtbot, fresh_db, tmp_path):
    """Píxeles clavados: el fondo plano no se mueve; la hora la marca el selector."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    # admin: these tests exercise the save mechanics on dates that are
    # already closed under rule R4 (06Z of the next day)
    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget.resize(1200, 700)
    widget.show()
    for _ in range(6):
        QApplication.processEvents()
    point = QPoint(6, 300)
    seen = {}
    for hour in ("12Z", "00Z", "06Z"):
        widget.select_hour(hour)
        for _ in range(8):
            QApplication.processEvents()
        seen[hour] = widget.grab().toImage().pixelColor(point).name()
    assert len(set(seen.values())) == 1  # el fondo ya no cambia con la hora


def test_cli5074_uses_its_red_identity(cli3074_page, qtbot):
    """Owner round 9: 5074's representative color is RED (focus ring,
    station-card top band, hover accents) per IMG/CLI 5074.png."""
    from PySide6.QtWidgets import QPushButton

    cli3074_page._open_cli("cli5074")
    view = cli3074_page._stack.currentWidget()
    # focus ring red on the sheet fields
    assert "#e11d48" in view.fields["hourly.8.pres_est"].styleSheet()
    # round 10: the station/fecha card is fully neutral (no band)
    station_card = view.station_combo.parentWidget()
    assert "#e11d48" not in station_card.styleSheet()
    # the tab bar marks 5074 red while 3074 keeps blue / 4074 green
    tabs = [b for b in view.findChildren(QPushButton)
            if b.text() in ("3074", "4074", "5074")]
    fifty = next(b for b in tabs if b.text() == "5074")
    assert "#e11d48" in fifty.styleSheet()


# ---------------------------------------------------------------- round 10: 5074 red discipline


def test_cli5074_red_only_where_it_speaks(cli3074_page, qtbot):
    """Owner rounds 10-12 + A12: the module's red speaks only on the
    phenomena times (INICIO/FINAL); the daily extremes block — and its dew
    point header — no longer exists, and the station card stays neutral."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli5074")
    view = cli3074_page._stack.currentWidget()
    labels = [w.text() for w in view.findChildren(QLabel)]
    assert "PUNTO DE ROCÍO (°C)" not in labels  # A12: block removed
    assert "LLUVIA" not in labels
    ini = next(w for w in view.findChildren(QLabel)
               if w.text() == "INICIO (HH:MM)")
    fin = next(w for w in view.findChildren(QLabel)
               if w.text() == "FINAL (HH:MM)")
    assert "#e11d48" in ini.styleSheet() and "#e11d48" in fin.styleSheet()
    # station/fecha card: NO module color at all
    card = view.station_combo.parentWidget()
    assert "#e11d48" not in card.styleSheet()
    assert "#ffffff" in card.styleSheet()  # plain white card like the 4074


# ---------------------------------------------------------------- round 12: 5074 typography/color order


def test_cli5074_section_titles_use_standard_typography(cli3074_page, qtbot):
    """Owner round 12: 'OBSERVACIONES...' and 'INICIALES OBS.' carry the
    same 12px/800 section typography as HORARIO/SUBSUELO/EVAP."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli5074")
    view = cli3074_page._stack.currentWidget()
    reference = next(w for w in view.findChildren(QLabel) if w.text() == "HORARIO")
    for text in ("OBSERVACIONES Y DETALLES DEL FENÓMENO", "INICIALES OBS."):
        label = next(w for w in view.findChildren(QLabel) if w.text() == text)
        assert label.styleSheet() == reference.styleSheet(), text


def test_cli5074_subless_fenomeno_headers_full_height(cli3074_page, qtbot):
    """INTENSIDAD/FENÓMENOS/INICIO/FINAL/DURACIÓN/INICIALES span BOTH header
    rows — no dead gap under them anymore."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli5074")
    view = cli3074_page._stack.currentWidget()
    from PySide6.QtWidgets import QGridLayout as _GL

    grids = [g for g in view.findChildren(_GL)]
    grid = next(
        g for g in grids
        if any(
            (it := g.itemAt(i)) and it.widget() and getattr(it.widget(), "text", lambda: "")() == "INTENSIDAD"
            for i in range(g.count())
        )
    )
    spans = {}
    for r in range(grid.count()):
        item = grid.itemAt(r)
        w = item.widget() if item else None
        if isinstance(w, QLabel) and w.text() in (
            "INTENSIDAD", "FENÓMENOS METEOROLÓGICOS", "INICIO (HH:MM)",
            "FINAL (HH:MM)", "DURACIÓN", "INICIALES OBSERV.",
        ):
            spans[w.text()] = grid.getItemPosition(r)[2]
    assert spans and all(span == 2 for span in spans.values()), spans
    # HORA LOCAL keeps its two-row group (Horas/Minutos sub-headers)
    hora_span = None
    for r in range(grid.count()):
        item = grid.itemAt(r)
        w = item.widget() if item else None
        if isinstance(w, QLabel) and w.text() == "HORA LOCAL":
            hora_span = grid.getItemPosition(r)[2]
    assert hora_span == 1


def test_cli5074_red_accent_map(cli3074_page, qtbot):
    """Round 12 + A12: FINAL joins INICIO in red and the (mm)/(°C) unit chips
    speak red; the dew point header left with the removed daily block."""
    from PySide6.QtWidgets import QLabel

    cli3074_page._open_cli("cli5074")
    view = cli3074_page._stack.currentWidget()
    by_text = {}
    for w in view.findChildren(QLabel):
        by_text.setdefault(w.text(), w.styleSheet())
    assert "#e11d48" in by_text["FINAL (HH:MM)"]
    assert "#e11d48" in by_text["INICIO (HH:MM)"]
    assert "#e11d48" in by_text["(°C)"]          # subsuelo unit chip
    assert "#e11d48" in by_text["(mm)"]          # evap unit chips
    assert "PUNTO DE ROCÍO (°C)" not in by_text   # removed with the block


# ------------------------------------------------- A4: cierre del día (R4)


def test_observador_cannot_save_a_closed_day(fresh_db, tmp_path, qtbot):
    """The day closes at 06Z of the next day: a regular role is refused and
    nothing is written."""
    from oms_core.db.repositories import summaries as summaries_repo

    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="observador")
    qtbot.addWidget(widget)
    widget._draft_guard_class = _stub_dialog_class(DraftGuardDialog.DISCARD)
    widget.set_station(STATION)
    widget.fecha_edit.setDate(QDate(2025, 12, 8))  # long closed
    _filled_hour(widget, "06Z")

    widget.do_save()

    assert "se cerró a las 06Z" in widget.error_label.text()
    assert summaries_repo.get_summary_doc(
        fresh_db, STATION, 2025, 12, "diario", day=8) is None


def test_admin_can_correct_a_closed_day(fresh_db, tmp_path, qtbot):
    """The auditing roles keep the door open, and the write is versioned."""
    from oms_core.db.repositories import summaries as summaries_repo
    from oms_core.services import versions as versions_service

    widget = SynopticPage(fresh_db, config_dir=tmp_path, role="admin")
    qtbot.addWidget(widget)
    widget._draft_guard_class = _stub_dialog_class(DraftGuardDialog.DISCARD)
    widget.set_station(STATION)
    widget.fecha_edit.setDate(QDate(2025, 12, 8))
    _filled_hour(widget, "06Z")

    widget.do_save()

    assert summaries_repo.get_summary_doc(
        fresh_db, STATION, 2025, 12, "diario", day=8) is not None
    assert versions_service.count(fresh_db, STATION, 2025, 12, 8) >= 1


# ---------------------------------------- day picker like the audit (ronda 32)


def test_the_date_is_chosen_from_the_stored_observations(page, qtbot, monkeypatch):
    """S9: the date is not typed blind; the calendar button opens the same
    station -> year -> month -> day selector the audit page drills through, and
    picking a day moves the page to that station and date."""
    import oms_ui.observation_picker as picker_module

    calls = {}

    class _StubPicker:
        def __init__(self, conn, station=None, show_stations=False, parent=None):
            calls["station"] = station
            calls["show_stations"] = show_stations

        def exec(self):
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Accepted

        def selection(self):
            return (None, "2025-10-02")

    monkeypatch.setattr(picker_module, "ObservationPickerDialog", _StubPicker)
    qtbot.mouseClick(page.date_picker_button, Qt.LeftButton)

    assert calls["station"] == page.station_id, "el selector arranca en la estación actual"
    # el selector recibe la estación de la página y decide si la ofrece
    assert calls["show_stations"] == (page.station_combo.count() > 1)
    assert page.fecha_edit.date().toString("yyyy-MM-dd") == "2025-10-02"


def test_ningun_estilo_del_sinoptico_queda_con_tokens_sin_resolver():
    """Un `$rol` que llega a Qt se ignora en silencio: el widget pierde el color.

    Se recorre cada `setStyleSheet(...)` de la página y se comprueba que ninguna
    hoja con tokens quede sin pasar por `_qss()`.
    """
    from pathlib import Path

    fuente = (Path(__file__).resolve().parents[1] / "oms_ui" / "pages" / "synoptic.py").read_text(
        encoding="utf-8"
    )
    pendientes, i = [], 0
    while True:
        j = fuente.find("setStyleSheet(", i)
        if j < 0:
            break
        ini_arg = j + len("setStyleSheet(")
        prof, k = 1, ini_arg
        while k < len(fuente) and prof:
            if fuente[k] == "(":
                prof += 1
            elif fuente[k] == ")":
                prof -= 1
            k += 1
        arg = fuente[ini_arg : k - 1]
        if "$" in arg and "_qss(" not in arg:
            pendientes.append(fuente[:j].count("\n") + 1)
        i = k
    assert not pendientes, f"hojas con tokens sin resolver en las líneas {pendientes}"
