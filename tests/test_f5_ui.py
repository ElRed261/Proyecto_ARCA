"""F5 — pytest-qt UI tests for the summary page.

QT_QPA_PLATFORM=offscreen is forced in tests/conftest.py; the real flow is
exercised with clicks: station/month/year selectors → Generar → the 31×21
table (QTableView over a QAbstractTableModel) with verbatim Spanish headers
and the corrections indicator → export to Excel writes a readable file.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from PySide6.QtCore import Qt

from oms_core.db.repositories import audit as audit_repo
from oms_core.importer.importer import Importer
from oms_core.services import summary as summary_service
from oms_ui.pages.summary import SummaryPage

FIXTURE_JSON = Path(__file__).parent / "fixtures" / "importer" / "json"


@pytest.fixture()
def page(qtbot, fresh_db):
    Importer(fresh_db).import_root(FIXTURE_JSON)
    widget = SummaryPage(fresh_db)
    qtbot.addWidget(widget)
    return widget


# ---------------------------------------------------------------- selectors


def test_selectors_list_stations_months_years(page):
    ids = [page.station_combo.itemText(i) for i in range(page.station_combo.count())]
    assert "Estación Central" in ids  # from the imported fixture diarios
    assert page.month_combo.count() == 12
    assert page.month_combo.itemText(0) == "enero"
    assert page.month_combo.itemText(4) == "mayo"
    assert page.year_spin.value() >= 2025


# ---------------------------------------------------------------- full flow


def test_generate_flow_31_rows_and_headers(page, qtbot, tmp_path):
    page.station_combo.setCurrentText("Estación Central")
    page.month_combo.setCurrentIndex(4)  # mayo
    page.year_spin.setValue(2025)
    qtbot.mouseClick(page.generate_button, Qt.LeftButton)

    model = page.table.model()
    assert model.rowCount() == 31
    assert model.columnCount() == 21
    assert model.headerData(0, Qt.Horizontal) == "Dias"
    assert model.headerData(20, Qt.Horizontal) == "Tensión de vapor"
    # the day with data shows the oracle value; a day without the diario is empty
    assert model.data(model.index(14, 0), Qt.DisplayRole) == "2025-05-15"
    assert model.data(model.index(14, 1), Qt.DisplayRole) == "29.0"
    assert model.data(model.index(9, 1), Qt.DisplayRole) == ""
    # the generated doc is stored and the history reflects it
    assert summary_service.load_doc(
        page.conn, "Estación Central", 2025, 5) is not None
    assert page.history_list.count() == 1
    assert "05/2025" in page.history_list.item(0).text()


def test_history_click_loads_doc_into_table(page, qtbot):
    page.station_combo.setCurrentText("Estación Central")
    page.month_combo.setCurrentIndex(4)
    page.year_spin.setValue(2025)
    qtbot.mouseClick(page.generate_button, Qt.LeftButton)

    page.history_list.setCurrentRow(0)
    model = page.table.model()
    assert model.rowCount() == 31


def test_export_button_writes_excel(page, qtbot, tmp_path):
    page.station_combo.setCurrentText("Estación Central")
    page.month_combo.setCurrentIndex(4)
    page.year_spin.setValue(2025)
    qtbot.mouseClick(page.generate_button, Qt.LeftButton)

    out = tmp_path / "exportada.xlsx"
    page.export_doc_to(out)  # the handler behind the export button
    import openpyxl

    wb = openpyxl.load_workbook(out)
    ws = wb.active
    assert [c.value for c in ws[1]] == list(summary_service.HEADERS)
    assert ws.cell(row=16, column=1).value == "2025-05-15"


def test_corrections_indicator_marks_the_day(page, qtbot):
    audit_repo.propose_correction(
        page.conn,
        station_id="Estación Central",
        fecha="2025-05-15",
        hora="12Z",
        campo="pres_est",
        valor_original="1013.0",
        valor_corregido="1020.0",
        justificacion="test",
        corregido_por="tester",
        estado="aprobado",
    )
    page.station_combo.setCurrentText("Estación Central")
    page.month_combo.setCurrentIndex(4)
    page.year_spin.setValue(2025)
    qtbot.mouseClick(page.generate_button, Qt.LeftButton)

    editor = page.table.model()
    idx = editor.createIndex(14, 0)
    assert editor.data(idx, Qt.BackgroundRole) is not None  # marked day
    assert "1" in str(editor.data(idx, Qt.ToolTipRole))


def test_generate_month_without_data_shows_null_table(page, qtbot):
    page.station_combo.setCurrentText("MDJB")
    page.month_combo.setCurrentIndex(1)  # febrero
    page.year_spin.setValue(2025)
    qtbot.mouseClick(page.generate_button, Qt.LeftButton)

    model = page.table.model()
    assert model.rowCount() == 28
    assert model.data(model.index(0, 1), Qt.DisplayRole) == ""
    # the doc sort of exists: 28 rows of nulls
    assert len(summary_service.load_doc(page.conn, "MDJB", 2025, 2)["datos"]) == 28
