"""DashboardPage — operations center (PRD F7).

PySide6 port of ``OLD/frontend/src/features/dashboard/pages/DashboardPage.jsx``:

- ops-center cards per station: today status (``X/8`` hours from the
  observations repository) plus days with data this month;
- assigned-station lock banner for non-privileged roles;
- sync pending badge with a shortcut to the maintenance panel.

Scope rule (§9 rule 5, via ``access.scope_for``): admin/control_calidad see
all stations, every other role sees only its assigned station. A
non-privileged role without an assigned station gets an honest banner
instead of a silently empty board.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import observations as observations_repo
from oms_core.db.repositories import stations as stations_repo
from oms_core.services import access
from oms_core.services import sync as sync_service

#: Hours of a complete synoptic day (mirrors the oracle HOURS list).
HOURS_PER_DAY = 8


_CARD_ACCENTS = ("blue", "teal", "violet", "orange", "gray")


def _accent_for(code: str) -> str:
    """Stable accent per station (IMG module-tile language)."""
    return _CARD_ACCENTS[abs(hash(code)) % len(_CARD_ACCENTS)]


def _monogram(name: str, code: str) -> str:
    parts = [w for w in name.split() if w]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    text = (name or code).strip()
    return (text[:2] if len(text) >= 2 else (text + "•")[:2]).upper()


class StationCard(QGroupBox):
    """One station: accent tile + today progress + month count + accent link.

    Test contract preserved: ``code_label``/``today_label``/``month_label``
    texts and the clickable ``go_button`` keep their semantics.
    """

    def __init__(
        self,
        code: str,
        name: str,
        done: int,
        month_days: int,
        on_go: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("", parent)
        self.code = code
        accent = _accent_for(code)
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        tile = QLabel(_monogram(name, code))
        tile.setProperty("tile", accent)
        tile.setFixedSize(48, 48)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(tile)
        title_box = QVBoxLayout()
        title = QLabel(name)
        title.setProperty("cardTitle", True)
        title.setWordWrap(True)
        title_box.addWidget(title)
        self.code_label = QLabel(code)
        self.code_label.setProperty("cardSub", True)
        title_box.addWidget(self.code_label)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        self.today_label = QLabel(f"Hoy: {done}/{HOURS_PER_DAY}")
        layout.addWidget(self.today_label)
        self.month_label = QLabel(f"{month_days} días con datos este mes")
        self.month_label.setProperty("cardSub", True)
        layout.addWidget(self.month_label)
        self.go_button = QPushButton("Continuar →")
        self.go_button.setProperty("link", "blue")
        self.go_button.setCursor(Qt.CursorShape.PointingHandCursor)
        if on_go is not None:
            self.go_button.clicked.connect(on_go)
        layout.addWidget(self.go_button)


class DashboardPage(QWidget):
    """Ops center: station cards, lock banner, sync badge."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        role: str = "observador",
        assigned_station: str | None = None,
        on_navigate: Callable[[str], None] | None = None,
        today: _dt.date | str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.role = role
        self.assigned_station = assigned_station
        self._on_navigate = on_navigate
        self.today_iso = self._coerce_today(today)

        try:
            self.scope: str | None = access.scope_for(role, assigned_station)
        except PermissionError:
            self.scope = None
        self.privileged = self.scope == "all"

        layout = QVBoxLayout(self)
        year, month, day = self.today_iso.split("-")
        self.date_label = QLabel(f"{day}/{month}/{year}")
        layout.addWidget(self.date_label)
        title = QLabel("Centro de operaciones")
        layout.addWidget(title)

        self.lock_label = QLabel("")
        layout.addWidget(self.lock_label)

        stations = {s.id: s for s in stations_repo.list_stations(conn)}
        if self.scope is None:
            codes: list[str] = []
            self.lock_label.setText(
                f"Sin estación asignada: el rol '{role}' requiere una estación asignada"
            )
        else:
            codes = (
                sorted(stations)
                if self.scope == "all"
                else ([self.scope] if self.scope in stations else [])
            )
            if assigned_station:
                name = (
                    stations[assigned_station].name
                    if assigned_station in stations
                    else assigned_station
                )
                if self.privileged:
                    self.lock_label.setText(f"Instancia bloqueada a {name} ({assigned_station})")
                else:
                    self.lock_label.setText(f"Tu estación: {name} ({assigned_station})")
            elif not self.privileged:
                self.lock_label.setText(
                    f"Sin estación asignada: el rol '{role}' requiere una estación asignada"
                )

        self._grid = QGridLayout()
        self._grid.setSpacing(12)
        self.station_cards: dict[str, StationCard] = {}
        self._card_codes: list[str] = []
        for code in codes:
            day_rows = observations_repo.get_day(conn, code, self.today_iso)
            done = min(len(day_rows), HOURS_PER_DAY)
            month_rows = observations_repo.get_month(conn, code, int(year), int(month))
            month_days = len({obs.fecha for obs in month_rows})
            card = StationCard(
                code,
                stations[code].name,
                done,
                month_days,
                on_go=self._go("synoptic"),
            )
            self.station_cards[code] = card
            self._card_codes.append(code)
        self._cards_box = QWidget()
        self._cards_box.setLayout(self._grid)
        from PySide6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_box)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll, 1)
        self._relayout_cards()

        # ---- sync badge (belongs to __init__: uses layout + conn) ------
        try:
            sync_status = sync_service.get_sync_status(conn)
            pending, synced = sync_status.pending, sync_status.synced
        except Exception:  # noqa: BLE001 - badge degrades, page stays usable
            pending, synced = 0, 0
        badge_row = QHBoxLayout()
        if pending > 0:
            self.sync_label = QLabel(f"{pending} pendientes de envío")
        else:
            self.sync_label = QLabel("Sincronización al día")
        self.sync_detail_label = QLabel(f"{synced} enviadas con éxito")
        self.sync_button = QPushButton("Ver sincronización →")
        go_sync = self._go("maintenance")
        if go_sync is not None:
            self.sync_button.clicked.connect(go_sync)
        badge_row.addWidget(self.sync_label)
        badge_row.addWidget(self.sync_detail_label)
        badge_row.addWidget(self.sync_button)
        badge_box = QWidget()
        badge_box.setLayout(badge_row)
        layout.addWidget(badge_box)
        # NO trailing stretch: the operations-center grid takes the FULL page
        # height (the 50/50 split with this stretch used to leave the center
        # panel at half the screen with dead space below — owner report).

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_cards()

    def _relayout_cards(self) -> None:
        """Responsive columns: 1 narrow, 2 comfortable, 3 wide."""
        width = self._cards_box.width() or self.width() or 800
        columns = 1 if width < 560 else (2 if width < 900 else 3)
        for index, code in enumerate(self._card_codes):
            self._grid.addWidget(
                self.station_cards[code], index // columns, index % columns
            )

    @staticmethod
    def _coerce_today(today: _dt.date | str | None) -> str:
        if today is None:
            return _dt.date.today().isoformat()
        if isinstance(today, _dt.date):
            return today.isoformat()
        _dt.date.fromisoformat(today)  # fail fast on garbage
        return today

    def _go(self, page_id: str) -> Callable[[], None] | None:
        if self._on_navigate is None:
            return None

        def _navigate() -> None:
            assert self._on_navigate is not None
            self._on_navigate(page_id)

        return _navigate
