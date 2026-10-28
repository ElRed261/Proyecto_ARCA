"""SummaryPage — monthly summary screen (PRD F5 + redesign rounds).

PySide6 port of ``OLD/frontend/src/features/summary/pages/SummaryPage.jsx``
backed by the Qt-free ``oms_core.services.summary`` service (ADR-03: only
presentation here) and ``oms_core.services.excel_export``.

Redesign (round 13+), against ``OLD/IMG/Resumen Mensual.png``:

- page header with the verbatim title/subtitle and the pill actions;
  ``Tabla de Datos`` appears only once a document is loaded (the image shows
  the history state, where the oracle hides it as well);
- the violet load panel ``CARGA AUTOMÁTICA POR ESTACIÓN Y PERÍODO`` with the
  station/month/year selectors, the REAL ``Incluir correcciones (overlay)``
  switch and ``Cargar Mes``;
- ``Historial de Reportes Guardados`` as cards (period badge, station, days,
  SYNOP tag, delete + open) or the dashed empty state with the verbatim copy;
- the 31x21 table with the 21 VERBATIM Spanish headers inside the
  ``Tabla de Datos`` tab, with its meta bar and the Excel export;
- one single vertical scroll region for the page (no nested scroll boxes).

Behaviour is the F5 port unchanged: generation is one transaction, the
day-level correction mark stays on the ``Dias`` cell (only while the overlay
is on, so the mark never claims something the table does not show), and the
history is the SQLite ``kind='mensual'`` index (no OS trash files).
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_core.services import excel_export
from oms_core.services import summary as summary_service
from oms_ui.icons import lucide_icon
from oms_ui.widgets import StyledComboBox

#: Months of the year in the UI's Spanish labels (index = month number - 1).
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# -- module palette (the violet identity of the summary module) --------------
def _qss(plantilla: str) -> str:
    """Resuelve una plantilla QSS con la paleta del tema aplicado (S1)."""
    from string import Template

    from oms_ui import theme as _theme

    return Template(plantilla).substitute(_theme.palette_actual())

_VIOLET = "$violeta"
_VIOLET_DEEP = "$violeta_fuerte"
_VIOLET_LIGHT = "$violeta_suave"
_VIOLET_LINE = "$violeta_borde"
_INK = "$texto_alt"
_SLATE = "$suave_alt"
_FAINT = "$tenue"
_BORDER = "$borde"
_PAGE = "$panel_alt"
_EMERALD = "$ok"

#: The cell mark (background) for days with approved corrections.
_MARK = None  # se construye con la paleta activa

_TAB_HISTORY = 0
_TAB_TABLE = 1
_TAB_CHARTS = 2


def _label(text: str, *, size: int = 13, weight: int = 600,
           color: str = _INK, extra: str = "") -> QLabel:
    """A label with the inline styling this page uses everywhere.

    Page-level QSS descendant rules do not paint reliably in this app
    (learned in the OBS rounds), so every widget carries its own style.
    """
    widget = QLabel(text)
    widget.setStyleSheet(_qss(
        f"QLabel {{ font-size: {size}px; font-weight: {weight};"
        f" color: {color}; background: transparent; {extra} }}"
    ))
    return widget


def _pill_qss(active: bool) -> str:
    if active:
        return (
            f"QPushButton {{ background-color: {_VIOLET_LIGHT}; color: {_VIOLET};"
            f" border: 1px solid {_VIOLET_LINE}; border-radius: 8px;"
            " padding: 8px 14px; font-size: 13px; font-weight: 600; }"
        )
    return (
        "QPushButton { background-color: $superficie; color: $suave;"
        f" border: 1px solid {_BORDER}; border-radius: 8px;"
        " padding: 8px 14px; font-size: 13px; font-weight: 600; }"
        "QPushButton:hover { background-color: $panel_alt; }"
    )


def _filled_qss(color: str = _VIOLET, hover: str = _VIOLET_DEEP) -> str:
    return _qss(
        f"QPushButton {{ background-color: {color}; color: $superficie;"
        " border: none; border-radius: 10px; padding: 10px 18px;"
        " font-size: 13px; font-weight: 700; }"
        f"QPushButton:hover {{ background-color: {hover}; }}"
        "QPushButton:disabled { background-color: $borde; color: $tenue; }"
    )


class _ClickableFrame(QFrame):
    """A card that reports clicks (the history entries open on click)."""

    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class SummaryTableModel(QAbstractTableModel):
    """31x21 model over the generated document's ``datos`` rows.

    The 21 headers are the verbatim oracle strings; numbers keep their type
    for the export path (Qt.EditRole) and render as-is for the screen; nulls
    render empty. The corrections indicator lives on the Dias cell
    (background + tooltip count), never altering the displayed values.
    """

    def __init__(self, doc: dict[str, Any] | None = None,
                 corrections: dict[int, int] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = list((doc or {}).get("datos") or [])
        self._corrections = dict(corrections or {})

    def set_document(self, doc: dict[str, Any],
                     corrections: dict[int, int] | None = None) -> None:
        self.beginResetModel()
        self._rows = list((doc or {}).get("datos") or [])
        self._corrections = dict(corrections or {})
        self.endResetModel()

    def corrections(self) -> dict[int, int]:
        return dict(self._corrections)

    # -- model contract ------------------------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return len(summary_service.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return summary_service.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        header = summary_service.HEADERS[index.column()]
        row = self._rows[index.row()]
        value = row.get(header)
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if value is None or value == "":
                return "" if role == Qt.ItemDataRole.DisplayRole else None
            if role == Qt.ItemDataRole.DisplayRole:
                return summary_service.display_value(header, value)
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole and header != "Dias":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.BackgroundRole:
            day = self._day_of_row(index.row())
            if day in self._corrections:
                return QBrush(QColor(_qss("$ambar_fondo")))
        if role == Qt.ItemDataRole.ToolTipRole:
            day = self._day_of_row(index.row())
            count = self._corrections.get(day)
            if count:
                return f"Correcciones aplicadas: {count}"
        return None

    def _day_of_row(self, row_index: int) -> int:
        try:
            return int(str(self._rows[row_index].get("Dias", ""))[-2:])
        except (ValueError, TypeError):
            return row_index + 1


class SummaryPage(QWidget):
    """The monthly summary screen (station/month/year -> generate -> table)."""

    def __init__(self, conn: sqlite3.Connection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.conn = conn
        self.doc: dict[str, Any] | None = None
        self._corrections: dict[int, int] = {}
        self.history_entries: list[dict[str, Any]] = []
        self.history_cards: list[QWidget] = []

        # -- selectors (public names: the tests drive them directly) ---------
        self.station_combo = StyledComboBox()
        for station in stations_repo.list_stations(conn, include_inactive=True):
            # the oracle shows the station NAME and keeps the key as value
            self.station_combo.addItem(station.name or station.id, station.id)
        self.station_combo.setMinimumWidth(200)

        self.month_combo = StyledComboBox()
        for name in MONTHS:
            self.month_combo.addItem(name)
        self.month_combo.setFixedWidth(150)

        self.year_combo = StyledComboBox()
        current_year = _dt.date.today().year
        for year in range(2020, current_year + 3):
            self.year_combo.addItem(str(year))
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.setFixedWidth(120)

        self.include_corrections = QCheckBox("Incluir correcciones (overlay)")
        self.include_corrections.setChecked(False)  # the image shows it off

        self.generate_button = QPushButton("Cargar Mes")
        self.generate_button.setIcon(lucide_icon("plus", _qss("$superficie"), 16))
        self.generate_button.setStyleSheet(_qss(_filled_qss()))
        self.generate_button.setFixedHeight(42)

        self.manual_button = QPushButton("Generar Manual")
        self.manual_button.setIcon(lucide_icon("plus", _qss("$superficie"), 16))
        self.manual_button.setStyleSheet(_qss(_filled_qss()))

        self.history_tab_button = QPushButton("Historial")
        self.history_tab_button.setIcon(lucide_icon("clock", _VIOLET, 16))
        self.table_tab_button = QPushButton("Tabla de Datos")
        self.table_tab_button.setIcon(lucide_icon("table", _qss("$suave"), 16))
        self.charts_tab_button = QPushButton("Gráficos")
        self.charts_tab_button.setIcon(lucide_icon("bar-chart-3", _qss("$suave"), 16))
        self._tab_buttons = (
            self.history_tab_button, self.table_tab_button, self.charts_tab_button,
        )
        for button in self._tab_buttons:
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.export_button = QPushButton("Exportar Excel")
        self.export_button.setIcon(lucide_icon("download", _qss("$superficie"), 16))
        self.export_button.setStyleSheet(_qss(_filled_qss(_EMERALD, "$ok_texto")))

        self.table = QTableView()
        self.model = SummaryTableModel()
        self.table.setModel(self.model)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(_qss(
            "QProgressBar { background-color: $superficie; border: none;"
            " border-radius: 3px; }"
            f"QProgressBar::chunk {{ background-color: {_VIOLET};"
            " border-radius: 3px; }"
        ))

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(_qss(
            f"QLabel {{ font-size: 12px; font-weight: 600; color: {_EMERALD};"
            " background: transparent; }"
        ))

        self._build_ui()
        self._switch_tab(_TAB_HISTORY)
        self.refresh_history()
        self._sync_tab_visibility()  # no document yet: history tab only

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        self.setWindowTitle("Resumen Mensual SYNOP")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(_qss(
            f"QScrollArea {{ background-color: {_PAGE}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background-color: {_PAGE}; }}"
        ))
        scroll.viewport().setStyleSheet(_qss(f"background-color: {_PAGE};"))

        content = QWidget()
        content.setStyleSheet(_qss(f"background-color: {_PAGE};"))
        page = QVBoxLayout(content)
        page.setContentsMargins(32, 24, 32, 32)
        page.setSpacing(20)
        page.addLayout(self._build_header())
        page.addWidget(self._build_card())
        page.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll)

        self.generate_button.clicked.connect(self.on_generate)
        self.manual_button.clicked.connect(self.on_generate_manual)
        self.export_button.clicked.connect(self.on_export)
        self.history_tab_button.clicked.connect(lambda: self._switch_tab(_TAB_HISTORY))
        self.table_tab_button.clicked.connect(lambda: self._switch_tab(_TAB_TABLE))
        self.charts_tab_button.clicked.connect(lambda: self._switch_tab(_TAB_CHARTS))

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(_label("Resumen Mensual SYNOP", size=26, weight=800))
        title_box.addWidget(_label(
            "Generación y visualización de resúmenes climáticos",
            size=14, weight=400, color=_SLATE,
        ))
        row.addLayout(title_box)
        row.addStretch(1)

        row.addWidget(self.history_tab_button)
        row.addWidget(self.table_tab_button)
        row.addWidget(self.charts_tab_button)
        row.addSpacing(4)
        row.addWidget(self.manual_button)
        return row

    def _build_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(_qss(
            "QFrame#card { background-color: $superficie;"
            f" border: 1px solid {_BORDER}; border-radius: 16px; }}"
        ))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addWidget(self._build_panel())
        layout.addWidget(self.status_label)
        layout.addSpacing(24)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_history_view())   # _TAB_HISTORY
        self.stack.addWidget(self._build_table_view())     # _TAB_TABLE
        # _TAB_CHARTS lands in T3; the pill stays hidden until then.
        self.charts_tab_button.setVisible(False)
        layout.addWidget(self.stack)
        return card

    def _build_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(_qss(
            "QFrame#panel { background-color: $violeta_suave;"
            f" border: 1px solid {_VIOLET_LINE}; border-radius: 16px; }}"
        ))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(8)
        gauge = QLabel()
        gauge.setPixmap(lucide_icon("gauge", _VIOLET, 16).pixmap(QSize(16, 16)))
        gauge.setStyleSheet("background: transparent;")
        head.addWidget(gauge)
        head.addWidget(_label(
            "CARGA AUTOMÁTICA POR ESTACIÓN Y PERÍODO",
            size=11, weight=800, color="$violeta_fuerte", extra="",
        ))
        head.addStretch(1)
        layout.addLayout(head)

        fields = QHBoxLayout()
        fields.setSpacing(16)
        fields.addLayout(self._field("Estación Meteorológica", self.station_combo), 1)
        fields.addLayout(self._field("Mes", self.month_combo))
        fields.addLayout(self._field("Año", self.year_combo))
        self.include_corrections.setStyleSheet(_qss(
            f"QCheckBox {{ font-size: 13px; font-weight: 700; color: $texto;"
            " background: transparent; spacing: 8px; }"
            f"QCheckBox::indicator {{ width: 17px; height: 17px;"
            f" border: 1px solid $borde_input; border-radius: 4px;"
            " background-color: $superficie; }"
            f"QCheckBox::indicator:checked {{ background-color: {_VIOLET};"
            " border-color: $violeta_fuerte; }"
        ))
        fields.addWidget(self.include_corrections, 0, Qt.AlignmentFlag.AlignBottom)
        fields.addWidget(self.generate_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(fields)
        layout.addWidget(self.progress)
        self.progress.hide()
        return panel

    def _field(self, caption: str, widget: QWidget) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(6)
        box.addWidget(_label(caption, size=12, weight=600, color=_SLATE))
        if isinstance(widget, StyledComboBox):
            widget.setStyleSheet(_qss(
                f"QComboBox {{ background-color: $superficie; border: 1px solid"
                f" {_BORDER}; border-radius: 10px; padding: 8px 12px;"
                f" font-size: 13px; font-weight: 500; color: {_INK}; }}"
                "QComboBox::drop-down { border: none; width: 22px; }"
            ))
        box.addWidget(widget)
        return box

    def _build_history_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        section = QHBoxLayout()
        section.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(lucide_icon("clock", _VIOLET, 20).pixmap(QSize(20, 20)))
        icon.setStyleSheet("background: transparent;")
        section.addWidget(icon)
        section.addWidget(_label("Historial de Reportes Guardados", size=20, weight=900))
        section.addStretch(1)
        layout.addLayout(section)
        layout.addSpacing(14)

        self.empty_state = QFrame()
        self.empty_state.setObjectName("empty")
        self.empty_state.setStyleSheet(_qss(
            "QFrame#empty { background-color: $panel_alt;"
            " border: 1px dashed $borde_input; border-radius: 16px; }"
        ))
        empty = QVBoxLayout(self.empty_state)
        empty.setContentsMargins(32, 48, 32, 48)
        empty.setSpacing(12)
        empty.addStretch(1)
        icon = QLabel()
        icon.setPixmap(lucide_icon("file-warning", _FAINT, 48).pixmap(QSize(48, 48)))
        icon.setStyleSheet("background: transparent;")
        empty.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addWidget(_label("No hay resúmenes", size=18, weight=900),
                        0, Qt.AlignmentFlag.AlignHCenter)
        body = _label(
            "Selecciona una estación y un período arriba para generar tu "
            "primer resumen mensual, o importa archivos manualmente.",
            size=14, weight=400, color=_SLATE,
        )
        body.setWordWrap(True)
        body.setFixedWidth(440)
        body.setMinimumHeight(66)  # three wrapped lines, never clipped
        empty.addWidget(body, 0, Qt.AlignmentFlag.AlignHCenter)
        empty.addStretch(1)

        self.history_box = QWidget()
        self.history_box.setStyleSheet("background: transparent;")
        self.history_layout = QVBoxLayout(self.history_box)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(12)

        layout.addWidget(self.empty_state)
        layout.addWidget(self.history_box)
        return view

    def _build_table_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        meta = QHBoxLayout()
        meta.setSpacing(16)
        self.meta_title = _label("", size=17, weight=800)
        self.meta_detail = _label("", size=13, weight=500, color=_SLATE)
        meta.addWidget(self.meta_title)
        meta.addWidget(self.meta_detail)
        meta.addStretch(1)
        meta.addWidget(self.export_button)
        layout.addLayout(meta)

        self.table.setMinimumHeight(520)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setStyleSheet(_qss(
            f"QTableView {{ background-color: $superficie; border: 1px solid {_BORDER};"
            " border-radius: 12px; gridline-color: $borde;"
            f" font-size: 12px; color: {_INK}; selection-background-color: $violeta_borde;"
            " selection-color: $texto_alt; }"
            "QHeaderView::section { background-color: $banda; color: $superficie;"
            " font-size: 11px; font-weight: 800; padding: 8px 6px; border: none;"
            " border-right: 1px solid $texto; }"
            "QTableView QTableCornerButton::section { background-color: $banda; }"
        ))
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.table, 1)
        return view

    # ------------------------------------------------------------ tab state

    def _switch_tab(self, index: int) -> None:
        if index == _TAB_CHARTS:  # no charts view yet (T3)
            index = _TAB_HISTORY
        self.stack.setCurrentIndex(index)
        for position, button in enumerate(self._tab_buttons):
            button.setStyleSheet(_qss(_pill_qss(position == index)))

    def _sync_tab_visibility(self) -> None:
        """Tabla de Datos exists only with a document (oracle + image)."""
        has_doc = self.doc is not None
        self.table_tab_button.setVisible(has_doc)
        if not has_doc and self.stack.currentIndex() != _TAB_HISTORY:
            self._switch_tab(_TAB_HISTORY)

    # ------------------------------------------------------------ handlers

    def on_generate(self) -> None:
        station = self.station_combo.currentData() or self.station_combo.currentText()
        if not station:
            return
        year = int(self.year_combo.currentText() or 0)
        month = self.month_combo.currentIndex() + 1
        overlay = self.include_corrections.isChecked()
        self._begin_progress()
        try:
            self.doc = summary_service.generate_month(
                self.conn, station, year, month, overlay=overlay)
        except (summary_service.SummaryError, sqlite3.Error) as exc:
            self._status(str(exc), error=True)
            return
        finally:
            self._end_progress()
        self._corrections = (
            summary_service.corrections_by_day(self.conn, station, year, month)
            if overlay else {}
        )
        self.model.set_document(self.doc, self._corrections)
        self._refresh_meta()
        marked = sum(1 for count in self._corrections.values() if count)
        self._status(
            f"Resumen generado exitosamente ({self.doc['meta']['total_dias']} días,"
            f" {marked} con correcciones)"
        )
        self.refresh_history()
        self._sync_tab_visibility()
        self._switch_tab(_TAB_TABLE)

    def on_generate_manual(self) -> None:
        """``Generar Manual`` — the oracle imports observation files here.

        Until the file-import port lands (T4 in ``odd/tasks/resumen-mensual.md``)
        the button generates the selected month on demand, never a dead
        placeholder.
        """
        self.on_generate()

    def on_export(self) -> None:
        if self.doc is None:
            self._status("Genera o carga un resumen antes de exportar", error=True)
            return
        meta = self.doc.get("meta") or {}
        default = (
            f"resumen_{meta.get('estacion', 'resumen')}_"
            f"{meta.get('periodo', '').replace('/', '_')}.xlsx"
        )
        path, _filter = QFileDialog.getSaveFileName(
            self, "Exportar a Excel", default, "Excel (*.xlsx)"
        )
        if not path:
            return
        self.export_doc_to(path)

    def export_doc_to(self, path) -> str:
        """Write the current doc to ``path``; shared by the button handler
        and the tests (no native dialogs in the flow they exercise)."""
        out = excel_export.export_to_excel(self.doc, path)
        self._status(f"Exportado a Excel correctamente: {out}")
        return str(out)

    def on_delete(self, entry: dict[str, Any] | None = None) -> None:
        if entry is None:
            return
        confirmed = QMessageBox.question(
            self, "Enviar a la papelera",
            "¿Está seguro que desea enviar a la papelera el resumen generado "
            f"para la estación \"{entry['station']}\" del período "
            f"\"{entry['period']}\"?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        summary_service.delete_doc(
            self.conn, entry["station"], entry["year"], entry["month"])
        if self.doc is not None:
            meta = self.doc.get("meta") or {}
            if (meta.get("estacion") == entry["station"]
                    and meta.get("periodo") == entry["period"]):
                self.doc = None
                self.model.set_document({})
                self._corrections = {}
        self.refresh_history()
        self._sync_tab_visibility()
        self._status("Resumen enviado a la papelera exitosamente")

    def open_history_entry(self, index: int) -> None:
        """Open the N-th history card (what clicking a card does)."""
        if not 0 <= index < len(self.history_entries):
            return
        entry = self.history_entries[index]
        self.doc = summary_service.load_doc(
            self.conn, entry["station"], entry["year"], entry["month"])
        if self.doc is None:
            return
        overlay = self.include_corrections.isChecked()
        self._corrections = (
            summary_service.corrections_by_day(
                self.conn, entry["station"], entry["year"], entry["month"])
            if overlay else {}
        )
        self.model.set_document(self.doc, self._corrections)
        self._refresh_meta()
        self._status(f"Resumen cargado: {entry['station']} · {entry['period']}")
        self._sync_tab_visibility()
        self._switch_tab(_TAB_TABLE)

    # -------------------------------------------------------------- helpers

    def refresh_history(self) -> None:
        self.history_entries = list(summary_service.list_history(self.conn))
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.history_cards = []
        for index, entry in enumerate(self.history_entries):
            card = self._make_card(entry, index)
            self.history_cards.append(card)
            self.history_layout.addWidget(card)
        self.history_layout.addStretch(1)

        has_entries = bool(self.history_entries)
        self.empty_state.setVisible(not has_entries)
        self.history_box.setVisible(has_entries)

    def _make_card(self, entry: dict[str, Any], index: int) -> QWidget:
        card = _ClickableFrame()
        card.setObjectName("historyCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(_qss(
            "QFrame#historyCard { background-color: $superficie;"
            f" border: 1px solid {_BORDER}; border-radius: 12px; }}"
            "QFrame#historyCard:hover { border-color: $violeta; }"
        ))
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(card)
        row.setContentsMargins(18, 14, 14, 14)
        row.setSpacing(14)

        badge = _label(entry["period"], size=11, weight=800, color=_VIOLET,
                       extra=f"background-color: {_VIOLET_LIGHT};"
                             f" border: 1px solid {_VIOLET_LINE};"
                             " border-radius: 8px; padding: 4px 10px;")
        row.addWidget(badge)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        text_box.addWidget(_label(entry["station"], size=15, weight=800))
        text_box.addWidget(_label(
            f"{entry['total_dias']} días analizados", size=12, weight=500,
            color=_SLATE,
        ))
        row.addLayout(text_box)
        row.addStretch(1)

        row.addWidget(_label("SYNOP", size=10, weight=800, color=_FAINT,
                             extra=""))

        delete = QPushButton()
        delete.setIcon(lucide_icon("trash-2", _FAINT, 16))
        delete.setToolTip("Enviar a la papelera")
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.setFixedSize(32, 32)
        delete.setStyleSheet(_qss(
            "QPushButton { background: transparent; border: none;"
            " border-radius: 8px; }"
            "QPushButton:hover { background-color: $error_suave; }"
        ))
        delete.clicked.connect(lambda _=False, e=entry: self.on_delete(e))
        row.addWidget(delete)

        arrow = QLabel()
        arrow.setPixmap(lucide_icon("arrow-right", _VIOLET, 16).pixmap(QSize(16, 16)))
        arrow.setStyleSheet("background: transparent;")
        row.addWidget(arrow)

        card.clicked.connect(lambda i=index: self.open_history_entry(i))
        return card

    def _refresh_meta(self) -> None:
        meta = (self.doc or {}).get("meta") or {}
        self.meta_title.setText(str(meta.get("estacion", "")))
        self.meta_detail.setText(
            f"Período: {meta.get('periodo', '')}   ·   "
            f"Días analizados: {meta.get('total_dias', 0)}"
        )

    def _begin_progress(self) -> None:
        self.progress.setRange(0, 0)  # busy indicator while SQLite runs
        self.progress.show()
        self._status("Generando resumen…")

    def _end_progress(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.hide()

    def _status(self, text: str, *, error: bool = False) -> None:
        color = "$error_fuerte" if error else _EMERALD
        self.status_label.setText(text)
        self.status_label.setStyleSheet(_qss(
            f"QLabel {{ font-size: 12px; font-weight: 600; color: {color};"
            " background: transparent; }"
        ))


__all__ = ["MONTHS", "SummaryPage", "SummaryTableModel"]
