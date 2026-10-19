"""AuditReportPage — error report + person summary (PRD F6).

PySide6 port of ``OLD/.../audit/pages/AuditReportPage.jsx`` over the Qt-free
``oms_core.services.audit`` report surfaces (ADR-03): ``detailed`` and
``person`` tabs, station/year/month filters, an inline note editor bound to
the selected (or first) detailed row, and a free-text general-notes field
kept for the printed/exported report header.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_ui.widgets import StyledComboBox

#: Service failures the status line can present (never crash the page).
_UI_ERRORS = (audit_service.AuditError, OSError, sqlite3.Error)

DETAIL_HEADERS = ("Estación", "Fecha", "Hora", "Campo", "Tipo", "Original", "Corregido", "Nota")
PERSON_HEADERS = ("Persona", "Errores", "Propuestas", "Aprobadas")


class AuditReportPage(QWidget):
    """Detailed | person tabs with filters and a notes field."""

    def __init__(
        self, conn: sqlite3.Connection, role: str = "admin", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.role = role
        self.denied = not access.can_access(role, "audit")
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)
        if self.denied:
            layout.addWidget(
                QLabel("Acceso denegado: la auditoría requiere rol admin o control_calidad.")
            )
            self._denied_widgets()
            return

        filters = QHBoxLayout()
        self.station_filter = QLineEdit()
        self.station_filter.setPlaceholderText("Station (optional)")
        self.year_filter = QLineEdit()
        self.year_filter.setPlaceholderText("YYYY")
        self.month_filter = StyledComboBox()
        self.month_filter.addItem("(All)", "")
        for num in sorted(audit_service.MONTH_NAMES):
            self.month_filter.addItem(audit_service.MONTH_NAMES[num], num)
        self.filter_button = QPushButton("Filtrar")
        self.filter_button.clicked.connect(self.apply_filters)
        filters.addWidget(QLabel("Estación"))
        filters.addWidget(self.station_filter)
        filters.addWidget(QLabel("Año"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Mes"))
        filters.addWidget(self.month_filter)
        filters.addWidget(self.filter_button)
        layout.addLayout(filters)

        layout.addWidget(QLabel("Notas Generales del Reporte"))
        self.notes_edit = QTextEdit()
        layout.addWidget(self.notes_edit)

        self.tabs = QTabWidget()
        self.detail_table = QTableWidget(0, len(DETAIL_HEADERS))
        self.detail_table.setHorizontalHeaderLabels(list(DETAIL_HEADERS))
        self.person_table = QTableWidget(0, len(PERSON_HEADERS))
        self.person_table.setHorizontalHeaderLabels(list(PERSON_HEADERS))
        self.tabs.addTab(self.detail_table, "Detailed")
        self.tabs.addTab(self.person_table, "Person")
        layout.addWidget(self.tabs)

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("Nota de la fila"))
        self.note_edit = QLineEdit()
        self.note_save_button = QPushButton("Guardar Nota")
        self.note_save_button.clicked.connect(self.save_note)
        note_row.addWidget(self.note_edit)
        note_row.addWidget(self.note_save_button)
        layout.addLayout(note_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self.apply_filters()

    def _denied_widgets(self) -> None:
        """Inert placeholders so callers can rely on the attributes."""
        self.station_filter = QLineEdit()
        self.year_filter = QLineEdit()
        self.month_filter = StyledComboBox()
        self.filter_button = QPushButton("Filtrar")
        self.notes_edit = QTextEdit()
        self.tabs = QTabWidget()
        self.detail_table = QTableWidget(0, len(DETAIL_HEADERS))
        self.person_table = QTableWidget(0, len(PERSON_HEADERS))
        self.note_edit = QLineEdit()
        self.note_save_button = QPushButton("Guardar Nota")
        self.status_label = QLabel("")

    # ------------------------------------------------------------------ data

    def _current_filters(self) -> dict:
        return {
            "station_id": self.station_filter.text().strip() or None,
            "year": self.year_filter.text().strip(),
            "month": self.month_filter.currentData() or "",
        }

    def apply_filters(self) -> None:
        """Reload both tabs from the service with the current filters."""
        if self.denied:
            return
        filters = self._current_filters()
        try:
            self._rows = audit_service.get_error_report(self.conn, **filters)
            summary = audit_service.get_person_summary(self.conn, **filters)
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.detail_table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            cells = (
                row["station_id"],
                row["fecha"],
                row["hora"],
                row["campo"],
                row["tipo_error"],
                row["valor_original"] or "",
                row["valor_corregido"] or "",
                row["nota"] or "",
            )
            for col_idx, value in enumerate(cells):
                self.detail_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        self.person_table.setRowCount(len(summary))
        for row_idx, row in enumerate(summary):
            cells = (
                row["persona"],
                str(row["errores_marcados"]),
                str(row["correcciones_propuestas"]),
                str(row["correcciones_aprobadas"]),
            )
            for col_idx, value in enumerate(cells):
                self.person_table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        self.status_label.setText(f"{len(self._rows)} rows")

    def _target_row(self) -> dict | None:
        """Selected detailed row, falling back to the first one."""
        if not self._rows:
            return None
        selected = self.detail_table.currentRow()
        if 0 <= selected < len(self._rows):
            return self._rows[selected]
        return self._rows[0]

    def save_note(self) -> None:
        """Persist the inline note edit to the target row's mark."""
        target = self._target_row()
        if target is None:
            self.status_label.setText("No rows to annotate.")
            return
        try:
            audit_service.update_mark_note(
                self.conn,
                role=self.role,
                mark_id=target["error_id"],
                nota=self.note_edit.text() or None,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.status_label.setText("Nota actualizada.")
        self.apply_filters()
