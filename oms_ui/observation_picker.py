"""Observation picker — the OBS "Cargar Observación" entry point.

The oracle opened a file explorer for a raw JSON. The owner asked instead for
the archive to be browsed inside the app: pick the station **by name** (the
list disappears when the session is bound to a single station), then walk
year -> month -> day under plain monochrome icons, and load the chosen day into
the form.

Days come from the stored daily documents (``summary_logs``, ``kind='diario'``),
which is what the application knows as an observation; a day exists there when
it was typed, migrated or imported.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_ui.icons import lucide_icon

_MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
_WEEKDAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")

_INK = "#334155"
_FAINT = "#94a3b8"
_LINE = "#e2e8f0"

_SQL_DAYS = """
SELECT station_id, year, month, day
  FROM summary_logs
 WHERE kind = 'diario'
"""


def month_name(month: str) -> str:
    """Spanish name for a ``01``-style month, or the raw value if unknown."""
    try:
        return _MONTHS[int(month) - 1]
    except (ValueError, IndexError):
        return month


def day_label(fecha: str) -> str:
    """``2024-04-28`` -> ``28 · dom``; the raw value when it cannot be parsed."""
    try:
        parsed = date.fromisoformat(fecha)
    except ValueError:
        return fecha
    return f"{parsed.day:02d} · {_WEEKDAYS[parsed.weekday()]}"


class ObservationPickerDialog(QDialog):
    """Browse the stored observations and return one ``(station, fecha)``."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        station: str | None = None,
        show_stations: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cargar observación")
        self.setMinimumSize(760, 520)
        self.setStyleSheet("QDialog { background-color: #f8fafc; }")

        self._days = self._load_days(conn)
        self._stations = [s for s in stations_repo.list_stations(conn)]
        self.selected_station: str | None = None
        self.selected_fecha: str | None = None

        codes = {s.id for s in self._stations}
        self._focus = station if station in codes else (
            self._stations[0].id if self._stations else None
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(12)
        outer.addWidget(self._header(show_stations))

        body = QHBoxLayout()
        body.setSpacing(12)
        if show_stations:
            body.addWidget(self._station_panel(), 0)
        body.addWidget(self._tree_panel(), 1)
        outer.addLayout(body, 1)

        outer.addLayout(self._footer())

        if self._focus:
            self._select_station_item(self._focus)
        self._fill_tree(self._focus)

    # ---------------------------------------------------------------- data

    @staticmethod
    def _load_days(conn: sqlite3.Connection) -> dict[str, dict[str, dict[str, list[str]]]]:
        """``{station: {year: {month: [day, ...]}}}`` from the stored documents."""
        tree: dict[str, dict[str, dict[str, list[str]]]] = {}
        try:
            rows = conn.execute(_SQL_DAYS).fetchall()
        except sqlite3.Error:
            return tree
        for row in rows:
            station, year, month, day = (str(value) for value in tuple(row)[:4])
            days = tree.setdefault(station, {}).setdefault(year, {}).setdefault(
                month, []
            )
            days.append(day)
        for years in tree.values():
            for months in years.values():
                for days in months.values():
                    # the columns store '1', '2', ... '10': sorting as text
                    # produced 1, 10, 11, 12 ... and lost the sequence
                    days.sort(key=lambda value: int(value or 0))
        return tree

    def _count_days(self, station: str) -> int:
        return sum(
            len(days)
            for months in self._days.get(station, {}).values()
            for days in months.values()
        )

    # --------------------------------------------------------------- layout

    def _header(self, show_stations: bool) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(lucide_icon("folder", _INK, 22).pixmap(22, 22))
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        words = QVBoxLayout()
        words.setSpacing(2)
        title = QLabel("Cargar observación")
        title.setStyleSheet(
            f"color: {_INK}; font-size: 18px; font-weight: 700;"
        )
        hint = QLabel(
            "Elegí la estación y después el año, el mes y el día."
            if show_stations else "Elegí el año, el mes y el día de la observación."
        )
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        words.addWidget(title)
        words.addWidget(hint)
        row.addLayout(words, 1)
        return header

    def _station_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(250)
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        caption = QLabel("ESTACIONES")
        caption.setStyleSheet(
            f"color: {_FAINT}; font-size: 11px; font-weight: 700;"
            "letter-spacing: 1px;"
        )
        column.addWidget(caption)
        self.station_list = QListWidget()
        self.station_list.setIconSize(QSize(18, 18))
        self.station_list.setStyleSheet(
            f"QListWidget {{ background: #ffffff; border: 1px solid {_LINE};"
            "border-radius: 8px; padding: 4px; }"
            "QListWidget::item { padding: 8px 6px; border-radius: 6px; }"
            "QListWidget::item:selected { background: #eff6ff; color: #1d4ed8; }"
        )
        for station_row in self._stations:
            item = QListWidgetItem(lucide_icon("cloud", _INK, 18), "")
            item.setData(Qt.ItemDataRole.UserRole, station_row.id)
            self.station_list.addItem(item)
            card = QLabel(
                f"<span style='color:#0f172a; font-weight:600;'>"
                f"{station_row.name}</span><br>"
                f"<span style='color:#94a3b8; font-size:11px;'>"
                f"{station_row.id} · {station_row.provincia}</span>"
            )
            card.setStyleSheet("background: transparent; border: none;")
            card.setContentsMargins(2, 2, 2, 2)
            self.station_list.setItemWidget(item, card)
            # the two-line card needs room for both lines inside the item's
            # padding (QSS gives 8px top/bottom), or the code gets clipped
            item.setSizeHint(QSize(0, 54))
        self.station_list.currentItemChanged.connect(self._on_station_picked)
        column.addWidget(self.station_list, 1)
        return panel

    def _tree_panel(self) -> QWidget:
        panel = QWidget()
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        caption = QLabel("DÍAS DE OBSERVACIÓN")
        caption.setStyleSheet(
            f"color: {_FAINT}; font-size: 11px; font-weight: 700;"
            "letter-spacing: 1px;"
        )
        column.addWidget(caption)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tree.setStyleSheet(
            f"QTreeWidget {{ background: #ffffff; border: 1px solid {_LINE};"
            "border-radius: 8px; padding: 6px; }"
            f"QTreeWidget::item {{ color: {_INK}; padding: 4px 2px; }}"
            "QTreeWidget::item:selected { background: #eff6ff; color: #1d4ed8; }"
        )
        self.tree.currentItemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        column.addWidget(self.tree, 1)
        self.empty_label = QLabel("Esta estación todavía no tiene observaciones.")
        self.empty_label.setStyleSheet("color: #64748b; font-size: 12px;")
        self.empty_label.setVisible(False)
        column.addWidget(self.empty_label)
        return panel

    def _footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        self.total_label = QLabel("")
        self.total_label.setStyleSheet(f"color: {_FAINT}; font-size: 12px;")
        footer.addWidget(self.total_label, 1)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setMinimumHeight(32)
        self.cancel_btn.clicked.connect(self.reject)
        self.load_btn = QPushButton("Cargar observación")
        self.load_btn.setMinimumHeight(32)
        self.load_btn.setEnabled(False)
        self.load_btn.setDefault(True)
        self.load_btn.setIcon(lucide_icon("folder", "#ffffff", 15))
        self.load_btn.setIconSize(QSize(15, 15))
        self.load_btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #ffffff;"
            "border: none; border-radius: 8px; padding: 6px 16px;"
            "font-weight: 600; }"
            "QPushButton:disabled { background-color: #cbd5e1; }"
        )
        self.load_btn.clicked.connect(self._accept_selection)
        footer.addWidget(self.cancel_btn, 0)
        footer.addWidget(self.load_btn, 0)
        return footer

    # -------------------------------------------------------------- filling

    def _select_station_item(self, station: str) -> None:
        if not hasattr(self, "station_list"):
            return
        for index in range(self.station_list.count()):
            item = self.station_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == station:
                self.station_list.setCurrentItem(item)
                return

    def _fill_tree(self, station: str | None) -> None:
        self.tree.clear()
        self.load_btn.setEnabled(False)
        years = self._days.get(station or "", {})
        if not years:
            self.empty_label.setVisible(True)
            self.total_label.setText("")
            return
        self.empty_label.setVisible(False)
        for year in sorted(years, reverse=True):
            year_days = sum(len(d) for d in years[year].values())
            year_item = QTreeWidgetItem(
                self.tree,
                [f"{year}   ·   {year_days} día{'s' if year_days != 1 else ''}"],
            )
            year_item.setIcon(0, lucide_icon("calendar", _INK, 16))
            year_item.setData(0, Qt.ItemDataRole.UserRole, {"year": year})
            for month in sorted(years[year], reverse=True):
                days = years[year][month]
                month_item = QTreeWidgetItem(
                    year_item,
                    [
                        f"{month_name(month)}   ·   {len(days)} día"
                        + ("s" if len(days) != 1 else "")
                    ],
                )
                month_item.setIcon(0, lucide_icon("calendar-days", _FAINT, 16))
                month_item.setData(0, Qt.ItemDataRole.UserRole, {"month": month})
                for day in days:
                    # the columns store '6' / '1', not '06' / '01'
                    fecha = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    day_item = QTreeWidgetItem(month_item, [day_label(fecha)])
                    day_item.setIcon(0, lucide_icon("file-text", _FAINT, 16))
                    day_item.setData(
                        0, Qt.ItemDataRole.UserRole, {"fecha": fecha}
                    )
        self.tree.expandToDepth(0)  # the newest year open, the rest folded
        self.total_label.setText(
            f"{self._count_days(station or '')} días de observación en total"
        )

    # --------------------------------------------------------------- events

    def _on_station_picked(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None:
            return
        station = current.data(Qt.ItemDataRole.UserRole)
        self._focus = station
        self._fill_tree(station)

    def _on_item_changed(self, current: QTreeWidgetItem | None, _previous=None) -> None:
        data = None if current is None else current.data(
            0, Qt.ItemDataRole.UserRole
        )
        self.load_btn.setEnabled(bool(data and data.get("fecha")))

    def _on_double_click(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("fecha"):
            self._accept_selection()

    def _accept_selection(self) -> None:
        item = self.tree.currentItem()
        data = None if item is None else item.data(0, Qt.ItemDataRole.UserRole)
        if not (data and data.get("fecha")):
            return
        self.selected_station = self._focus
        self.selected_fecha = data["fecha"]
        self.accept()

    def selection(self) -> tuple[str | None, str | None]:
        """``(station id, ISO date)``; both ``None`` when nothing was chosen."""
        return self.selected_station, self.selected_fecha


__all__ = ["ObservationPickerDialog", "day_label", "month_name"]
