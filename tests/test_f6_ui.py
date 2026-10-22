"""F6 — pytest-qt UI tests for the three audit pages (offscreen).

Wizard navigation (stations -> years -> months -> days), the observation hour
grid with marks plus the mark/unmark/note/propose/export flows, and the report
page (detailed|person tabs, filters, notes field). Role gating: encargado sees
no audit entry (enforced boundary, like the OLD App.jsx RoleRoute guard).
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget

from oms_core.db.repositories import summaries as summaries_repo
from oms_ui.main_window import MainWindow

STATION = "78485"
FECHA = "2025-12-08"
FILENAME = "7848508122025.json"


def _make_base(tmp_path: Path) -> Path:
    base = tmp_path / "synop"
    month_dir = base / STATION.lower() / "2025" / "12"
    month_dir.mkdir(parents=True)
    doc = {
        "meta": {"estacion": STATION, "fecha": "08122025", "observador": "Juan Perez"},
        "horas": {
            "06Z": {
                "observador": "Juan Perez",
                "datos": {
                    "ts": "23.2",
                    "th": "22.3",
                    "pres_est": "1025.3",
                    "p3": "1022.3",
                    "p24": "1024.1",
                    "correc_alt": "1.6",
                },
                "synop": {"Nddff": "81005"},
                "calculado": {},
            }
        },
    }
    (month_dir / FILENAME).write_text(json.dumps(doc), encoding="utf-8")
    return base


def _seed_diario(conn):
    text = json.dumps(
        {
            "meta": {"estacion": STATION, "fecha": "08122025", "observador": ""},
            "horas": {
                "06Z": {
                    "observador": "Juan Perez",
                    "datos": {
                        "ts": "23.2",
                        "th": "22.3",
                        "pres_est": "1025.3",
                        "correc_alt": "1.6",
                    },
                    "synop": {"Nddff": "81005"},
                    "calculado": {},
                },
                "12Z": {
                    "observador": "",
                    "datos": {
                        "ts": "25.0",
                        "th": "23.0",
                        "pres_est": "1024.0",
                        "correc_alt": "1.6",
                    },
                    "synop": {},
                    "calculado": {},
                },
            },
        }
    )
    summaries_repo.upsert_summary_doc(
        conn,
        station_id=STATION,
        year=2025,
        month=12,
        kind="diario",
        data=text,
        sha256="seed",
        day=8,
    )


def _click_item(qtbot, widget: QListWidget, row: int) -> None:
    item = widget.item(row)
    assert item is not None
    rect = widget.visualItemRect(item)
    qtbot.mouseClick(widget.viewport(), Qt.LeftButton, pos=rect.center())


# ---------------------------------------------------------------- wizard


def test_wizard_navigates_four_steps(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.audit import AuditPage

    base = _make_base(tmp_path)
    page = AuditPage(fresh_db, base, role="admin")
    qtbot.addWidget(page)

    assert page.step == 1
    # the oracle renders CARD GRIDS, not lists (round 28)
    assert len(page.station_cards) == 1
    page.station_cards[0].clicked.emit()
    assert page.step == 2
    assert len(page.year_cards) == 1
    page.year_cards[0].clicked.emit()
    assert page.step == 3
    assert len(page.month_cards) == 1
    page.month_cards[0].clicked.emit()
    assert page.step == 4
    assert len(page.day_rows) == 1


def test_wizard_back_button_returns_one_level(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.audit import AuditPage

    base = _make_base(tmp_path)
    page = AuditPage(fresh_db, base, role="admin")
    qtbot.addWidget(page)

    page.station_cards[0].clicked.emit()
    assert page.step == 2
    qtbot.mouseClick(page.back_button, Qt.LeftButton)
    assert page.step == 1


def test_wizard_denied_for_encargado(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.audit import AuditPage

    page = AuditPage(fresh_db, tmp_path, role="encargado")
    qtbot.addWidget(page)
    assert page.denied is True


# ---------------------------------------------------------------- observation page


def test_observation_hour_grid_shows_marks(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.audit_observation import AuditObservationPage

    base = _make_base(tmp_path)
    _seed_diario(fresh_db)
    page = AuditObservationPage(
        fresh_db, base, STATION, FECHA, role="admin", user_email="auditor@arca"
    )
    qtbot.addWidget(page)

    assert page.hour_buttons["06Z"].isEnabled()
    qtbot.mouseClick(page.hour_buttons["12Z"], Qt.LeftButton)
    assert page.active_hour == "12Z"
    # the observer-less hour carries the auto mark badge
    assert "12Z" in page.marks_label.text() or len(page.mark_blocks) >= 1


def test_observation_mark_propose_export_flow(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.audit_observation import AuditObservationPage

    base = _make_base(tmp_path)
    _seed_diario(fresh_db)
    page = AuditObservationPage(
        fresh_db, base, STATION, FECHA, role="admin", user_email="auditor@arca"
    )
    qtbot.addWidget(page)

    page.select_cell("ts")
    page.mark_dialog.type_combo.setCurrentText("Sintaxis")
    page.mark_dialog.note_edit.setPlainText("typo")
    qtbot.mouseClick(page.mark_dialog.save_button, Qt.LeftButton)
    assert len(page.mark_blocks) >= 1

    page.select_cell("ts")
    qtbot.mouseClick(page.to_correction_button, Qt.LeftButton)
    page.correction_dialog.value_edit.setText("23.5")
    page.correction_dialog.justification_edit.setPlainText("oracle round-trip")
    qtbot.mouseClick(page.correction_dialog.save_button, Qt.LeftButton)

    qtbot.mouseClick(page.export_button, Qt.LeftButton)
    assert "cor.json" in page.status_label.text()
    out = Path(page.status_label.text().rsplit(":", 1)[-1].strip())
    assert out.exists()
    exported = json.loads(out.read_text(encoding="utf-8"))
    assert exported["horas"]["06Z"]["datos"]["ts"] == "23.5"


def test_observation_denied_for_encargado(qtbot, fresh_db, tmp_path):
    from oms_ui.pages.audit_observation import AuditObservationPage

    page = AuditObservationPage(
        fresh_db, tmp_path, STATION, FECHA, role="encargado", user_email="enc@arca"
    )
    qtbot.addWidget(page)
    assert page.denied is True


# ---------------------------------------------------------------- report page


def test_report_tabs_filters_and_notes(qtbot, fresh_db):
    from oms_core.db.repositories import audit as audit_repo
    from oms_ui.pages.audit_report import AuditReportPage

    audit_repo.mark_error(
        fresh_db,
        station_id="78451",
        fecha="2025-06-10",
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@x",
    )
    page = AuditReportPage(fresh_db, role="admin")
    qtbot.addWidget(page)

    # round 25: the observer's sheet comes first — it is the published report
    assert page.tabs.count() == 3
    assert page.tabs.tabText(0) == "Por observador"
    assert page.tabs.tabText(1) == "Detalle"
    assert page.tabs.tabText(2) == "Actividad del auditor"
    assert page.detail_table.rowCount() == 1
    # the observer row plus the TOTAL row the published sheet needs
    assert page.observer_table.rowCount() == 2
    assert page.observer_table.item(1, 0).text() == "TOTAL"

    page.notes_edit.setPlainText("general note")
    assert page.notes_edit.toPlainText() == "general note"

    page.station_filter.setText("ZZZ-no-match")
    qtbot.mouseClick(page.filter_button, Qt.LeftButton)
    assert page.detail_table.rowCount() == 0
    page.station_filter.setText("")
    qtbot.mouseClick(page.filter_button, Qt.LeftButton)
    assert page.detail_table.rowCount() == 1

    page.tabs.setCurrentIndex(1)
    assert page.person_table.rowCount() == 1
    assert page.person_table.item(0, 0).text() == "auditor@x"


def test_report_note_edit_updates_db(qtbot, fresh_db):
    from oms_core.db.repositories import audit as audit_repo
    from oms_ui.pages.audit_report import AuditReportPage

    mark_id = audit_repo.mark_error(
        fresh_db,
        station_id="78451",
        fecha="2025-06-10",
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@x",
    )
    page = AuditReportPage(fresh_db, role="admin")
    qtbot.addWidget(page)

    page.note_edit.setText("fixed note")
    qtbot.mouseClick(page.note_save_button, Qt.LeftButton)
    (stored,) = audit_repo.get_error_marks(fresh_db, "78451", "2025-06-10")
    assert stored.nota == "fixed note"
    assert mark_id > 0


# ---------------------------------------------------------------- nav gating


def test_main_window_hides_audit_for_encargado(qtbot, fresh_db):
    window = MainWindow(role="encargado", db_path=fresh_db)
    qtbot.addWidget(window)
    assert "audit" not in window.visible_pages()


def test_main_window_shows_audit_for_admin_and_cc(qtbot, fresh_db):
    for role in ("admin", "control_calidad"):
        window = MainWindow(role=role, db_path=fresh_db)
        qtbot.addWidget(window)
        assert "audit" in window.visible_pages()
