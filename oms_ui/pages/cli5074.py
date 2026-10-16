"""Cli5074View — daily form sheet (max/min, subsuelo, evaporímetros...).

Embeddable view (owner round 5: no extra windows) ported from
``OLD/frontend/src/features/synoptic/cli5074/pages/Cli5074Page.jsx``:
sections DIARIO (15 fields), HORARIO (rows 2/8/14/20 × 6 pressure/thermograph
fields), SUBSUELO (d5..d100), EVAPORÍMETROS (piche/tanque/evaporigrafo),
FENÓMENOS (12 rows × hora/min/ráfaga/intensidad/fenomeno/inicio/final/
duración/iniciales) plus iniciales/manuales. The doc rides the transactional
``cli_service.save_cli`` under ``cli5074`` (the sections dict as-is).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

#: (section key, human label, field list) — oracle getInitialState verbatim.
_SECTIONS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    ("daily", "DIARIO", (
        ("temp_max", "T Máx"), ("temp_min", "T Mín"),
        ("rafaga_dir", "Ráfaga Dir"), ("rafaga_vel", "Ráfaga Vel"),
        ("rafaga_hora", "Ráfaga Hora"),
        ("hum_max", "HR Máx"), ("hum_min", "HR Mín"),
        ("pres_max", "P Máx"), ("pres_min", "P Mín"),
        ("insolac", "Insolac"), ("radiac", "Radiac"),
        ("lluvia", "Lluvia"), ("evap_tanque_a", "Evap. Tanque A"),
        ("punto_rocio", "Punto Rocío"), ("recorrido_viento", "Recorrido Viento"),
    )),
    ("subsuelo", "SUBSUELO (°C)", tuple(
        (f"d{depth}", f"{depth} cm") for depth in (5, 10, 15, 20, 25, 50, 100)
    )),
    ("evaporimetros", "EVAPORÍMETROS", (
        ("piche", "Piche"), ("tanque_c", "Tanque C"), ("evaporigrafo", "Evaporígrafo"),
    )),
)
_HOURLY_ROWS = (2, 8, 14, 20)
_HOURLY_FIELDS: tuple[tuple[str, str], ...] = (
    ("lect_bar", "Let. Bar."), ("term_anexo", "Term. Anexo"),
    ("correc_temp", "Correc. Temp."), ("pres_est", "Pres. Est."),
    ("correc_alt", "Correc. Alt."), ("pres_nmm", "Pres. NMM"),
)
_FENO_ROWS = 12
_FENO_FIELDS: tuple[tuple[str, str], ...] = (
    ("hora", "Hora"), ("min", "Min"), ("raf_dir", "Ráf Dir"),
    ("raf_vel", "Ráf Vel"), ("intensidad", "Intens."),
    ("fenomeno", "Fenómeno"), ("inicio", "Inicio"), ("final", "Final"),
    ("duracion", "Duración"), ("iniciales", "Iniciales"),
)
_SECTION_QSS = (
    "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "border-radius: 10px; }"
)
_LABEL_QSS = (
    "color: #475569; font-weight: 600; font-size: 11px; background: transparent;"
)
_INPUT_QSS = (
    "QLineEdit { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "color: #1e293b; font-size: 12px; padding: 3px 6px; }"
    "QLineEdit:focus { border-color: #38bdf8; background-color: #f0f9ff; }"
)
_SAVE_QSS = (
    "QPushButton { background-color: #0ea5e9; color: #ffffff;"
    "border: none; border-radius: 8px; padding: 7px 14px;"
    "font-weight: 700; font-size: 12px; }"
    "QPushButton:hover { background-color: #0284c7; }"
)


def get_initial_state() -> dict[str, Any]:
    """Oracle getInitialState: empty sections in the stored doc's shape."""
    return {
        "daily": {field: "" for field, _t in _SECTIONS[0][2]},
        "hourly": {
            str(row): {field: "" for field, _t in _HOURLY_FIELDS}
            for row in _HOURLY_ROWS
        },
        "subsuelo": {field: "" for field, _t in _SECTIONS[1][2]},
        "evaporimetros": {field: "" for field, _t in _SECTIONS[2][2]},
        "iniciales_obs": "",
        "observaciones_manuales": "",
        "fenomenos": [
            {field: "" for field, _t in _FENO_FIELDS} for _ in range(_FENO_ROWS)
        ],
    }


class Cli5074View(QWidget):
    """CLI 5074 daily form embedded in the synoptic page view stack."""

    synop_hour_requested = Signal(str)
    back_requested = Signal()
    switch_requested = Signal(str)

    MODULE_KEY = "cli5074"
    TITLE = "CLI 5074 - OBSERVACIONES DE SUPERFICIE"

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

        self.fields: dict[str, QLineEdit] = {}
        self.feno_inputs: list[dict[str, QLineEdit]] = []

        self._build()
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
            "font-size: 18px; font-weight: 800; color: #0f172a;"
            "background: transparent;"
        )
        title.setWordWrap(True)
        top.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch(1)
        self._build_tabs(top)
        self._build_ver_hora(top)

        self.save_btn = QPushButton("Guardar")
        self.save_btn.setIcon(lucide_icon("save", "#ffffff", 15))
        self.save_btn.setIconSize(QSize(15, 15))
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(_SAVE_QSS)
        self.save_btn.clicked.connect(self.save_data)
        top.addWidget(self.save_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(top)

        self._build_station_card(outer)
        for section_key, label, fields in _SECTIONS:
            self._build_section_card(outer, section_key, label, fields)

        # HORARIO (rows 2/8/14/20)
        hourly_card = QFrame()
        hourly_card.setStyleSheet(_SECTION_QSS)
        hourly_l = QVBoxLayout(hourly_card)
        hourly_l.setContentsMargins(14, 10, 14, 10)
        hourly_title = QLabel("HORARIO (2-8-14-20 LOCAL)")
        hourly_title.setStyleSheet(
            "font-weight: 800; font-size: 12px; color: #0f172a;"
            "background: transparent;"
        )
        hourly_l.addWidget(hourly_title)
        self.hour_inputs: dict[int, dict[str, QLineEdit]] = {}
        for row in _HOURLY_ROWS:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(6)
            row_label = QLabel(f"{row}:00")
            row_label.setStyleSheet(_LABEL_QSS)
            row_label.setMinimumWidth(48)
            row_layout.addWidget(row_label)
            self.hour_inputs[row] = {}
            for field, label in _HOURLY_FIELDS:
                edit = self._field_edit(f"hourly.{row}.{field}")
                self.hour_inputs[row][field] = edit
                row_layout.addWidget(QLabel(label))
                row_layout.addWidget(edit)
            hourly_l.addLayout(row_layout)
        outer.addWidget(hourly_card)

        # FENÓMENOS (12 rows × 10 fields)
        feno_card = QFrame()
        feno_card.setStyleSheet(_SECTION_QSS)
        feno_l = QVBoxLayout(feno_card)
        feno_l.setContentsMargins(14, 10, 14, 10)
        feno_title = QLabel("FENÓMENOS (12 registros)")
        feno_title.setStyleSheet(
            "font-weight: 800; font-size: 12px; color: #0f172a;"
            "background: transparent;"
        )
        feno_l.addWidget(feno_title)
        feno_grid = QGridLayout()
        feno_grid.setHorizontalSpacing(6)
        for col, (_field, label) in enumerate(_FENO_FIELDS):
            head = QLabel(label)
            head.setStyleSheet(_LABEL_QSS)
            feno_grid.addWidget(head, 0, col)
        for row in range(_FENO_ROWS):
            self.feno_inputs.append({})
            for col, (field, _label) in enumerate(_FENO_FIELDS):
                edit = self._field_edit(f"fenomenos.{row}.{field}")
                self.feno_inputs[row][field] = edit
                feno_grid.addWidget(edit, row + 1, col)
        feno_l.addLayout(feno_grid)
        outer.addWidget(feno_card, 1)

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
                "border-radius: 5px; padding: 3px 9px; font-size: 11px;"
                "font-weight: bold; }"
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
        for hour in ("00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"):
            button = QPushButton(hour)
            button.setStyleSheet(
                "QPushButton { background-color: #ffffff; color: #475569;"
                "border: none; border-radius: 5px; padding: 3px 7px;"
                "font-size: 11px; font-weight: bold; }"
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
        card.setStyleSheet(_SECTION_QSS)
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)

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

    def _build_section_card(
        self,
        outer: QVBoxLayout,
        section_key: str,
        label: str,
        fields: tuple[tuple[str, str], ...],
    ) -> None:
        card = QFrame()
        card.setStyleSheet(_SECTION_QSS)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel(label)
        title.setStyleSheet(
            "font-weight: 800; font-size: 12px; color: #0f172a;"
            "background: transparent;"
        )
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        for index, (field, field_label) in enumerate(fields):
            grid.addWidget(QLabel(field_label), index // 5, (index % 5) * 2)
            edit = self._field_edit(f"{section_key}.{field}")
            grid.addWidget(edit, index // 5, (index % 5) * 2 + 1)
        layout.addLayout(grid)
        outer.addWidget(card)

    # ------------------------------------------------------------ data I/O

    def state(self) -> dict[str, Any]:
        """The stored-doc dict: sections + iniciales/manuales + fenómenos."""
        data = get_initial_state()
        for key, widget in self.fields.items():
            parts = key.split(".")
            if parts[0] == "fenomenos":  # fenomenos.<row>.<field>
                data["fenomenos"][int(parts[1])][parts[2]] = widget.text().strip()
            elif parts[0] == "hourly":  # hourly.<row>.<field>
                data["hourly"][parts[1]][parts[2]] = widget.text().strip()
            elif len(parts) == 2:  # <section>.<field>
                data[parts[0]][parts[1]] = widget.text().strip()
            else:
                data[key] = widget.text().strip()
        return data

    def set_state(self, data: dict[str, Any]) -> None:
        for key, widget in self.fields.items():
            parts = key.split(".")
            if parts[0] == "fenomenos":
                rows = data.get("fenomenos") or []
                if isinstance(rows, list) and int(parts[1]) < len(rows):
                    value = rows[int(parts[1])].get(parts[2])
                    if value is not None:
                        widget.setText(str(value))
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
                    widget.setText(str(value))

    def load_data(self) -> None:
        doc = cli_service.load_cli(self._conn, self.station, self.fecha, self.MODULE_KEY)
        if isinstance(doc, dict):
            self.set_state(doc)

    def save_data(self) -> None:
        cli_service.save_cli(
            self._conn, self.station, self.fecha, self.MODULE_KEY, self.state()
        )
        self.save_btn.setToolTip("Guardado en el documento diario ✓")
