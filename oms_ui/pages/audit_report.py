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
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
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

#: The report's first table: the OWNER's sheet — who made the mistakes, how
#: many, and the two rates that make the numbers comparable (spec S3).
OBSERVER_HEADERS = (
    "Observador", "Errores", "Horas auditadas", "Tasa por observación",
    "Campos auditados", "Tasa por campos (%)", "Tipos", "Grupos",
)
DETAIL_HEADERS = (
    "Estación", "Fecha / Hora", "Observador", "Campo", "Grupo",
    "Tipo de Error", "Datos Orig. → Corr.", "Nota",
)
PERSON_HEADERS = (
    "Usuario/Auditor", "Errores Marcados", "Correcciones Propuestas",
    "Correcciones Aprobadas",
)


def _table(headers: tuple[str, ...]) -> QTableWidget:
    """A read-only table with the report's standard look."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    header.setMinimumSectionSize(80)
    table.verticalHeader().setDefaultSectionSize(26)
    return table


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
        self._observers: list[dict] = []

        self.setObjectName("auditReport")
        self.setStyleSheet(
            "QWidget#auditReport { background: #f8fafc; }"
            "QFrame#reportCard { background: #ffffff; border: 1px solid #e2e8f0;"
            " border-radius: 14px; }"
            "QLabel#reportTitle { color: #0f172a; font-size: 22px;"
            " font-weight: 900; }"
            "QLabel#reportSubtitle { color: #64748b; font-size: 12px; }"
            "QLabel#reportLabel { color: #475569; font-size: 11px;"
            " font-weight: 700; }"
            "QPushButton#reportPrimary { background: #f97316; color: #ffffff;"
            " border: none; border-radius: 9px; padding: 8px 16px;"
            " font-weight: 700; }"
            "QPushButton#reportGhost { background: #ffffff; color: #334155;"
            " border: 1px solid #cbd5e1; border-radius: 9px;"
            " padding: 7px 14px; }"
        )
        layout = QVBoxLayout(self)
        if self.denied:
            layout.addWidget(
                QLabel("Acceso denegado: la auditoría requiere rol admin o control_calidad.")
            )
            self._denied_widgets()
            return

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("Reporte General de Errores")
        title.setObjectName("reportTitle")
        subtitle = QLabel(
            "Detalle de inconsistencias, resumen por persona y conteo por observador"
        )
        subtitle.setObjectName("reportSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        layout.addLayout(header)

        filters_card = QFrame()
        filters_card.setObjectName("reportCard")
        filters = QHBoxLayout(filters_card)
        filters.setContentsMargins(12, 10, 12, 10)
        self.station_filter = QLineEdit()
        self.station_filter.setPlaceholderText("Código de estación (opcional)")
        self.year_filter = QLineEdit()
        self.year_filter.setPlaceholderText("AAAA")
        self.month_filter = StyledComboBox()
        self.month_filter.addItem("(Todos)", "")
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
        self.filter_button.setObjectName("reportPrimary")
        filters.addWidget(self.filter_button)
        layout.addWidget(filters_card)

        notes_card = QFrame()
        notes_card.setObjectName("reportCard")
        notes_box = QVBoxLayout(notes_card)
        notes_box.setContentsMargins(12, 10, 12, 10)
        notes_label = QLabel("Notas Generales del Reporte")
        notes_label.setObjectName("reportLabel")
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Notas generales del reporte (salen en el PDF)"
        )
        self.notes_edit.setMaximumHeight(60)
        notes_box.addWidget(notes_label)
        notes_box.addWidget(self.notes_edit)
        layout.addWidget(notes_card)

        self.tabs = QTabWidget()
        self.observer_table = _table(OBSERVER_HEADERS)
        self.detail_table = _table(DETAIL_HEADERS)
        self.person_table = _table(PERSON_HEADERS)
        self.tabs.addTab(self.observer_table, "Por observador")
        self.tabs.addTab(self.detail_table, "Detalle de Inconsistencias")
        self.tabs.addTab(self.person_table, "Resumen por Persona")
        self.tabs.setStyleSheet(
            "QTabBar::tab { background: #ffffff; color: #475569;"
            " border: 1px solid #e2e8f0; border-bottom: none;"
            " border-top-left-radius: 9px; border-top-right-radius: 9px;"
            " padding: 8px 18px; margin-right: 4px; font-weight: 700; }"
            "QTabBar::tab:selected { background: #f97316; color: #ffffff;"
            " border-color: #f97316; }"
            "QTabWidget::pane { border: none; background: #f8fafc; }"
        )
        layout.addWidget(self.tabs, 1)

        export_row = QHBoxLayout()
        self.pdf_button = QPushButton("Exportar PDF")
        self.pdf_button.setObjectName("reportPrimary")
        self.pdf_button.clicked.connect(lambda: self.export_pdf())
        export_row.addStretch(1)
        export_row.addWidget(self.pdf_button)
        layout.addLayout(export_row)

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel("Nota de la fila"))
        self.note_edit = QLineEdit()
        self.note_save_button = QPushButton("Guardar Nota")
        self.note_save_button.setObjectName("reportGhost")
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
        self.observer_table = QTableWidget(0, len(OBSERVER_HEADERS))
        self.detail_table = QTableWidget(0, len(DETAIL_HEADERS))
        self.person_table = QTableWidget(0, len(PERSON_HEADERS))
        self.note_edit = QLineEdit()
        self.note_save_button = QPushButton("Guardar Nota")
        self.note_save_button.setObjectName("reportGhost")
        self.pdf_button = QPushButton("Exportar PDF")
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
            observers = audit_service.get_observer_summary(self.conn, **filters)
            summary = audit_service.get_person_summary(self.conn, **filters)
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self._observers = observers
        self._fill_observers(observers)
        self.detail_table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            cells = (
                row["station_id"],
                f"{row['fecha']} · {row['hora']}",
                row["observador"],
                row["campo"],
                row["grupo"],
                row["tipo_error"],
                f"{row['valor_original'] or ''} → {row['valor_corregido'] or ''}",
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
        self.status_label.setText(
            f"{len(observers)} observadores · {len(self._rows)} marcas"
        )

    def _fill_observers(self, observers: list[dict]) -> None:
        """The owner's sheet: errors per observer plus the two rates."""
        self.observer_table.setRowCount(len(observers) + (1 if observers else 0))
        totals = {"errores": 0, "horas": 0, "campos": 0}
        for row_idx, row in enumerate(observers):
            totals["errores"] += row["errores"]
            totals["horas"] += row["horas_auditadas"]
            totals["campos"] += row["campos_auditados"]
            cells = (
                row["persona"],
                str(row["errores"]),
                str(row["horas_auditadas"]),
                f"{row['tasa_por_observacion']:.2f}",
                str(row["campos_auditados"]),
                f"{row['tasa_por_campos']:.2f}",
                ", ".join(
                    f"{tipo} {count}"
                    for tipo, count in sorted(row["por_tipo"].items())
                ),
                ", ".join(
                    f"{grupo} {count}"
                    for grupo, count in sorted(row["por_grupo"].items())
                ),
            )
            for col_idx, value in enumerate(cells):
                self.observer_table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        if not observers:
            return
        # total row: the report has to add up when it is published
        rate_hours = totals["errores"] / totals["horas"] if totals["horas"] else 0.0
        rate_fields = (
            100 * totals["errores"] / totals["campos"] if totals["campos"] else 0.0
        )
        totals_cells = (
            "TOTAL", str(totals["errores"]), str(totals["horas"]),
            f"{rate_hours:.2f}", str(totals["campos"]), f"{rate_fields:.2f}", "", "",
        )
        last = len(observers)
        for col_idx, value in enumerate(totals_cells):
            item = QTableWidgetItem(value)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.observer_table.setItem(last, col_idx, item)

    # ---------------------------------------------------------------- PDF

    def _report_html(self) -> str:
        """The published sheet as HTML (what the PDF prints)."""
        filters = self._current_filters()
        period = " · ".join(
            part
            for part in (
                f"Estación {filters['station_id']}" if filters["station_id"] else "Todas las estaciones",
                filters["year"] or "todos los años",
                audit_service.MONTH_NAMES.get(filters["month"], "todos los meses")
                if filters["month"] else "todos los meses",
            )
            if part
        )
        rows = "".join(
            "<tr>"
            f"<td>{row['persona']}</td>"
            f"<td align='right'>{row['errores']}</td>"
            f"<td align='right'>{row['horas_auditadas']}</td>"
            f"<td align='right'>{row['tasa_por_observacion']:.2f}</td>"
            f"<td align='right'>{row['campos_auditados']}</td>"
            f"<td align='right'>{row['tasa_por_campos']:.2f}</td>"
            "</tr>"
            for row in self._observers
        )
        total_errors = sum(row["errores"] for row in self._observers)
        total_hours = sum(row["horas_auditadas"] for row in self._observers)
        total_fields = sum(row["campos_auditados"] for row in self._observers)
        rate_hours = total_errors / total_hours if total_hours else 0.0
        rate_fields = 100 * total_errors / total_fields if total_fields else 0.0
        notes = self.notes_edit.toPlainText().strip()
        notes_html = f"<p><b>Notas generales:</b> {notes}</p>" if notes else ""
        return f"""
        <h1 style="font-size:16pt;">OMS · Reporte de errores por observador</h1>
        <p style="color:#475569;">{period}</p>
        <table border="1" cellspacing="0" cellpadding="5" width="100%">
          <thead>
            <tr style="background:#e2e8f0;">
              <th align="left">Observador</th><th>Errores</th>
              <th>Horas auditadas</th><th>Tasa por observación</th>
              <th>Campos auditados</th><th>Tasa por campos (%)</th>
            </tr>
          </thead>
          <tbody>
            {rows or "<tr><td colspan='6'>Sin observaciones auditadas en el período.</td></tr>"}
            <tr style="font-weight:bold; background:#f1f5f9;">
              <td>TOTAL</td>
              <td align="right">{total_errors}</td>
              <td align="right">{total_hours}</td>
              <td align="right">{rate_hours:.2f}</td>
              <td align="right">{total_fields}</td>
              <td align="right">{rate_fields:.2f}</td>
            </tr>
          </tbody>
        </table>
        {notes_html}
        <p style="color:#94a3b8; font-size:9pt;">
          Generado el {audit_service._now_local()} · cada error se atribuye al
          observador de su hora
        </p>
        """

    def export_pdf(self, path: str | None = None) -> str:
        """Write the report to a real PDF (Qt, no extra dependency)."""
        from PySide6.QtCore import QMarginsF, QSizeF
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

        if not path:
            path, _filter = QFileDialog.getSaveFileName(
                self, "Exportar reporte", "reporte_errores.pdf", "PDF (*.pdf)"
            )
            if not path:
                return ""
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        writer = QPdfWriter(path)
        writer.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Landscape,
                QMarginsF(15, 15, 15, 15),
                QPageLayout.Unit.Millimeter,
            )
        )
        writer.setResolution(150)
        document = QTextDocument()
        document.setPageSize(QSizeF(writer.width(), writer.height()))
        document.setHtml(self._report_html())
        document.print_(writer)
        self.status_label.setText(f"PDF generado: {path}")
        return path

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
            self.status_label.setText("No hay marcas para anotar.")
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
