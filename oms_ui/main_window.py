"""Main window of Neo Arca — AppShell with collapsible rail (PRD F7.5).

A left rail (76px icon-only <-> 232px with labels, QSettings-persisted)
with the six Sidebar entries filtered by role through
``oms_core.services.access`` and a stacked content area. Every entry shows
its REAL page (dashboard, synoptic, summary, audit wizard + report tabs,
maintenance, stations admin): no placeholders remain. The audit observation
drill-down (station + date) opens as a dialog from the wizard.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import app_config as app_config_repo
from oms_core.services import access
from oms_ui.pages.stations_admin import StationsAdminPage

#: Nav entries mirroring OLD Sidebar.jsx MODULES (id, label, accent, monogram)
#: — the role filtering itself lives in oms_core.services.access.
NAV_ENTRIES = (
    ("dashboard", "Inicio", "#3b82f6", "IN"),
    ("synoptic", "Sinóptico", "#3b82f6", "SI"),
    ("summary", "Resumen", "#a855f7", "RE"),
    ("audit", "Auditoría", "#f97316", "AU"),
    ("maintenance", "Configuración", "#0d9488", "CO"),
    ("admin", "Seguridad", "#64748b", "SE"),
)

_RAIL_EXPANDED_WIDTH = 232
_RAIL_COLLAPSED_WIDTH = 76


class MainWindow(QMainWindow):
    """Application shell. Emits :attr:`logout_requested` from the Salir button."""

    logout_requested = Signal()

    def __init__(
        self,
        role: str,
        db_path: str | Path | sqlite3.Connection,
        email: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neo Arca")
        self.role = role
        self.email = email
        self._conn = db_path if isinstance(db_path, sqlite3.Connection) else None
        self._db_path = None if self._conn is not None else Path(db_path)
        self._pages: dict[str, QWidget] = {}  # before rail: selection refresh reads it
        self._settings = QSettings("NeoArca", "shell")
        self._collapsed = self._settings.value("rail_collapsed", False, type=bool)

        self.stack = QStackedWidget()

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_rail())
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Listo")

        for page_id, _label, _accent, _mono in NAV_ENTRIES:
            if not access.can_access(role, page_id):
                continue
            self._pages[page_id] = self._build_page(page_id)
            self.stack.addWidget(self._pages[page_id])
        self._refresh_rail_selection()
        if self._pages:
            self.stack.setCurrentIndex(0)

    # -- rail ------------------------------------------------------------

    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("rail")
        rail.setStyleSheet("#rail { background-color: #ffffff; border-right: 1px solid #e2e8f0; }")
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        self._rail_buttons: dict[str, QPushButton] = {}
        for page_id, label, accent, mono in NAV_ENTRIES:
            if not access.can_access(self.role, page_id):
                continue
            button = QPushButton()
            button.setProperty("page_id", page_id)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setMinimumHeight(44)
            button.setToolTip(label)
            button.clicked.connect(lambda _=False, p=page_id: self._navigate_to(p))
            self._rail_buttons[page_id] = button
            layout.addWidget(button)

        layout.addStretch(1)

        if self.email:
            from PySide6.QtWidgets import QLabel

            self._email_label = QLabel(self.email)
            self._email_label.setStyleSheet(
                "font-size: 11px; color: #64748b; background: transparent;"
            )
            self._email_label.setWordWrap(True)
            layout.addWidget(self._email_label)

        self._toggle_button = QPushButton("«" if not self._collapsed else "»")
        self._toggle_button.setToolTip("Colapsar menú" if not self._collapsed else "Expandir menú")
        self._toggle_button.clicked.connect(self.toggle_rail)
        layout.addWidget(self._toggle_button)

        self._logout_button = QPushButton("Salir")
        self._logout_button.clicked.connect(self.logout_requested.emit)
        layout.addWidget(self._logout_button)

        self._rail_widget = rail
        self._apply_rail_mode()
        return rail

    def _apply_rail_mode(self) -> None:
        collapsed = self._collapsed
        self._rail_widget.setFixedWidth(
            _RAIL_COLLAPSED_WIDTH if collapsed else _RAIL_EXPANDED_WIDTH
        )
        for page_id, label, accent, mono in NAV_ENTRIES:
            button = self._rail_buttons.get(page_id)
            if button is None:
                continue
            if collapsed:
                button.setText(mono)
                button.setStyleSheet(
                    f"QPushButton {{ border: none; border-left: 3px solid {accent}; "
                    f"font-weight: 800; font-size: 15px; color: {accent}; padding: 10px 0; }}"
                )
            else:
                button.setText(f"  {label}")
                button.setStyleSheet(
                    "QPushButton { border: none; text-align: left; padding: 10px 12px; "
                    "font-weight: 600; color: #334155; }"
                )
        self._toggle_button.setText("»" if collapsed else "«")
        self._toggle_button.setToolTip(
            "Expandir menú" if collapsed else "Colapsar menú"
        )
        if hasattr(self, "_email_label"):
            self._email_label.setVisible(not collapsed)
        if hasattr(self, "_logout_button"):
            self._logout_button.setText("⏻" if collapsed else "Salir")
            self._logout_button.setToolTip("Salir")
        self._refresh_rail_selection()

    def toggle_rail(self) -> None:
        """Flip collapsed state and persist it (oracle Sidebar behavior)."""
        self._collapsed = not self._collapsed
        self._settings.setValue("rail_collapsed", self._collapsed)
        self._apply_rail_mode()

    @property
    def rail_collapsed(self) -> bool:
        return self._collapsed

    def _refresh_rail_selection(self) -> None:
        current = self.stack.currentWidget() if self._pages else None
        for page_id, button in self._rail_buttons.items():
            active = self._pages.get(page_id) is current
            button.setProperty("active", "true" if active else None)
            base = button.styleSheet()
            if active:
                if "background" not in base or "#dbeafe" not in base:
                    button.setStyleSheet(base + " QPushButton { background-color: #dbeafe; }")
            else:
                button.setStyleSheet(base.replace(" QPushButton { background-color: #dbeafe; }", ""))

    # -- pages (unchanged builders) ---------------------------------------

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
        self.stack.setCurrentIndex(index)
        self._refresh_rail_selection()

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
        """Kept for API compatibility (rail calls _navigate_to directly)."""
        if 0 <= row < len(self.visible_pages()):
            self._navigate_to(self.visible_pages()[row])

    def visible_pages(self) -> list[str]:
        """Ids of the nav entries the current role can open, in nav order."""
        return [pid for pid, _label, _accent, _mono in NAV_ENTRIES if pid in self._pages]

    def status(self, message: str, timeout: int = 5000) -> None:
        """Global status-bar message (toast equivalent)."""
        self.statusBar().showMessage(message, timeout)
