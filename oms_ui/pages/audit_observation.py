"""AuditObservationPage — single-day audit grid (PRD F6).

PySide6 port of ``OLD/.../audit/pages/AuditObservationPage.jsx`` over the
Qt-free ``oms_core.services.audit`` service (ADR-03): an 8-hour selector, a
read-only grid of the flattened observation (click a cell to mark), the day's
marks list, mark/unmark/note/propose flows and the corrected-JSON export.

Applying a correction from this page proposes AND approves in one click (the
oracle's single "Aplicar Corrección" button created ``estado='aprobado'``
directly); the split propose-then-approve gate stays testable at the service
level (``oms_core.services.audit.propose_correction`` starts ``pendiente``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories.audit import MarkConflictError
from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_ui.widgets import StyledComboBox

#: Service failures the status line can present (never crash the page).
_UI_ERRORS = (audit_service.AuditError, MarkConflictError, OSError, sqlite3.Error)

#: Curated grid fields (datos + SYNOP groups + observer), Spanish labels.
FIELD_LABELS: dict[str, str] = {
    "observador": "Nombre del Observador",
    "ts": "Temperatura Seca (Ts)",
    "th": "Temperatura Húmeda (Th)",
    "pres_est": "Presión de la Estación",
    "p3": "Presión hace 3 horas (P3)",
    "p24": "Presión hace 24 horas (P24)",
    "t_max": "Temperatura Máxima (Tx)",
    "t_min": "Temperatura Mínima (Tn)",
    "t_max_24h": "Temp. Máxima 24h",
    "t_min_24h": "Temp. Mínima 24h",
    "ll": "Precipitación (Lluvia)",
    "ll_24h": "Precipitación 24h",
    "viento_dir": "Viento Dirección",
    "viento_vel": "Viento Velocidad",
    "visibilidad": "Visibilidad (VV)",
    "correc_alt": "Corrección por Altitud",
    "meteo_2_1": "YYGGiw (Grupo 2)",
    "meteo_4_irixhvv": "Ir iX H VV (Grupo 4)",
    "meteo_4_1": "N dd ff",
    "meteo_4_6": "7 ww W1 W2",
    "meteo_6_0": "8Nh CL CM CH",
    "meteo_6_2": "0CS DL DM DH",
    "meteo_6_3": "1sn Tx Tx Tx",
    "meteo_6_4": "2sn Tn Tn Tn",
    "meteo_8_0": "5n Fn Fn Fn",
    "meteo_8_1": "56 DL DM DH",
    "meteo_8_3": "6 RRR tr",
    "meteo_8_4": "7 R24 R24 R24 R24",
    "pres_nmm": "Presión NMM",
    "punto_rocio": "Punto de Rocío (Td)",
    "tension_vapor": "Tensión de Vapor (Tv)",
    "humedad_relativa": "Humedad Relativa (Hr)",
    "diferencia": "Diferencia (Ts - Th)",
}

#: Derived values render read-only (recomputed by the service on load).
READONLY_FIELDS = frozenset(
    {
        "pres_nmm",
        "punto_rocio",
        "tension_vapor",
        "humedad_relativa",
        "diferencia",
    }
)

ERROR_TYPES = ("Sintaxis", "Cálculo", "Consistencia", "Falta de datos", "Otro")


class MarkDialog(QDialog):
    """Mark / edit / remove an error mark plus its note."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Marcar error")
        layout = QFormLayout(self)
        self.title_label = QLabel("")
        layout.addRow(self.title_label)
        self.type_combo = StyledComboBox()
        self.type_combo.addItems(ERROR_TYPES)
        layout.addRow("Tipo de error", self.type_combo)
        self.note_edit = QTextEdit()
        layout.addRow("Nota", self.note_edit)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Guardar Marca")
        self.remove_button = QPushButton("Quitar Marca")
        self.remove_button.setEnabled(False)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.remove_button)
        layout.addRow(buttons)


class CorrectionDialog(QDialog):
    """Propose (+approve, one click like the oracle) a corrected value."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aplicar corrección")
        layout = QFormLayout(self)
        self.title_label = QLabel("")
        layout.addRow(self.title_label)
        self.original_label = QLabel("")
        layout.addRow("Valor original", self.original_label)
        self.value_edit = QLineEdit()
        layout.addRow("Valor corregido", self.value_edit)
        self.justification_edit = QTextEdit()
        layout.addRow("Justificación", self.justification_edit)
        box = QDialogButtonBox()
        self.save_button = QPushButton("Aplicar Corrección")
        box.addButton(self.save_button, QDialogButtonBox.AcceptRole)
        layout.addRow(box)


class AuditObservationPage(QWidget):
    """Hour grid with marks, mark/unmark/note/propose/export flows."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        base_dir: str | Path,
        station: str,
        fecha: str,
        role: str = "admin",
        user_email: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.base_dir = Path(base_dir)
        self.station = station
        self.fecha = fecha
        self.role = role
        self.user_email = user_email or "auditor@arca"
        self.denied = not access.can_access(role, "audit")

        self.active_hour = "06Z"
        self.selected_campo: str | None = None
        self._data: dict | None = None
        self.cells: dict[str, QLineEdit] = {}
        self.hour_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        if self.denied:
            layout.addWidget(
                QLabel("Acceso denegado: la auditoría requiere rol admin o control_calidad.")
            )
            self.marks_label = QLabel("")
            self.error_list = QListWidget()
            self.export_button = QPushButton("Export")
            self.to_correction_button = QPushButton("Correct")
            self.status_label = QLabel("")
            self.mark_dialog = MarkDialog(self)
            self.correction_dialog = CorrectionDialog(self)
            return

        header = QHBoxLayout()
        self.info_label = QLabel(f"Estación {station} — {fecha}")
        header.addWidget(self.info_label)
        self.export_button = QPushButton("Guardar Correcciones")
        self.export_button.clicked.connect(self.export_corrected)
        header.addWidget(self.export_button)
        layout.addLayout(header)

        hours_row = QHBoxLayout()
        for hora in audit_service.HOURS:
            button = QPushButton(hora)
            button.clicked.connect(lambda _=False, h=hora: self.set_hour(h))
            hours_row.addWidget(button)
            self.hour_buttons[hora] = button
        layout.addLayout(hours_row)

        self.marks_label = QLabel("")
        layout.addWidget(self.marks_label)

        self.grid = QGridLayout()
        layout.addLayout(self.grid)
        for row, (campo, label) in enumerate(FIELD_LABELS.items()):
            self.grid.addWidget(QLabel(label), row, 0)
            cell = QLineEdit()
            cell.setReadOnly(True)
            cell.setProperty("campo", campo)
            cell.mousePressEvent = lambda event, c=campo: self.select_cell(c)
            self.grid.addWidget(cell, row, 1)
            self.cells[campo] = cell

        actions = QHBoxLayout()
        self.to_correction_button = QPushButton("Aplicar Corrección")
        self.to_correction_button.clicked.connect(self.open_correction_dialog)
        actions.addWidget(self.to_correction_button)
        layout.addLayout(actions)

        self.error_list = QListWidget()
        layout.addWidget(QLabel("Marcas en este día"))
        layout.addWidget(self.error_list)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.mark_dialog = MarkDialog(self)
        self.mark_dialog.save_button.clicked.connect(self.save_mark)
        self.mark_dialog.remove_button.clicked.connect(self.remove_mark)
        self.correction_dialog = CorrectionDialog(self)
        self.correction_dialog.save_button.clicked.connect(self.save_correction)

        self.reload()

    # ------------------------------------------------------------------ data

    def reload(self) -> None:
        """Reload the flattened view + marks from the service."""
        try:
            self._data = audit_service.load_observation_with_audit(
                self.conn, self.station, self.fecha
            )
        except audit_service.AuditError as exc:
            self.status_label.setText(str(exc))
            return
        hours = [
            h
            for h in audit_service.HOURS
            if isinstance(self._data["observation"].get(h), dict)
            and any(k not in ("station_id", "observador") for k in self._data["observation"][h])
        ]
        for hora, button in self.hour_buttons.items():
            button.setEnabled(hora in hours)
        if self.active_hour not in hours and hours:
            self.active_hour = hours[0]
        self._refresh_grid()
        self._refresh_marks()

    def set_hour(self, hora: str) -> None:
        """Switch the grid to another synoptic hour."""
        if hora in self.hour_buttons and not self.hour_buttons[hora].isEnabled():
            return
        self.active_hour = hora
        self._refresh_grid()

    def _hour_view(self) -> dict:
        if self._data is None:
            return {}
        view = self._data["observation"].get(self.active_hour)
        return view if isinstance(view, dict) else {}

    def _marks_for(self, hora: str, campo: str) -> dict | None:
        if self._data is None:
            return None
        for mark in self._data["error_marks"]:
            if mark["hora"] == hora and mark["campo"] == campo:
                return mark
        return None

    def _correction_for(self, hora: str, campo: str) -> dict | None:
        if self._data is None:
            return None
        for corr in self._data["corrections"]:
            if corr["hora"] == hora and corr["campo"] == campo:
                return corr
        return None

    def _refresh_grid(self) -> None:
        view = self._hour_view()
        for campo, cell in self.cells.items():
            value = view.get(campo, "")
            cell.setText("" if value is None else str(value))
            mark = self._marks_for(self.active_hour, campo)
            corr = self._correction_for(self.active_hour, campo)
            if mark is not None:
                cell.setStyleSheet("border: 2px solid #dc2626; background: #fef2f2;")
                cell.setToolTip(f"Error: {mark['tipo_error']} ({mark['nota'] or 'sin nota'})")
            elif corr is not None:
                cell.setStyleSheet("border: 2px solid #059669; background: #ecfdf5;")
                cell.setToolTip(f"Corregido: {corr['valor_corregido']}")
            else:
                cell.setStyleSheet("")
                cell.setToolTip(FIELD_LABELS.get(campo, campo))

    def _refresh_marks(self) -> None:
        self.error_list.clear()
        if self._data is None:
            self.marks_label.setText("")
            return
        marks = self._data["error_marks"]
        by_hour: dict[str, int] = {}
        for mark in marks:
            by_hour[mark["hora"]] = by_hour.get(mark["hora"], 0) + 1
            self.error_list.addItem(f"{mark['hora']} — {mark['campo']}: {mark['tipo_error']}")
        summary = ", ".join(f"{hora}: {count} mark(s)" for hora, count in sorted(by_hour.items()))
        self.marks_label.setText(f"{len(marks)} mark(s) — {summary}" if summary else "0 mark(s)")
        observer = self._data["observation"].get("observador") or "Desconocido"
        self.info_label.setText(f"Estación {self.station} — {self.fecha} — Obs: {observer}")

    # ----------------------------------------------------------------- flows

    def select_cell(self, campo: str) -> None:
        """Open the mark dialog for a grid cell (hour = active hour)."""
        self.selected_campo = campo
        existing = self._marks_for(self.active_hour, campo)
        label = FIELD_LABELS.get(campo, campo)
        self.mark_dialog.title_label.setText(f"{self.active_hour} — {label}")
        if existing is not None:
            index = self.mark_dialog.type_combo.findText(existing["tipo_error"])
            self.mark_dialog.type_combo.setCurrentIndex(max(index, 0))
            self.mark_dialog.note_edit.setPlainText(existing["nota"] or "")
            self.mark_dialog.remove_button.setEnabled(True)
        else:
            self.mark_dialog.type_combo.setCurrentIndex(0)
            self.mark_dialog.note_edit.setPlainText("")
            self.mark_dialog.remove_button.setEnabled(False)
        self.mark_dialog.show()

    def save_mark(self) -> None:
        """Create the error mark for the selected cell (oracle: mark_error)."""
        if self.selected_campo is None:
            return
        try:
            audit_service.mark_error(
                self.conn,
                role=self.role,
                station_id=self.station,
                fecha=self.fecha,
                hora=self.active_hour,
                campo=self.selected_campo,
                tipo_error=self.mark_dialog.type_combo.currentText(),
                nota=self.mark_dialog.note_edit.toPlainText() or None,
                marcado_por=self.user_email,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.mark_dialog.hide()
        self.status_label.setText("Error marcado correctamente.")
        self.reload()

    def remove_mark(self) -> None:
        """Drop the selected cell mark and its slot corrections (oracle cascade)."""
        if self.selected_campo is None:
            return
        existing = self._marks_for(self.active_hour, self.selected_campo)
        if existing is None or existing.get("id") is None:
            return
        try:
            audit_service.unmark_error(self.conn, role=self.role, mark_id=existing["id"])
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.mark_dialog.hide()
        self.status_label.setText("Marca de error eliminada.")
        self.reload()

    def open_correction_dialog(self) -> None:
        """Prefill the correction dialog for the selected cell."""
        if self.selected_campo is None:
            return
        view = self._hour_view()
        current = view.get(self.selected_campo, "")
        existing = self._correction_for(self.active_hour, self.selected_campo)
        label = FIELD_LABELS.get(self.selected_campo, self.selected_campo)
        self.correction_dialog.title_label.setText(f"{self.active_hour} — {label}")
        self.correction_dialog.original_label.setText("" if current is None else str(current))
        self.correction_dialog.value_edit.setText(
            existing["valor_corregido"] if existing else ("" if current is None else str(current))
        )
        self.correction_dialog.justification_edit.setPlainText(
            existing["justificacion"] if existing else ""
        )
        self.mark_dialog.hide()
        self.correction_dialog.show()

    def save_correction(self) -> None:
        """Propose + approve the corrected value in one click (oracle parity)."""
        if self.selected_campo is None:
            return
        view = self._hour_view()
        current = view.get(self.selected_campo, "")
        try:
            corr = audit_service.propose_correction(
                self.conn,
                role=self.role,
                station_id=self.station,
                fecha=self.fecha,
                hora=self.active_hour,
                campo=self.selected_campo,
                valor_original="" if current is None else str(current),
                valor_corregido=self.correction_dialog.value_edit.text(),
                justificacion=self.correction_dialog.justification_edit.toPlainText(),
                corregido_por=self.user_email,
            )
            audit_service.approve_correction(
                self.conn,
                role=self.role,
                correction_id=corr["id"],
                aprobado_por=self.user_email,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.correction_dialog.hide()
        self.status_label.setText("Corrección aplicada (overlay activo).")
        self.reload()

    def export_corrected(self) -> None:
        """Write the corrected copy next to the original (never overwrites)."""
        try:
            path = audit_service.export_corrected_json(
                self.conn,
                self.base_dir,
                self.station,
                self.fecha,
                role=self.role,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.status_label.setText(f"Exported: {path}")
