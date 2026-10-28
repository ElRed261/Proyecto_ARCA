"""Main window of Neo Arca — AppShell with collapsible rail (PRD F7.5).

A left rail (76px icon-only <-> 200px with labels, QSettings-persisted)
with the six Sidebar entries filtered by role through
``oms_core.services.access`` and a stacked content area. Every entry shows
its REAL page (dashboard, synoptic, summary, audit wizard + report tabs,
maintenance, stations admin): no placeholders remain. The audit observation
drill-down (station + date) opens as a dialog from the wizard.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
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
#: Rail entries WITHOUT "Inicio": the dashboard is the program's default
#: landing point, not a selectable module (owner round 11 — a logo will
#: replace it once the owner picks one).
#: Owner round 25: Auditoría sits RIGHT AFTER Sinóptico — the auditor works
#: next to the observation it marks, before the monthly summary.
_RAIL_MODULE_IDS = ("synoptic", "audit", "summary", "maintenance",
                   "transform", "admin")

NAV_ENTRIES = (
    ("dashboard", "Inicio", "#3b82f6", "IN"),
    ("synoptic", "Sinóptico", "#3b82f6", "SI"),
    ("audit", "Auditoría", "#f97316", "AU"),
    ("summary", "Resumen", "#a855f7", "RE"),
    ("maintenance", "Configuración", "#0d9488", "CO"),
    ("transform", "Transformar", "#0ea5e9", "TR"),
    ("admin", "Seguridad", "#64748b", "SE"),
)

_RAIL_EXPANDED_WIDTH = 200
_RAIL_COLLAPSED_WIDTH = 76



def _repolish(widget) -> None:
    """Reevalúa el QSS de un widget tras cambiar una propiedad dinámica.

    Qt no reaplica los selectores por propiedad solo: hay que despulir y pulir.
    """
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
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

        # maximize -> restore clamp: WM restore used to leave the frame taller
        # than the usable screen, pushing the titlebar AND the bottom bar out
        # of reach. Debounced so it never fights the event-storm of a
        # maximize/restore transition nor the user's manual resizes.
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(80)
        self._fit_timer.timeout.connect(self._refit_clamp)

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
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        # owner round 11: a logo mark (identity TBD by the owner) — also the
        # home click target: tapping it returns to the default landing page
        from PySide6.QtWidgets import QLabel

        self._rail_logo = QLabel("OMS")
        self._rail_logo.setObjectName("railLogo")
        self._rail_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rail_logo.setToolTip("Inicio")
        self._rail_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rail_logo.mousePressEvent = lambda _event: self._navigate_to("dashboard")
        layout.addWidget(self._rail_logo)

        self._rail_buttons: dict[str, QPushButton] = {}
        for page_id, label, accent, mono in NAV_ENTRIES:
            if page_id not in _RAIL_MODULE_IDS:  # Inicio is NOT an option
                continue
            if not access.can_access(self.role, page_id):
                continue
            button = QPushButton()
            button.setProperty("page_id", page_id)
            button.setProperty("rail", "nav")
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
            self._email_label.setObjectName("railEmail")
            # Sin PlainText, Qt lee el correo como enlace y lo pinta azul
            # y subrayado, ignorando el QSS.
            self._email_label.setTextFormat(Qt.TextFormat.PlainText)
            self._email_label.setWordWrap(True)
            layout.addWidget(self._email_label)

        # owner round 11 (Gemini-style): NO «/» toggle button — clicking the
        # rail's empty space collapses when expanded, expands when collapsed
        self._toggle_button = None
        rail.mousePressEvent = lambda _event: self.toggle_rail()

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
        self._rail_widget.setProperty("collapsed", "true" if collapsed else "false")
        for page_id, label, _accent, mono in NAV_ENTRIES:
            button = self._rail_buttons.get(page_id)
            if button is None:
                continue
            button.setProperty("collapsed", "true" if collapsed else "false")
            button.setText(mono if collapsed else f"  {label}")
            _repolish(button)
        self._rail_logo.setText("OMS" if collapsed else "OMS · Observations")
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
            button.setProperty("active", "true" if active else "false")
            _repolish(button)

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
        from oms_core.services.audit import resolve_base_dir
        from oms_ui.pages.audit_observation import AuditObservationPage

        conn = self._open_conn()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Auditoría {station} {fecha}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            AuditObservationPage(
                conn, resolve_base_dir(conn), station, fecha, role=self.role
            )
        )
        dialog.resize(900, 600)
        dialog.exec()

    def _build_audit(self, conn: sqlite3.Connection) -> QWidget:
        from oms_core.services.audit import resolve_base_dir
        from oms_ui.pages.audit import AuditPage
        from oms_ui.pages.audit_report import AuditReportPage

        tabs = QTabWidget()
        wizard = AuditPage(
            conn,
            resolve_base_dir(conn),
            role=self.role,
            on_open_day=self._open_observation,
            on_open_report=lambda: tabs.setCurrentIndex(1),
        )
        tabs.addTab(wizard, "Revisar")
        tabs.addTab(AuditReportPage(conn, role=self.role), "Reporte")
        # the module's orange, not the application default: the switch between
        # reviewing and reporting is part of the audit screen (owner round 29)
        tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #f8fafc; }"
            "QTabBar::tab { background: #ffffff; color: #475569;"
            " border: 1px solid #e2e8f0; border-bottom: none;"
            " border-top-left-radius: 10px; border-top-right-radius: 10px;"
            " padding: 9px 22px; margin-right: 4px; font-weight: 700;"
            " font-size: 13px; }"
            "QTabBar::tab:hover { color: #c2410c; }"
            "QTabBar::tab:selected { background: #f97316; color: #ffffff;"
            " border-color: #f97316; }"
        )
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

            return SynopticPage(conn, role=self.role)
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
        if page_id == "transform":
            from oms_ui.pages.transformar import TransformarPage

            return TransformarPage(conn)
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

    def resizeEvent(self, event) -> None:
        """Watch for a frame that outgrows the usable screen (restore path)."""
        super().resizeEvent(event)
        if self.isMaximized() or not self.isVisible():
            return
        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        frame = self.frameGeometry()
        if (frame.width() > avail.width() or frame.height() > avail.height()) \
                and not self._fit_timer.isActive():
            self._fit_timer.start()

    def _refit_clamp(self) -> None:
        """Re-apply the screen fit after a maximize/restore transition."""
        if self.isMaximized() or not self.isVisible():
            return
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        frame = self.frameGeometry()
        if frame.width() > avail.width() or frame.height() > avail.height():
            self.fit_to_screen()

    def fit_to_screen(self, fraction: float = 0.92) -> None:
        """Size to the usable desktop so the titlebar is always visible.

        A hardcoded 1280x800 on <1080p screens pushes the titlebar out of
        reach (and hides the bottom bar). Never fullscreen: windowed,
        decorated and fully reachable, whatever the resolution.
        """
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        width = min(int(avail.width() * fraction), 1280)
        height = min(int(avail.height() * fraction), 800)
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(avail.center())
        self.move(frame.topLeft())
