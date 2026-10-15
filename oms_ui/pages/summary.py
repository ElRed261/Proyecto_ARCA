"""SummaryPage — monthly summary screen (PRD F5).

PySide6 port of ``OLD/frontend/src/features/summary/pages/SummaryPage.jsx``
backed by the Qt-free ``oms_core.services.summary`` service (ADR-03: only
presentation here) and ``oms_core.services.excel_export``:

- station/month/year selectors (stations repository);
- Generar button with inline progress (no frozen UI);
- history list of the generated summaries (kind='mensual') with load +
  delete (DB row instead of the OS trash file of the oracle);
- the 31×21 table: QTableView over a QAbstractTableModel with the 21 VERBATIM
  Spanish headers (json_pipeline serde renames — typos included);
- export-to-Excel button writing the openpyxl workbook;
- the corrections indicator: days touched by approved audit corrections get
  a distinct background on the Dias cell plus a tooltip with the count.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_core.services import excel_export
from oms_core.services import summary as summary_service

#: Months of the year in the UI's Spanish labels (index = month number - 1).
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_CORRECTION_QSS = """
SummaryPage QLabel { color: #0f172a; }
SummaryPage QLabel#ok { color: #065f46; }
"""

#: The cell mark (background) for days with approved corrections.
_MARK = QBrush(QColor("#fef9c3"))


class SummaryTableModel(QAbstractTableModel):
    """31×21 model over the generated document's ``datos`` rows.

    The 21 headers are the verbatim oracle strings; numbers keep their type
    for the export path (Qt.EditRole) and render as-is for the screen; nulls
    render empty. The corrections indicator lives on the Dias cell
    (background + tooltip count), never altering the displayed values.
    """

    def __init__(self, doc: dict[str, Any] | None = None,
                 corrections: dict[int, int] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = list((doc or {}).get("datos") or [])
        self._corrections = dict(corrections or {})

    def set_document(self, doc: dict[str, Any],
                     corrections: dict[int, int] | None = None) -> None:
        self.beginResetModel()
        self._rows = list((doc or {}).get("datos") or [])
        self._corrections = dict(corrections or {})
        self.endResetModel()

    def corrections(self) -> dict[int, int]:
        return dict(self._corrections)

    # -- model contract ------------------------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return len(summary_service.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return summary_service.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        header = summary_service.HEADERS[index.column()]
        row = self._rows[index.row()]
        value = row.get(header)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if value is None or value == "":
                return "" if role == Qt.ItemDataRole.DisplayRole else None
            return str(value) if role == Qt.ItemDataRole.DisplayRole else value
        if role == Qt.ItemDataRole.TextAlignmentRole and header != "Dias":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.BackgroundRole:
            day = self._day_of_row(index.row())
            if day in self._corrections:
                return _MARK
        if role == Qt.ItemDataRole.ToolTipRole:
            day = self._day_of_row(index.row())
            count = self._corrections.get(day)
            if count:
                return f"Correcciones aplicadas: {count}"
        return None

    def _day_of_row(self, row_index: int) -> int:
        try:
            return int(str(self._rows[row_index].get("Dias", ""))[-2:])
        except (ValueError, TypeError):
            return row_index + 1


class SummaryPage(QWidget):
    """The monthly summary screen (station/month/year → generate → table)."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.doc: dict[str, Any] | None = None
        self._corrections: dict[int, int] = {}

        self.station_combo = QComboBox()
        for station in stations_repo.list_stations(conn, include_inactive=True):
            self.station_combo.addItem(station.id, station.id)

        self.month_combo = QComboBox()
        for name in MONTHS:
            self.month_combo.addItem(name)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1990, 2250)
        self.year_spin.setValue(_dt.date.today().year)

        self.generate_button = QPushButton("Generar")
        self.export_button = QPushButton("Exportar a Excel")
        self.delete_button = QPushButton("Enviar a la papelera")
        self.history_list = QListWidget()
        self.table = QTableView()
        self.model = SummaryTableModel()
        self.table.setModel(self.model)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.status_label = QLabel("Resumen Mensual SYNOP")
        self.status_label.setObjectName("ok")

        self._build_ui()
        self.setStyleSheet(_CORRECTION_QSS)
        self.refresh_history()

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        self.setWindowTitle("Resumen Mensual SYNOP")
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Estación"))
        top.addWidget(self.station_combo)
        top.addWidget(QLabel("Mes"))
        top.addWidget(self.month_combo)
        top.addWidget(QLabel("Año"))
        top.addWidget(self.year_spin)
        top.addWidget(self.generate_button)
        top.addWidget(self.export_button)
        layout.addLayout(top)

        self.progress.hide()  # inline progress: visible only while generating
        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)

        middle = QHBoxLayout()
        history_box = QVBoxLayout()
        history_box.addWidget(QLabel("Historial"))
        history_box.addWidget(self.history_list)
        history_box.addWidget(self.delete_button)
        middle.addLayout(history_box, 1)
        middle.addWidget(self.table, 3)
        layout.addLayout(middle, 1)

        self.generate_button.clicked.connect(self.on_generate)
        self.export_button.clicked.connect(self.on_export)
        self.delete_button.clicked.connect(self.on_delete)
        self.history_list.currentRowChanged.connect(self.on_history_selected)

    # ------------------------------------------------------------ handlers

    def on_generate(self) -> None:
        station = self.station_combo.currentText()
        if not station:
            return
        year, month = self.year_spin.value(), self.month_combo.currentIndex() + 1
        self._begin_progress()
        try:
            self.doc = summary_service.generate_month(self.conn, station, year, month)
        except (summary_service.SummaryError, sqlite3.Error) as exc:
            self._status(str(exc), error=True)
            return
        finally:
            self._end_progress()
        self._corrections = summary_service.corrections_by_day(
            self.conn, station, year, month)
        self.model.set_document(self.doc, self._corrections)
        marked = sum(1 for count in self._corrections.values() if count)
        self._status(
            f"Resumen generado exitosamente ({self.doc['meta']['total_dias']} días,"
            f" {marked} con correcciones)"
        )
        self.refresh_history()

    def on_export(self) -> None:
        if self.doc is None:
            self._status("Genera o carga un resumen antes de exportar", error=True)
            return
        meta = self.doc.get("meta") or {}
        default = f"resumen_{meta.get('estacion', 'resumen')}_{meta.get('periodo', '').replace('/', '_')}.xlsx"
        path, _filter = QFileDialog.getSaveFileName(
            self, "Exportar a Excel", default, "Excel (*.xlsx)"
        )
        if not path:
            return
        self.export_doc_to(path)

    def export_doc_to(self, path) -> str:
        """Write the current doc to ``path``; shared by the button handler
        and the tests (no native dialogs in the flow they exercise)."""
        out = excel_export.export_to_excel(self.doc, path)
        self._status(f"Exportado a Excel correctamente: {out}")
        return str(out)

    def on_delete(self) -> None:
        item = self.history_list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        summary_service.delete_doc(self.conn, entry["station"], entry["year"],
                                   entry["month"])
        self.doc = None
        self.model.set_document({})
        self.refresh_history()
        self._status("Resumen enviado a la papelera exitosamente")

    def on_history_selected(self, row: int) -> None:
        if row < 0:
            return
        entry = self.history_list.item(row).data(Qt.ItemDataRole.UserRole)
        self.doc = summary_service.load_doc(self.conn, entry["station"],
                                            entry["year"], entry["month"])
        if self.doc is None:
            return
        self._corrections = summary_service.corrections_by_day(
            self.conn, entry["station"], entry["year"], entry["month"])
        self.model.set_document(self.doc, self._corrections)
        self._status(f"Resumen cargado: {entry['station']} · {entry['period']}")

    # -------------------------------------------------------------- helpers

    def refresh_history(self) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for entry in summary_service.list_history(self.conn):
            item = QListWidgetItem(
                f"{entry['station']} · {entry['period']} · {entry['total_dias']} días"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_list.addItem(item)
        self.history_list.blockSignals(False)

    def _begin_progress(self) -> None:
        self.progress.setRange(0, 0)  # busy indicator while SQLite runs
        self.progress.show()
        self._status("Generando resumen…")

    def _end_progress(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

    def _status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setObjectName("error" if error else "ok")
        self.status_label.setStyleSheet(self.styleSheet())  # re-evaluate QSS


__all__ = ["MONTHS", "SummaryPage", "SummaryTableModel"]
