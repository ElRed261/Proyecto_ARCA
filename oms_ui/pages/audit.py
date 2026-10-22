"""AuditPage — the module's drill-down, replicated from the OLD.

Faithful port of ``OLD/.../audit/pages/AuditPage.jsx``: the orange header with
the "Reporte General de Errores" button, the clickable breadcrumb bar
(Estaciones › Estación X › Año › Mes) and the four steps as CARD GRIDS — one card
per station, year, month and day — instead of the list widgets this page used
to be. The day row carries exactly what the oracle shows: the day with its
date, the observer, the registered hours and the error/correction/unreviewed
badges plus the orange "Auditar" button.

Colours follow the oracle's accent: ``#f97316`` (orange 500) for the module.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from oms_core.services import access
from oms_core.services import audit as audit_service
from oms_ui.icons import lucide_icon

ACCENT = "#f97316"

_PAGE_QSS = f"""
QWidget#auditPage {{ background-color: #f8fafc; }}
QFrame#auditCard {{ background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 12px; }}
QFrame#auditCard:hover {{ border-color: #fdba74; }}
QFrame#auditPanel {{ background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 16px; }}
QFrame#crumbBar {{ background: #ffffff; border: 1px solid #f1f5f9;
    border-radius: 12px; }}
QLabel#crumb {{ color: #475569; font-weight: 600; font-size: 13px; }}
QLabel#crumbActive {{ color: {ACCENT}; font-weight: 800; font-size: 13px; }}
QLabel#stepTitle {{ color: #1e293b; font-size: 18px; font-weight: 800; }}
QLabel#cardHint {{ color: #f97316; font-size: 10px; font-weight: 800;
    letter-spacing: 1px; }}
QLabel#cardTitle {{ color: #1e293b; font-size: 16px; font-weight: 800; }}
QLabel#cardFooter {{ color: #64748b; font-size: 12px; font-weight: 600; }}
QLabel#dayTitle {{ color: #1e293b; font-size: 15px; font-weight: 800; }}
QLabel#dayMeta {{ color: #64748b; font-size: 12px; }}
QPushButton#moduleTitle {{ color: #0f172a; font-size: 26px; font-weight: 900;
    text-align: left; border: none; background: transparent; }}
QPushButton#reportButton {{ background: {ACCENT}; color: #ffffff; border: none;
    border-radius: 10px; padding: 9px 16px; font-weight: 700; }}
QPushButton#backButton {{ background: #ffffff; color: {ACCENT};
    border: 1px solid #fed7aa; border-radius: 20px; padding: 6px 14px;
    font-weight: 700; }}
QPushButton#auditButton {{ background: #ffedd5; color: #c2410c; border: none;
    border-radius: 8px; padding: 7px 14px; font-weight: 700; }}
QPushButton#auditButton:hover {{ background: {ACCENT}; color: #ffffff; }}
"""


def day_badge(conn: sqlite3.Connection, station_id: str, day: dict) -> str:
    """The day's badge text: counts plus whether the audit was closed.

    The row renders individual pills (like the oracle), but the RULE of what a
    day says lives here so callers and tests share one wording.
    """
    closed = audit_service.get_audit_day(
        conn, station_id=station_id, fecha=day["date"]
    )
    badges: list[str] = []
    if day.get("error_count"):
        count = day["error_count"]
        badges.append(f"{count} error" + ("" if count == 1 else "es"))
    if day.get("correction_count"):
        count = day["correction_count"]
        badges.append(f"{count} corrección" + ("" if count == 1 else "es"))
    badges.append("auditado" if closed is not None else "sin auditar")
    return f" ({', '.join(badges)})"


class _Card(QFrame):
    """A clickable card (the oracle's divs with onClick)."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("auditCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # QMouseEvent
        self.clicked.emit()
        super().mousePressEvent(event)


#: pill styles: red errors, emerald corrections, slate unreviewed
_BADGE_STYLES: dict[str, str] = {
    "error": "background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca;",
    "ok": "background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0;",
    "muted": "background: #f1f5f9; color: #94a3b8; border: 1px solid #e2e8f0;",
}


class _Badge(QLabel):
    """Small pill: red errors, emerald corrections, slate unreviewed."""

    def __init__(self, text: str, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            _BADGE_STYLES.get(kind, _BADGE_STYLES["muted"])
            + "border-radius: 10px; padding: 3px 9px; font-size: 11px;"
            "font-weight: 700;"
        )


class AuditPage(QWidget):
    """Stations -> years -> months -> days drill-down (oracle look)."""

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
        self.station_cards: list[_Card] = []
        self.year_cards: list[_Card] = []
        self.month_cards: list[_Card] = []
        self.day_rows: list[QFrame] = []

        self.setObjectName("auditPage")
        self.setStyleSheet(_PAGE_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        if self.denied:
            self.denial_label = QLabel(
                "Acceso denegado: la auditoría requiere rol admin o control_calidad."
            )
            outer.addWidget(self.denial_label)
            self.back_button = QPushButton("← Volver al Dashboard")
            self.report_button = QPushButton("Reporte General de Errores")
            self.breadcrumb_label = QLabel("Estaciones")
            self.status_label = QLabel("")
            return

        self._build_header(outer)
        self._build_breadcrumbs(outer)

        self.panel = QFrame()
        self.panel.setObjectName("auditPanel")
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(18, 16, 18, 18)
        self.panel_layout.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.panel)
        outer.addWidget(scroll, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        outer.addWidget(self.status_label)

        self._set_step(1)

    # ---------------------------------------------------------------- header

    def _build_header(self, outer: QVBoxLayout) -> None:
        header = QHBoxLayout()
        # the owner did not want a back button here: the rail and the
        # breadcrumbs already move you
        self.back_button = QPushButton("← Volver al Dashboard")
        self.back_button.hide()
        self.back_button.clicked.connect(self._on_back)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.title_label = QPushButton("Módulo de Auditoría")
        self.title_label.setObjectName("moduleTitle")
        self.title_label.setEnabled(False)  # looks like a heading, not a button
        subtitle = QLabel(
            "Control de Calidad, Marcado de Errores y Superposición de Correcciones"
        )
        subtitle.setStyleSheet("color: #64748b; font-size: 12px;")
        titles.addWidget(self.title_label)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        self.report_button = QPushButton("  Reporte General de Errores")
        self.report_button.setObjectName("reportButton")
        self.report_button.setIcon(lucide_icon("file-text", "#ffffff", 16))
        self.report_button.clicked.connect(self._open_report)
        header.addWidget(self.report_button, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(header)

    def _build_breadcrumbs(self, outer: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("crumbBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(6)
        self._crumb_row = row
        self.breadcrumb_label = QLabel("Estaciones")
        self.breadcrumb_label.setObjectName("crumbActive")
        row.addWidget(self.breadcrumb_label)
        row.addStretch(1)
        outer.addWidget(bar)

    def _refresh_breadcrumbs(self) -> None:
        while self._crumb_row.count():
            item = self._crumb_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        steps: list[tuple[str, int | None]] = [("Estaciones", 1)]
        if self.selected_station:
            steps.append(
                (f"Estación {self._station_name(self.selected_station)}", 2)
            )
        if self.selected_year:
            steps.append((self.selected_year, 3))
        if self.selected_month:
            steps.append((audit_service.MONTH_NAMES.get(self.selected_month, self.selected_month), None))
        for index, (text, target) in enumerate(steps):
            if index:
                chevron = QLabel()
                chevron.setPixmap(
                    lucide_icon("chevron-right", "#94a3b8", 14).pixmap(14, 14)
                )
                self._crumb_row.addWidget(chevron)
            label = QLabel(text)
            label.setObjectName(
                "crumbActive" if target == self.step else "crumb"
            )
            if target is not None:
                label.setCursor(Qt.CursorShape.PointingHandCursor)
                label.mousePressEvent = (
                    lambda event, s=target: self._set_step(s)
                )
            self._crumb_row.addWidget(label)
        self._crumb_row.addStretch(1)

    # ----------------------------------------------------------------- steps

    def _set_step(self, step: int) -> None:
        self.step = step
        self._clear_panel()
        if step == 1:
            self._render_stations()
        elif step == 2:
            self._render_years()
        elif step == 3:
            self._render_months()
        else:
            self._render_days()
        self._refresh_breadcrumbs()

    def _clear_panel(self) -> None:
        while self.panel_layout.count():
            item = self.panel_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            layout = item.layout()
            if layout is not None:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()

    def _step_title(self, icon: str, text: str) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        glyph = QLabel()
        glyph.setPixmap(lucide_icon(icon, ACCENT, 18).pixmap(18, 18))
        title = QLabel(text)
        title.setObjectName("stepTitle")
        row.addWidget(glyph)
        row.addWidget(title, 1)
        return holder

    def _empty_state(self, icon: str, message: str) -> QWidget:
        box = QFrame()
        box.setObjectName("auditCard")
        column = QVBoxLayout(box)
        column.setContentsMargins(20, 40, 20, 40)
        column.setSpacing(8)
        glyph = QLabel()
        glyph.setPixmap(lucide_icon(icon, "#cbd5e1", 40).pixmap(40, 40))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(message)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setStyleSheet("color: #64748b; font-weight: 600;")
        column.addWidget(glyph)
        column.addWidget(text)
        return box

    def _grid(self, columns: int) -> tuple[QWidget, QGridLayout]:
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        return holder, grid

    # ------------------------------------------------------------- stations

    def _render_stations(self) -> None:
        self.station_cards = []
        self.panel_layout.addWidget(
            self._step_title("radio", "Seleccione una Estación Meteorológica")
        )
        stations = audit_service.browse_stations(self.base_dir, self.conn)
        self.stations_list = stations  # name kept: callers/tests read it
        if not stations:
            self.panel_layout.addWidget(
                self._empty_state(
                    "radio",
                    "No se encontraron directorios de estaciones en synop.",
                )
            )
            self.panel_layout.addStretch(1)
            return
        holder, grid = self._grid(4)
        for index, station in enumerate(stations):
            card = _Card()
            column = QVBoxLayout(card)
            column.setContentsMargins(14, 12, 14, 12)
            column.setSpacing(4)
            hint = QLabel("ESTACIÓN")
            hint.setObjectName("cardHint")
            name = QLabel(station.get("name") or station.get("code", ""))
            name.setObjectName("cardTitle")
            footer = QHBoxLayout()
            explorar = QLabel("Explorar años")
            explorar.setObjectName("cardFooter")
            arrow = QLabel()
            arrow.setPixmap(
                lucide_icon("chevron-right", "#94a3b8", 14).pixmap(14, 14)
            )
            footer.addWidget(explorar)
            footer.addStretch(1)
            footer.addWidget(arrow)
            column.addWidget(hint)
            column.addWidget(name)
            column.addLayout(footer)
            code = station.get("code")
            card.clicked.connect(
                lambda _checked=False, c=code: self._on_station_clicked(c)
            )
            grid.addWidget(card, index // 4, index % 4)
            self.station_cards.append(card)
        self.panel_layout.addWidget(holder)
        self.panel_layout.addStretch(1)

    def _station_name(self, code: str | None) -> str:
        for station in getattr(self, "stations_list", []) or []:
            if station.get("code") == code:
                return station.get("name") or code or ""
        return code or ""

    def _on_station_clicked(self, code: str | None) -> None:
        if not code:
            return
        self.selected_station = code
        self.selected_year = None
        self.selected_month = None
        self._set_step(2)

    # ---------------------------------------------------------------- years

    def _render_years(self) -> None:
        self.year_cards = []
        self.panel_layout.addWidget(
            self._step_title("calendar", "Seleccione el Año de Observación")
        )
        years = audit_service.browse_years(
            self.base_dir, self.selected_station or ""
        )
        self.years_list = years
        if not years:
            self.panel_layout.addWidget(
                self._empty_state(
                    "calendar", "No hay carpetas de años para esta estación."
                )
            )
            self.panel_layout.addStretch(1)
            return
        holder, grid = self._grid(4)
        for index, year in enumerate(years):
            card = _Card()
            column = QVBoxLayout(card)
            column.setContentsMargins(14, 16, 14, 16)
            column.setSpacing(2)
            glyph = QLabel()
            glyph.setPixmap(lucide_icon("calendar", "#94a3b8", 26).pixmap(26, 26))
            glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(str(year))
            label.setObjectName("cardTitle")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(glyph)
            column.addWidget(label)
            card.clicked.connect(lambda y=year: self._on_year_clicked(y))
            grid.addWidget(card, index // 4, index % 4)
            self.year_cards.append(card)
        self.panel_layout.addWidget(holder)
        self.panel_layout.addStretch(1)

    def _on_year_clicked(self, year: str | None) -> None:
        if not year:
            return
        self.selected_year = str(year)
        self.selected_month = None
        self._set_step(3)

    # --------------------------------------------------------------- months

    def _render_months(self) -> None:
        self.month_cards = []
        self.panel_layout.addWidget(self._step_title("calendar-days", "Seleccione el Mes"))
        months = audit_service.browse_months(
            self.base_dir, self.selected_station or "", self.selected_year or ""
        )
        self.months_list = months
        if not months:
            self.panel_layout.addWidget(
                self._empty_state(
                    "calendar-days",
                    "No hay carpetas de meses registradas en este año.",
                )
            )
            self.panel_layout.addStretch(1)
            return
        holder, grid = self._grid(4)
        for index, month in enumerate(months):
            card = _Card()
            column = QVBoxLayout(card)
            column.setContentsMargins(14, 12, 14, 12)
            column.setSpacing(2)
            hint = QLabel(f"Mes {month}")
            hint.setObjectName("cardFooter")
            name = QLabel(audit_service.MONTH_NAMES.get(month, month))
            name.setObjectName("cardTitle")
            column.addWidget(hint)
            column.addWidget(name)
            card.clicked.connect(lambda m=month: self._on_month_clicked(m))
            grid.addWidget(card, index // 4, index % 4)
            self.month_cards.append(card)
        self.panel_layout.addWidget(holder)
        self.panel_layout.addStretch(1)

    def _on_month_clicked(self, month: str | None) -> None:
        if not month:
            return
        self.selected_month = str(month)
        self._set_step(4)

    # ----------------------------------------------------------------- days

    def _render_days(self) -> None:
        self.day_rows = []
        month_name = audit_service.MONTH_NAMES.get(
            self.selected_month or "", self.selected_month or ""
        )
        self.panel_layout.addWidget(
            self._step_title(
                "file-text",
                f"Listado de Días — Estación {self._station_name(self.selected_station)}"
                f" ({month_name} {self.selected_year})",
            )
        )
        days = audit_service.browse_days(
            self.base_dir,
            self.conn,
            self.selected_station or "",
            self.selected_year or "",
            self.selected_month or "",
        )
        self.days_list = days
        if not days:
            self.panel_layout.addWidget(
                self._empty_state(
                    "file-text",
                    "No se encontraron observaciones persistidas en este mes.",
                )
            )
            self.panel_layout.addStretch(1)
            return
        for day in days:
            self.panel_layout.addWidget(self._day_row(day))
        self.panel_layout.addStretch(1)

    def _day_row(self, day: dict) -> QFrame:
        row_frame = QFrame()
        row_frame.setObjectName("auditCard")
        row = QHBoxLayout(row_frame)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        day_number = str(day.get("date", "")).split("-")[-1]
        title = QLabel(f"Día {day_number} ({day.get('date')})")
        title.setObjectName("dayTitle")
        texts.addWidget(title)
        meta = QHBoxLayout()
        meta.setSpacing(14)
        observer = QLabel(f"Obs: {day.get('observador') or 'Desconocido'}")
        observer.setObjectName("dayMeta")
        hours = QLabel(f"Horas: {day.get('horas_registradas', 0)}")
        hours.setObjectName("dayMeta")
        meta.addWidget(observer)
        meta.addWidget(hours)
        meta.addStretch(1)
        texts.addLayout(meta)
        row.addLayout(texts, 1)

        closed = audit_service.get_audit_day(
            self.conn, station_id=self.selected_station or "", fecha=day["date"]
        )
        badges = QHBoxLayout()
        badges.setSpacing(6)
        if day.get("error_count"):
            count = day["error_count"]
            badges.addWidget(
                _Badge(f"{count} {'Error' if count == 1 else 'Errores'}", "error")
            )
        if day.get("correction_count"):
            count = day["correction_count"]
            badges.addWidget(
                _Badge(
                    f"{count} {'Corrección' if count == 1 else 'Correcciones'}",
                    "ok",
                )
            )
        if closed is not None:
            badges.addWidget(_Badge("Auditado", "ok"))
        elif not day.get("error_count") and not day.get("correction_count"):
            badges.addWidget(_Badge("Sin auditar", "muted"))
        row.addLayout(badges, 0)

        audit_button = QPushButton("  Auditar")
        audit_button.setObjectName("auditButton")
        audit_button.setIcon(lucide_icon("chevron-right", "#c2410c", 14))
        audit_button.clicked.connect(
            lambda: self._open_day_for(day.get("date", ""))
        )
        row.addWidget(audit_button, 0)
        self.day_rows.append(row_frame)
        return row_frame

    # --------------------------------------------------------------- events

    def _open_day_for(self, date: str) -> None:
        if self._on_open_day is not None and self.selected_station:
            self._on_open_day(self.selected_station, date)

    def _open_report(self) -> None:
        if self._on_open_report is not None:
            self._on_open_report()

    def _on_back(self) -> None:
        if self.step > 1:
            self._set_step(self.step - 1)
            return
        parent = self.parent()
        while parent is not None and not hasattr(parent, "show_page"):
            parent = parent.parent()
        if parent is not None:
            parent.show_page("dashboard")


__all__ = ["AuditPage", "day_badge"]
