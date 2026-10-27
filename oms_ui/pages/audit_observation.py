"""AuditObservationPage — the oracle's audit sheet, replicated.

Port of ``OLD/.../audit/pages/AuditObservationPage.jsx``. The owner's complaint
was exact: the module existed but the window did not look like the oracle. This
is the oracle's own layout:

* header with the orange station pill, the calendar+date pill and the black
  "Auditoría de Datos Meteorológicos" title; on the right the observer/auditor
  card, the three CLI reference buttons and the emerald "Guardar Correcciones";
* the red "⚠ Observador no identificado" alert, with the protocol text;
* the hour bar: the active hour in ORANGE, the others slate, disabled when the
  hour has no data, with a red dot for errors and an emerald one for
  corrections;
* a 3/4 + 1/4 body: card "Secciones SYNOP OMM" (rows of 4 / 7 / 6 fields) and
  card "Cálculos e Instrumentales de Estación" (rows of 4 / 4 / 6 / 5 / 4),
  both clickable per field; on the right the orange gradient "Estado de
  Auditoría" card (Inconsistencias / Corregidos) and the "Marcas en este día"
  card with one block per mark: hour + field, type pill, note, author and the
  trash button, plus the corrected value when it exists;
* the two modals with the oracle's headers (slate for marking, emerald for the
  correction overlay).

The page keeps ONE stylesheet (properties for the cell states) because that is
what makes it build in ~0.08 s instead of ~0.5 s.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories.audit import MarkConflictError
from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_core.services import document_map as dm
from oms_ui.icons import lucide_icon

ORANGE = "#f97316"
ORANGE_DARK = "#c2410c"
EMERALD = "#059669"

#: Service failures the status line can present (never crash the page).
_UI_ERRORS = (audit_service.AuditError, MarkConflictError, OSError, sqlite3.Error)

ERROR_TYPES = audit_service.ERROR_TYPES

#: The synoptic day starts at 06Z (the owner's own hour order, the same one the
#: observation sheet uses): auditing must not start at midnight.
AUDIT_HOURS: tuple[str, ...] = (
    "06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z",
)

#: The SYNOP groups in the order the OMM manual prints them (Manual N°306,
#: FM 12 SYNOP): Sección 1 carries the main observation —
#: ``iRixhVV Nddff 1snTTT 2snTdTdTd 4PPPP 5appp 6RRRtR 7wwW1W2 8NhCLCMCH`` — and
#: Sección 3 (``333``) the supplementary groups. Auditing in that order is
#: auditing the message as the observer wrote it.
SYNOP_SECTIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "SECCIÓN 1 · OBSERVACIÓN PRINCIPAL",
        (
            ("meteo_2_1", "YYGG Iw"),
            ("meteo_4_irixhvv", "Ir iX H VV"),
            ("meteo_4_1", "N dd ff"),
            ("meteo_6_3", "1sn Tx Tx Tx"),
            ("meteo_6_4", "2sn Tn Tn Tn"),
            ("meteo_6_0", "8Nh CL CM CH"),
            ("meteo_4_6", "7 ww W1 W2"),
            ("meteo_8_3", "6 RRR tr"),
        ),
    ),
    (
        "SECCIÓN 3 · 333 SUPLEMENTARIOS",
        (
            ("meteo_6_2", "0CS DL DM DH"),
            ("meteo_8_0", "5n Fn Fn Fn"),
            ("meteo_8_1", "56 DL DM DH"),
            ("meteo_8_4", "7 R24 R24 R24 R24"),
        ),
    ),
)

#: The oracle's row layout for the instrumentals card.
INSTRUMENT_ROWS: tuple[tuple[tuple[str, str], ...], ...] = (
    (
        ("ts", "Temp. Seca (Ts)"),
        ("th", "Temp. Húmeda (Th)"),
        ("punto_rocio", "Punto Rocío (Td)"),
        ("humedad_relativa", "Humedad Relativa (Hr)"),
    ),
    (
        ("pres_est", "Presión Estación (Pres_est)"),
        ("p3", "Presión 3h (P3)"),
        ("p24", "Presión 24h (P24)"),
        ("correc_alt", "Corrección por Altitud"),
    ),
    (
        ("t_max", "Temp. Máxima (Tx)"),
        ("t_min", "Temp. Mínima (Tn)"),
        ("t_max_24h", "Tx 24h"),
        ("t_min_24h", "Tn 24h"),
        ("ll", "Lluvia (LL)"),
        ("ll_24h", "Lluvia 24h (LL_24h)"),
    ),
    (
        ("pres_nmm", "Presión NMM"),
        ("tension_vapor", "Tensión Vapor"),
        ("diferencia", "Diferencia (Ts-Th)"),
        ("viento_dir", "Viento Dirección"),
        ("viento_vel", "Viento Velocidad"),
    ),
    (
        ("observador", "Nombre del Observador"),
        ("visibilidad", "Visibilidad (VV)"),
        ("tend_dif", "Tendencia Dif."),
        ("tend_car", "Tendencia Car"),
    ),
)

#: Field label -> the title the oracle prints. The observer is NOT a group: it
#: heads the SYNOP card on its own (owner round 31), because it is the datum the
#: auditor checks first.
FIELD_LABELS: dict[str, str] = {
    campo: title
    for _section, rows in SYNOP_SECTIONS
    for campo, title in rows
}
FIELD_LABELS.update(
    {campo: title for row in INSTRUMENT_ROWS for campo, title in row}
)
FIELD_LABELS["observador"] = "Nombre del Observador"

#: Derived values render read-only (recomputed by the service on load).
READONLY_FIELDS = frozenset(
    {"pres_nmm", "punto_rocio", "tension_vapor", "humedad_relativa", "diferencia"}
)

_PAGE_QSS = f"""
QWidget#auditPage {{ background-color: #f8fafc; }}
QFrame#auditCard {{ background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 14px; }}
QLabel#sectionTitle {{ color: #1e293b; font-size: 16px; font-weight: 800; }}
QLabel#sectionHint {{ color: #94a3b8; font-size: 10px; font-weight: 700;
    }}
QLabel#fieldLabel {{ color: #475569; font-size: 11px; font-weight: 700;
    background: transparent; }}
QLabel#title {{ color: #0f172a; font-size: 21px; font-weight: 900; }}
QLabel#pillOrange {{ background: {ORANGE}; color: #ffffff; font-weight: 800;
    font-size: 11px; border-radius: 6px; padding: 4px 9px; }}
QLabel#pillSlate {{ background: #e2e8f0; color: #334155; font-weight: 700;
    font-size: 11px; border-radius: 6px; padding: 4px 9px; }}
QLineEdit[state="plain"] {{ background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 6px 8px; color: #1e293b; }}
QLineEdit[state="mark"] {{ background: #fef2f2; border: 2px solid #ef4444;
    border-radius: 8px; padding: 5px 7px; color: #b91c1c; font-weight: 800; }}
QLineEdit[state="fixed"] {{ background: #ecfdf5; border: 2px solid #10b981;
    border-radius: 8px; padding: 5px 7px; color: #047857; font-weight: 700; }}
QPushButton#hourActive {{ background: {ORANGE}; color: #ffffff; border: none;
    border-radius: 10px; padding: 9px 14px; font-weight: 800; }}
QPushButton#hourIdle {{ background: #f1f5f9; color: #334155; border: none;
    border-radius: 10px; padding: 9px 14px; font-weight: 700; }}
QPushButton#hourIdle:hover {{ background: #fff7ed; color: {ORANGE_DARK}; }}
QPushButton#hourEmpty {{ background: #f8fafc; color: #cbd5e1; border: none;
    border-radius: 10px; padding: 9px 14px; font-weight: 700; }}
QPushButton#cliButton {{ background: #f1f5f9; color: #475569;
    border: 1px solid #e2e8f0; border-radius: 8px; padding: 5px 10px;
    font-weight: 700; font-size: 11px; }}
QPushButton#cliButton:hover {{ background: #eff6ff; color: #1d4ed8;
    border-color: #bfdbfe; }}
QPushButton#saveButton {{ background: #059669; color: #ffffff; border: none;
    border-radius: 10px; padding: 9px 16px; font-weight: 800; }}
QPushButton#ghost {{ background: #ffffff; color: #334155;
    border: 1px solid #cbd5e1; border-radius: 9px; padding: 6px 12px; }}
QPushButton#backButton {{ background: #ffffff; color: {ORANGE};
    border: 1px solid #fed7aa; border-radius: 20px; padding: 6px 14px;
    font-weight: 700; }}
"""


def cli_reference_html(
    conn: sqlite3.Connection, station: str, fecha: str, module: str
) -> str:
    """The stored CLI sheet as an HTML table (oracle "CLI xxxx" reference)."""
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
                value = ", ".join(k for k, v in value.items() if v)
            cells.append(f"<td>{'' if value in (None, False) else value}</td>")
        body.append(f"<tr><td><b>{row_key}</b></td>{''.join(cells)}</tr>")
    return (
        "<table border='1' cellspacing='0' cellpadding='4' width='100%'>"
        f"<thead><tr><th>Fila</th>{header}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


class CliPeekDialog(QDialog):
    """Read-only view of a stored CLI sheet."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        station: str,
        fecha: str,
        module: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"CLI {module} — {station} · {fecha}")
        self.resize(780, 520)
        box = QVBoxLayout(self)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setHtml(cli_reference_html(conn, station, fecha, module))
        box.addWidget(viewer)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        box.addWidget(close)


class MarkDialog(QDialog):
    """The oracle's MODAL 1: mark / edit / remove an error."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Opciones de Auditoría")
        self.setMinimumWidth(420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        header = QLabel()
        header.setStyleSheet("background: #0f172a; border-radius: 0;")
        header_box = QVBoxLayout(header)
        header_box.setContentsMargins(14, 10, 14, 10)
        self.title_label = QLabel("")
        self.title_label.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 800;"
        )
        header_box.addWidget(self.title_label)
        outer.addWidget(header)

        body = QWidget()
        form = QFormLayout(body)
        form.setContentsMargins(14, 12, 14, 12)
        self.current_label = QLabel("")
        self.current_label.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;"
            "padding: 6px 8px; color: #334155;"
        )
        form.addRow("Valor actual", self.current_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(ERROR_TYPES)
        form.addRow("Tipo de error", self.type_combo)
        self.group_label = QLabel("")
        form.addRow("Grupo del dato", self.group_label)
        self.note_edit = QTextEdit()
        self.note_edit.setMaximumHeight(80)
        form.addRow("Nota", self.note_edit)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Guardar Marca")
        self.save_button.setStyleSheet(
            "background: #0f172a; color: #ffffff; border-radius: 8px;"
            "padding: 8px 14px; font-weight: 700;"
        )
        self.correction_button = QPushButton("Aplicar Corrección")
        self.correction_button.setStyleSheet(
            f"background: #ecfdf5; color: {EMERALD}; border: 1px solid #a7f3d0;"
            "border-radius: 8px; padding: 8px 14px; font-weight: 700;"
        )
        self.remove_button = QPushButton("Quitar Marca")
        self.remove_button.setStyleSheet(
            "background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca;"
            "border-radius: 8px; padding: 8px 14px; font-weight: 700;"
        )
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.correction_button)
        buttons.addWidget(self.remove_button)
        form.addRow(buttons)
        outer.addWidget(body)


class CorrectionDialog(QDialog):
    """The oracle's MODAL 2: correction overlay."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Corrección Overlay")
        self.setMinimumWidth(420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        header = QLabel()
        header.setStyleSheet(f"background: {EMERALD};")
        header_box = QVBoxLayout(header)
        header_box.setContentsMargins(14, 10, 14, 10)
        pill = QLabel("CORRECCIÓN OVERLAY")
        pill.setStyleSheet(
            "background: #ffffff; color: #047857; border-radius: 4px;"
            "padding: 1px 6px; font-size: 9px; font-weight: 800;"
        )
        header_box.addWidget(pill, 0, Qt.AlignmentFlag.AlignLeft)
        self.title_label = QLabel("")
        self.title_label.setStyleSheet(
            "color: #ffffff; font-size: 16px; font-weight: 800;"
        )
        header_box.addWidget(self.title_label)
        outer.addWidget(header)

        body = QWidget()
        form = QFormLayout(body)
        form.setContentsMargins(14, 12, 14, 12)
        self.original_label = QLabel("")
        self.original_label.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;"
            "padding: 6px 8px; color: #334155;"
        )
        form.addRow("Valor original", self.original_label)
        self.value_edit = QLineEdit()
        form.addRow("Valor corregido", self.value_edit)
        self.justification_edit = QTextEdit()
        self.justification_edit.setMaximumHeight(70)
        form.addRow("Justificación", self.justification_edit)
        self.corrector_edit = QLineEdit()
        self.corrector_edit.setPlaceholderText("Quién corrige (corrector)")
        form.addRow("Corrector", self.corrector_edit)
        box = QDialogButtonBox()
        self.save_button = QPushButton("Aplicar Corrección")
        box.addButton(self.save_button, QDialogButtonBox.AcceptRole)
        form.addRow(box)
        outer.addWidget(body)


class AuditObservationPage(QWidget):
    """The oracle's audit sheet: sections, marks and the audit panel."""

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
        self.mark_blocks: list[QFrame] = []
        self.cli_buttons: dict[str, QPushButton] = {}

        self.setObjectName("auditPage")
        self.setStyleSheet(_PAGE_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        if self.denied:
            layout.addWidget(
                QLabel(
                    "Acceso denegado: la auditoría requiere rol admin o "
                    "control_calidad."
                )
            )
            self._denied_widgets()
            return

        self._build_header(layout)
        self._build_alert(layout)
        self._build_hours(layout)
        self._build_body(layout)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.mark_dialog = MarkDialog(self)
        self.mark_dialog.save_button.clicked.connect(self.save_mark)
        self.mark_dialog.remove_button.clicked.connect(self.remove_mark)
        self.mark_dialog.correction_button.clicked.connect(self._open_correction)
        self.correction_dialog = CorrectionDialog(self)
        self.correction_dialog.save_button.clicked.connect(self.save_correction)
        self.cli_dialog: CliPeekDialog | None = None

        self.reload()

    # ---------------------------------------------------------------- header

    def _denied_widgets(self) -> None:
        self.back_button = QPushButton()
        self.close_button = QPushButton()
        self.state_label = QLabel("")
        self.marks_label = QLabel("")
        self.error_list = QWidget()
        self.export_button = QPushButton()
        self.to_correction_button = QPushButton()
        self.status_label = QLabel("")
        self.observer_banner = QLabel("")
        self.correction_dialog = CorrectionDialog(self)
        self.mark_dialog = MarkDialog(self)

    def _build_header(self, layout: QVBoxLayout) -> None:
        header = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)

        pills = QHBoxLayout()
        pills.setSpacing(6)
        station_pill = QLabel(f"ESTACIÓN {self.station}")
        station_pill.setObjectName("pillOrange")
        # a QLabel cannot hold text and a pixmap at once: the icon goes in its
        # own label so the date stays readable
        date_pill = QFrame()
        date_pill.setObjectName("pillSlate")
        date_row = QHBoxLayout(date_pill)
        date_row.setContentsMargins(6, 2, 8, 2)
        date_row.setSpacing(4)
        calendar_icon = QLabel()
        calendar_icon.setPixmap(
            lucide_icon("calendar", "#334155", 12).pixmap(12, 12)
        )
        date_row.addWidget(calendar_icon)
        date_row.addWidget(QLabel(self.fecha))
        pills.addWidget(station_pill)
        pills.addWidget(date_pill)
        pills.addStretch(1)
        left.addLayout(pills)

        title = QLabel("Auditoría de Datos Meteorológicos")
        title.setObjectName("title")
        left.addWidget(title)

        self.back_button = QPushButton("← Volver al Selector")
        self.back_button.setObjectName("backButton")
        self.back_button.hide()  # owner round 29: the module needs no back button
        row = QHBoxLayout()
        row.addWidget(self.back_button)
        row.addLayout(left, 1)
        header.addLayout(row, 1)

        right = QVBoxLayout()
        right.setSpacing(6)
        info = QFrame()
        info.setObjectName("auditCard")
        info_row = QHBoxLayout(info)
        info_row.setContentsMargins(10, 6, 10, 6)
        info_row.setSpacing(10)
        self.observer_label = QLabel("Observador: —")
        self.observer_label.setStyleSheet(
            "color: #64748b; font-size: 11px; font-weight: 600;"
        )
        auditor_label = QLabel(f"Auditor: {self.user_email}")
        auditor_label.setStyleSheet(
            "color: #64748b; font-size: 11px; font-weight: 600;"
        )
        info_row.addWidget(self.observer_label)
        info_row.addWidget(auditor_label)
        right.addWidget(info, 0, Qt.AlignmentFlag.AlignRight)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        for module in ("3074", "4074", "5074"):
            button = QPushButton(f" CLI {module}")
            button.setObjectName("cliButton")
            button.setIcon(lucide_icon("book-open", "#475569", 13))
            button.clicked.connect(
                lambda _=False, m=module: self.show_cli_reference(m)
            )
            buttons.addWidget(button)
            self.cli_buttons[module] = button
        self.export_button = QPushButton("  Guardar Correcciones")
        self.export_button.setObjectName("saveButton")
        self.export_button.setIcon(lucide_icon("save", "#ffffff", 15))
        self.export_button.clicked.connect(self.export_corrected)
        buttons.addWidget(self.export_button)
        right.addLayout(buttons)

        self.state_label = QLabel("")
        self.state_label.setStyleSheet("color: #64748b; font-size: 11px;")
        self.close_button = QPushButton("Terminar auditoría")
        self.close_button.setObjectName("ghost")
        self.close_button.clicked.connect(self.toggle_audit_day)
        state_row = QHBoxLayout()
        state_row.addWidget(self.state_label)
        state_row.addWidget(self.close_button)
        right.addLayout(state_row)

        header.addLayout(right, 0)
        layout.addLayout(header)

    def _build_alert(self, layout: QVBoxLayout) -> None:
        self.observer_banner = QLabel("")
        self.observer_banner.setWordWrap(True)
        self.observer_banner.setStyleSheet(
            "background: #fef2f2; color: #991b1b; border: 1px solid #fecaca;"
            "border-radius: 12px; padding: 10px 14px; font-size: 12px;"
        )
        self.observer_banner.setVisible(False)
        layout.addWidget(self.observer_banner)

    def _build_hours(self, layout: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("auditCard")
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(6)
        for hora in AUDIT_HOURS:
            holder = QWidget()
            column = QHBoxLayout(holder)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(3)
            dot = QLabel()
            dot.setFixedSize(7, 7)
            dot.setStyleSheet("background: transparent; border-radius: 3px;")
            button = QPushButton(hora)
            button.setObjectName("hourIdle")
            button.clicked.connect(lambda _=False, h=hora: self.set_hour(h))
            column.addWidget(button)
            column.addWidget(dot)
            self.hour_buttons[hora] = button
            self.hour_dots[hora] = dot
            row.addWidget(holder)
        layout.addWidget(bar)

    def _build_body(self, layout: QVBoxLayout) -> None:
        body = QHBoxLayout()
        body.setSpacing(12)

        left = QWidget()
        left_column = QVBoxLayout(left)
        left_column.setContentsMargins(0, 0, 0, 0)
        left_column.setSpacing(12)
        left_column.addWidget(self._synop_card())
        left_column.addWidget(self._instrument_card())
        left_column.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(left)
        body.addWidget(scroll, 3)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self._state_card())
        right.addWidget(self._marks_card(), 1)
        body.addLayout(right, 1)
        layout.addLayout(body, 1)

    def _card(self, title: str, hint: str = "") -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("auditCard")
        column = QVBoxLayout(card)
        column.setContentsMargins(16, 12, 16, 14)
        column.setSpacing(10)
        head = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        head.addWidget(label, 1)
        if hint:
            hint_label = QLabel(hint.upper())
            hint_label.setObjectName("sectionHint")
            head.addWidget(hint_label, 0, Qt.AlignmentFlag.AlignVCenter)
        column.addLayout(head)
        return card, column

    def _field(self, campo: str, title: str) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        label = QLabel(title)
        label.setObjectName("fieldLabel")
        label.setVisible(bool(title))
        cell = QLineEdit()
        cell.setProperty("state", "plain")
        cell.setReadOnly(campo not in READONLY_FIELDS)
        cell.setMinimumHeight(30)
        cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell.setProperty("campo", campo)
        cell.setCursor(Qt.CursorShape.PointingHandCursor)
        cell.mousePressEvent = lambda event, c=campo: self.select_cell(c)
        column.addWidget(label)
        column.addWidget(cell)
        self.cells[campo] = cell
        return holder

    def _rows_grid(self, rows, columns: int = 4) -> QWidget:
        """A tidy grid: every row is a fixed number of equal columns.

        The oracle used per-row ``grid-cols-N`` counts (4, 7, 5...), which left
        the sheet ragged: fields of a 5-field row were narrower than the ones
        above them. Wrapping the same ORIGINAL ORDER into a constant column
        count keeps the sequence and makes the columns line up.
        """
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        index = 0
        for row in rows:
            for campo, title in row:
                grid.addWidget(
                    self._field(campo, title), index // columns, index % columns
                )
                index += 1
        for column_index in range(columns):
            grid.setColumnStretch(column_index, 1)
        return holder

    def _synop_card(self) -> QFrame:
        card, column = self._card(
            "Secciones SYNOP OMM",
            "Hacer click en un campo para marcar error o corregir",
        )
        for section_title, rows in SYNOP_SECTIONS:
            caption = QLabel(section_title)
            caption.setStyleSheet(
                "color: #f97316; font-size: 10px; font-weight: 800;"
                "padding-top: 4px;"
            )
            column.addWidget(caption)
            column.addWidget(self._rows_grid((rows,)))
        return card

    def _instrument_card(self) -> QFrame:
        card, column = self._card("Cálculos e Instrumentales de Estación")
        column.addWidget(self._rows_grid(INSTRUMENT_ROWS))
        return card

    def _state_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: {ORANGE}; border-radius: 14px;")
        column = QVBoxLayout(card)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(8)
        title = QLabel("  ESTADO DE AUDITORÍA")
        title.setStyleSheet(
            "color: #ffedd5; font-size: 11px; font-weight: 800;"
            ""
        )
        title.setPixmap(lucide_icon("radio", "#ffedd5", 13).pixmap(13, 13))
        column.addWidget(title)

        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        self.marks_value = QLabel("0")
        self.corrections_value = QLabel("0")
        for caption, value in (
            ("Inconsistencias", self.marks_value),
            ("Corregidos", self.corrections_value),
        ):
            tile = QFrame()
            tile.setStyleSheet(
                "background: rgba(255,255,255,0.16); border-radius: 10px;"
            )
            tile_column = QVBoxLayout(tile)
            tile_column.setContentsMargins(10, 8, 10, 8)
            caption_label = QLabel(caption)
            caption_label.setStyleSheet(
                "color: #ffedd5; font-size: 10px; font-weight: 700;"
            )
            value.setStyleSheet(
                "color: #ffffff; font-size: 22px; font-weight: 900;"
            )
            tile_column.addWidget(caption_label)
            tile_column.addWidget(value)
            tiles.addWidget(tile)
        column.addLayout(tiles)
        footer = QLabel(
            "Correcciones activas mediante Overlay dinámico."
        )
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(
            "color: rgba(255,237,213,0.85); font-size: 9px;"
        )
        column.addWidget(footer)
        return card

    def _marks_card(self) -> QFrame:
        card, column = self._card("Marcas en este día")
        self.marks_label = QLabel("")
        self.marks_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        column.addWidget(self.marks_label)
        self.marks_host = QWidget()
        self.marks_layout = QVBoxLayout(self.marks_host)
        self.marks_layout.setContentsMargins(0, 0, 0, 0)
        self.marks_layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.marks_host)
        column.addWidget(scroll, 1)
        self.to_correction_button = QPushButton("Aplicar Corrección")
        self.to_correction_button.setObjectName("ghost")
        self.to_correction_button.clicked.connect(self.open_correction_dialog)
        column.addWidget(self.to_correction_button)
        self.empty_marks = QLabel("Sin marcas de error registradas.")
        self.empty_marks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_marks.setStyleSheet("color: #94a3b8; font-size: 11px;")
        column.addWidget(self.empty_marks)
        self.error_list = self.marks_host  # name kept for callers/tests
        return card

    # ------------------------------------------------------------------ data

    def reload(self) -> None:
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
            for h in AUDIT_HOURS
            if isinstance(self._data["observation"].get(h), dict)
            and any(
                k not in ("station_id", "observador", "nombre_observador")
                for k in self._data["observation"][h]
            )
        ]
        for hora, button in self.hour_buttons.items():
            button.setEnabled(hora in hours)
        if self.active_hour not in hours:
            self.active_hour = hours[0] if hours else "06Z"
        self._refresh_grid()
        self._refresh_marks()

    def set_hour(self, hora: str) -> None:
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
                state = "mark"
                tip = f"Error: {mark['tipo_error']}"
                if mark.get("nota"):
                    tip += f" — {mark['nota']}"
            elif corr is not None:
                state, tip = "fixed", f"Corregido: {corr['valor_corregido']}"
            else:
                state, tip = "plain", FIELD_LABELS.get(campo, campo)
            cell.setProperty("state", state)
            cell.setToolTip(tip)
            style = cell.style()
            style.unpolish(cell)
            style.polish(cell)
        self._refresh_hour_buttons()
        self._refresh_observer_alert()

    def _refresh_hour_buttons(self) -> None:
        marks = self._data["error_marks"] if self._data else []
        corrections = self._data["corrections"] if self._data else []
        for hora, button in self.hour_buttons.items():
            active = hora == self.active_hour
            if not button.isEnabled():
                button.setObjectName("hourEmpty")
            elif active:
                button.setObjectName("hourActive")
            else:
                button.setObjectName("hourIdle")
            style = button.style()
            style.unpolish(button)
            style.polish(button)
            dot = self.hour_dots[hora]
            if any(m["hora"] == hora for m in marks):
                color = "#ef4444"
            elif any(c["hora"] == hora for c in corrections):
                color = "#10b981"
            else:
                color = "transparent"
            dot.setStyleSheet(f"background: {color}; border-radius: 3px;")

    def _refresh_observer_alert(self) -> None:
        view = self._hour_view()
        has_data = any(
            key not in ("station_id", "observador", "nombre_observador")
            and value not in ("", None)
            for key, value in view.items()
        )
        observer = str(view.get("observador") or "").strip()
        missing = has_data and not observer
        self.observer_label.setText(
            f"Observador: {observer or '—'}" + ("  ⚠ SIN NOMBRE" if missing else "")
        )
        self.observer_label.setStyleSheet(
            "color: #dc2626; font-size: 11px; font-weight: 800;"
            if missing
            else "color: #64748b; font-size: 11px; font-weight: 600;"
        )
        self.observer_banner.setText(
            "⚠ Observador no identificado\n"
            "Esta observación no registra el nombre del observador de turno. "
            "Según el protocolo, toda observación DEBE incluir la identificación "
            "del personal responsable. Se recomienda marcar este dato como error "
            'de tipo "Falta de datos".'
        )
        self.observer_banner.setVisible(missing)

    def _refresh_marks(self) -> None:
        for block in self.mark_blocks:
            block.setParent(None)
            block.deleteLater()
        self.mark_blocks = []
        if self._data is None:
            self.marks_label.setText("")
            return
        marks = self._data["error_marks"]
        corrections = self._data["corrections"]
        self.marks_value.setText(str(len(marks)))
        self.corrections_value.setText(str(len(corrections)))
        self.empty_marks.setVisible(not marks)
        self.marks_label.setText(
            f"{len(marks)} inconsistencia(s) · {len(corrections)} corrección(es)"
            if marks
            else ""
        )
        for mark in marks:
            self.marks_layout.addWidget(self._mark_block(mark))
        self.marks_layout.addStretch(1)

    def _mark_block(self, mark: dict) -> QFrame:
        block = QFrame()
        block.setStyleSheet(
            "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;"
        )
        column = QVBoxLayout(block)
        column.setContentsMargins(10, 8, 10, 8)
        column.setSpacing(3)
        head = QHBoxLayout()
        title = QLabel(
            f"{mark['hora']} - {FIELD_LABELS.get(mark['campo'], mark['campo'])}"
        )
        title.setStyleSheet(
            f"color: {ORANGE_DARK}; font-size: 11px; font-weight: 800;"
        )
        pill = QLabel(mark["tipo_error"])
        pill.setStyleSheet(
            "background: #fee2e2; color: #b91c1c; border-radius: 4px;"
            "padding: 1px 5px; font-size: 9px; font-weight: 700;"
        )
        head.addWidget(title, 1)
        head.addWidget(pill)
        column.addLayout(head)
        if mark.get("nota"):
            note = QLabel(f"“{mark['nota']}”")
            note.setWordWrap(True)
            note.setStyleSheet("color: #475569; font-size: 11px; font-style: italic;")
            column.addWidget(note)
        footer = QHBoxLayout()
        author = QLabel(f"Por: {str(mark.get('marcado_por') or '').split('@')[0]}")
        author.setStyleSheet("color: #94a3b8; font-size: 9px;")
        footer.addWidget(author)
        footer.addStretch(1)
        trash = QPushButton()
        trash.setFixedSize(20, 20)
        trash.setCursor(Qt.CursorShape.PointingHandCursor)
        trash.setIcon(lucide_icon("trash-2", "#ef4444", 12))
        trash.setStyleSheet("border: none; background: transparent;")
        trash.setToolTip("Eliminar marca")
        trash.clicked.connect(lambda _=False, mid=mark["id"]: self._remove_mark_id(mid))
        footer.addWidget(trash)
        column.addLayout(footer)
        corr = self._correction_for(mark["hora"], mark["campo"])
        if corr is not None:
            corrected = QLabel(f"Corregido: {corr['valor_corregido']}")
            corrected.setStyleSheet(
                f"color: {EMERALD}; font-size: 10px; font-weight: 700;"
            )
            column.addWidget(corrected)
        self.mark_blocks.append(block)
        return block

    # ----------------------------------------------------------------- flows

    def select_cell(self, campo: str) -> None:
        self.selected_campo = campo
        mark = self._marks_for(self.active_hour, campo)
        dialog = self.mark_dialog
        dialog.title_label.setText(
            f"{self.active_hour} · {FIELD_LABELS.get(campo, campo)}"
        )
        dialog.current_label.setText(str(self._hour_view().get(campo, "")))
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

    def _open_correction(self) -> None:
        self.mark_dialog.hide()
        self.open_correction_dialog()

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
            existing["valor_corregido"]
            if existing
            else ("" if current is None else str(current))
        )
        dialog.justification_edit.setPlainText(
            existing["justificacion"] if existing else ""
        )
        dialog.corrector_edit.setText(self.user_email)
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
        self.mark_dialog.hide()
        self.status_label.setText("Marca guardada.")
        self.reload()

    def remove_mark(self) -> None:
        campo = self.selected_campo
        mark = None if campo is None else self._marks_for(self.active_hour, campo)
        if mark is None:
            return
        self.mark_dialog.hide()
        self._remove_mark_id(mark["id"])

    def _remove_mark_id(self, mark_id: int) -> None:
        try:
            audit_service.unmark_error(self.conn, role=self.role, mark_id=mark_id)
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
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
                nota=self.mark_dialog.note_edit.toPlainText() or None,
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.status_label.setText("Nota actualizada.")
        self.reload()

    def save_correction(self) -> None:
        """Propose + approve in one click (the oracle's single button)."""
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
                self.conn, self.base_dir, self.station, self.fecha, role=self.role
            )
        except _UI_ERRORS as exc:
            self.status_label.setText(str(exc))
            return
        self.status_label.setText(f"Correcciones exportadas: {path}")

    def show_cli_reference(self, module: str) -> None:
        """Open the project's REAL CLI sheet for this day (owner round 29).

        The oracle navigated to the CLI pages; embedding the actual views here
        gives the auditor the same sheet, with its own formatting and data.
        """
        from oms_ui.pages import cli3074, cli4074, cli5074

        classes = {
            "3074": cli3074.Cli3074View,
            "4074": cli4074.Cli4074View,
            "5074": cli5074.Cli5074View,
        }
        dialog = QDialog(self)
        dialog.setWindowTitle(f"CLI {module} — {self.station} · {self.fecha}")
        dialog.resize(1500, 760)
        box = QVBoxLayout(dialog)
        box.setContentsMargins(8, 8, 8, 8)
        view = classes[module](
            self.conn, station=self.station, fecha=self.fecha
        )
        # opened FROM the audit: the sheet's own "back" closes this window and
        # there is no extra close button underneath (owner round 31)
        back = getattr(view, "back_button", None)
        if back is not None:
            back.show()
            back.setText("← Cerrar CLI")
        view.back_requested.connect(dialog.accept)
        box.addWidget(view, 1)
        self.cli_dialog = dialog
        dialog.show()

    # -------------------------------------------------------------- closure

    def toggle_audit_day(self) -> None:
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


__all__ = [
    "AuditObservationPage",
    "CliPeekDialog",
    "CorrectionDialog",
    "MarkDialog",
    "cli_reference_html",
]
