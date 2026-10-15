"""Main window of Neo Arca (PRD F3 skeleton).

A left nav with the six Sidebar entries filtered by role through
``oms_core.services.access`` and a stacked content area. Only the stations
admin page exists in F3; the rest are placeholders for F4-F7.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

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

    def _build_page(self, page_id: str) -> QWidget:
        if page_id == "admin":
            return StationsAdminPage(self._open_conn())
        if page_id == "summary":
            from oms_ui.pages.summary import SummaryPage

            return SummaryPage(self._open_conn())
        placeholder = QLabel(f"Página '{page_id}' — pendiente (F4-F7)")
        placeholder.setStyleSheet("color: #64748b;")
        return placeholder

    def _on_nav(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def visible_pages(self) -> list[str]:
        """Ids of the nav entries the current role can open, in nav order."""
        return [pid for pid, _ in NAV_ENTRIES if pid in self._pages]
