"""AuditObservationPage — single-day audit sheet (PRD F6, owner round 26).

PySide6 port of ``OLD/.../audit/pages/AuditObservationPage.jsx`` over the
Qt-free ``oms_core.services.audit`` service (ADR-03). The owner's complaint was
exact: the grid existed but could not be read — it was a bare list of labels
with no sections, no colours and no visible marks. It is now a mirror of the
observation form:

* sections as cards, in the observation's own order, each with its accent
  colour (presión, tendencia, temperatura, humedad, viento, visibilidad,
  tiempo presente, identificación, nubosidad, precipitación, evaporación,
  suelo y nieve, observador);
* every hour as a tab with a state dot: red when it carries marks, green when
  it only carries corrections, grey when it is clean, dimmed when it has no
  data;
* a marked cell is red with the error type in its tooltip, a corrected one is
  green; a click opens the mark dialog;
* a side panel with the audit counters, the day's marks and the closure
  (Terminar / Reabrir auditoría).

Performance note: the page carries ONE stylesheet and every cell changes a
dynamic property (``state``) instead of receiving its own ``setStyleSheet``.
Per-widget stylesheets are the single most expensive thing in these views
(~48% of a CLI view build, measured), so the audit sheet must not repeat it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories.audit import MarkConflictError
from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_core.services import document_map as dm
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
    "tend_car": "Tendencia C.A.R",
    "tend_dif": "Diferencia de Tendencia (Dif)",
    "pres_nmm": "Presión NMM",
    "punto_rocio": "Punto de Rocío (Td)",
    "tension_vapor": "Tensión de Vapor (Tv)",
    "humedad_relativa": "Humedad Relativa (Hr)",
    "diferencia": "Diferencia (Ts - Th)",
}

#: Spanish section titles, in the order the observation itself is laid out.
SECTION_TITLES: dict[str, str] = {
    "presión": "PRESIÓN",
    "tendencia": "TENDENCIA",
    "temperatura": "TEMPERATURA",
    "humedad": "HUMEDAD",
    "viento": "VIENTO",
    "nubosidad": "NUBOSIDAD",
    "visibilidad": "VISIBILIDAD",
    "tiempo presente": "TIEMPO PRESENTE",
    "identificación": "IDENTIFICACIÓN",
    "precipitación": "PRECIPITACIÓN",
    "evaporación": "EVAPORACIÓN",
    "suelo y nieve": "SUELO Y NIEVE",
    "observador": "OBSERVADOR",
    "otro": "OTROS",
}

#: Accent of each section header (same family as the observation sheet).
SECTION_COLORS: dict[str, str] = {
    "presión": "#1e293b",
    "tendencia": "#1d4ed8",
    "temperatura": "#b91c1c",
    "humedad": "#0e7490",
    "viento": "#0f766e",
    "nubosidad": "#4b5563",
    "visibilidad": "#7c3aed",
    "tiempo presente": "#c2410c",
    "identificación": "#334155",
    "precipitación": "#1d4ed8",
    "evaporación": "#0e7490",
    "suelo y nieve": "#713f12",
    "observador": "#475569",
    "otro": "#64748b",
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

_PAGE_QSS = """
QWidget#auditPage { background: #f8fafc; }
QFrame#auditCard { background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 10px; }
QLabel#panelTitle { color: #475569; font-weight: 800; font-size: 11px;
    letter-spacing: 1px; background: transparent; }
QLabel#fieldLabel { color: #334155; font-size: 12px; background: transparent; }
QLabel#panelValue { color: #0f172a; font-size: 20px; font-weight: 800;
    background: transparent; }
QLineEdit[state="plain"] { background: #ffffff; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 3px 6px; color: #0f172a; }
QLineEdit[state="mark"] { background: #fef2f2; border: 2px solid #dc2626;
    border-radius: 6px; padding: 2px 5px; color: #991b1b; font-weight: 700; }
QLineEdit[state="fixed"] { background: #ecfdf5; border: 2px solid #059669;
    border-radius: 6px; padding: 2px 5px; color: #065f46; font-weight: 600; }
QPushButton[hour="true"] { background: #f1f5f9; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 5px 10px; color: #334155; font-weight: 600; }
QPushButton[hour="true"][active="true"] { background: #1e293b; color: #f8fafc;
    border-color: #1e293b; }
QPushButton[hour="true"]:disabled { color: #cbd5e1; border-color: #e2e8f0;
    background: #f8fafc; }
QPushButton#primary { background: #1e293b; color: #f8fafc; border: none;
    border-radius: 8px; padding: 7px 16px; font-weight: 700; }
QPushButton#ghost { background: #ffffff; color: #334155;
    border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 14px; }
QListWidget { background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 8px; }
"""


def _repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


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
        self.group_label = QLabel("")
        layout.addRow("Grupo del dato", self.group_label)
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
        self.corrector_edit = QLineEdit()
        self.corrector_edit.setPlaceholderText("Quién corrige (corrector)")
        layout.addRow("Corrector", self.corrector_edit)
        self.justification_edit = QTextEdit()
        layout.addRow("Justificación", self.justification_edit)
        box = QDialogButtonBox()
        self.save_button = QPushButton("Aplicar Corrección")
        box.addButton(self.save_button, QDialogButtonBox.AcceptRole)
        layout.addRow(box)


ERROR_TYPES = audit_service.ERROR_TYPES


def cli_reference_html(conn: sqlite3.Connection, station: str, fecha: str,
                       module: str) -> str:
    """The stored CLI sheet as an HTML table (read-only reference view).

    The oracle put a "Ver CLI 3074/4074/5074" button next to the grid so the
    auditor could compare the observation with the instrumental sheets without
    leaving the page.
    """
    from oms_core.services import cli as cli_service

    block = cli_service.load_cli(conn, station, fecha, f"cli{module}")
    if not isinstance(block, dict) or not block:
        return "<p style='color:#64748b;'>Sin datos guardados para este CLI.</p>"
    rows = block.get("horas") if isinstance(block.get("horas"), dict) else block
    if not isinstance(rows, dict):
        return "<p style='color:#64748b;'>Formato de CLI no reconocido.</p>"
    columns: list[str] = []
    for row in rows.values():
        if isinstance(row, dict):
            for key, value in row.items():
                if value not in ("", None, False) and key not in columns:
                    columns.append(key)
    if not columns:
        return "<p style='color:#64748b;'>Sin datos guardados para este CLI.</p>"
    header = "".join(f"<th align='left'>{col}</th>" for col in columns)
    body = []
    for row_key in sorted(rows, key=lambda k: int(k) if str(k).isdigit() else 0):
        row = rows[row_key]
        if not isinstance(row, dict):
            continue
        cells = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, dict):
                value = ", ".join(f"{k}" for k, v in value.items() if v)
            cells.append(f"<td>{'' if value in (None, False) else value}</td>")
        body.append(f"<tr><td><b>{row_key}</b></td>{''.join(cells)}</tr>")
    return (
        "<table border='1' cellspacing='0' cellpadding='4' width='100%'>"
        f"<thead><tr><th>Fila</th>{header}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


class CliPeekDialog(QDialog):
    """Read-only view of a stored CLI sheet."""

    def __init__(self, conn: sqlite3.Connection, station: str, fecha: str,
                 module: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"CLI {module} — {station} · {fecha}")
        self.resize(760, 520)
        box = QVBoxLayout(self)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setHtml(cli_reference_html(conn, station, fecha, module))
        box.addWidget(viewer)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        box.addWidget(close)


def sections() -> list[tuple[str, str, list[str]]]:
    """``(group, title, fields)`` in the observation's own order.

    Every field the window can mark appears exactly once, which is what keeps
    the grid and the report's field list from drifting apart.
    """
    grouped: dict[str, list[str]] = {}
    for campo in FIELD_LABELS:
        grouped.setdefault(dm.group_for_field(campo), []).append(campo)
    ordered: list[tuple[str, str, list[str]]] = []
    for group in dm.GROUP_ORDER:
        if group in grouped:
            ordered.append(
                (group, SECTION_TITLES.get(group, group.upper()), grouped[group])
            )
    return ordered


class AuditObservationPage(QWidget):
    """Sectioned sheet with marks, mark/unmark/correct/export and closure."""

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
        self.hour_dots: dict[str, QLabel] = {}
        self.section_frames: dict[str, QFrame] = {}

        self.setObjectName("auditPage")
        self.setStyleSheet(_PAGE_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        if self.denied:
            layout.addWidget(
                QLabel("Acceso denegado: la auditoría requiere rol admin o control_calidad.")
            )
            self._denied_widgets()
            return

        self._build_header(layout)
        self._build_hours(layout)
        self._build_body(layout)
        self.observer_banner = QLabel("")
        self.observer_banner.setStyleSheet(
            "background: #fef2f2; color: #991b1b; border: 1px solid #fecaca;"
            "border-radius: 8px; padding: 6px 10px; font-weight: 700;"
        )
        self.observer_banner.setVisible(False)
        layout.addWidget(self.observer_banner)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #64748b; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.mark_dialog = MarkDialog(self)
        self.mark_dialog.save_button.clicked.connect(self.save_mark)
        self.mark_dialog.remove_button.clicked.connect(self.remove_mark)
        self.correction_dialog = CorrectionDialog(self)
        self.correction_dialog.save_button.clicked.connect(self.save_correction)

        self.reload()

    # ---------------------------------------------------------------- layout

    def _denied_widgets(self) -> None:
        """Inert placeholders so callers can rely on the attributes."""
        self.back_button = QPushButton()
        self.close_button = QPushButton()
        self.state_label = QLabel("")
        self.marks_label = QLabel("")
        self.error_list = QListWidget()
        self.export_button = QPushButton()
        self.to_correction_button = QPushButton()
        self.status_label = QLabel("")
        self.correction_dialog = CorrectionDialog(self)
        self.mark_dialog = MarkDialog(self)

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        self.back_button = QPushButton("← Sinóptico")
        self.back_button.setObjectName("ghost")
        header.addWidget(self.back_button)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.info_label = QLabel(f"Estación {self.station} · {self.fecha}")
        self.info_label.setStyleSheet(
            "color: #0f172a; font-size: 17px; font-weight: 800;"
        )
        self.marks_label = QLabel("")
        self.marks_label.setStyleSheet("color: #64748b; font-size: 12px;")
        titles.addWidget(self.info_label)
        titles.addWidget(self.marks_label)
        header.addLayout(titles, 1)

        self.state_label = QLabel("")
        self.state_label.setStyleSheet("color: #475569; font-size: 12px;")
        self.close_button = QPushButton("Terminar auditoría")
        self.close_button.setObjectName("ghost")
        self.close_button.clicked.connect(self.toggle_audit_day)
        header.addWidget(self.state_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

    def _build_hours(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.setSpacing(6)
        for hora in audit_service.HOURS:
            column = QVBoxLayout()
            column.setSpacing(2)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                "background: #e2e8f0; border-radius: 5px;"
            )
            dot_wrap = QHBoxLayout()
            dot_wrap.addStretch(1)
            dot_wrap.addWidget(dot)
            dot_wrap.addStretch(1)
            column.addLayout(dot_wrap)
            button = QPushButton(hora)
            button.setProperty("hour", "true")
            button.clicked.connect(lambda _=False, h=hora: self.set_hour(h))
            column.addWidget(button)
            self.hour_buttons[hora] = button
            self.hour_dots[hora] = dot
            row.addLayout(column)
        layout.addLayout(row)

    def _build_body(self, layout: QVBoxLayout) -> None:
        body = QHBoxLayout()
        body.setSpacing(12)

        # Two independent columns (like the observation sheet): a grid would
        # stretch every row to the tallest card and leave big empty gaps.
        grid_host = QWidget()
        columns = QHBoxLayout(grid_host)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(10)
        left = QVBoxLayout()
        right = QVBoxLayout()
        for side in (left, right):
            side.setSpacing(10)
        for index, (group, title, fields) in enumerate(sections()):
            card = self._section_card(group, title, fields)
            (left if index % 2 == 0 else right).addWidget(card)
        left.addStretch(1)
        right.addStretch(1)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(grid_host)
        body.addWidget(scroll, 1)
        body.addWidget(self._panel(), 0)
        layout.addLayout(body, 1)

    def _section_card(self, group: str, title: str, fields: list[str]) -> QFrame:
        card = QFrame()
        card.setObjectName("auditCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        box = QVBoxLayout(card)
        box.setContentsMargins(10, 8, 10, 10)
        box.setSpacing(6)
        header = QLabel(title)
        header.setFixedHeight(22)
        header.setStyleSheet(
            f"background: {SECTION_COLORS.get(group, '#334155')}; color: #f8fafc;"
            "border-radius: 6px; padding: 0 8px; font-size: 11px;"
            "font-weight: 800; letter-spacing: 1px;"
        )
        box.addWidget(header)
        for campo in fields:
            line = QHBoxLayout()
            line.setSpacing(6)
            label = QLabel(FIELD_LABELS[campo])
            label.setObjectName("fieldLabel")
            label.setMinimumWidth(150)
            cell = QLineEdit()
            cell.setReadOnly(campo not in READONLY_FIELDS)
            cell.setProperty("state", "plain")
            cell.setMinimumHeight(26)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setProperty("campo", campo)
            cell.mousePressEvent = lambda event, c=campo: self.select_cell(c)
            line.addWidget(label, 0)
            line.addWidget(cell, 1)
            box.addLayout(line)
            self.cells[campo] = cell
        self.section_frames[group] = card
        return card

    def _panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("auditCard")
        panel.setFixedWidth(300)
        box = QVBoxLayout(panel)
        box.setContentsMargins(12, 10, 12, 12)
        box.setSpacing(8)

        title = QLabel("ESTADO DE AUDITORÍA")
        title.setObjectName("panelTitle")
        box.addWidget(title)

        counters = QHBoxLayout()
        self.marks_value = QLabel("0")
        self.corrections_value = QLabel("0")
        for caption, value in (("ERRORES", self.marks_value), ("CORRECCIONES", self.corrections_value)):
            column = QVBoxLayout()
            value.setObjectName("panelValue")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(caption)
            label.setObjectName("panelTitle")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(value)
            column.addWidget(label)
            counters.addLayout(column)
        box.addLayout(counters)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        self.cli_dialog: CliPeekDialog | None = None
        self.to_correction_button = QPushButton("Aplicar Corrección")
        self.to_correction_button.setObjectName("primary")
        self.to_correction_button.clicked.connect(self.open_correction_dialog)
        self.export_button = QPushButton("Guardar Correcciones")
        self.export_button.setObjectName("ghost")
        self.export_button.clicked.connect(self.export_corrected)
        actions.addWidget(self.to_correction_button)
        actions.addWidget(self.export_button)
        box.addLayout(actions)

        marks_title = QLabel("MARCAS EN ESTE DÍA")
        marks_title.setObjectName("panelTitle")
        box.addWidget(marks_title)
        self.error_list = QListWidget()
        self.error_list.currentRowChanged.connect(self._on_mark_selected)
        box.addWidget(self.error_list, 1)
        remove_row = QPushButton("Quitar marca seleccionada")
        remove_row.setObjectName("ghost")
        remove_row.clicked.connect(self.remove_selected_mark)
        box.addWidget(remove_row)
        cli_row = QHBoxLayout()
        self.cli_buttons: dict[str, QPushButton] = {}
        for module in ("3074", "4074", "5074"):
            button = QPushButton(f"Ver {module}")
            button.setObjectName("ghost")
            button.clicked.connect(
                lambda _=False, m=module: self.show_cli_reference(m)
            )
            cli_row.addWidget(button)
            self.cli_buttons[module] = button
        box.addLayout(cli_row)

        note_title = QLabel("NOTA DE LA MARCA")
        note_title.setObjectName("panelTitle")
        box.addWidget(note_title)
        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(64)
        self.note_edit.setPlaceholderText("Nota para la marca seleccionada")
        box.addWidget(self.note_edit)
        self.note_button = QPushButton("Guardar Nota")
        self.note_button.setObjectName("ghost")
        self.note_button.clicked.connect(self.save_note)
        box.addWidget(self.note_button)
        return panel

    # ------------------------------------------------------------------ data

    def reload(self) -> None:
        """Reload the flattened view + marks from the service."""
        # the closure state is database-only, so it paints even when the day
        # file is missing from the archive (the grid below cannot load then)
        self._refresh_audit_state()
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
            and any(
                k not in ("station_id", "observador")
                for k in self._data["observation"][h]
            )
        ]
        for hora, button in self.hour_buttons.items():
            button.setEnabled(hora in hours)
        if self.active_hour not in hours and hours:
            self.active_hour = hours[0]
        self._refresh_grid()
        self._refresh_marks()

    def set_hour(self, hora: str) -> None:
        """Switch the sheet to another synoptic hour."""
        if hora in self.hour_buttons and not self.hour_buttons[hora].isEnabled():
            return
        self.active_hour = hora
        self._refresh_grid()
        self._refresh_hour_buttons()

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
                state, tip = "mark", f"Error: {mark['tipo_error']}"
                if mark.get("nota"):
                    tip += f" — {mark['nota']}"
            elif corr is not None:
                state = "fixed"
                tip = f"Corregido: {corr['valor_corregido']}"
            else:
                state, tip = "plain", FIELD_LABELS.get(campo, campo)
            cell.setProperty("state", state)
            cell.setToolTip(tip)
            _repolish(cell)
        self._refresh_hour_buttons()
        self._select_hour_button()
        self._refresh_observer_banner()

    def _refresh_observer_banner(self) -> None:
        """Red banner when the hour has data but nobody signed it (oracle)."""
        view = self._hour_view()
        has_data = any(
            key not in ("station_id", "observador", "nombre_observador")
            and value not in ("", None)
            for key, value in view.items()
        )
        observer = str(view.get("observador") or "").strip()
        missing = has_data and not observer
        self.observer_banner.setText(
            "⚠ Observador no identificado: marcar el nombre de la hora."
        )
        self.observer_banner.setVisible(missing)

    def _refresh_hour_buttons(self) -> None:
        """A dot per hour: red with marks, green only corrected, grey clean."""
        for hora, dot in self.hour_dots.items():
            marks = 0
            corrections = 0
            if self._data is not None:
                marks = sum(1 for m in self._data["error_marks"] if m["hora"] == hora)
                corrections = sum(
                    1 for c in self._data["corrections"] if c["hora"] == hora
                )
            if marks:
                color = "#dc2626"
            elif corrections:
                color = "#059669"
            else:
                color = "#cbd5e1"
            dot.setStyleSheet(f"background: {color}; border-radius: 5px;")

    def _select_hour_button(self) -> None:
        for hora, button in self.hour_buttons.items():
            button.setProperty("active", "true" if hora == self.active_hour else None)
            _repolish(button)

    def _refresh_marks(self) -> None:
        self.error_list.clear()
        if self._data is None:
            self.marks_label.setText("")
            return
        marks = self._data["error_marks"]
        corrections = self._data["corrections"]
        for mark in marks:
            group = dm.group_for_field(mark["campo"])
            self.error_list.addItem(
                f"{mark['hora']} · {FIELD_LABELS.get(mark['campo'], mark['campo'])}"
                f" — {mark['tipo_error']} ({group})"
            )
        self.marks_value.setText(str(len(marks)))
        self.corrections_value.setText(str(len(corrections)))
        hour_view = self._hour_view()
        observer = (
            str(hour_view.get("observador") or "")
            or str(self._data["observation"].get("observador") or "")
            or "Desconocido"
        )
        self.info_label.setText(
            f"Estación {self.station} · {self.fecha} · Obs: {observer}"
        )
        by_hour: dict[str, int] = {}
        for mark in marks:
            by_hour[mark["hora"]] = by_hour.get(mark["hora"], 0) + 1
        if marks:
            detail = ", ".join(
                f"{hora}: {count}" for hora, count in sorted(by_hour.items())
            )
            self.marks_label.setText(
                f"{len(marks)} error(es) marcados · {detail}"
            )
        else:
            self.marks_label.setText("Sin errores marcados en este día")

    # ----------------------------------------------------------------- flows

    def select_cell(self, campo: str) -> None:
        """Open the mark dialog for one cell (or edit its existing mark)."""
        self.selected_campo = campo
        mark = self._marks_for(self.active_hour, campo)
        dialog = self.mark_dialog
        dialog.title_label.setText(
            f"{self.active_hour} · {FIELD_LABELS.get(campo, campo)}"
        )
        dialog.group_label.setText(dm.group_for_field(campo))
        if mark is not None:
            index = dialog.type_combo.findText(mark["tipo_error"])
            if index >= 0:
                dialog.type_combo.setCurrentIndex(index)
            dialog.note_edit.setPlainText(mark.get("nota") or "")
            dialog.remove_button.setEnabled(True)
        else:
            dialog.type_combo.setCurrentIndex(0)
            dialog.note_edit.setPlainText("")
            dialog.remove_button.setEnabled(False)
        dialog.show()

    def open_correction_dialog(self) -> None:
        campo = self.selected_campo
        if campo is None:
            self.status_label.setText("Elegí una celda primero.")
            return
        dialog = self.correction_dialog
        dialog.title_label.setText(
            f"{self.active_hour} · {FIELD_LABELS.get(campo, campo)}"
        )
        current = self._hour_view().get(campo, "")
        existing = self._correction_for(self.active_hour, campo)
        dialog.original_label.setText("" if current is None else str(current))
        dialog.value_edit.setText(
            existing["valor_corregido"] if existing else
            ("" if current is None else str(current))
        )
        dialog.justification_edit.setPlainText(
            existing["justificacion"] if existing else ""
        )
        dialog.show()

    def save_mark(self) -> None:
        campo = self.selected_campo
        if campo is None:
            return
        try:
            audit_service.mark_error(
                self.conn,
                role=self.role,
                station_id=self.station,
                fecha=self.fecha,
                hora=self.active_hour,
                campo=campo,
                tipo_error=self.mark_dialog.type_combo.currentText(),
                marcado_por=self.user_email,
                nota=self.mark_dialog.note_edit.toPlainText() or None,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.mark_dialog.accept()
        self.status_label.setText("Marca guardada.")
        self.reload()

    def remove_mark(self) -> None:
        campo = self.selected_campo
        mark = None if campo is None else self._marks_for(self.active_hour, campo)
        if mark is None:
            return
        try:
            audit_service.unmark_error(
                self.conn, role=self.role, mark_id=mark["id"]
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.mark_dialog.accept()
        self.status_label.setText("Marca quitada.")
        self.reload()

    def save_note(self) -> None:
        campo = self.selected_campo
        mark = None if campo is None else self._marks_for(self.active_hour, campo)
        if mark is None:
            self.status_label.setText("Elegí una celda marcada para anotarla.")
            return
        try:
            audit_service.update_mark_note(
                self.conn,
                role=self.role,
                mark_id=mark["id"],
                nota=self.note_edit.toPlainText() or None,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.status_label.setText("Nota actualizada.")
        self.reload()

    def save_correction(self) -> None:
        """Propose + approve the corrected value in one click (oracle parity).

        The oracle's single "Aplicar Corrección" button created the correction
        already approved; the two-step gate stays testable at the service.
        """
        campo = self.selected_campo
        if campo is None:
            return
        current = self._hour_view().get(campo, "")
        try:
            correction = audit_service.propose_correction(
                self.conn,
                role=self.role,
                station_id=self.station,
                fecha=self.fecha,
                hora=self.active_hour,
                campo=campo,
                valor_original="" if current is None else str(current),
                valor_corregido=self.correction_dialog.value_edit.text(),
                justificacion=self.correction_dialog.justification_edit.toPlainText(),
                corregido_por=(
                    self.correction_dialog.corrector_edit.text().strip()
                    or self.user_email
                ),
            )
            audit_service.approve_correction(
                self.conn,
                role=self.role,
                correction_id=correction["id"],
                aprobado_por=self.user_email,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.correction_dialog.hide()
        self.status_label.setText("Corrección aplicada (overlay activo).")
        self.reload()

    def export_corrected(self) -> None:
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
        self.status_label.setText(f"Correcciones exportadas: {path}")

    def show_cli_reference(self, module: str) -> None:
        """Open the stored CLI sheet read-only (oracle 'Ver CLI' button)."""
        self.cli_dialog = CliPeekDialog(
            self.conn, self.station, self.fecha, module, self
        )
        self.cli_dialog.show()

    def _on_mark_selected(self, row: int) -> None:
        """Selecting a list row selects its cell, so the panel acts on it."""
        if self._data is None or row < 0:
            return
        marks = self._data["error_marks"]
        if row >= len(marks):
            return
        mark = marks[row]
        self.active_hour = mark["hora"]
        self.selected_campo = mark["campo"]
        self.note_edit.setPlainText(mark.get("nota") or "")
        self._refresh_grid()

    def remove_selected_mark(self) -> None:
        """Delete the mark chosen in the list (oracle per-row delete)."""
        row = self.error_list.currentRow()
        if self._data is None or row < 0 or row >= len(self._data["error_marks"]):
            self.status_label.setText("Elegí una marca de la lista.")
            return
        mark = self._data["error_marks"][row]
        try:
            audit_service.unmark_error(self.conn, role=self.role, mark_id=mark["id"])
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.status_label.setText("Marca quitada.")
        self.reload()

    # -------------------------------------------------------------- closure

    def toggle_audit_day(self) -> None:
        """Close (or reopen) this day's audit; the report counts on it."""
        closed = audit_service.get_audit_day(
            self.conn, station_id=self.station, fecha=self.fecha
        )
        try:
            if closed is None:
                audit_service.close_audit_day(
                    self.conn,
                    role=self.role,
                    station_id=self.station,
                    fecha=self.fecha,
                    auditado_por=self.user_email,
                )
            else:
                audit_service.reopen_audit_day(
                    self.conn,
                    role=self.role,
                    station_id=self.station,
                    fecha=self.fecha,
                )
        except _UI_ERRORS as exc:
            self.state_label.setText(str(exc))
            return
        self._refresh_audit_state()

    def _refresh_audit_state(self) -> None:
        """Paint the closure state and the button that toggles it."""
        closed = audit_service.get_audit_day(
            self.conn, station_id=self.station, fecha=self.fecha
        )
        if closed is None:
            self.state_label.setText("Día sin terminar")
            self.close_button.setText("Terminar auditoría")
            return
        self.state_label.setText(
            f"Auditado por {closed['auditado_por']} · {closed['auditado_en']}"
        )
        self.close_button.setText("Reabrir auditoría")
