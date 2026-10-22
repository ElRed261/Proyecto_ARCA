"""Cli5074View — extreme observations & phenomena daily sheet.

Embeddable view (owner round 5: no extra windows) shaped EXACTLY as
``IMG/CLI 5074.png`` (oracle ``Cli5074Page.jsx`` + ``getInitialState``):

- EXTREMOS band: grouped two-row header — TEMPERATURA °C (Máxima/Mínima),
  RÁFAGA MÁXIMA (DIR.-VEL. Dir/Vel + Hora Local HH:MM), HUM. REL. (%)
  Máx/Mín, PRESIÓN ESTACIÓN (hPa) Máxima/Minima, INSOLAC (HORA), RADIAC
  (CAL/CM²), LLUVIA (mm), EVAPOR. TANQUE A (mm), PUNTO DE ROCÍO (°C)
  (emerald, full height) and RECORRIDO DEL VIENTO (km) — one data row;
- HORARIO: fields as ROWS (Lect. Bar/Term. Anexo/Correc. Temp./Pres. Est./
  Correc. Alt./Pres. NMM) and the synoptic hours 2/8/14/20 as COLUMNS;
- TEMPERATURA SUBSUELO: (cm) 5..100 header over one (°C) data row;
- EVAP. 0.00 A 0.00 HL (Piche/Tanque C/Evaporígrafo) + INICIALES OBS.;
- FENÓMENOS: OBSERVACIONES Y DETALLES textarea + the 12-row table with
  HORA LOCAL (Horas/Minutos), RÁFAGAS DE VIENTO (dd 16-P / ff m/s),
  INTENSIDAD, FENÓMENOS METEOROLÓGICOS, INICIO (HH:MM, emerald), FINAL
  (HH:MM), DURACIÓN, INICIALES OBSERV.

The doc rides the transactional ``cli_service.save_cli`` under ``cli5074``
(stored shape = the sections dict of ``get_initial_state``). Autosave is
debounced and silent (owner round 8: no save button anywhere in the CLIs).
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_core.services import cli as cli_service
from oms_ui.icons import lucide_icon
from oms_ui.widgets import StyledComboBox

_LOGGER = logging.getLogger(__name__)

#: CLI autosave debounce. Test-injectable (suite waits the real path at
#: 50ms instead of 700ms).
AUTOSAVE_MS = 700

#: oracle getInitialState sections (field, header label, header color).
_HOURLY_ROWS = (2, 8, 14, 20)
_HOURLY_FIELDS: tuple[tuple[str, str], ...] = (
    ("lect_bar", "LECT. BAR (mmHg)"),
    ("term_anexo", "TERM. ANEXO (°C)"),
    ("correc_temp", "CORREC. TEMP."),
    ("pres_est", "PRES. EST. (hPa)"),
    ("correc_alt", "CORREC. ALT."),
    ("pres_nmm", "PRES. NMM (hPa)"),
)
_SUBSUELO_DEPTHS = (5, 10, 15, 20, 25, 50, 100)
_EVAP_FIELDS: tuple[tuple[str, str], ...] = (
    ("piche", "PICHE"), ("tanque_c", "TANQUE C."), ("evaporigrafo", "EVAPORÍGRAFO"),
)
_FENO_ROWS = 12
_FENO_GROUPS: tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...] = (
    ("HORA LOCAL", "#334155", 2, (("hora", "HORAS"), ("min", "MINUTOS"))),
    ("RÁFAGAS DE VIENTO", "#334155", 2, (
        ("raf_dir", "dd 16-P"), ("raf_vel", "ff (m/s)"),
    )),
    ("INTENSIDAD", "#334155", 1, (("intensidad", ""),)),
    ("FENÓMENOS METEOROLÓGICOS", "#334155", 1, (("fenomeno", ""),)),
    ("INICIO (HH:MM)", "#e11d48", 1, (("inicio", ""),)),
    ("FINAL (HH:MM)", "#e11d48", 1, (("final", ""),)),
    ("DURACIÓN", "#334155", 1, (("duracion", ""),)),
    ("INICIALES OBSERV.", "#334155", 1, (("iniciales", ""),)),
)

#: owner round 12: unit sub-headers (mm)/(°C) speak the module's red.
_UNIT_RED_QSS = (
    "background-color: #e11d48; color: #ffffff; font-weight: 600;"
    "font-size: 10px; padding: 4px 2px;"
)
_SECTION_QSS = (
    "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "border-radius: 10px; }"
)
#: owner round 10: the station/fecha card carries NO module color — the
#: 4074's clean line (only the group headers speak the identity).
_LABEL_QSS = (
    "color: #475569; font-weight: 600; font-size: 11px; background: transparent;"
)
_HEADER_QSS = (
    "background-color: {color}; color: #ffffff; font-weight: bold;"
    "font-size: 11px; padding: 5px 4px;"
)
_SUB_HEADER_QSS = (
    "background-color: #1f2937; color: #cbd5e1; font-weight: 600;"
    "font-size: 10px; padding: 4px 2px;"
)
_INPUT_QSS = (
    "QLineEdit { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "color: #1e293b; font-size: 12px; padding: 3px 6px; }"
    "QLineEdit:focus { border-color: #e11d48; background-color: #fff1f2; }"
)
_TEXT_QSS = (
    "QPlainTextEdit { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "color: #475569; font-size: 12px; border-radius: 6px; }"
)


def get_initial_state() -> dict[str, Any]:
    """Oracle getInitialState: empty sections in the stored doc's shape."""
    return {
        "hourly": {
            str(row): {field: "" for field, _t in _HOURLY_FIELDS}
            for row in _HOURLY_ROWS
        },
        "subsuelo": {f"d{d}": "" for d in _SUBSUELO_DEPTHS},
        "evaporimetros": {field: "" for field, _t in _EVAP_FIELDS},
        "iniciales_obs": "",
        "observaciones_manuales": "",
        "fenomenos": [
            {field: "" for field, _t in _FENO_GROUPS} if False else
            {field: "" for group in _FENO_GROUPS for field, _t in group[3]}
            for _ in range(_FENO_ROWS)
        ],
    }


class Cli5074View(QWidget):
    """CLI 5074 extremes & phenomena sheet, embedded in the view stack."""

    synop_hour_requested = Signal(str)
    back_requested = Signal()
    switch_requested = Signal(str)

    MODULE_KEY = "cli5074"
    TITLE = "CLI 5074 - OBSERVACIONES EXTREMAS Y FENÓMENOS"

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
        self.setWindowTitle(self.TITLE)
        # transparent: the page's hourly gradient shows through (round 6)
        self.setStyleSheet("background: transparent;")

        self.fields: dict[str, QLineEdit] = {}
        self.feno_inputs: dict[int, dict[str, QLineEdit]] = {}

        self._loading = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_MS)
        self._autosave_timer.timeout.connect(self.save_data)
        self._build()
        for widget in self.fields.values():
            if isinstance(widget, QLineEdit):  # el bridge conecta por su lado
                widget.textChanged.connect(self._schedule_autosave)
        self.load_data()

    # ------------------------------------------------------------ building

    def _build(self) -> None:
        central = QWidget()
        central.setStyleSheet("background: transparent;")
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
            "QPushButton:hover { background-color: #ffe4e6; }"
        )
        back_btn.clicked.connect(self.back_requested.emit)
        top.addWidget(back_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        title = QLabel(self.TITLE)
        title.setStyleSheet(
            # the CLI sheets sit on the hour's photograph: white title, like
            # the synoptic page over a photo
            "font-size: 18px; font-weight: 800; color: #ffffff;"
            "background: transparent;"
        )
        title.setWordWrap(True)
        top.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        self._build_tabs(top)
        self._build_ver_hora(top)
        outer.addLayout(top)

        self._build_station_card(outer)

        middle = QHBoxLayout()
        middle.setSpacing(10)
        self._build_hourly_card(middle)

        right = QVBoxLayout()
        right.setSpacing(10)
        self._build_subsuelo_card(right)
        bottom_right = QHBoxLayout()
        bottom_right.setSpacing(10)
        self._build_evap_card(bottom_right)
        self._build_iniciales_card(bottom_right)
        right.addLayout(bottom_right)
        middle.addLayout(right, 1)
        outer.addLayout(middle)

        self._build_fenomenos_card(outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        host.setLayout(outer)
        scroll.setWidget(host)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

    def _section_card(self, layout, title_text: str | None = None) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setStyleSheet(_SECTION_QSS)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(8)
        if title_text:
            title = QLabel(title_text)
            title.setStyleSheet(
                "font-weight: 800; font-size: 12px; color: #0f172a;"
                "background: transparent;"
            )
            card_layout.addWidget(title)
        layout.addWidget(card)
        return card, card_layout

    def _build_station_card(self, outer: QVBoxLayout) -> None:
        card = QFrame()
        card.setStyleSheet(_SECTION_QSS)  # neutral, like the 4074
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
        self.fecha_edit = QLineEdit(f"{self.fecha[8:]}/{self.fecha[5:7]}/{self.fecha[:4]}")
        self.fecha_edit.setReadOnly(True)
        self.fecha_edit.setStyleSheet(_INPUT_QSS)

        grid.addWidget(meta_label("ESTACIÓN:"), 0, 0)
        grid.addWidget(self.station_combo, 0, 1)
        grid.addWidget(meta_label("FECHA:"), 0, 2)
        grid.addWidget(self.fecha_edit, 0, 3)
        grid.setColumnStretch(4, 1)
        outer.addWidget(card)

    def _build_hourly_card(self, layout: QHBoxLayout) -> None:
        _card, card_layout = self._section_card(layout, "HORARIO")
        grid = QGridLayout()
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        card_layout.addLayout(grid)
        corner = QLabel("HORA LOCAL")
        corner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        corner.setStyleSheet(_HEADER_QSS.format(color="#1e293b"))
        grid.addWidget(corner, 0, 0)
        for col_index, row in enumerate(_HOURLY_ROWS):
            head = QLabel(str(row))
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setStyleSheet(_HEADER_QSS.format(color="#334155"))
            grid.addWidget(head, 0, 1 + col_index)
        self.hour_inputs: dict[int, dict[str, QLineEdit]] = {}
        for row_index, (field, label) in enumerate(_HOURLY_FIELDS):
            row_label = QLabel(label)
            row_label.setStyleSheet(_LABEL_QSS)
            grid.addWidget(row_label, 1 + row_index, 0)
            self.hour_inputs.setdefault(_HOURLY_ROWS[0], {})  # safety
            for col_index, hour in enumerate(_HOURLY_ROWS):
                edit = self._field_edit(f"hourly.{hour}.{field}")
                self.hour_inputs.setdefault(hour, {})[field] = edit
                grid.addWidget(edit, 1 + row_index, 1 + col_index)
        grid.setColumnStretch(0, 2)
        for col_index in range(len(_HOURLY_ROWS)):
            grid.setColumnStretch(1 + col_index, 1)

    def _build_subsuelo_card(self, right: QVBoxLayout) -> None:
        _card, layout = self._section_card(right, "TEMPERATURA SUBSUELO")
        grid = QGridLayout()
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        layout.addLayout(grid)
        cm_label = QLabel("(cm)")
        cm_label.setStyleSheet(_SUB_HEADER_QSS)
        grid.addWidget(cm_label, 0, 0)
        for col_index, depth in enumerate(_SUBSUELO_DEPTHS):
            head = QLabel(str(depth))
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setStyleSheet(_SUB_HEADER_QSS)
            grid.addWidget(head, 0, 1 + col_index)
        c_label = QLabel("(°C)")
        c_label.setStyleSheet(_UNIT_RED_QSS)
        grid.addWidget(c_label, 1, 0)
        for col_index, depth in enumerate(_SUBSUELO_DEPTHS):
            edit = self._field_edit(f"subsuelo.d{depth}")
            grid.addWidget(edit, 1, 1 + col_index)
        for c in range(len(_SUBSUELO_DEPTHS) + 1):
            grid.setColumnStretch(c, 1)

    def _build_evap_card(self, bottom_right: QHBoxLayout) -> None:
        _card, layout = self._section_card(bottom_right, "EVAP. 0.00 A 0.00 HL")
        grid = QGridLayout()
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        layout.addLayout(grid)
        for col_index, (field, label) in enumerate(_EVAP_FIELDS):
            head = QLabel(label)
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            head.setStyleSheet(_SUB_HEADER_QSS)
            grid.addWidget(head, 0, col_index)
            sub = QLabel("(mm)")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sub.setStyleSheet(_UNIT_RED_QSS)
            grid.addWidget(sub, 1, col_index)
            edit = self._field_edit(f"evaporimetros.{field}")
            grid.addWidget(edit, 2, col_index)
        for c in range(len(_EVAP_FIELDS)):
            grid.setColumnStretch(c, 1)

    def _build_iniciales_card(self, bottom_right: QHBoxLayout) -> None:
        # owner round 11: the header shrinks to a whisper so the OBSERVER
        # initials field is the protagonist (tall, roomy)
        _card, layout = self._section_card(bottom_right, None)
        label = QLabel("INICIALES OBS.")
        label.setStyleSheet(
            "font-weight: 800; font-size: 12px; color: #0f172a;"
            "background: transparent;"
        )
        layout.addWidget(label)
        edit = QLineEdit()
        edit.setStyleSheet(_INPUT_QSS)
        edit.setMinimumHeight(64)  # tall: the initials take the stage
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fields["iniciales_obs"] = edit
        layout.addWidget(edit)

    def _build_fenomenos_card(self, outer: QVBoxLayout) -> None:
        card = QFrame()
        card.setStyleSheet(_SECTION_QSS)
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 12)
        row.setSpacing(10)

        # OBSERVACIONES Y DETALLES textarea (oracle placeholder verbatim);
        # owner round 11: whisper header, the manual-detail area is the
        # protagonist and grows with the card
        left = QVBoxLayout()
        left_title = QLabel("OBSERVACIONES Y DETALLES DEL FENÓMENO")
        left_title.setStyleSheet(
            "font-weight: 800; font-size: 12px; color: #0f172a;"
            "background: transparent;"
        )
        left.addWidget(left_title)
        manual = QPlainTextEdit()
        manual.setPlaceholderText(
            "Espacio destinado a detallar más información de forma manual..."
        )
        manual.setStyleSheet(_TEXT_QSS)
        self.fields["observaciones_manuales"] = _PlainTextBridge(manual, self._schedule_autosave)
        left.addWidget(manual)
        row.addLayout(left, 1)

        # fenómenos table (groups + 12 rows)
        feno_grid = QGridLayout()
        feno_grid.setHorizontalSpacing(0)
        feno_grid.setVerticalSpacing(0)
        col = 0
        for text, color, span, fields in _FENO_GROUPS:
            no_sub = all(not sub for _f, sub in fields)
            header = QLabel(text)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setWordWrap(True)
            header.setStyleSheet(_HEADER_QSS.format(color=color))
            # sin subtítulo el header abarca ambas filas: sin hueco debajo
            feno_grid.addWidget(header, 0, col, 2 if no_sub else 1, span)
            for offset, (field, sub) in enumerate(fields):
                if sub:
                    sub_label = QLabel(sub)
                    sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    sub_label.setStyleSheet(_SUB_HEADER_QSS)
                    feno_grid.addWidget(sub_label, 1, col + offset)
                col_offset = col + offset
                for row_index in range(_FENO_ROWS):
                    edit = self._field_edit(f"fenomenos.{row_index}.{field}")
                    if field == "fenomeno":
                        edit.setPlaceholderText("Ej: Tormenta, Gr")
                    self.feno_inputs.setdefault(row_index, {})[field] = edit
                    feno_grid.addWidget(edit, 2 + row_index, col_offset)
            col += span
        for c in range(col):
            feno_grid.setColumnStretch(c, 1)
        row.addLayout(feno_grid, 3)
        outer.addWidget(card, 1)

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
                f"color: {'#e11d48' if active else '#475569'}; border: none;"
                "border-radius: 6px; padding: 6px 14px; font-size: 12px;"
                "font-weight: bold; min-height: 24px; }"
                "QPushButton:hover { background-color: #ecfdf5; }"
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
                "QPushButton:hover { color: #e11d48; background-color: #fff1f2; }"
            )
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, h=hour: self.synop_hour_requested.emit(h)
            )
            hour_row.addWidget(button)
        top.addWidget(hour_box, 0, Qt.AlignmentFlag.AlignVCenter)

    # ------------------------------------------------------------ behavior

    def _schedule_autosave(self, *args) -> None:
        if self._loading:
            return
        self._autosave_timer.start()

    def _field_edit(self, storage_key: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setStyleSheet(_INPUT_QSS)
        edit.setMinimumHeight(26)
        field = storage_key.split(".")[-1]
        edit.editingFinished.connect(
            lambda w=edit, f=field: self._normalize_edit(w, f)
        )
        self.fields[storage_key] = edit
        return edit

    def _normalize_edit(self, widget: QLineEdit, field: str) -> None:
        """Oracle enforceOneDecimal: one decimal + ceil hum fields."""
        value = widget.text().strip()
        normalized = cli_service.enforce_one_decimal(
            value, field,
            decimal_fields=cli_service.DECIMAL_FIELDS_5074,
            ceil_fields=cli_service.CEIL_FIELDS_5074,
        )
        if normalized != value:
            widget.setText("" if normalized is None else str(normalized))

    # ------------------------------------------------------------ data I/O

    def state(self) -> dict[str, Any]:
        """The stored-doc dict: sections + iniciales/manuales + fenómenos."""
        data = get_initial_state()
        for key, widget in self.fields.items():
            parts = key.split(".")
            if parts[0] == "fenomenos":
                data["fenomenos"][int(parts[1])][parts[2]] = widget.toPlainText().strip() \
                    if hasattr(widget, "toPlainText") else widget.text().strip()
            elif parts[0] == "hourly":
                data["hourly"][parts[1]][parts[2]] = widget.text().strip()
            elif len(parts) == 2:
                data[parts[0]][parts[1]] = widget.text().strip()
            else:
                data[key] = widget.toPlainText().strip() \
                    if hasattr(widget, "toPlainText") else widget.text().strip()
        return data

    def set_state(self, data: dict[str, Any]) -> None:
        for key, widget in self.fields.items():
            parts = key.split(".")
            if parts[0] == "fenomenos":
                rows = data.get("fenomenos") or []
                if isinstance(rows, list) and int(parts[1]) < len(rows):
                    value = rows[int(parts[1])].get(parts[2])
                    if value is not None:
                        widget.setPlainText(str(value)) if hasattr(widget, "setPlainText") else widget.setText(str(value))
            elif parts[0] == "hourly":
                row_data = (data.get("hourly") or {}).get(parts[1]) or {}
                value = row_data.get(parts[2])
                if value is not None:
                    widget.setText(str(value))
            elif len(parts) == 2:
                section = data.get(parts[0]) or {}
                value = section.get(parts[1])
                if value is not None:
                    widget.setText(str(value))
            else:
                value = data.get(key)
                if value is not None:
                    widget.setPlainText(str(value)) if hasattr(widget, "setPlainText") else widget.setText(str(value))

    def load_data(self) -> None:
        self._loading = True
        try:
            doc = cli_service.load_cli(self._conn, self.station, self.fecha, self.MODULE_KEY)
            if isinstance(doc, dict):
                self.set_state(doc)
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
                self._conn, self.station, self.fecha, self.MODULE_KEY, self.state()
            )
        except (cli_service.SaveError, ValueError, sqlite3.Error):
            _LOGGER.exception("CLI 5074 autosave falló")


class _PlainTextBridge:
    """Adapts a QPlainTextEdit to the fields dict (text()/setText contract)."""

    def __init__(self, editor: QPlainTextEdit, on_change) -> None:
        self._editor = editor
        self._editor.textChanged.connect(lambda: on_change())

    def text(self) -> str:
        return self._editor.toPlainText()

    def setText(self, text: str) -> None:
        self._editor.setPlainText(text)

    def setPlainText(self, text: str) -> None:
        self._editor.setPlainText(text)

    def toPlainText(self) -> str:
        return self._editor.toPlainText()
