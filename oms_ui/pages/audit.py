"""AuditPage — 4-step audit wizard (PRD F6).

PySide6 port of ``OLD/frontend/src/features/audit/pages/AuditPage.jsx`` backed
by the Qt-free ``oms_core.services.audit`` service (ADR-03: only presentation
here): stations -> years -> months -> days drill-down over the filesystem base
dir, with per-day error/correction badges read from SQLite (F1 audit repo).

Role gating uses the enforced boundary (``access.can_access``): roles without
audit access (encargado, observador) get a denial panel instead of the wizard.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_core.services.audit import AuditError


class AuditPage(QWidget):
    """Stations -> years -> months -> days drill-down."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        base_dir: str | Path,
        role: str = "admin",
        on_open_day: Callable[[str, str], None] | None = None,
        on_open_report: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.base_dir = Path(base_dir)
        self.role = role
        self.denied = not access.can_access(role, "audit")
        self._on_open_day = on_open_day
        self._on_open_report = on_open_report

        self.step = 1
        self.selected_station: str | None = None
        self.selected_year: str | None = None
        self.selected_month: str | None = None

        layout = QVBoxLayout(self)
        if self.denied:
            self.denial_label = QLabel(
                "Acceso denegado: la auditoría requiere rol admin o control_calidad."
            )
            layout.addWidget(self.denial_label)
            # inert placeholders so callers can always rely on the attributes
            self.stations_list = QListWidget()
            self.years_list = QListWidget()
            self.months_list = QListWidget()
            self.days_list = QListWidget()
            self.back_button = QPushButton("Back")
            self.report_button = QPushButton("Report")
            self.breadcrumb_label = QLabel("")
            return

        self.title_label = QLabel("Módulo de Auditoría")
        layout.addWidget(self.title_label)

        top = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.go_back)
        self.report_button = QPushButton("General error report")
        self.report_button.clicked.connect(self._open_report)
        top.addWidget(self.back_button)
        top.addWidget(self.report_button)
        layout.addLayout(top)

        self.breadcrumb_label = QLabel("Estaciones")
        layout.addWidget(self.breadcrumb_label)

        self.stack = QStackedWidget()
        self.stations_list = QListWidget()
        self.years_list = QListWidget()
        self.months_list = QListWidget()
        self.days_list = QListWidget()
        for widget in (self.stations_list, self.years_list, self.months_list, self.days_list):
            self.stack.addWidget(widget)
        layout.addWidget(self.stack)

        self.stations_list.itemClicked.connect(self._on_station_clicked)
        self.years_list.itemClicked.connect(self._on_year_clicked)
        self.months_list.itemClicked.connect(self._on_month_clicked)
        self.days_list.itemDoubleClicked.connect(self._on_day_opened)

        self.open_day_button = QPushButton("Open selected day")
        self.open_day_button.clicked.connect(self._open_selected_day)
        layout.addWidget(self.open_day_button)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        self._load_stations()

    # ------------------------------------------------------------------ load

    def _load_stations(self) -> None:
        self.stations_list.clear()
        try:
            stations = audit_service.browse_stations(self.base_dir, self.conn)
        except (AuditError, OSError, sqlite3.Error) as exc:  # never break the wizard
            self.status_label.setText(f"Error loading stations: {exc}")
            return
        for station in stations:
            self.stations_list.addItem(f"{station['code']} — {station['name']}")

    # --------------------------------------------------------------- steps

    def _set_step(self, step: int) -> None:
        self.step = step
        self.stack.setCurrentIndex(step - 1)
        crumbs = ["Estaciones"]
        if self.selected_station:
            crumbs.append(self.selected_station)
        if self.selected_year:
            crumbs.append(self.selected_year)
        if self.selected_month:
            label = audit_service.MONTH_NAMES.get(self.selected_month, self.selected_month)
            crumbs.append(label)
        self.breadcrumb_label.setText(" > ".join(crumbs))

    def _station_code(self, row: int) -> str:
        return self.stations_list.item(row).text().split(" — ")[0]

    def _on_station_clicked(self, item: Any) -> None:
        self.selected_station = self._station_code(self.stations_list.row(item))
        self.selected_year = None
        self.selected_month = None
        self.years_list.clear()
        for year in audit_service.browse_years(self.base_dir, self.selected_station):
            self.years_list.addItem(year)
        self._set_step(2)

    def _on_year_clicked(self, item: Any) -> None:
        self.selected_year = self.years_list.item(self.years_list.row(item)).text()
        self.selected_month = None
        self.months_list.clear()
        assert self.selected_station is not None
        for month in audit_service.browse_months(
            self.base_dir, self.selected_station, self.selected_year
        ):
            label = audit_service.MONTH_NAMES.get(month, month)
            self.months_list.addItem(f"{month} — {label}")
        self._set_step(3)

    def _on_month_clicked(self, item: Any) -> None:
        self.selected_month = (
            self.months_list.item(self.months_list.row(item)).text().split(" — ")[0]
        )
        self.days_list.clear()
        assert self.selected_station is not None and self.selected_year is not None
        for day in audit_service.browse_days(
            self.base_dir, self.conn, self.selected_station, self.selected_year, self.selected_month
        ):
            badges = []
            if day["error_count"]:
                badges.append(f"{day['error_count']} errors")
            if day["correction_count"]:
                badges.append(f"{day['correction_count']} corrections")
            suffix = f" ({', '.join(badges)})" if badges else " (not audited)"
            self.days_list.addItem(f"{day['date']}{suffix}")
        self._set_step(4)

    def _on_day_opened(self, item: Any) -> None:
        self._open_selected_day()

    def _open_selected_day(self) -> None:
        row = self.days_list.currentRow()
        if row < 0 or self.days_list.count() == 0:
            return
        date = self.days_list.item(row).text().split(" (")[0]
        if self._on_open_day is not None and self.selected_station is not None:
            self._on_open_day(self.selected_station, date)

    def _open_report(self) -> None:
        if self._on_open_report is not None:
            self._on_open_report()

    def go_back(self) -> None:
        """Return one drill-down level (wizard Back button)."""
        if self.step == 4:
            self.selected_month = None
            self._set_step(3)
        elif self.step == 3:
            self.selected_year = None
            self._set_step(2)
        elif self.step == 2:
            self.selected_station = None
            self._set_step(1)
