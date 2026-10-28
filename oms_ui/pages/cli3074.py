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

import logging
import sqlite3
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
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


def _qss(plantilla: str) -> str:
    from string import Template

    from oms_ui import theme as _theme

    return Template(plantilla).substitute(_theme.palette_actual())


#: oracle synopRows: synoptic UTC hour -> local row number (1-based).
SYNOP_ROWS: dict[str, int] = {
    "06Z": 2, "09Z": 5, "12Z": 8, "15Z": 11,
    "18Z": 14, "21Z": 17, "00Z": 20, "03Z": 23,
}

#: per-row fields in column order (field, sub-header text, read-only).
#: column of the per-hour observer initials, after the phenomenon lanes
_OBS_COLUMN: int = 25

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

_MAIN_ROW_TINT = "$acento_fondo"      # filas de la hora principal
_MAIN_STICKY_TINT = "$acento_suave"   # celdas de número fijo
#: Encabezado de grupo: fondo tintado de la identidad del módulo y letra
#: oscura, para que se lea en los dos temas (forma del mockup).
_HEADER_QSS = (
    "background-color: {color}; color: {text}; font-weight: 800;"
    "font-size: 11px; padding: 6px 4px; border-radius: 3px;"
)
_DEFAULT = {"color": "$acento_suave", "text": "$acento_texto"}
#: Sub-encabezado: texto gris, sin relleno.
_SUB_HEADER_QSS = (
    "background-color: transparent; color: $suave_alt; font-weight: 600;"
    "font-size: 10px; padding: 2px;"
)
INPUT_QSS = (
    "QLineEdit { background-color: $superficie; border: 1px solid $borde;"
    "color: $texto; font-size: 12px; padding: 3px 4px; }"
    "QLineEdit:focus { border-color: $acento; background-color: $acento_fondo; }"
)
_RO_QSS = (
    "QLineEdit { background-color: $acento_fondo; border: 1px solid $acento_suave;"
    "color: $acento_texto; font-weight: bold; font-size: 12px; padding: 3px 4px; }"
)
_MAIN_INPUT_QSS = (
    "QLineEdit { background-color: $acento_suave; border: 1px solid $borde;"
    "color: $texto; font-size: 12px; padding: 3px 4px; }"
    "QLineEdit:focus { border-color: $acento; background-color: $superficie; }"
)
_MAIN_RO_QSS = (
    "QLineEdit { background-color: $acento_suave; border: 1px solid $borde;"
    "color: $acento_texto; font-weight: bold; font-size: 12px; padding: 3px 4px; }"
)
_CHECKBOX_QSS = (
    "QCheckBox::indicator { width: 17px; height: 17px;"
    "border: 2px solid $suave_alt; border-radius: 3px; background-color: $superficie; }"
    "QCheckBox::indicator:hover { border-color: $acento_texto; }"
    "QCheckBox::indicator:checked { background-color: $acento;"
    "border-color: $acento_texto; }"
    "QCheckBox { background-color: transparent; }"
)
_MAIN_CHECKBOX_QSS = (
    "QCheckBox::indicator { width: 17px; height: 17px;"
    "border: 2px solid $suave_alt; border-radius: 3px; background-color: $acento_fondo; }"
    "QCheckBox::indicator:hover { border-color: $acento_texto; }"
    "QCheckBox::indicator:checked { background-color: $acento;"
    "border-color: $acento_texto; }"
    "QCheckBox { background-color: transparent; }"
)
#: ONE stylesheet for the whole sheet. The cells carry a ``row`` property
#: ("main"/"sub") and ``ro`` for read-only, so Qt parses the rules once instead
#: of 400 times: per-widget setStyleSheet measured 48% of the build time.
_SHEET_QSS = """
QLineEdit[row="sub"] { background-color: $superficie; border: 1px solid $borde;
    color: $texto; font-size: 12px; padding: 3px 4px; }
QLineEdit[row="sub"]:focus { border-color: $acento; background-color: $acento_fondo; }
QLineEdit[row="sub"][ro="true"] { background-color: $acento_fondo;
    border: 1px solid $acento_suave; color: $acento_texto; font-weight: bold;
    font-size: 12px; padding: 3px 4px; }
QLineEdit[row="main"] { background-color: $acento_suave; border: 1px solid $borde;
    color: $texto; font-size: 12px; padding: 3px 4px; }
QLineEdit[row="main"]:focus { border-color: $acento; background-color: $superficie; }
QLineEdit[row="main"][ro="true"] { background-color: $acento_fondo;
    border: 1px solid $borde; color: $acento_texto; font-weight: bold;
    font-size: 12px; padding: 3px 4px; }
/* base rules first, attribute overrides after: Qt matches the subcontrol
   rules only when the base `::indicator` block exists */
QCheckBox { background-color: transparent; }
QCheckBox::indicator { width: 17px; height: 17px;
    border: 2px solid $suave_alt; border-radius: 3px; background-color: $superficie; }
QCheckBox::indicator:hover { border-color: $acento_texto; }
QCheckBox::indicator:checked { background-color: $acento;
    border-color: $acento_texto; }
QCheckBox#checkMain::indicator { background-color: $acento_fondo; }
QCheckBox#checkMain::indicator:checked { background-color: $acento; }
/* object names, not attributes: QLabel attribute selectors did not match
   here while they do on QLineEdit, and a silently unstyled header is worse
   than a slightly longer selector */
QLabel { background: transparent; }
QLabel#hourMain { background-color: $acento_suave; color: $acento_texto;
    font-weight: bold; font-size: 12px; padding: 4px 6px;
    border-radius: 3px; }
QLabel#hourSub { background-color: $panel; color: $suave;
    font-weight: bold; font-size: 12px; padding: 4px 6px;
    border-radius: 3px; }
"""

_SAVE_QSS = (
    "QPushButton { background-color: $acento; color: $sobre_acento;"
    "border: none; border-radius: 8px; padding: 7px 14px;"
    "font-weight: 700; font-size: 12px; }"
    "QPushButton:hover { background-color: $acento_hover; }"
)


class _VerticalLabel(QLabel):
    """Rotated sub-header (the oracle fenómenos abbr column heads).

    Owner round 7: dark chip like the other sub-headers — the bare gray
    glyphs on the page background were unreadable.
    """

    def __init__(self, text: str, tooltip: str) -> None:
        super().__init__()
        self._text = text
        self.setToolTip(tooltip)
        self.setFixedSize(26, 44)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(_qss("$suave_alt")))
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(7.5)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


_LOGGER = logging.getLogger(__name__)

#: CLI autosave debounce. Test-injectable (suite waits the real path at
#: 50ms instead of 700ms).
AUTOSAVE_MS = 700


class Cli3074View(QWidget):
    """The CLI 3074 station sheet with 24 local-hour rows.

    Embeddable view (owner round 5: no extra windows — the CLI lives in the
    same window as the synoptic page, swapped by a view stack).
    """

    #: VER HORA SYNOP jumps: the synoptic page reacts by selecting the hour
    synop_hour_requested = Signal(str)
    #: the round back arrow: return to the last open synoptic hour
    back_requested = Signal()
    #: module tabs (3074/4074/5074): the host swaps CLI views
    switch_requested = Signal(str)

    MODULE_KEY = "cli3074"
    TITLE = "CLI 3074 · Observaciones de superficie"

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
        self.setWindowTitle(self.TITLE)  # transparent: the page's hourly
        # gradient shows through (owner round 6: fondo según la hora)

        #: oracle rows state: numerics + stored extras (p3 when present).
        self._row_data: dict[int, dict[str, Any]] = {
            row: cli_service.default_row(cli_service.DECIMAL_FIELDS_3074)
            for row in range(1, 25)
        }
        self.row_inputs: dict[int, dict[str, QLineEdit]] = {}
        self.row_checks: dict[int, dict[str, QCheckBox]] = {}

        self._loading = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_MS)
        self._autosave_timer.timeout.connect(self.save_data)
        self.setStyleSheet(_qss(_SHEET_QSS))  # ONE sheet: cells carry row/ro properties
        self._build()
        for row_map in self.row_inputs.values():
            for edit in row_map.values():
                edit.textChanged.connect(self._schedule_autosave)
        for row_map in self.row_checks.values():
            for check in row_map.values():
                check.toggled.connect(self._schedule_autosave)
        self.load_data()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        central = QWidget()
        # the NEAREST ancestor sheet wins, so the sheet lives here: a
        # "background: transparent" here used to swallow every child rule
        central.setStyleSheet(_qss(_SHEET_QSS))
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # top band: back + title + module tabs + VER HORA SYNOP + Guardar --
        top = QHBoxLayout()
        back_btn = QPushButton()
        # exposed so an embedding window (audit) can repurpose it as "close"
        self.back_button = back_btn
        back_btn.setFixedSize(40, 40)
        back_btn.setIcon(lucide_icon("arrow-left", _qss("$acento_texto"), 18))
        back_btn.setIconSize(QSize(18, 18))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setToolTip("Volver a la última hora de observación")
        back_btn.setStyleSheet(_qss(
            "QPushButton { background-color: $superficie; border: 1px solid $borde;"
            "border-radius: 20px; }"
            "QPushButton:hover { background-color: $acento_suave; }"
        ))
        back_btn.clicked.connect(self.back_requested.emit)
        top.addWidget(back_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        title = QLabel(self.TITLE)
        title.setObjectName("cliTitle")
        title.setStyleSheet(_qss(
            "QLabel#cliTitle { font-size: 18px; font-weight: 800;"
            "color: $texto_alt; background: transparent; }"
        ))
        title.setWordWrap(False)
        top.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)

        # module tabs (oracle intra-CLI navigation)
        tabs_box = QWidget()
        tabs_box.setStyleSheet(_qss("background-color: $panel; border-radius: 8px;"))
        tabs_row = QHBoxLayout(tabs_box)
        tabs_row.setContentsMargins(4, 4, 4, 4)
        tabs_row.setSpacing(4)
        for module_key, label in (
            ("cli3074", "3074"),
            ("cli4074", "4074"),
            ("cli5074", "5074"),
        ):
            active = module_key == self.MODULE_KEY
            tab = QPushButton(label)
            tab.setProperty("mod", module_key)
            tab.setStyleSheet(_qss(
                "QPushButton { border: 1px solid transparent;"
                " border-radius: 6px; padding: 6px 14px; font-size: 12px;"
                " font-weight: 800; min-height: 24px; }"
                "QPushButton[mod='cli3074'] { background-color: $acento_fondo;"
                " border-color: $acento; color: $acento_texto; }"
                "QPushButton:hover { border-color: $acento; }"
            ))
            tab.setCursor(Qt.CursorShape.PointingHandCursor)
            if not active:
                tab.clicked.connect(
                    lambda _=False, m=module_key: self.switch_requested.emit(m)
                )
            tabs_row.addWidget(tab)
        top.addWidget(tabs_box, 0, Qt.AlignmentFlag.AlignVCenter)

        hour_box = QWidget()
        hour_box.setStyleSheet(_qss("background-color: $panel; border-radius: 8px;"))
        hour_row = QHBoxLayout(hour_box)
        hour_row.setContentsMargins(8, 4, 8, 4)
        hour_row.setSpacing(4)
        hour_hint = QLabel("VER HORA SYNOP:")
        hour_hint.setStyleSheet(_qss(
            "color: $suave_alt; font-size: 10px; font-weight: 700;"
            "background: transparent;"
        ))
        hour_row.addWidget(hour_hint)
        self._hour_buttons: dict[str, QPushButton] = {}
        for hour in ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z",
                      "00Z", "03Z"):  # the day starts at 06Z
            button = QPushButton(hour)
            button.setStyleSheet(_qss(
                "QPushButton { background-color: $superficie; color: $suave;"
                "border: none; border-radius: 6px; padding: 6px 12px;"
                "font-size: 12px; font-weight: bold; min-height: 24px; }"
                "QPushButton:hover { color: $acento_texto; background-color: $acento_fondo; }"
            ))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Ver la hora Sinóptica {hour}")
            # oracle: navigate('/synoptic', { activeHour: h })
            button.clicked.connect(
                lambda _checked=False, h=hour: self.synop_hour_requested.emit(h)
            )
            self._hour_buttons[hour] = button
            hour_row.addWidget(button)
        top.addWidget(hour_box, 0, Qt.AlignmentFlag.AlignVCenter)

        # NO save button (owner round 8): edits autosave debounced+silently
        outer.addLayout(top)

        # locked station card (oracle StationHeader isLocked) ---------------
        card = self._card_host()
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(10)

        def meta_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(_qss(
                "color: $suave; font-weight: 700; font-size: 11px;"
                "background: transparent;"
            ))
            return label

        self.station_combo = StyledComboBox()
        for row in stations_repo.list_stations(self._conn):
            self.station_combo.addItem(f"{row.name} ({row.id})", row.id)
        index = self.station_combo.findData(self.station)
        self.station_combo.setCurrentIndex(max(index, 0))
        self.station_combo.setEnabled(False)  # locked like the oracle route
        self.station_combo.setStyleSheet(_qss(
            "QComboBox { background-color: $panel_alt; border: 1px solid $borde_input;"
            "border-radius: 6px; padding: 4px 8px; color: $suave; height: 24px; }"
        ))

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
            label.setStyleSheet(_qss(_HEADER_QSS.format(**_DEFAULT)))
            grid.addWidget(label, 0, col, rowspan, span)

        group_header(1, 3, "PRESIÓN (hPa)", "$banda")
        group_header(4, 2, "3 H. TEND", "$banda")
        group_header(6, 2, "TEMPERATURA", "$banda")
        group_header(8, 3, "HUMEDAD", "$banda")
        group_header(11, 2, "VIENTO", "$banda")
        group_header(13, 1, "VISIBILIDAD (km)", "$banda", rowspan=2)
        group_header(15, 10, "FENÓMENOS", "$banda")

        for index, (field, text, _ro) in enumerate(ROW_FIELDS):
            sub = QLabel(text)
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setWordWrap(True)
            sub.setStyleSheet(_qss(_SUB_HEADER_QSS))  # 14 labels: direct rule is fine
            grid.addWidget(sub, 1, 1 + index)

        tp_label = QLabel("T. PRES.")
        tp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tp_label.setToolTip("Tiempo presente")
        tp_label.setStyleSheet(_qss(_SUB_HEADER_QSS))
        grid.addWidget(tp_label, 0, 14, 2, 1)  # full header height = VISIBILIDAD

        for index, (_key, abbr, tooltip) in enumerate(FENOMENOS):
            grid.addWidget(_VerticalLabel(abbr, tooltip), 1, 15 + index)

        # OBS.: the observer' initials of THIS hour (owner round 23). It goes
        # after the phenomena lanes so no existing column moves.
        obs_label = QLabel("OBS.")
        obs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        obs_label.setToolTip("Iniciales del observador de la hora")
        obs_label.setWordWrap(True)
        obs_label.setStyleSheet(_qss(_SUB_HEADER_QSS))
        grid.addWidget(obs_label, 0, _OBS_COLUMN, 2, 1)

        for row in range(1, 25):
            self._build_data_row(grid, row)
        for col in range(1, 15):  # numeric + visibility columns share the stretch
            grid.setColumnStretch(col, 1)
        # A value like "1010.3" needs ~50 px with the padding; letting the
        # columns shrink below that clipped the numbers to "10.3". The grid
        # keeps its minimum and the sheet scrolls sideways when it must.
        for col in range(1, 15):
            grid.setColumnMinimumWidth(col, 62)
        for index in range(len(FENOMENOS)):  # fixed checkbox lanes
            grid.setColumnMinimumWidth(15 + index, 32)
        grid.setColumnMinimumWidth(_OBS_COLUMN, 62)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(grid_host)
        sheet_layout.addWidget(scroll)
        outer.addWidget(sheet_card, 1)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(central)

    def _card_host(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_qss(
            "QFrame { background-color: $superficie; border: 1px solid $borde;"
            "border-radius: 10px; }"
        ))
        return frame

    def _ro_meta_field(self) -> QLineEdit:
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setStyleSheet(_qss(
            "background-color: $panel_alt; border: 1px solid $borde;"
            "border-radius: 6px; padding: 4px 8px; color: $texto;"
            "font-size: 12px;"
        ))
        return edit

    def _build_data_row(self, grid: QGridLayout, row: int) -> None:
        main = (row - 2) % 3 == 0
        hour_label = QLabel(str(row))
        hour_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hour_label.setObjectName("hourMain" if main else "hourSub")
        grid.addWidget(hour_label, row + 1, 0)

        self.row_inputs.setdefault(row, {})
        for index, (field, _text, read_only) in enumerate(ROW_FIELDS):
            edit = QLineEdit()
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.setProperty("row", "main" if main else "sub")
            if read_only:
                edit.setProperty("ro", "true")
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
        vis_edit.setProperty("row", "main" if main else "sub")
        vis_edit.setMinimumHeight(26)
        self.row_inputs[row]["visibilidad"] = vis_edit
        grid.addWidget(vis_edit, row + 1, 13)

        tp_edit = QLineEdit()
        tp_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tp_edit.setProperty("row", "main" if main else "sub")
        tp_edit.setMinimumHeight(26)
        self.row_inputs[row]["tiempo_presente"] = tp_edit
        grid.addWidget(tp_edit, row + 1, 14)

        obs_edit = QLineEdit()
        obs_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        obs_edit.setProperty("row", "main" if main else "sub")
        obs_edit.setMinimumHeight(26)
        obs_edit.setToolTip("Iniciales del observador de la hora")
        self.row_inputs[row]["observador"] = obs_edit
        grid.addWidget(obs_edit, row + 1, _OBS_COLUMN)

        self.row_checks.setdefault(row, {})
        for index, (key, _abbr, tooltip) in enumerate(FENOMENOS):
            check = QCheckBox()
            check.setToolTip(tooltip)
            check.setCursor(Qt.CursorShape.PointingHandCursor)
            check.setObjectName("checkMain" if main else "checkSub")
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
        values["observador"] = (
            self.row_inputs[row]["observador"].text().strip()
        )
        return values

    def set_row(self, row: int, data: dict[str, Any]) -> None:
        for field, _text, _ro in ROW_FIELDS:
            value = data.get(field)
            if value is not None:
                self.row_inputs[row][field].setText(str(value))
        # visibility and T.PRES. live outside ROW_FIELDS (they have their own
        # columns), so they must be painted explicitly
        for field in ("visibilidad", "tiempo_presente", "observador"):
            value = data.get(field)
            widget = self.row_inputs[row].get(field)
            if value is not None and widget is not None:
                widget.setText(str(value))
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
        self._loading = True
        try:
            self._load_data_inner()
        finally:
            self._loading = False

    def _load_data_inner(self) -> None:
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
        """Transactional save via the service (autosave path, no button)."""
        try:
            cli_service.save_cli(
                self._conn, self.station, self.fecha, "cli3074",
                {"horas": self.rows_payload()},
            )
        except (cli_service.SaveError, ValueError, sqlite3.Error):
            _LOGGER.exception("CLI 3074 autosave falló")

    def _schedule_autosave(self, *args) -> None:
        if self._loading:
            return
        self._autosave_timer.start()
