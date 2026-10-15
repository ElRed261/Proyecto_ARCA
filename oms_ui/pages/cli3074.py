"""Cli3074Window — CLI 3074 hourly surface observations (IMG/CLI 3074.png).

PySide6 port of ``OLD/frontend/src/features/synoptic/cli3074/pages/
Cli3074Page.jsx`` backed by ``oms_core.services.cli``:

- 24 local-hour rows (HORA LOCAL 1..24) with the synoptic-hour rows
  (2, 5, 8, ... 23) tinted as main hours;
- columns verbatim: PRESIÓN (hPa) Esta./NMM/Altímetro, 3 H. TEND C.A.R/Dif,
  TEMPERATURA Seco/Húmedo, HUMEDAD Pto R/T Vap/HR % (computed, read-only),
  VIENTO Dir (16 P)/Vel (m/s), VISIBILIDAD (km), T. PRES. and the ten WMO
  020003 fenómenos booleans (GR/SQ/FG/TS/LT/RD/DS/HZ/FG/FC, rotated heads);
- VER HORA SYNOP buttons emit :attr:`synop_hour_requested` (oracle navigates
  to the synoptic page with ``activeHour`` — the caller wires the jump);
- the station card is the locked StationHeader (oracle ``isLocked``) with
  the station's latitud/longitud/elevacion and the working date;
- saving writes ``{"horas": {...}}`` through the transactional
  ``cli_service.save_cli``; the derived fields (tend Dif/C.A.R, visibilidad,
  tiempo presente) are recalculated by ``cli_service.load_cli3074`` on
  every load (oracle ``load_cli3074_json_core``).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_core.services import cli as cli_service
from oms_ui.icons import lucide_icon

#: oracle synopRows: synoptic UTC hour -> local row number (1-based).
SYNOP_ROWS: dict[str, int] = {
    "06Z": 2, "09Z": 5, "12Z": 8, "15Z": 11,
    "18Z": 14, "21Z": 17, "00Z": 20, "03Z": 23,
}

#: per-row fields in column order (field, sub-header text, read-only).
ROW_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("pres_est", "Esta.", False),
    ("pres_nmm", "NMM", False),
    ("pres_alti", "Altímetro", False),
    ("tend_car", "C.A.R", False),
    ("tend_dif", "Dif", False),
    ("temp_seco", "SECO", False),
    ("temp_humedo", "HÚMEDO", False),
    ("hum_ptor", "PTO R (°C)", True),
    ("hum_tvap", "T VAP (hPa)", True),
    ("hum_hr", "HR %", True),
    ("viento_dir", "DIR (16 P)", False),
    ("viento_vel", "VEL (m/s)", False),
)

#: oracle fenomenosList: key, rotated abbr, tooltip description (WMO 020003).
FENOMENOS: tuple[tuple[str, str, str], ...] = (
    ("granizo", "GR", "Granizo (tormenta con granizo)"),
    ("ventarron", "SQ", "Ventarrón (Squalls)"),
    ("neblina", "FG", "Neblina (mist)"),
    ("trueno", "TS", "Trueno (Thunderstorm)"),
    ("relampago", "LT", "Relámpago (Lightning visible)"),
    ("rocio", "RD", "Rocío (Dew)"),
    ("polvo", "DS", "Polvo (Duststorm)"),
    ("calima", "HZ", "Calima (Haze)"),
    ("niebla", "FG", "Niebla (Fog)"),
    ("tornado", "FC", "Tornado (Funnel cloud)"),
)

_MAIN_ROW_TINT = "#eff6ff"      # sky-50 main-hour rows
_MAIN_STICKY_TINT = "#bae6fd"   # sky-200 sticky-number cells
_GROUP_COLORS = {
    "pres": "#0c4a6e", "tend": "#1e40af", "temp": "#3730a3",
    "hum": "#1e293b", "viento": "#86198f", "vis": "#1e293b",
    "feno": "#334155",
}
_HEADER_QSS = (
    "background-color: {color}; color: #ffffff; font-weight: bold;"
    "font-size: 11px; padding: 5px 4px;"
)
_SUB_HEADER_QSS = (
    "background-color: #1f2937; color: #cbd5e1; font-weight: 600;"
    "font-size: 10px; padding: 4px 2px;"
)
INPUT_QSS = (
    "QLineEdit { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "color: #1e293b; font-size: 12px; padding: 3px 4px; }"
    "QLineEdit:focus { border-color: #38bdf8; background-color: #f0f9ff; }"
)
_RO_QSS = (
    "QLineEdit { background-color: #eff6ff; border: 1px solid #dbeafe;"
    "color: #0369a1; font-weight: bold; font-size: 12px; padding: 3px 4px; }"
)
_SAVE_QSS = (
    "QPushButton { background-color: #0ea5e9; color: #ffffff;"
    "border: none; border-radius: 8px; padding: 7px 14px;"
    "font-weight: 700; font-size: 12px; }"
    "QPushButton:hover { background-color: #0284c7; }"
)


class _VerticalLabel(QLabel):
    """Rotated sub-header (the oracle fenómenos abbr column heads)."""

    def __init__(self, text: str, tooltip: str) -> None:
        super().__init__()
        self._text = text
        self.setToolTip(tooltip)
        self.setFixedSize(26, 40)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.translate(0, self.height())
        painter.rotate(-90)
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawText(
            0, 0, self.height(), self.width(),
            Qt.AlignmentFlag.AlignCenter, self._text,
        )
        painter.end()


class Cli3074Window(QMainWindow):
    """The CLI 3074 station sheet with 24 local-hour rows."""

    #: VER HORA SYNOP jumps: the synoptic page reacts by selecting the hour
    synop_hour_requested = Signal(str)

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        station: str,
        fecha: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self.station = station
        self.fecha = fecha
        self.setWindowTitle("CLI 3074 - OBSERVACIONES DE SUPERFICIE")

        #: oracle rows state: numerics + stored extras (p3 when present).
        self._row_data: dict[int, dict[str, Any]] = {
            row: cli_service.default_row(cli_service.DECIMAL_FIELDS_3074)
            for row in range(1, 25)
        }
        self.row_inputs: dict[int, dict[str, QLineEdit]] = {}
        self.row_checks: dict[int, dict[str, QCheckBox]] = {}

        self._build()
        self.load_data()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # top band: title + VER HORA SYNOP + Guardar -----------------------
        top = QHBoxLayout()
        title = QLabel("CLI 3074 - OBSERVACIONES DE SUPERFICIE")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #0f172a;"
            "background: transparent;"
        )
        title.setWordWrap(True)
        top.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)

        hour_box = QWidget()
        hour_box.setStyleSheet("background-color: #e2e8f0; border-radius: 8px;")
        hour_row = QHBoxLayout(hour_box)
        hour_row.setContentsMargins(8, 4, 8, 4)
        hour_row.setSpacing(4)
        hour_hint = QLabel("VER HORA SYNOP:")
        hour_hint.setStyleSheet(
            "color: #64748b; font-size: 10px; font-weight: 700;"
            "background: transparent;"
        )
        hour_row.addWidget(hour_hint)
        self._hour_buttons: dict[str, QPushButton] = {}
        for hour in ("00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"):
            button = QPushButton(hour)
            button.setStyleSheet(
                "QPushButton { background-color: #ffffff; color: #475569;"
                "border: none; border-radius: 5px; padding: 3px 7px;"
                "font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { color: #0369a1; background-color: #f0f9ff; }"
            )
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Ver la hora Sinóptica {hour}")
            # oracle: navigate('/synoptic', { activeHour: h })
            button.clicked.connect(
                lambda _checked=False, h=hour: self.synop_hour_requested.emit(h)
            )
            self._hour_buttons[hour] = button
            hour_row.addWidget(button)
        top.addWidget(hour_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self.save_btn = QPushButton("Guardar")
        self.save_btn.setIcon(lucide_icon("save", "#ffffff", 15))
        self.save_btn.setIconSize(self.save_btn.iconSize())
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(_SAVE_QSS)
        self.save_btn.clicked.connect(self.save_data)
        top.addWidget(self.save_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(top)

        # locked station card (oracle StationHeader isLocked) ---------------
        card = self._card_host()
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(10)

        def meta_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "color: #475569; font-weight: 700; font-size: 11px;"
                "background: transparent;"
            )
            return label

        self.station_combo = QComboBox()
        for row in stations_repo.list_stations(self._conn):
            self.station_combo.addItem(f"{row.name} ({row.id})", row.id)
        index = self.station_combo.findData(self.station)
        self.station_combo.setCurrentIndex(max(index, 0))
        self.station_combo.setEnabled(False)  # locked like the oracle route
        self.station_combo.setStyleSheet(
            "QComboBox { background-color: #f8fafc; border: 1px solid #cbd5e1;"
            "border-radius: 6px; padding: 4px 8px; color: #475569; height: 24px; }"
        )

        self.latitud_edit = self._ro_meta_field()
        self.longitud_edit = self._ro_meta_field()
        self.altura_edit = self._ro_meta_field()
        self.fecha_edit = self._ro_meta_field()
        year, month, day = self.fecha.split("-")
        self.fecha_edit.setText(f"{day}/{month}/{year}")
        station_row = next(
            (s for s in stations_repo.list_stations(self._conn) if s.id == self.station),
            None,
        )
        if station_row is not None:
            self.latitud_edit.setText(str(round(station_row.latitud, 4)))
            self.longitud_edit.setText(str(round(station_row.longitud, 4)))
            self.altura_edit.setText(str(round(station_row.ch, 1)))

        grid.addWidget(meta_label("ESTACIÓN:"), 0, 0)
        grid.addWidget(self.station_combo, 0, 1)
        grid.addWidget(meta_label("LATITUD:"), 0, 2)
        grid.addWidget(self.latitud_edit, 0, 3)
        grid.addWidget(meta_label("LONGITUD:"), 0, 4)
        grid.addWidget(self.longitud_edit, 0, 5)
        grid.addWidget(meta_label("ALTURA:"), 0, 6)
        grid.addWidget(self.altura_edit, 0, 7)
        grid.addWidget(meta_label("FECHA:"), 0, 8)
        grid.addWidget(self.fecha_edit, 0, 9)
        grid.setColumnStretch(10, 1)
        outer.addWidget(card)

        # THE SPREADSHEET: grouped two-row header + 24 hour rows -----------
        sheet_card = self._card_host()
        sheet_layout = QVBoxLayout(sheet_card)
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        sheet_layout.addWidget(grid_host)

        def group_header(col: int, span: int, text: str, color: str,
                         rowspan: int = 1) -> None:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setStyleSheet(_HEADER_QSS.format(color=color))
            grid.addWidget(label, 0, col, rowspan, span)

        group_header(1, 3, "PRESIÓN (hPa)", _GROUP_COLORS["pres"])
        group_header(4, 2, "3 H. TEND", _GROUP_COLORS["tend"])
        group_header(6, 2, "TEMPERATURA", _GROUP_COLORS["temp"])
        group_header(8, 3, "HUMEDAD", _GROUP_COLORS["hum"])
        group_header(11, 2, "VIENTO", _GROUP_COLORS["viento"])
        group_header(13, 1, "VISIBILIDAD (km)", _GROUP_COLORS["vis"], rowspan=2)
        group_header(14, 11, "FENÓMENOS", _GROUP_COLORS["feno"])

        for index, (field, text, _ro) in enumerate(ROW_FIELDS):
            sub = QLabel(text)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setWordWrap(True)
            sub.setStyleSheet(_SUB_HEADER_QSS)
            grid.addWidget(sub, 1, 1 + index)

        tp_label = QLabel("T. PRES.")
        tp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tp_label.setToolTip("Tiempo presente")
        tp_label.setStyleSheet(_SUB_HEADER_QSS)
        grid.addWidget(tp_label, 1, 14)

        for index, (_key, abbr, tooltip) in enumerate(FENOMENOS):
            grid.addWidget(_VerticalLabel(abbr, tooltip), 1, 15 + index)

        for row in range(1, 25):
            self._build_data_row(grid, row)
        for col in range(1, 14):  # numeric + visibility columns share the stretch
            grid.setColumnStretch(col, 1)
        for index in range(len(FENOMENOS)):  # fixed checkbox lanes
            grid.setColumnMinimumWidth(15 + index, 32)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(grid_host)
        sheet_layout.addWidget(scroll)
        outer.addWidget(sheet_card, 1)

        self.setCentralWidget(central)

    def _card_host(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0;"
            "border-radius: 10px; }"
        )
        return frame

    def _ro_meta_field(self) -> QLineEdit:
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0;"
            "border-radius: 6px; padding: 4px 8px; color: #334155;"
            "font-size: 12px;"
        )
        return edit

    def _build_data_row(self, grid: QGridLayout, row: int) -> None:
        main = (row - 2) % 3 == 0
        hour_label = QLabel(str(row))
        hour_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hour_label.setStyleSheet(
            f"background-color: {_MAIN_STICKY_TINT if main else '#f1f5f9'};"
            f"color: {'#0c4a6e' if main else '#475569'}; font-weight: bold;"
            "font-size: 12px; padding: 4px 6px;"
        )
        grid.addWidget(hour_label, row + 1, 0)

        self.row_inputs.setdefault(row, {})
        for index, (field, _text, read_only) in enumerate(ROW_FIELDS):
            edit = QLineEdit()
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setStyleSheet(_RO_QSS if read_only else INPUT_QSS)
            edit.setMinimumHeight(26)
            if read_only:
                edit.setReadOnly(True)
            else:
                edit.editingFinished.connect(
                    lambda w=edit, f=field, r=row: self._normalize_edit(w, f, r)
                )
            self.row_inputs[row][field] = edit
            grid.addWidget(edit, row + 1, 1 + index)

        vis_edit = QLineEdit()
        vis_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vis_edit.setStyleSheet(INPUT_QSS)
        vis_edit.setMinimumHeight(26)
        self.row_inputs[row]["visibilidad"] = vis_edit
        grid.addWidget(vis_edit, row + 1, 13)

        tp_edit = QLineEdit()
        tp_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tp_edit.setStyleSheet(INPUT_QSS)
        tp_edit.setMinimumHeight(26)
        self.row_inputs[row]["tiempo_presente"] = tp_edit
        grid.addWidget(tp_edit, row + 1, 14)

        self.row_checks.setdefault(row, {})
        for index, (key, _abbr, tooltip) in enumerate(FENOMENOS):
            check = QCheckBox()
            check.setToolTip(tooltip)
            check.setCursor(Qt.CursorShape.PointingHandCursor)
            self.row_checks[row][key] = check
            grid.addWidget(
                check, row + 1, 15 + index, 1, 1, Qt.AlignmentFlag.AlignCenter
            )

    # ------------------------------------------------------------ behavior

    def _normalize_edit(self, widget: QLineEdit, field: str, row: int) -> None:
        """Blur pass: enforce_one_decimal verbatim (one decimal / ceil)."""
        value = widget.text().strip()
        normalized = cli_service.enforce_one_decimal(
            value, field,
            decimal_fields=cli_service.DECIMAL_FIELDS_3074,
            ceil_fields=cli_service.CEIL_FIELDS_3074,
        )
        if normalized != value:
            widget.setText("" if normalized is None else str(normalized))
        if field == "pres_est":
            self._recompute_tend(row)

    def _recompute_tend(self, row: int) -> None:
        """Oracle updateRowField: recalc Dif/C.A.R when pres_est changes.

        Uses the row's stored p3 (present only when a prior save wrote it;
        the oracle line for 3074 keeps it in the behind-the-scenes payload).
        Without a valid p3 the oracle clears both cells — ported verbatim.
        """
        import oms_calc

        data = self._row_data[row]
        data["pres_est"] = self.row_inputs[row]["pres_est"].text().strip()
        pres_est = data.get("pres_est") or ""
        p3 = str(data.get("p3") or "")
        try:
            pres_value = float(pres_est) if pres_est else None
            p3_value = float(p3) if p3 else None
        except (TypeError, ValueError):
            pres_value, p3_value = None, None
        if pres_value is not None and p3_value is not None:
            self.row_inputs[row]["tend_dif"].setText(f"{abs(pres_value - p3_value):.1f}")
            self.row_inputs[row]["tend_car"].setText(
                oms_calc.calc_car(pres_est, p3)
            )
        else:
            self.row_inputs[row]["tend_dif"].setText("")
            self.row_inputs[row]["tend_car"].setText("")

    # ------------------------------------------------------------ data I/O

    def row_values(self, row: int) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field, _text, _ro in ROW_FIELDS:
            values[field] = self.row_inputs[row][field].text().strip()
        fenomenos: dict[str, Any] = {
            key: self.row_checks[row][key].isChecked()
            for key, _abbr, _tip in FENOMENOS
        }
        fenomenos["tiempo_presente"] = (
            self.row_inputs[row]["tiempo_presente"].text().strip()
        )
        values["fenomenos"] = fenomenos
        return values

    def set_row(self, row: int, data: dict[str, Any]) -> None:
        for field, _text, _ro in ROW_FIELDS:
            value = data.get(field)
            if value is not None:
                self.row_inputs[row][field].setText(str(value))
        fenomenos = data.get("fenomenos") or {}
        if isinstance(fenomenos, dict):
            for key, _abbr, _tip in FENOMENOS:
                self.row_checks[row][key].setChecked(bool(fenomenos.get(key)))
            tp = fenomenos.get("tiempo_presente")
            if tp is not None:
                self.row_inputs[row]["tiempo_presente"].setText(str(tp))

    def rows_payload(self) -> dict[str, dict[str, Any]]:
        """Shape the service expects: {"horas": {"1".."24": row dict}}."""
        payload: dict[str, dict[str, Any]] = {}
        for row in range(1, 25):
            row_dict = self.row_values(row)
            extras = {"p3": self._row_data[row].get("p3") or ""}
            row_dict.update(extras)
            payload[str(row)] = row_dict
        return payload

    def load_data(self) -> None:
        """Stored sheet + the oracle derived pass (tend Dif/C.A.R, etc.)."""
        doc = cli_service.load_cli3074(self._conn, self.station, self.fecha)
        horas = (doc or {}).get("horas") if isinstance(doc, dict) else None
        if not isinstance(horas, dict):
            return
        for row in range(1, 25):
            data = horas.get(str(row))
            if isinstance(data, dict):
                self._row_data[row].update(
                    {k: v for k, v in data.items() if k != "fenomenos"}
                )
                self.set_row(row, data)

    def save_data(self) -> None:
        """Transactional save via the service; visual error feedback."""
        try:
            cli_service.save_cli(
                self._conn, self.station, self.fecha, "cli3074",
                {"horas": self.rows_payload()},
            )
        except (cli_service.SaveError, ValueError) as exc:
            self.save_btn.setText("Error ✗")
            self.save_btn.setToolTip(f"Error al guardar: {exc}")
            self.save_btn.setStyleSheet(
                "QPushButton { background-color: #dc2626; color: #ffffff;"
                "border: none; border-radius: 8px; padding: 7px 14px;"
                "font-weight: 700; font-size: 12px; }"
            )
            QTimer.singleShot(2500, self._restore_save_style)
        else:
            self.save_btn.setText("Guardar")
            self.save_btn.setToolTip("Guardado en el documento diario ✓")
            self.save_btn.setStyleSheet(_SAVE_QSS)

    def _restore_save_style(self) -> None:
        self.save_btn.setText("Guardar")
        self.save_btn.setStyleSheet(_SAVE_QSS)
