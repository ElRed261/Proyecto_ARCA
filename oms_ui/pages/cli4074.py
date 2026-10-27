"""Cli4074View — cloud observation sheet, 24 local-hour rows.

Embeddable view (owner round 5: no extra windows) ported from
``OLD/frontend/src/features/synoptic/cli4074/pages/Cli4074Page.jsx``:
N + CÚMULONIMBOS (Cant/Tipo/Altura) + NUBES BAJAS CL (Cant/Tipo/Dir/
Altura/TOTAL) + NUBES MEDIAS CM ×5 + NUBES ALTAS CH ×5 + LLUVIA 6H +
TEMPS Máx/Mín + EST. SUELO + OBS. The doc rides the transactional
``cli_service.save_cli`` under ``cli4074`` (shape: ``{"horas": ...}``).
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_core.services import cli as cli_service
from oms_ui.icons import lucide_icon
from oms_ui.widgets import StyledComboBox

#: (field, sub-header text) in column order; groups carry their own colors.
GROUPS_4074: tuple[tuple[str, str, int, tuple[tuple[str, str], ...]], ...] = (
    ("CÚMULONIMBOS", "#334155", 3, (
        ("cb_cant", "Cant"), ("cb_tipo", "Tipo"), ("cb_altura", "Altura"),
    )),
    ("NUBES BAJAS (CL)", "#334155", 5, (
        ("nb_cant", "Cant"), ("nb_tipo", "Tipo"), ("nb_direc", "Dir"),
        ("nb_altura", "Altura"), ("nb_total", "TOTAL"),
    )),
    ("NUBES MEDIAS (CM)", "#334155", 5, (
        ("nm_cant", "Cant"), ("nm_tipo", "Tipo"), ("nm_direc", "Dir"),
        ("nm_altura", "Altura"), ("nm_total", "TOTAL"),
    )),
    ("NUBES ALTAS (CH)", "#334155", 5, (
        ("na_cant", "Cant"), ("na_tipo", "Tipo"), ("na_direc", "Dir"),
        ("na_altura", "Altura"), ("na_total", "TOTAL"),
    )),
)
_ROWSPAN_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("nubosidad", "N", "#1e293b"),
    ("lluvia_6h", "LLUVIA 6H (mm)", "#1e293b"),
    ("estado_suelo", "EST. SUELO", "#1e293b"),
    ("observador", "OBS.", "#1e293b"),
)
#: ONE stylesheet for the sheet: each cell carries ``row`` ("main"/"sub") and
#: ``ro`` so Qt parses the rules once instead of ~350 times.
_SHEET_QSS = """
QLineEdit[row="sub"] { background-color: #ffffff; border: 1px solid #e2e8f0;
    color: #1e293b; font-size: 12px; padding: 3px 4px; }
QLineEdit[row="sub"]:focus { border-color: #38bdf8; background-color: #f0f9ff; }
QLineEdit[row="main"] { background-color: #d1fae5; border: 1px solid #a7f3d0;
    color: #1e293b; font-size: 12px; padding: 3px 4px; }
QLineEdit[row="main"]:focus { border-color: #10b981; background-color: white; }
QLineEdit[row="main"][ro="true"] { background-color: #a7f3d0;
    border: 1px solid #6ee7b7; color: #065f46; font-weight: 600; }
QLineEdit[row="sub"][ro="true"] { background-color: #f8fafc;
    border: 1px solid #e2e8f0; color: #475569; }
"""

_TEMPS: tuple[tuple[str, str], ...] = (("temp_max", "Máx"), ("temp_min", "Mín"))
#: Rows that keep the grey "0" placeholder: exactly the eight synoptic hours
#: (rows 2/5/8/11/14/17/20/23). Every other row stays visually blank.
ZERO_PLACEHOLDER_ROWS: frozenset[int] = frozenset(
    {2, 5, 8, 11, 14, 17, 20, 23}
)
#: main-hour rows tinted GREEN across the full row (IMG/CLI 4074.png).
_MAIN_TINT = "#d1fae5"
_MAIN_STICKY = "#a7f3d0"
_MAIN_NUMBER = "#059669"
_MAIN_INPUT_QSS = (
    "QLineEdit { background-color: #d1fae5; border: 1px solid #a7f3d0;"
    "color: #1e293b; font-size: 12px; padding: 3px 4px; }"
    "QLineEdit:focus { border-color: #10b981; background-color: white; }"
)
_CHECKBOX_QSS = (
    "QCheckBox::indicator { width: 17px; height: 17px;"
    "border: 2px solid #64748b; border-radius: 4px; background-color: #ffffff; }"
    "QCheckBox::indicator:hover { border-color: #10b981; }"
    "QCheckBox::indicator:checked { background-color: #10b981;"
    "border-color: #047857; }"
    "QCheckBox { background-color: transparent; }"
)
INPUT_QSS = (
    "QLineEdit { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "color: #1e293b; font-size: 12px; padding: 3px 4px; }"
    "QLineEdit:focus { border-color: #38bdf8; background-color: #f0f9ff; }"
)
_HEADER_QSS = (
    "background-color: {color}; color: #ffffff; font-weight: bold;"
    "font-size: 11px; padding: 5px 3px;"
)
_SUB_HEADER_QSS = (
    "background-color: #1f2937; color: #cbd5e1; font-weight: 600;"
    "font-size: 10px; padding: 4px 2px;"
)
_SAVE_QSS = (
    "QPushButton { background-color: #0ea5e9; color: #ffffff;"
    "border: none; border-radius: 8px; padding: 7px 14px;"
    "font-weight: 700; font-size: 12px; }"
    "QPushButton:hover { background-color: #0284c7; }"
)


_LOGGER = logging.getLogger(__name__)

#: CLI autosave debounce. Test-injectable (suite waits the real path at
#: 50ms instead of 700ms).
AUTOSAVE_MS = 700


class Cli4074View(QWidget):
    """CLI 4074 cloud sheet embedded in the synoptic page view stack."""

    synop_hour_requested = Signal(str)
    back_requested = Signal()
    switch_requested = Signal(str)

    MODULE_KEY = "cli4074"
    TITLE = "CLI 4074 - NUBOSIDAD Y TEMPERATURA"

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
        self.setWindowTitle(self.TITLE)  # transparent: hourly gradient behind

        self.row_inputs: dict[int, dict[str, QLineEdit]] = {
            row: {} for row in range(1, 25)
        }
        self._loading = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_MS)
        self._autosave_timer.timeout.connect(self.save_data)
        self._build()
        for row_map in self.row_inputs.values():
            for edit in row_map.values():
                edit.textChanged.connect(self._schedule_autosave)
        self.load_data()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        central = QWidget()
        central.setStyleSheet(_SHEET_QSS)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        top = QHBoxLayout()
        back_btn = QPushButton()
        # exposed so an embedding window (audit) can repurpose it as "close"
        self.back_button = back_btn
        back_btn.setFixedSize(40, 40)
        back_btn.setIcon(lucide_icon("arrow-left", "#0369a1", 18))
        back_btn.setIconSize(QSize(18, 18))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setToolTip("Volver a la última hora de observación")
        back_btn.setStyleSheet(
            "QPushButton { background-color: #ffffff; border: 1px solid #e2e8f0;"
            "border-radius: 20px; }"
            "QPushButton:hover { background-color: #e0f2fe; }"
        )
        back_btn.clicked.connect(self.back_requested.emit)
        top.addWidget(back_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        title = QLabel(self.TITLE)
        title.setStyleSheet(
            # fondo plano (sin fotografía ni degradado): tinta de texto
                        "font-size: 18px; font-weight: 800; color: #0f172a;"
            "background: transparent;"
        )
        title.setWordWrap(True)
        top.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        self._build_tabs(top)
        self._build_ver_hora(top)

        # NO save button (owner round 8): autosave debounced+silently
        outer.addLayout(top)

        self._build_station_card(outer)

        sheet_card = QFrame()
        sheet_card.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0;"
            "border-radius: 10px; }"
        )
        sheet_layout = QVBoxLayout(sheet_card)
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)

        col = 1

        #: owner round 8: TOTAL headers full height + emerald (like N/LLUVIA)
        TOTAL_FIELDS = {"nb_total", "nm_total", "na_total"}

        def rowspan_header(text: str, color: str, at_col: int) -> None:
            header = QLabel(text)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setWordWrap(True)
            header.setStyleSheet(_HEADER_QSS.format(color=color))
            grid.addWidget(header, 0, at_col, 2, 1)  # full header height

        def group_header(at_col: int, text: str, color: str,
                          span: int, fields: tuple[tuple[str, str], ...]) -> None:
            header = QLabel(text)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setWordWrap(True)
            header.setStyleSheet(_HEADER_QSS.format(color=color))
            grid.addWidget(header, 0, at_col, 1, span)
            for offset, (field, sub) in enumerate(fields):
                if field in TOTAL_FIELDS:  # full height + emerald, like N
                    rowspan_header(sub, "#047857", at_col + offset)
                    continue
                sub_label = QLabel(sub)
                sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sub_label.setStyleSheet(_SUB_HEADER_QSS)
                grid.addWidget(sub_label, 1, at_col + offset)

        # column order verbatim IMG/CLI 4074.png: N first, then the four
        # cloud groups, lluvia, temps, est. suelo, obs. — every rowspan
        # interleaved at its real column (the celdas already follow this
        # order via _all_fields)
        rowspan_header("N", _ROWSPAN_FIELDS[0][2], col); col += 1
        group_header(col, "CÚMULONIMBOS", GROUPS_4074[0][1], 3, GROUPS_4074[0][3]); col += 3
        group_header(col, "NUBES BAJAS (CL)", GROUPS_4074[1][1], 5, GROUPS_4074[1][3]); col += 5
        group_header(col, "NUBES MEDIAS (CM)", GROUPS_4074[2][1], 5, GROUPS_4074[2][3]); col += 5
        group_header(col, "NUBES ALTAS (CH)", GROUPS_4074[3][1], 5, GROUPS_4074[3][3]); col += 5
        rowspan_header("LLUVIA 6H (mm)", _ROWSPAN_FIELDS[1][2], col); col += 1
        group_header(col, "TEMPS.", "#334155", 2, _TEMPS); col += 2
        rowspan_header("EST. SUELO", _ROWSPAN_FIELDS[2][2], col); col += 1
        rowspan_header("OBS.", _ROWSPAN_FIELDS[3][2], col); col += 1

        for row in range(1, 25):
            number = QLabel(str(row))
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main = (row - 2) % 3 == 0
            number.setStyleSheet(
                f"background-color: {_MAIN_STICKY if main else '#f1f5f9'};"
                f"color: {_MAIN_NUMBER if main else '#475569'}; font-weight: bold;"
                "font-size: 12px; padding: 4px 5px;"
            )
            grid.addWidget(number, row + 1, 0)
            for cindex, (field, _text) in enumerate(self._all_fields()):
                edit = QLineEdit()
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if field != "observador" and row in ZERO_PLACEHOLDER_ROWS:
                    # the sheet looks empty with only a few values; a grey 0
                    # marks "no data" without inventing stored zeros (R1).
                    # Only the rows the owner marked keep it.
                    edit.setPlaceholderText("0")
                edit.setProperty("row", "main" if main else "sub")
                edit.setMinimumHeight(26)
                edit.editingFinished.connect(
                    lambda w=edit, f=field: self._normalize_edit(w, f)
                )
                self.row_inputs[row][field] = edit
                grid.addWidget(edit, row + 1, 1 + cindex)
        for cindex in range(len(self._all_fields())):
            grid.setColumnStretch(1 + cindex, 1)
            # 4074 values are short (a temperature, a digit); 46 px keeps
            # every column on screen at 1366 while never clipping them.
            grid.setColumnMinimumWidth(1 + cindex, 46)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(grid_host)
        sheet_layout.addWidget(scroll)
        outer.addWidget(sheet_card, 1)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(central)

    @staticmethod
    def _all_fields() -> tuple[tuple[str, str], ...]:
        fields: list[tuple[str, str]] = [("nubosidad", "N")]
        for _g, _c, _s, group_fields in GROUPS_4074:
            fields.extend(group_fields)
        fields.append(("lluvia_6h", "LLUVIA 6H"))
        fields.extend(_TEMPS)
        fields.extend([("estado_suelo", "EST. SUELO"), ("observador", "OBS.")])
        return tuple(fields)

    def _build_tabs(self, top: QHBoxLayout) -> None:
        tabs_box = QWidget()
        tabs_box.setStyleSheet("background-color: #e2e8f0; border-radius: 8px;")
        tabs_row = QHBoxLayout(tabs_box)
        tabs_row.setContentsMargins(4, 4, 4, 4)
        tabs_row.setSpacing(4)
        for module_key, label in (
            ("cli3074", "3074"), ("cli4074", "4074"), ("cli5074", "5074"),
        ):
            active = module_key == self.MODULE_KEY
            tab = QPushButton(label)
            tab.setStyleSheet(
                f"QPushButton {{ background-color: {'#ffffff' if active else 'transparent'};"
                f"color: {'#0369a1' if active else '#475569'}; border: none;"
                "border-radius: 6px; padding: 6px 14px; font-size: 12px;"
                "font-weight: bold; min-height: 24px; }"
                "QPushButton:hover { background-color: #f0f9ff; }"
            )
            tab.setCursor(Qt.CursorShape.PointingHandCursor)
            if not active:
                tab.clicked.connect(
                    lambda _=False, m=module_key: self.switch_requested.emit(m)
                )
            tabs_row.addWidget(tab)
        top.addWidget(tabs_box, 0, Qt.AlignmentFlag.AlignVCenter)

    def _build_ver_hora(self, top: QHBoxLayout) -> None:
        hour_box = QWidget()
        hour_box.setStyleSheet("background-color: #e2e8f0; border-radius: 8px;")
        hour_row = QHBoxLayout(hour_box)
        hour_row.setContentsMargins(8, 4, 8, 4)
        hour_row.setSpacing(4)
        hint = QLabel("VER HORA SYNOP:")
        hint.setStyleSheet(
            "color: #64748b; font-size: 10px; font-weight: 700;"
            "background: transparent;"
        )
        hour_row.addWidget(hint)
        for hour in ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z",
                      "00Z", "03Z"):  # the day starts at 06Z
            button = QPushButton(hour)
            button.setStyleSheet(
                "QPushButton { background-color: #ffffff; color: #475569;"
                "border: none; border-radius: 6px; padding: 6px 12px;"
                "font-size: 12px; font-weight: bold; min-height: 24px; }"
                "QPushButton:hover { color: #0369a1; background-color: #f0f9ff; }"
            )
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, h=hour: self.synop_hour_requested.emit(h)
            )
            hour_row.addWidget(button)
        top.addWidget(hour_box, 0, Qt.AlignmentFlag.AlignVCenter)

    def _build_station_card(self, outer: QVBoxLayout) -> None:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0;"
            "border-radius: 10px; }"
        )
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)

        def meta_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "color: #475569; font-weight: 700; font-size: 11px;"
                "background: transparent;"
            )
            return label

        self.station_combo = StyledComboBox()
        for row in stations_repo.list_stations(self._conn):
            self.station_combo.addItem(f"{row.name} ({row.id})", row.id)
        self.station_combo.setCurrentIndex(
            max(self.station_combo.findData(self.station), 0)
        )
        self.station_combo.setEnabled(False)  # locked like the oracle route
        self.station_combo.setStyleSheet(
            "QComboBox { background-color: #f8fafc; border: 1px solid #cbd5e1;"
            "border-radius: 6px; padding: 4px 8px; color: #475569; height: 24px; }"
        )
        self.fecha_edit = _ro_field(f"{self.fecha[8:]}/{self.fecha[5:7]}/{self.fecha[:4]}")

        station_row = next(
            (s for s in stations_repo.list_stations(self._conn) if s.id == self.station),
            None,
        )
        self.latitud_edit = _ro_field(
            "" if station_row is None else str(round(station_row.latitud, 4))
        )
        self.longitud_edit = _ro_field(
            "" if station_row is None else str(round(station_row.longitud, 4))
        )
        self.altura_edit = _ro_field(
            "" if station_row is None else str(round(station_row.ch, 1))
        )

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

    # ------------------------------------------------------------ behavior

    def _normalize_edit(self, widget: QLineEdit, field: str) -> None:
        value = widget.text().strip()
        normalized = cli_service.enforce_one_decimal(
            value, field,
            decimal_fields=cli_service.DECIMAL_FIELDS_4074,
            ceil_fields=cli_service.CEIL_FIELDS_4074,
        )
        if normalized != value:
            widget.setText("" if normalized is None else str(normalized))

    # ------------------------------------------------------------ data I/O

    def row_values(self, row: int) -> dict[str, str]:
        return {
            field: self.row_inputs[row][field].text().strip()
            for field, _text in self._all_fields()
        }

    def set_row(self, row: int, data: dict) -> None:
        for field, _text in self._all_fields():
            value = data.get(field)
            if value is not None:
                self.row_inputs[row][field].setText(str(value))

    def load_data(self) -> None:
        self._loading = True
        try:
            doc = cli_service.load_cli4074(self._conn, self.station, self.fecha)
            horas = (doc or {}).get("horas") if isinstance(doc, dict) else None
            if isinstance(horas, dict):
                for row in range(1, 25):
                    data = horas.get(str(row))
                    if isinstance(data, dict):
                        self.set_row(row, data)
        finally:
            self._loading = False

    def flush_pending(self) -> None:
        """Write whatever is still waiting on the autosave debounce.

        The CLI views are cached across days (``SynopticPage._cli_views``), so
        a context change reloads the same widgets: an edit typed 699 ms ago
        would be written against the NEW day or silently dropped. Every
        context change therefore flushes first.
        """
        timer = getattr(self, "_autosave_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
            self.save_data()

    def save_data(self) -> None:
        try:
            cli_service.save_cli(
                self._conn, self.station, self.fecha, self.MODULE_KEY,
                {"horas": {str(r): self.row_values(r) for r in range(1, 25)}},
            )
        except (cli_service.SaveError, ValueError, sqlite3.Error):
            _LOGGER.exception("CLI 4074 autosave falló")

    def _schedule_autosave(self, *args) -> None:
        if self._loading:
            return
        self._autosave_timer.start()


def _ro_field(text: str) -> QLineEdit:
    edit = QLineEdit(text)
    edit.setReadOnly(True)
    edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
    edit.setStyleSheet(
        "background-color: #f8fafc; border: 1px solid #e2e8f0;"
        "border-radius: 6px; padding: 4px 8px; color: #334155; font-size: 12px;"
    )
    return edit

