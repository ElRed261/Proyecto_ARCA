"""SynopticPage — the queen screen (PRD F4).

PySide6 port of ``OLD/frontend/src/features/synoptic/pages/SynopticPage.jsx``
+ ``SaveConfirmModal.jsx`` + the beforeunload guard, backed by the Qt-free
``oms_core.services.synoptic`` service (ADR-03: only presentation here).

Behaviors ported from the oracle:

- 8 hour selector buttons with completion dots + ``hour: done/total campos``
  tooltips and an active-hour progress bar (honest hourCompletion);
- 17 base fields always, the 4 even-only fields (Tmax/Tmin ×24h) enabled
  only on 00Z/06Z/12Z/18Z;
- SYNOP group fields capped to 5 characters with a digits-and-'/' validator
  (server cap mirrored at the widget);
- meteo_6_2 (0CS DL DM DH) vs meteo_8_1 (56 DL DM DH) mutual exclusion plus
  cyclonic-season and iX gating from the oracle rows 6/8;
- Ctrl+S save shortcut, Alt+1..8 hour switch, tab-order navigation;
- pre-save review dialog listing partial hours + empty count (guardado
  honesto, SaveConfirmModal);
- structured save errors highlight the guilty field in red AND switch to its
  hour (parseFieldError contract);
- pressure normalization on focus-out (15.3 → 1015.3);
- observer name prefilled/remembered per station;
- closeEvent guard offering to save the in-progress draft bound to
  station+fecha (beforeunload equivalent, P4.4), with a debounced autosave
  while editing.

``build_synoptic_window`` is the screenshot/offscreen helper: it constructs
the window with sample data WITHOUT showing it (the caller takes the shot).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from PySide6.QtCore import QDate, QRegularExpression, Qt, QTimer
from PySide6.QtGui import QKeySequence, QRegularExpressionValidator, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

import oms_calc
from oms_core.db.repositories import stations as stations_repo
from oms_core.services import synoptic as synoptic_service

_AAXX = "AAXX"

#: Grid fields (key, label) — base always; t_* are the even-only extras.
_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("ts", "Ts (°C)"),
    ("th", "Th (°C)"),
    ("pres_est", "Pres. estación (hPa)"),
    ("p3", "P3 (hPa)"),
    ("p24", "P24 (hPa)"),
    ("viento_dir", "Viento dir (°)"),
    ("viento_vel", "Viento vel"),
    ("visibilidad", "Visibilidad"),
    ("ll", "LL (mm)"),
    ("meteo_2_1", "YYGG Iw"),
    ("meteo_4_irixhvv", "Ir iX H VV"),
    ("meteo_4_1", "N dd ff"),
    ("meteo_4_6", "7 ww W1W2"),
    ("meteo_6_2", "0CS DL DM DH"),
    ("meteo_8_1", "56 DL DM DH"),
    ("extra_8ns_1", "8Ns extra 1"),
    ("extra_8ns_2", "8Ns extra 2"),
    ("t_max", "T máx"),
    ("t_min", "T mín"),
    ("t_max_24h", "T máx 24h"),
    ("t_min_24h", "T mín 24h"),
    ("meteo_6_3", "1snTxTxTx"),
    ("meteo_6_4", "2snTnTnTn"),
    ("meteo_6_0", "8Nh CL CM CH"),
    ("meteo_6_5", "3E jjj"),
    ("meteo_6_6", "5 EEEjE"),
    ("meteo_8_0", "5n Fn Fn Fn"),
    ("meteo_8_3", "6RRRtr"),
    ("meteo_8_4", "7R24"),
    ("meteo_8_5", "8NsChs"),
    ("meteo_8_6", "8NsChs"),
    ("meteo_10_0", "8NsChs"),
    ("meteo_10_1", "8NsChs"),
    ("meteo_10_2", "9Sp SpSpSp"),
    ("meteo_10_3", "9Sp SpSpSp"),
    ("meteo_10_4", "9Sp SpSpSp"),
    ("meteo_10_5", "9Sp SpSpSp"),
    ("meteo_10_6", "9Sp SpSpSp"),
    ("meteo_12_0", "8NsChs"),
    ("meteo_12_1", "8NsChs"),
    ("meteo_12_2", "9Sp SpSpSp"),
    ("meteo_12_3", "9Sp SpSpSp"),
    ("meteo_12_4", "9Sp SpSpSp"),
    ("meteo_12_5", "9Sp SpSpSp"),
    ("meteo_12_6", "9Sp SpSpSp"),
    ("meteo_14_0", "8NsChs"),
    ("meteo_14_1", "8NsChs"),
    ("meteo_14_2", "9Sp SpSpSp"),
    ("meteo_14_3", "9Sp SpSpSp"),
    ("meteo_14_4", "9Sp SpSpSp"),
    ("meteo_14_5", "9Sp SpSpSp"),
    ("meteo_14_6", "9Sp SpSpSp"),
    ("meteo_16_0", "9Sp est"),
    ("meteo_16_1", "9Sp est"),
    ("meteo_16_2", "9Sp est"),
    ("meteo_16_3", "9Sp est"),
    ("meteo_16_4", "9Sp est"),
)

_EVEN_ONLY_KEYS = (
    "t_max", "t_min", "t_max_24h", "t_min_24h",
    "meteo_6_3", "meteo_6_4",  # manual 1sn/2sn slots (oracle even-hour inputs)
)
_PRESSURE_KEYS = ("pres_est", "p3", "p24")

#: Placeholders verbatim (meteoPlaceholders rows 2/4/6/8/10/12/14/16).
_PLACEHOLDERS: dict[str, str] = {
    "meteo_6_0": "8", "meteo_6_5": "3///",
    "meteo_8_1": "56", "meteo_8_3": "6", "meteo_8_4": "7",
    "meteo_8_5": "8", "meteo_8_6": "8",
    **{f"meteo_{r}_{i}": ("8..." if i < 2 else "9Sp…")
       for r in (10, 12, 14) for i in range(7)},
    **{f"meteo_16_{i}": "9Sp…" for i in range(5)},
    "ts": "°C", "let_barom": "Lectura...", "t_max": "°C",
    "t_max_24h": "°C", "th": "°C", "correc_temp": "0.0",
    "pres_est": "hPa", "p3": "hPa", "p24": "hPa",
    "t_min": "°C", "t_min_24h": "°C", "ll": "mm", "ll_24h": "mm",
}

#: Tooltips verbatim (oracle title= attributes; rows 10/12/14/16 have none).
_TOOLTIPS: dict[str, str] = {
    "meteo_6_0": "8NhCLCMCH: nubes",
    "meteo_6_5": "3Ejjj: estado del suelo",
    "meteo_6_6": "5EEEjE: evaporación",
    "meteo_8_0": "5nFnFnFn: insolación",
    "meteo_8_4": "7R24R24R24R24: precipitación 24h",
    "meteo_8_5": "8NsChshs: nube adicional",
    "meteo_8_6": "8NsChshs: nube adicional",
    "let_barom": "Lectura barométrica sin corregir",
    "correc_temp": "Corrección por temperatura",
    "pres_est": "Presión de la estación",
    "p3": "Presión hace 3 horas",
    "p24": "Presión hace 24 horas",
    "t_max": "Temperatura máxima",
    "t_min": "Temperatura mínima",
    "th": "Temperatura húmeda",
    "ll": "Precipitación (mm)",
    "ll_24h": "Precipitación 24h (mm)",
}

#: Derived read-only readouts of the "Cálculos de Estación" block.

_GROUP_RE = QRegularExpression(r"[0-9/]{0,5}")

_ERROR_QSS = """
SynopticPage QLineEdit[error="true"] { border: 2px solid #ef4444; }
SynopticPage QPushButton[fill="part"] { background: #fffbeb; }
SynopticPage QPushButton[fill="ok"] { background: #ecfdf5; }
SynopticPage QPushButton[fill="empty"] { background: #f8fafc; color: #94a3b8; }
SynopticPage QPushButton[active="true"] { border: 2px solid #2563eb; font-weight: bold; }
"""


def normalize_pressure(value: object) -> str:
    """synopticUtils.normalizePressure port: 15.3 → 1015.3 (short form)."""
    text = "" if value is None else str(value)
    if not text.strip():
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number < 100:
        return f"{1000 + number:.1f}"
    return text


def _initial_observations() -> dict[str, dict[str, str]]:
    return {hora: {} for hora in synoptic_service.HOURS}


def _repolish(widget: QWidget) -> None:
    style: QStyle = widget.style()
    style.unpolish(widget)
    style.polish(widget)


class SaveReviewDialog(QDialog):
    """Guardado honesto: partial hours listed before writing (SaveConfirmModal).

    Confirm proceeds ("Guardar igual"); reject goes back to review ("Revisar").
    """

    def __init__(self, review: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.review = review
        self.setWindowTitle("Hay horas sin completar")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Estas horas tienen datos parciales y se guardarán tal cual. Las horas\n"
            f"totalmente vacías ({review.get('empty_count', 0)}) se guardan vacías."
        ))
        partial = [
            f"{item['hora']}: {item['done']}/{item['total']} campos"
            for item in review.get("partial", [])
        ]
        self.rows = QLabel("\n".join(partial) or "(sin horas parciales)")
        layout.addWidget(self.rows)
        buttons = QHBoxLayout()
        cancel = QPushButton("Revisar")
        save = QPushButton("Guardar igual")
        save.setDefault(True)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def entries(self) -> list[str]:
        return self.rows.text().split("\n")


class DraftGuardDialog(QDialog):
    """closeEvent guard: save the draft / discard / cancel (beforeunload port)."""

    SAVE_DRAFT = QDialog.Accepted          # 1
    DISCARD = QDialog.Accepted + 1         # 2
    CANCEL = QDialog.Rejected              # 0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.decision: int = self.CANCEL
        self.setWindowTitle("Cambios sin guardar")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Hay cambios sin guardar en esta observación.\n¿Qué hacemos con el borrador?"
        ))
        buttons = QHBoxLayout()
        draft_btn = QPushButton("Guardar borrador")
        discard_btn = QPushButton("Descartar")
        cancel_btn = QPushButton("Cancelar")
        draft_btn.clicked.connect(lambda: self._decide(self.SAVE_DRAFT))
        discard_btn.clicked.connect(lambda: self._decide(self.DISCARD))
        cancel_btn.clicked.connect(lambda: self._decide(self.CANCEL))
        buttons.addWidget(draft_btn)
        buttons.addWidget(discard_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def _decide(self, decision: int) -> None:
        self.decision = decision
        self.done(decision)


class SynopticPage(QWidget):
    """The 8-hour observation grid with drafts, review and structured errors."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        config_dir: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._config_dir = config_dir
        self.observations = _initial_observations()
        self.active_hour = "06Z"
        self.results_per_hour: dict[str, dict[str, str]] = {}

        self._stations = {
            station.id: station for station in stations_repo.list_stations(conn)
        }
        self._draft_timer = QTimer(self)
        self._draft_timer.setSingleShot(True)
        self._draft_timer.setInterval(500)
        self._draft_timer.timeout.connect(self._flush_draft)
        self._dirty = False  # true only for user-entered edits (closeEvent guard)
        self._draft_guard_class = DraftGuardDialog  # test hook: swap for a stub

        self.hour_buttons: dict[str, QPushButton] = {}
        self.field_widgets: dict[str, QLineEdit] = {}
        self.readouts: dict[str, QLineEdit] = {}
        self.auto_cells: dict[str, QLineEdit] = {}

        self._build_ui()
        self._install_shortcuts()
        self.setStyleSheet(_ERROR_QSS)
        self._observer_prefill()

    # ------------------------------------------------------------ building

    def _grid_header(self, grid: QGridLayout, row: int, cells: list) -> None:
        """Slate header row (oracle tableHeader); cells are (text, span)."""
        col = 0
        for text, span in cells:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setStyleSheet(
                "background-color: #475569; color: white; font-weight: 600;"
                "font-size: 11px; padding: 6px; border-radius: 4px;"
            )
            grid.addWidget(label, row, col, 1, span)
            col += span

    def _grid_header_text(self, grid: QGridLayout, row: int, texts: list) -> None:
        """Slate header row from plain labels (one column each)."""
        self._grid_header(grid, row, [(text, 1) for text in texts])

    def _grid_const(self, grid: QGridLayout, row: int, col: int, text: str) -> None:
        """Readonly slate constant cell (AAXX/333/555, oracle constantClass)."""
        cell = QLineEdit(text)
        cell.setReadOnly(True)
        cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell.setStyleSheet(
            "background-color: #e2e8f0; color: #334155; font-weight: bold;"
            "border: 1px solid #94a3b8; border-radius: 4px;"
        )
        grid.addWidget(cell, row, col)

    def _grid_auto(self, grid: QGridLayout, row: int, col: int, key: str) -> None:
        """Readonly blue computed cell (oracle readonlyClass groups)."""
        cell = QLineEdit()
        cell.setReadOnly(True)
        cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell.setStyleSheet(
            "background-color: #ffffff; color: #1d4ed8; font-weight: bold;"
            "border: 1px solid #cbd5e1; border-radius: 4px;"
        )
        grid.addWidget(cell, row, col)
        self.auto_cells[key] = cell

    def _grid_field(self, grid: QGridLayout, row: int, col: int, key: str,
                    colspan: int = 1) -> None:
        widget = self._make_grid_input(key)
        grid.addWidget(widget, row, col, 1, colspan)

    def _build_ui(self) -> None:
        self.setWindowTitle("Observación Sinóptica")

        outer = QHBoxLayout(self)
        left = QVBoxLayout()

        # observer row (full width, oracle row 0) --------------------------
        self.observer_label = QLabel("Observador")
        self.observer_edit = QLineEdit()
        self.observer_edit.setPlaceholderText("Nombre del Observador...")
        self.observer_label.setBuddy(self.observer_edit)

        # station/date/alt live in the grid (row 2) and the calc panel;
        # the widgets stay alive here so setters/tests keep working
        self.station_combo = QComboBox()
        for station in self._stations.values():
            self.station_combo.addItem(f"{station.name} ({station.id})", station.id)
        # nothing selected until the user (or an observation) picks a station
        if self.station_combo.count():
            self.station_combo.setCurrentIndex(-1)

        self.fecha_edit = QDateEdit()
        self.fecha_edit.setDisplayFormat("dd/MM/yyyy")
        self.fecha_edit.setCalendarPopup(False)

        self.correc_alt_edit = QLineEdit()
        self.correc_alt_edit.setReadOnly(True)
        self.correc_alt_edit.setStyleSheet("background: #f1f5f9; color: #0f172a; font-weight: bold;")

        meta_grid = QGridLayout()
        meta_grid.addWidget(self.observer_label, 0, 0)
        meta_grid.addWidget(self.observer_edit, 0, 1, 1, 6)
        left.addLayout(meta_grid)

        # data grid: OBS grouped rows (header labels + inputs in order) ----
        grid_box = QGroupBox("Grilla meteorológica")
        grid = QGridLayout(grid_box)
        self._grid_header(grid, 0, [("MiMi MjMj", 1), ("YYGG Iw", 1),
                                    ("IIiii", 1), ("Fecha", 4)])
        self._grid_const(grid, 1, 0, "AAXX")
        self._grid_field(grid, 1, 1, "meteo_2_1")
        grid.addWidget(self.station_combo, 1, 2)
        grid.addWidget(self.fecha_edit, 1, 3, 1, 4)
        self._grid_header(grid, 2, [("Ir iX H VV", 1), ("N dd ff", 1),
                                    ("1sn T T T", 1), ("2sn Td Td Td", 1),
                                    ("4 P P P P", 1), ("5 a P P P", 1),
                                    ("7 ww W1 W2", 1)])
        self._grid_field(grid, 3, 0, "meteo_4_irixhvv")
        self._grid_field(grid, 3, 1, "meteo_4_1")
        self._grid_auto(grid, 3, 2, "grupo_1sn_ttt")
        self._grid_auto(grid, 3, 3, "grupo_2sn_td")
        self._grid_auto(grid, 3, 4, "grupo_4pppp")
        self._grid_auto(grid, 3, 5, "grupo_5appp")
        self._grid_field(grid, 3, 6, "meteo_4_6")
        self._grid_header(grid, 4, [("8Nh CL CM CH", 1), ("333", 1),
                                    ("0CS DL DM DH", 1), ("1sn Tx Tx Tx", 1),
                                    ("2sn Tn Tn Tn", 1), ("3E j j j", 1),
                                    ("5 EEEjE", 1)])
        self._grid_field(grid, 5, 0, "meteo_6_0")
        self._grid_const(grid, 5, 1, "333")
        self._grid_field(grid, 5, 2, "meteo_6_2")
        self._grid_field(grid, 5, 3, "meteo_6_3")
        self._grid_field(grid, 5, 4, "meteo_6_4")
        self._grid_field(grid, 5, 5, "meteo_6_5")
        self._grid_field(grid, 5, 6, "meteo_6_6")
        self._grid_header(grid, 6, [("5n Fn Fn Fn", 1), ("56DL DM DH", 1),
                                    ("58/59 P24P24P24", 1), ("6 RRR tr", 1),
                                    ("7R24R24R24R24", 1), ("8NsChs hs", 1),
                                    ("8NsChs hs", 1)])
        self._grid_field(grid, 7, 0, "meteo_8_0")
        self._grid_field(grid, 7, 1, "meteo_8_1")
        self._grid_auto(grid, 7, 2, "grupo_58_59_p24")
        self._grid_field(grid, 7, 3, "meteo_8_3")
        self._grid_field(grid, 7, 4, "meteo_8_4")
        self._grid_field(grid, 7, 5, "meteo_8_5")
        self._grid_field(grid, 7, 6, "meteo_8_6")
        for pos, row in enumerate((10, 12, 14)):
            base = 8 + pos * 2
            self._grid_header(grid, base, [("8NsChs hs", 1), ("8NsChs hs", 1),
                                           ("9Sp SpSpSp", 1), ("9Sp SpSpSp", 1),
                                           ("9Sp SpSpSp", 1), ("9Sp SpSpSp", 1),
                                           ("9Sp SpSpSp", 1)])
            for col in range(7):
                self._grid_field(grid, base + 1, col, f"meteo_{row}_{col}")
        self._grid_header(grid, 14, [("9Sp SpSpSp", 1), ("9Sp SpSpSp", 1),
                                     ("9Sp SpSpSp", 1), ("9Sp SpSpSp", 1),
                                     ("9Sp SpSpSp", 1), ("555", 1), ("29 UUU", 1)])
        for col in range(5):
            self._grid_field(grid, 15, col, f"meteo_16_{col}")
        self._grid_const(grid, 15, 5, "555")
        self._grid_auto(grid, 15, 6, "grupo_29uuu")
        self.grid = grid
        left.addWidget(grid_box, 1)

        # station calc panel: OBS 7-column grid (headers + raw inputs + --
        # computed readouts). Raw widgets are (re)created here via the same
        # factory, so validators, gating and blur behavior travel with them.
        calc_box = QGroupBox("Cálculos de Estación")
        calc = QGridLayout(calc_box)

        def chead(row: int, col: int, text: str, span: int = 1) -> None:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                "background-color: #475569; color: white; font-weight: 600;"
                "padding: 6px; border-radius: 4px;"
            )
            calc.addWidget(label, row, col, 1, span)

        def cfield(row: int, col: int, key: str) -> None:
            calc.addWidget(self._make_grid_input(key), row, col)

        def cro(row: int, col: int, store: dict, key: str) -> None:
            cell = QLineEdit()
            cell.setReadOnly(True)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(
                "background-color: #f1f5f9; color: #1d4ed8; font-weight: bold;"
                "border: 1px solid #cbd5e1; border-radius: 4px;"
            )
            calc.addWidget(cell, row, col)
            store[key] = cell

        chead(0, 0, "Cálculos de Estación", 2)
        chead(0, 2, "Presión de la Estación")
        chead(0, 3, "P 3 Horas")
        chead(0, 4, "P 24 Horas")
        chead(0, 5, "Máx. / Mín.")
        chead(0, 6, "Máx. / Mín. (24 H)")
        self._grid_header_text(calc, 1, ["Ts.", "Let. Barom.", "P 3",
                                          "P 24", "T Máx.", "T Máx."])
        cfield(1, 1, "ts")
        cfield(2, 2, "let_barom")
        cfield(2, 3, "p3")
        cfield(2, 4, "p24")
        cfield(2, 5, "t_max")
        cfield(2, 6, "t_max_24h")
        self._grid_header_text(calc, 3, ["Th.", "Correc. Temp.", "Let.",
                                          "Let.", "T Mín.", "T Mín."])
        cfield(3, 1, "th")
        cfield(4, 2, "correc_temp")
        cro(2, 1, self.readouts, "punto_rocio")
        cro(4, 3, self.auto_cells, "p3_let")
        cro(4, 4, self.auto_cells, "p24_let")
        cfield(4, 5, "t_min")
        cfield(4, 6, "t_min_24h")
        self._grid_header_text(calc, 5, ["Tv.", "Pres. Est.", "Dif.",
                                          "Dif.", "LL", "LL"])
        cro(5, 1, self.readouts, "tension_vapor")
        cfield(5, 2, "pres_est")
        cro(5, 3, self.auto_cells, "p3_dif")
        cro(5, 4, self.auto_cells, "p24_dif")
        cfield(5, 5, "ll")
        cfield(5, 6, "ll_24h")
        self._grid_header_text(calc, 6, ["Dif.", "Correc. Alt."])
        cro(6, 1, self.readouts, "diferencia")
        calc.addWidget(self.correc_alt_edit, 6, 2)
        self._grid_header_text(calc, 7, ["Hr.", "Pres. NMM"])
        cro(7, 1, self.readouts, "humedad_relativa")
        cro(7, 2, self.readouts, "pres_nmm")
        left.addWidget(calc_box)

        form_host = QWidget()
        form_host.setLayout(left)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)
        outer.addWidget(scroll, 1)

        # right panel: hours + actions -------------------------------------
        right = QVBoxLayout()
        hours_box = QGroupBox("Horas de Observación")  # also the selector card
        hours_grid = QGridLayout(hours_box)
        for index, hora in enumerate(synoptic_service.HOURS):
            row, col = divmod(index, 2)
            button = QPushButton(hora)
            button.setProperty("fill", "empty")
            button.clicked.connect(lambda _=False, h=hora: self.select_hour(h))
            self.hour_buttons[hora] = button
            hours_grid.addWidget(button, row, col)
        right.addWidget(hours_box)

        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("←")
        self.prev_btn.setToolTip("Hora anterior")
        self.prev_btn.clicked.connect(lambda: self._step_hour(-1))
        self.next_btn = QPushButton("→")
        self.next_btn.setToolTip("Hora siguiente")
        self.next_btn.clicked.connect(lambda: self._step_hour(1))
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.next_btn)
        right.addLayout(nav_row)

        self.progress_label = QLabel("0/21 campos")
        self.progress = QProgressBar()
        right.addWidget(self.progress_label)
        right.addWidget(self.progress)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #b91c1c; font-weight: bold;")
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #047857; font-weight: bold;")

        cli_box = QGroupBox("MÓDULOS CLI")
        cli_row = QHBoxLayout(cli_box)
        for module_key, label in (
            ("cli3074", "3074"),
            ("cli4074", "4074"),
            ("cli5074", "5074"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, m=module_key: self._open_cli(m))
            cli_row.addWidget(button)
        right.addWidget(cli_box)

        extra_box = QGroupBox("NUBOSIDAD EXTRA")
        extra_grid = QGridLayout(extra_box)
        for row, (key, label) in enumerate((
            ("extra_8ns_1", "GRUPO EXTRA 1 (8NS)"),
            ("extra_8ns_2", "GRUPO EXTRA 2 (8NS)"),
        )):
            title = QLabel(label)
            title.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #64748b;"
                "background: transparent;"
            )
            extra_grid.addWidget(title, row * 2, 0)
            extra_grid.addWidget(self._make_grid_input(key), row * 2 + 1, 0)
        right.addWidget(extra_box)

        self.save_btn = QPushButton("Guardar Observación")
        self.save_btn.setProperty("dark", True)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save_clicked)
        self.cargar_btn = QPushButton("Cargar JSON")
        self.cargar_btn.clicked.connect(self._load_json_file)
        save_row = QHBoxLayout()
        save_row.addWidget(self.save_btn)
        save_row.addWidget(self.cargar_btn)
        right.addWidget(self.error_label)
        right.addWidget(self.status_label)
        right.addLayout(save_row)
        right.addStretch(1)

        side_host = QWidget()
        side_host.setLayout(right)
        outer.addWidget(side_host, 0, Qt.AlignmentFlag.AlignTop)

        # wiring -----------------------------------------------------------
        self.station_combo.currentIndexChanged.connect(self._on_station_changed)
        self.fecha_edit.dateChanged.connect(self._on_date_changed)
        self.observer_edit.textChanged.connect(self._on_observer_changed)

    def _step_hour(self, delta: int) -> None:
        """Prev/next hour buttons (clamped at the ends, no wrap)."""
        hours = synoptic_service.HOURS
        try:
            index = hours.index(self.active_hour)
        except ValueError:
            return
        self.select_hour(hours[min(max(index + delta, 0), len(hours) - 1)])

    def _open_cli(self, module_key: str) -> None:
        """Open the generic CLI sheet dialog (OBS MÓDULOS CLI card)."""
        from oms_ui.pages.cli_dialog import CliModuleDialog

        if not self.station_id or not self.fecha_iso:
            self.clear_error_state()
            self.error_label.setText(
                "Elegí estación y fecha antes de abrir el módulo CLI"
            )
            return
        dialog = CliModuleDialog(
            self._conn, self.station_id, self.fecha_iso, module_key, self
        )
        if dialog.exec():
            try:
                dialog.save()
            except Exception as exc:  # noqa: BLE001 - service errors show inline
                self.error_label.setText(f"Error al guardar {module_key}: {exc}")
                return
            self.status_label.setText(f"{module_key} guardado")

    def _load_json_file(self, path: str | None = None) -> None:
        """Load a diario JSON file into the form (OBS Cargar JSON)."""
        from PySide6.QtWidgets import QFileDialog

        from oms_core.importer.parse import parse_daily

        if path is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self, "Cargar JSON", "", "JSON (*.json)"
            )
            if not chosen:
                return
            path = chosen
        try:
            with open(path, encoding="utf-8") as handle:
                import json as _json

                payload = _json.load(handle)
            doc = parse_daily(payload)
        except Exception as exc:  # noqa: BLE001 - bad files show inline
            self.error_label.setText(f"JSON inválido: {exc}")
            return
        if doc.station:
            self.set_station(doc.station)
        if doc.fecha_iso:
            self.set_date(doc.fecha_iso)
        count = 0
        for row in doc.horarias:
            hora = getattr(row, "hora", "")
            if hora not in synoptic_service.HOURS:
                continue
            datos = getattr(row, "datos", {}) or {}
            entry = self.observations.setdefault(hora, {})
            for key, value in datos.items():
                if value is None:
                    continue
                entry[str(key)] = str(value)
            observer = getattr(row, "observador", "") or ""
            if observer:
                entry["nombre_observador"] = str(observer)
            count += 1
        self._load_hour_into_fields()
        self._refresh_hour_mode()
        self.refresh_progress()
        self._update_readouts()
        self.status_label.setText(f"JSON cargado: {count} horas")

    def _make_grid_input(self, key: str) -> QLineEdit:
        widget = QLineEdit()
        if key.startswith(synoptic_service.GROUP_PREFIXES):
            widget.setValidator(QRegularExpressionValidator(_GROUP_RE, widget))
            widget.setMaxLength(synoptic_service.GROUP_MAX_LEN)
        placeholder = _PLACEHOLDERS.get(key)
        if placeholder:
            widget.setPlaceholderText(placeholder)
        tooltip = _TOOLTIPS.get(key)
        if tooltip:
            widget.setToolTip(tooltip)
        widget.setProperty("field_key", key)
        widget.textChanged.connect(lambda _text, k=key: self._on_field_changed(k))
        if key in _PRESSURE_KEYS:
            widget.editingFinished.connect(lambda k=key: self._on_pressure_blur(k))
        self.field_widgets[key] = widget
        return widget

    def _install_shortcuts(self) -> None:
        self._shortcuts: list[QShortcut] = [
            QShortcut(QKeySequence("Ctrl+S"), self, self._on_save_shortcut),
        ]
        for index in range(1, 9):
            self._shortcuts.append(QShortcut(
                QKeySequence(f"Alt+{index}"), self,
                lambda n=index: self._on_alt_hour(n),
            ))

    # ------------------------------------------------------------ accessors

    def field(self, key: str) -> QLineEdit:
        return self.field_widgets[key]

    @property
    def station_id(self) -> str | None:
        return self.station_combo.currentData()

    @property
    def fecha_iso(self) -> str | None:
        date: QDate = self.fecha_edit.date()
        if not date.isValid():
            return None
        return date.toString("yyyy-MM-dd")

    def set_station(self, station_id: str) -> None:
        index = self.station_combo.findData(station_id)
        if index < 0:
            self.station_combo.addItem(station_id, station_id)
            index = self.station_combo.findData(station_id)
        self.station_combo.setCurrentIndex(index)

    def set_date(self, iso: str) -> None:
        parts = iso.split("-")
        self.fecha_edit.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))

    def select_hour(self, hora: str) -> None:
        if hora not in synoptic_service.HOURS or hora == self.active_hour:
            return
        self._schedule_draft_autosave(force=True)
        self.active_hour = hora
        self._load_hour_into_fields()
        self._refresh_hour_mode()
        self.refresh_progress()
        self._update_readouts()

    def hour_value(self, hora: str, key: str) -> str:
        value = self.observations.get(hora, {}).get(key)
        return "" if value is None else str(value)

    def set_hour_value(self, hora: str, key: str, value: str) -> None:
        self.observations.setdefault(hora, {})[key] = value

    def active_hour_data(self) -> dict[str, str]:
        return dict(self.observations.get(self.active_hour) or {})

    def collect_day_data(self) -> dict[str, dict[str, str]]:
        return {hora: dict(self.observations.get(hora) or {}) for hora in synoptic_service.HOURS}

    # ------------------------------------------------------------ state

    def _mark_dirty(self) -> None:
        """User-entered edit: only these trigger the closeEvent draft guard."""
        self._dirty = True

    def _observer_prefill(self) -> None:
        """Remembered observer name for this station; a prefill is not a user edit."""
        station = self.station_id
        if not station:
            return
        widget = self.observer_edit
        widget.blockSignals(True)
        widget.setText(synoptic_service.observer_for(self._conn, station))
        widget.blockSignals(False)

    # ------------------------------------------------------------ field events

    def _on_field_changed(self, key: str) -> None:
        hour_data = self.observations.setdefault(self.active_hour, {})
        hour_data[key] = self.field_widgets[key].text()
        # Ir/iX digits derived from the combined group (oracle handleIrIxChange,
        # set-only like the oracle: shortening keeps the stale digit)
        if key == "meteo_4_irixhvv":
            value = hour_data.get(key, "")
            if len(value) >= 1:
                hour_data["ir"] = value[0]
            if len(value) >= 2:
                hour_data["ix"] = value[1]

        # clear the guilt of the field the user just touched (oracle
        # handleChange clears errorField on any edit)
        widget = self.field_widgets.get(key)
        if widget is not None and widget.property("error"):
            widget.setProperty("error", None)
            _repolish(widget)
            self.error_label.setText("")

        # meteo_6_2 (0CS) vs meteo_8_1 (56) mutual exclusion, verbatim oracle
        if key == "meteo_6_2" and hour_data.get("meteo_6_2", "").strip():
            hour_data["meteo_8_1"] = ""
            widget_81 = self.field_widgets.get("meteo_8_1")
            if widget_81 is not None and widget_81.text():
                widget_81.blockSignals(True)
                widget_81.setText("")
                widget_81.blockSignals(False)
        elif key == "meteo_8_1" and hour_data.get("meteo_8_1", "").strip():
            hour_data["meteo_6_2"] = ""
            widget_62 = self.field_widgets.get("meteo_6_2")
            if widget_62 is not None and widget_62.text():
                widget_62.blockSignals(True)
                widget_62.setText("")
                widget_62.blockSignals(False)

        self._mark_dirty()
        self._schedule_draft_autosave()
        self.refresh_progress()
        self._update_readouts()
        self._refresh_dynamic_states()

    def _on_pressure_blur(self, key: str) -> None:
        widget = self.field_widgets.get(key)
        if widget is None:
            return
        normalized = normalize_pressure(widget.text())
        if normalized != widget.text():
            widget.setText(normalized)  # re-enters _on_field_changed

    def _on_observer_changed(self, text: str) -> None:
        self.observations.setdefault(self.active_hour, {})["nombre_observador"] = text
        self._mark_dirty()
        self._schedule_draft_autosave()

    def _on_station_changed(self) -> None:
        station = self._stations.get(self.station_id or "")
        ch = "" if station is None else str(station.ch)
        self.correc_alt_edit.setText(ch)
        # the correction travels as hour data (oracle per-hour correc_alt)
        for hora in synoptic_service.HOURS:
            self.observations.setdefault(hora, {})["correc_alt"] = ch
        self._observer_prefill()
        self._schedule_draft_autosave()
        self._update_readouts()

    def _on_date_changed(self) -> None:
        self._refresh_dynamic_states()
        self._schedule_draft_autosave()

    def _on_save_shortcut(self) -> None:
        self.save_clicked()

    def _on_alt_hour(self, number: int) -> None:
        """Alt+1..8 handler body (the QShortcut wiring calls it directly)."""
        if 1 <= number <= len(synoptic_service.HOURS):
            self.select_hour(synoptic_service.HOURS[number - 1])

    # ------------------------------------------------------------ hour mode

    def _load_hour_into_fields(self) -> None:
        for key, widget in self.field_widgets.items():
            widget.blockSignals(True)
            widget.setText(self.hour_value(self.active_hour, key))
            widget.blockSignals(False)

    def _refresh_hour_mode(self) -> None:
        even = self.active_hour in synoptic_service.EVEN_HOURS
        for key, widget in self.field_widgets.items():
            if key in _EVEN_ONLY_KEYS:
                widget.setEnabled(even)
        self._refresh_dynamic_states()
        for hora, button in self.hour_buttons.items():
            button.setProperty("active", "true" if hora == self.active_hour else None)
            _repolish(button)

    def _refresh_dynamic_states(self) -> None:
        data = self.observations.get(self.active_hour) or {}

        irixhv = data.get("meteo_4_irixhvv") or ""
        ix = irixhv[1:2] if len(irixhv) >= 2 else ""
        weather_ok = oms_calc.should_include_weather(ix)
        widget_46 = self.field_widgets.get("meteo_4_6")
        if widget_46 is not None:
            widget_46.setEnabled(weather_ok)
            widget_46.setToolTip(
                "7wwW1W2: tiempo presente y pasado" if weather_ok
                else "Omitido (iX≠1,4)"
            )

        # 6RRRtr gated by Ir like the oracle (results.include_precipitation):
        # empty Ir disables, verbatim oracle behavior
        ir = irixhv[0:1] if len(irixhv) >= 1 else ""
        precip_ok = bool(ir) and oms_calc.should_include_precipitation(ir)
        widget_83 = self.field_widgets.get("meteo_8_3")
        if widget_83 is not None:
            widget_83.setEnabled(precip_ok)
            widget_83.setToolTip(
                "6RRRtr: precipitación" if precip_ok
                else "Omitido (Ir=3,4)"
            )

        # row 6/8 exclusions + cyclonic-season gate (June–November, oracle)
        fecha = self.fecha_iso or ""
        month = int(fecha[5:7]) if len(fecha) >= 7 else 0
        cyclonic = 6 <= month <= 11
        has_0cs = bool((data.get("meteo_6_2") or "").strip())
        has_56 = bool((data.get("meteo_8_1") or "").strip())
        widget_62 = self.field_widgets.get("meteo_6_2")
        widget_81 = self.field_widgets.get("meteo_8_1")
        if widget_62 is not None:
            widget_62.setEnabled(not has_56)
        if widget_81 is not None:
            widget_81.setEnabled(cyclonic and not has_0cs)
            widget_81.setToolTip(
                "56DLDMDH: nubes dirección" if (cyclonic and not has_0cs)
                else (
                    "Deshabilitado: fuera de temporada ciclónica (Junio - Noviembre)"
                    if not cyclonic
                    else "Deshabilitado: use 0CS DL DM DH en su lugar"
                )
            )

    # ------------------------------------------------------------ progress

    def refresh_progress(self) -> None:
        for hora, button in self.hour_buttons.items():
            completion = synoptic_service.hour_completion(self.observations.get(hora) or {}, hora)
            button.setToolTip(f"{hora}: {completion['done']}/{completion['total']} campos")
            fill = (
                "empty" if completion["done"] == 0
                else "ok" if completion["ratio"] == 1.0
                else "part"
            )
            if button.property("fill") != fill:
                button.setProperty("fill", fill)
                _repolish(button)
        active = synoptic_service.hour_completion(
            self.observations.get(self.active_hour) or {}, self.active_hour
        )
        self.progress.setRange(0, active["total"])
        self.progress.setValue(int(active["done"]))
        self.progress_label.setText(
            f"{self.active_hour}: {active['done']}/{active['total']} campos"
        )

    def _update_readouts(self) -> None:
        derived = self._derive_active()
        self.results_per_hour[self.active_hour] = derived
        for key, widget in self.readouts.items():
            widget.blockSignals(True)
            widget.setText(derived.get(key, ""))
            widget.blockSignals(False)
        self._update_autos()

    def _update_autos(self) -> None:
        """Fill the readonly SYNOP group cells (oracle row 4/8/16 autos)."""
        if not self.auto_cells:
            return
        data = self.active_hour_data()
        station = self._stations.get(self.station_id or "")
        correction = self.correc_alt_edit.text() or (
            "" if station is None else str(station.ch)
        )
        groups: dict = {}
        try:
            request = {
                "station_id": self.station_id,
                "correc_alt": data.get("correc_alt") or (correction or None),
                "ts": data.get("ts") or None,
                "th": data.get("th") or None,
                "pres_est": data.get("pres_est") or None,
                "p3": data.get("p3") or None,
                "p24": data.get("p24") or None,
                "ir": data.get("ir") or None,
                "ix": data.get("ix") or None,
            }
            payload = oms_calc.realizar_calculos_json(
                json.dumps(request), correction or None
            )
            loaded = json.loads(payload)
            if isinstance(loaded, dict):
                groups = loaded
        except Exception:  # noqa: BLE001 - autos stay empty on bad input
            groups = {}
        for key, widget in self.auto_cells.items():
            widget.blockSignals(True)
            widget.setText(groups.get(key, ""))
            widget.blockSignals(False)

    def _derive_active(self) -> dict[str, str]:
        data = self.active_hour_data()
        prev_hora = oms_calc.get_prev_hour(self.active_hour)
        prev_nddff = (self.observations.get(prev_hora) or {}).get("meteo_4_1", "")
        station = self._stations.get(self.station_id or "")
        correction = self.correc_alt_edit.text() or ("" if station is None else str(station.ch))
        json_text = oms_calc.recalculate_derived_fields_json(
            None,
            data.get("ts") or None,
            data.get("th") or None,
            data.get("pres_est") or None,
            data.get("p3") or None,
            data.get("p24") or None,
            data.get("correc_alt") or (correction or None),
            data.get("meteo_4_irixhvv") or None,
            data.get("meteo_4_6") or None,
            data.get("meteo_4_1") or None,
            prev_nddff or None,
            correction or None,
        )
        return json.loads(json_text)

    # ------------------------------------------------------------ save

    def clear_error_state(self) -> None:
        for widget in self.field_widgets.values():
            if widget.property("error"):
                widget.setProperty("error", None)
                _repolish(widget)
        self.error_label.setText("")

    def _highlight_guilty_field(self, error: synoptic_service.SaveError) -> None:
        culprit = (
            {"field": error.field, "hour": error.hour}
            if error.field and error.hour
            else synoptic_service.parse_field_error(str(error))
            or synoptic_service.parse_field_error(error.detail)
        )
        if culprit is None:
            self.error_label.setText(f"Error al guardar la observación — {error.detail}")
            return
        field, hour = culprit["field"], culprit["hour"]
        switched = hour != self.active_hour
        if switched and hour in synoptic_service.HOURS:
            self.select_hour(hour)
        widget = self.field_widgets.get(field)
        if widget is not None:
            widget.setProperty("error", True)
            _repolish(widget)
        if switched:
            self.error_label.setText(f"Revisá el campo {field} en {hour}")
        else:
            self.error_label.setText(f"Error al guardar la observación — {error.detail}")

    def save_clicked(self) -> None:
        """Save entry point: honest review first, then the transactional save."""
        if not self.station_id:
            self.clear_error_state()
            self.error_label.setText("Debe seleccionar una estación antes de guardar")
            return
        if not self.fecha_iso:
            self.clear_error_state()
            self.error_label.setText("Debe seleccionar una fecha antes de guardar")
            return
        review = synoptic_service.pre_save_review(self.collect_day_data())
        if review["partial"]:
            dialog = SaveReviewDialog(review, self)
            if dialog.exec() != QDialog.Accepted:
                return  # "Revisar": back to the grid, nothing saved
        self.do_save()

    def do_save(self) -> None:
        self.clear_error_state()
        station = self.station_id or ""
        fecha = self.fecha_iso or ""
        observer = self.observer_edit.text().strip() or None
        day_data = self.collect_day_data()
        for hora in synoptic_service.HOURS:
            data = dict(day_data.get(hora) or {})
            try:
                synoptic_service.save_hour(
                    self._conn, station, fecha, hora, data, observer=observer
                )
            except synoptic_service.SaveError as error:
                self._highlight_guilty_field(error)
                return  # stop on the first failure (oracle: whole day fails)
        synoptic_service.remember_observer(self._conn, station, self.observer_edit.text())
        self._discard_draft()
        self._dirty = False
        self._update_readouts_after_save(station, fecha)
        self.status_label.setText(
            f"Observación guardada. Fecha: {self.fecha_edit.date().toString('dd/MM/yyyy')}"
        )

    def _update_readouts_after_save(self, station: str, fecha: str) -> None:
        """Cache the derived values that just landed in the DB."""
        results: dict[str, dict[str, str]] = {}
        for hora in synoptic_service.HOURS:
            data = dict(self.observations.get(hora) or {})
            prev_hora = oms_calc.get_prev_hour(hora)
            prev_nddff = (self.observations.get(prev_hora) or {}).get("meteo_4_1", "")
            station_row = self._stations.get(station)
            correction = data.get("correc_alt") or (
                "" if station_row is None else str(station_row.ch)
            )
            results[hora] = json.loads(oms_calc.recalculate_derived_fields_json(
                None,
                data.get("ts") or None,
                data.get("th") or None,
                data.get("pres_est") or None,
                data.get("p3") or None,
                data.get("p24") or None,
                data.get("correc_alt") or None,
                data.get("meteo_4_irixhvv") or None,
                data.get("meteo_4_6") or None,
                data.get("meteo_4_1") or None,
                prev_nddff or None,
                correction or None,
            ))
        self.results_per_hour = results

    # ------------------------------------------------------------ drafts

    def _schedule_draft_autosave(self, force: bool = False) -> None:
        """Debounced P4.4 autosave: bound only when station+fecha are known."""
        if not force and not (self.station_id and self.fecha_iso):
            return
        if self.station_id and self.fecha_iso:
            self._draft_timer.start()

    def _flush_draft(self) -> None:
        station = self.station_id
        fecha = self.fecha_iso
        if not station or not fecha:
            return
        draft = synoptic_service.bind_draft(
            self.observations, self.active_hour, self.results_per_hour, station, fecha
        )
        synoptic_service.save_draft(self._config_dir, draft)
        self._dirty = False

    def _discard_draft(self) -> None:
        synoptic_service.clear_draft(self._config_dir)

    def _prefill_from_draft(self) -> bool:
        """Restore an existing valid draft for this station+fecha (oracle)."""
        draft = synoptic_service.load_draft(self._config_dir, self.station_id, self.fecha_iso)
        if draft is None:
            return False
        observations = draft.get("observations")
        if isinstance(observations, dict):
            for hora, hour_data in observations.items():
                if hora in synoptic_service.HOURS and isinstance(hour_data, dict):
                    self.observations[hora] = dict(hour_data)
        active = draft.get("active_hour")
        if active in synoptic_service.HOURS:
            self.active_hour = active
        results = draft.get("results_per_hour")
        if isinstance(results, dict):
            self.results_per_hour = results
        self._load_hour_into_fields()
        self._refresh_hour_mode()
        self.refresh_progress()
        self._update_readouts()
        self._dirty = False
        return True

    # ------------------------------------------------------------ close guard

    def closeEvent(self, event: Any) -> None:  # QCloseEvent
        """beforeunload equivalent: offer to save the unflushed draft (P4.4).

        Only user-entered edits arm the guard: programmatic station/date
        selection (initialization, screenshots) closes silently.
        """
        if not self._dirty:
            event.accept()
            return
        dialog = self._draft_guard_class(self)
        outcome = dialog.exec()
        if outcome == DraftGuardDialog.SAVE_DRAFT:
            self._flush_draft()
            event.accept()
        elif outcome == DraftGuardDialog.DISCARD:
            event.accept()
        else:
            event.ignore()


class SynopticWindow(QMainWindow):
    """Top-level holder so the page's closeEvent guard really runs."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        station: str | None = None,
        fecha: str | None = None,
        config_dir: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.page = SynopticPage(conn, config_dir=config_dir, parent=self)
        self.setCentralWidget(self.page)
        if station:
            self.page.set_station(station)
        if fecha:
            self.page.set_date(fecha)

    def closeEvent(self, event: Any) -> None:  # QCloseEvent
        self.page.closeEvent(event)


#: Sample data for the screenshot path (one complete even hour; plausible
#: values from a real 06Z observation, legacy corpus 78485 2025-12-08).
SAMPLE_HOUR_DATA = {
    "06Z": {
        "ts": "23.2", "th": "22.3", "pres_est": "1025.3", "p3": "1022.3",
        "p24": "1024.1", "viento_dir": "180", "viento_vel": "12",
        "visibilidad": "55", "ll": "", "meteo_2_1": "08030",
        "meteo_4_irixhvv": "32566", "meteo_4_1": "50102", "meteo_4_6": "72221",
        "meteo_6_2": "06000", "meteo_8_1": "", "extra_8ns_1": "81819",
        "extra_8ns_2": "85180", "t_max": "", "t_min": "", "t_max_24h": "",
        "t_min_24h": "",
    },
}


def build_synoptic_window(
    conn: sqlite3.Connection,
    *,
    station: str,
    fecha: str,
    config_dir: str | None = None,
) -> SynopticWindow:
    """Construct the queen screen with sample data WITHOUT showing it.

    The window stays hidden; the caller (parent) renders the screenshot
    offscreen. Uses the seeded station's real ch correction so the pressure
    readouts appear like a production day.
    """
    window = SynopticWindow(conn, station=station, fecha=fecha, config_dir=config_dir)
    page = window.page
    # P4.4 priority: a draft bound to this station+fecha beats the sample
    if not page._prefill_from_draft():
        for hora, data in SAMPLE_HOUR_DATA.items():
            page.observations[hora] = dict(data)
        page._load_hour_into_fields()
        page._refresh_hour_mode()
        page.refresh_progress()
        page._update_readouts()
    window.setWindowTitle(
        f"Observación Sinóptica — {station} "
        f"{page.fecha_edit.date().toString('dd/MM/yyyy')}"
    )
    return window
