"""Main window of Neo Arca (PRD F3 skeleton, F4-F7 pages wired).

A left nav with the six Sidebar entries filtered by role through
``oms_core.services.access`` and a stacked content area. Every entry shows
its REAL page now (dashboard, synoptic, summary, audit wizard + report tabs,
maintenance, stations admin): no placeholders remain. The audit observation
drill-down (station + date) opens as a dialog from the wizard.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import app_config as app_config_repo
from oms_core.services import access
from oms_ui.pages.stations_admin import StationsAdminPage

#: Nav entries mirroring OLD Sidebar.jsx MODULES (id, label) — the role
#: filtering itself lives in oms_core.services.access.
NAV_ENTRIES = (
    ("dashboard", "Inicio"),
    ("synoptic", "Sinóptico"),
    ("summary", "Resumen"),
    ("audit", "Auditoría"),
    ("maintenance", "Configuración"),
    ("admin", "Seguridad"),
)


class MainWindow(QMainWindow):
    def __init__(self, role: str, db_path: str | Path | sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neo Arca")
        self.role = role
        self._conn = db_path if isinstance(db_path, sqlite3.Connection) else None
        self._db_path = None if self._conn is not None else Path(db_path)

        self.nav = QListWidget()
        self.nav.setMaximumWidth(200)
        self.stack = QStackedWidget()

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._pages: dict[str, QWidget] = {}
        for page_id, label in NAV_ENTRIES:
            if not access.can_access(role, page_id):
                continue
            self.nav.addItem(label)
            self._pages[page_id] = self._build_page(page_id)
            self.stack.addWidget(self._pages[page_id])
        self.nav.currentRowChanged.connect(self._on_nav)
        if self.nav.count() > 0:
            self.nav.setCurrentRow(0)

    def _open_conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        from oms_core.db.connection import connect

        return connect(self._db_path)

    def _assigned_station(self, conn: sqlite3.Connection) -> str | None:
        try:
            return app_config_repo.get(conn, "assigned_station") or None
        except Exception:  # noqa: BLE001 - a broken KV never breaks the shell
            return None

    def _navigate_to(self, page_id: str) -> None:
        try:
            index = self.visible_pages().index(page_id)
        except ValueError:
            return
        self.nav.setCurrentRow(index)

    def _open_observation(self, station: str, fecha: str) -> None:
        from oms_core.services.audit import default_base_dir
        from oms_ui.pages.audit_observation import AuditObservationPage

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Auditoría {station} {fecha}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            AuditObservationPage(
                self._open_conn(), default_base_dir(), station, fecha, role=self.role
            )
        )
        dialog.resize(900, 600)
        dialog.exec()

    def _build_audit(self, conn: sqlite3.Connection) -> QWidget:
        from oms_core.services.audit import default_base_dir
        from oms_ui.pages.audit import AuditPage
        from oms_ui.pages.audit_report import AuditReportPage

        tabs = QTabWidget()
        wizard = AuditPage(
            conn,
            default_base_dir(),
            role=self.role,
            on_open_day=self._open_observation,
            on_open_report=lambda: tabs.setCurrentIndex(1),
        )
        tabs.addTab(wizard, "Revisar")
        tabs.addTab(AuditReportPage(conn, role=self.role), "Reporte")
        return tabs

    def _build_page(self, page_id: str) -> QWidget:
        conn = self._open_conn()
        if page_id == "admin":
            return StationsAdminPage(conn)
        if page_id == "audit":
            return self._build_audit(conn)
        if page_id == "summary":
            from oms_ui.pages.summary import SummaryPage

            return SummaryPage(conn)
        if page_id == "synoptic":
            from oms_ui.pages.synoptic import SynopticPage

            return SynopticPage(conn)
        if page_id == "dashboard":
            from oms_ui.pages.dashboard import DashboardPage

            return DashboardPage(
                conn,
                role=self.role,
                assigned_station=self._assigned_station(conn),
                on_navigate=self._navigate_to,
            )
        if page_id == "maintenance":
            from oms_ui.pages.maintenance import MaintenancePage

            return MaintenancePage(conn, role=self.role, db_path=self._db_path)
        raise AssertionError(f"unknown page id: {page_id!r} (no placeholders remain)")

    def _on_nav(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def visible_pages(self) -> list[str]:
        """Ids of the nav entries the current role can open, in nav order."""
        return [pid for pid, _ in NAV_ENTRIES if pid in self._pages]
