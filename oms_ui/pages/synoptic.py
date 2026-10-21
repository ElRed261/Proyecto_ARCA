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
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, QRegularExpression, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRegularExpressionValidator,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import oms_calc
from oms_core.db.repositories import stations as stations_repo
from oms_core.services import past_weather
from oms_core.services import synoptic as synoptic_service
from oms_ui.icons import icon_pixmap, lucide_icon
from oms_ui.widgets import StyledComboBox

_AAXX = "AAXX"

_LOGGER = logging.getLogger(__name__)

#: toast auto-dismiss (owner round 6: 5s). Test-injectable so the suite
#: exercises the real dismissal path without sleeping 5 seconds.
STATUS_TOAST_MS = 5000

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
    "meteo_4_irixhvv": "Ir iX H VV", "meteo_4_6": "7",
    "meteo_6_0": "8", "meteo_6_2": "0", "meteo_6_3": "10",
    "meteo_6_4": "20", "meteo_6_5": "3///",
    "meteo_8_1": "56", "meteo_8_3": "6", "meteo_8_4": "7",
    "meteo_8_5": "8", "meteo_8_6": "8",
    **{f"meteo_{r}_{i}": ("8..." if i < 2 else "9Sp…")
       for r in (10, 12, 14) for i in range(7)},
    **{f"meteo_16_{i}": "9" for i in range(5)},
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

#: Inline stylesheets — per-widget, not page-wide. Probe finding: the
#: page-level descendant selectors rendered backgrounds unreliably while
#: every inline rule painted correctly; the visual contract goes inline.
FIELD_QSS = (
    "QLineEdit { background-color: #ffffff; border: 1px solid #cbd5e1;"
    "border-radius: 4px; padding: 5px 8px; color: #1e293b;"
    "selection-background-color: #bfdbfe; }"
    "QLineEdit:disabled { background-color: #e2e8f0; color: #94a3b8; }"
)
FIELD_ERROR_QSS = (
    "QLineEdit { background-color: #ffffff; border: 2px solid #ef4444;"
    "border-radius: 4px; padding: 5px 8px; color: #1e293b; }"
)
RO_QSS = (
    "QLineEdit { background-color: #ffffff; border: 1px solid #cbd5e1;"
    "border-radius: 4px; padding: 5px 8px; color: #2563eb; font-weight: bold; }"
    "QLineEdit:disabled { background-color: #e2e8f0; color: #94a3b8; }"
)
CONST_QSS = (
    "QLineEdit { background-color: #e2e8f0; border: 1px solid #94a3b8;"
    "border-radius: 4px; padding: 5px 8px; color: #334155; font-weight: bold; }"
)
CARD_QSS = (
    "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0;"
    "border-radius: 16px; }"
)
CARDHEAD_QSS = (
    "color: #94a3b8; font-size: 12px; font-weight: 700; background: transparent;"
    "border: none;"
)
MINILABEL_QSS = (
    "color: #94a3b8; font-size: 11px; font-weight: 700; background: transparent;"
    "border: none;"
)
HOURBTN_QSS = (
    "QPushButton { background-color: #f8fafc; color: #475569;"
    "border: 1px solid #f1f5f9; border-radius: 8px;"
    "padding: 8px 6px; font-weight: 700; font-size: 12px; }"
    "QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }"
)
DAYNAV_BACK_QSS = (
    "QPushButton { background-color: #eff6ff; border: 1px solid #dbeafe;"
    "border-radius: 8px; padding: 8px 0; }"
    "QPushButton:hover { background-color: #dbeafe; }"
)
DAYNAV_FORWARD_QSS = (
    "QPushButton { background-color: #f0fdf4; border: 1px solid #dcfce7;"
    "border-radius: 8px; padding: 8px 0; }"
    "QPushButton:hover { background-color: #dcfce7; }"
)
CLI_BTN_QSS = (
    "QToolButton { background-color: #f8fafc; color: #334155;"
    "border: 1px solid #e2e8f0; border-radius: 10px;"
    "padding: 5px 2px; font-size: 11px; font-weight: 700; }"
    "QToolButton:hover { background-color: #fef3c7; border-color: #fde68a; }"
)
SECONDARY_BTN_QSS = (
    "QPushButton { background-color: #f8fafc; color: #334155;"
    "border: 1px solid #e2e8f0; border-radius: 12px;"
    "padding: 7px 10px; font-size: 12px; font-weight: 700; }"
    "QPushButton:hover { background-color: #f1f5f9; }"
)


def _hour_button_qss(bg: str) -> str:
    """Completion tint over the slate-50 base (oracle dot-color contract)."""
    return (
        f"QPushButton {{ background-color: {bg}; color: #475569;"
        "border: 1px solid #f1f5f9; border-radius: 8px;"
        "padding: 8px 6px; font-weight: 700; font-size: 12px; }"
        "QPushButton:hover { color: #0f172a; }"
    )


def _progress_qss(chunk: str) -> str:
    return (
        "QProgressBar { background-color: #f1f5f9; border: none;"
        "border-radius: 3px; }"
        f"QProgressBar::chunk {{ background-color: {chunk}; border-radius: 3px; }}"
    )


#: Hour themes verbatim from synopticConfig.hourThemes: the page is a
#: bg-gradient-to-br surface whose stops, accent chips and title text
#: follow the observation hour ("escala de azules según altura del sol").
HOUR_THEMES: dict[str, dict[str, str]] = {
    # hora local RD = UTC-4; cada par from/to es el cielo real de esa hora:
    # 00Z=20:00 dusk (violeta cayendo a indigo), 03Z=23:00 noche, 06Z=02:00
    # noche profunda, 09Z=05:00 amanecer (azul noche + ambar al horizonte),
    # 12Z=08:00 mañana azul cielo, 15Z=11:00 mediodia pleno, 18Z=14:00
    # tarde luminosa, 21Z=17:00 golden hour (violeta alto + dorado bajo).
    "00Z": {"from": "#4a3a7a", "to": "#1e1b4b", "accent": "#4a3a7a", "text": "#e2e8f0"},
    "03Z": {"from": "#172554", "to": "#0b1026", "accent": "#172554", "text": "#dbeafe"},
    "06Z": {"from": "#0f172a", "to": "#020617", "accent": "#1e293b", "text": "#e2e8f0"},
    "09Z": {"from": "#1e2a5a", "to": "#b45309", "accent": "#35426b", "text": "#fde68a"},
    "12Z": {"from": "#38bdf8", "to": "#93c5fd", "accent": "#0369a1", "text": "#0c4a6e"},
    "15Z": {"from": "#0ea5e9", "to": "#7dd3fc", "accent": "#0284c7", "text": "#0c4a6e"},
    "18Z": {"from": "#22b8ea", "to": "#67e8f9", "accent": "#0e7490", "text": "#0c4a6e"},
    "21Z": {"from": "#614e72", "to": "#f59e0b", "accent": "#6d28d9", "text": "#fef3c7"},
}

#: lucide icon per hour selector button (oracle JSX hour-icons mapping).
HOUR_ICONS: dict[str, tuple[str, str]] = {
    "06Z": ("sunrise", "#fb923c"),
    "09Z": ("sun", "#f59e0b"),
    "12Z": ("sun", "#f59e0b"),
    "15Z": ("sun", "#f59e0b"),
    "18Z": ("sunset", "#fb7185"),
    "21Z": ("moon", "#818cf8"),
    "00Z": ("moon", "#818cf8"),
    "03Z": ("moon", "#818cf8"),
}

#: slate-600 header chips (oracle tableHeader slate bg; square corners).
_HEADER_QSS = (
    "background-color: #475569; color: #ffffff; font-weight: 600;"
    "font-size: 12px; padding: 7px 6px; border-radius: 6px;"
)


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



#: Observation-hour photographs (assets/hours/<HOUR>.webp, processed at
#: 1920x1080 WebP q82: 5.3 MB of source JPEGs became 569 KB in the package).
HOUR_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "hours"
HOUR_BACKGROUNDS: dict[str, Path] = {
    hora: HOUR_ASSET_DIR / f"{hora}.webp" for hora in synoptic_service.HOURS
}

#: Decoded-and-scaled photos, keyed by (hour, width, height). Painting must not
#: decode or rescale anything: a resize produces one new entry and the rest of
#: the session reuses it.
_BACKGROUND_CACHE: dict[tuple[str, int, int], QPixmap] = {}
_BACKGROUND_CACHE_LIMIT = 24


def hour_background(hora: str, size: QSize) -> QPixmap | None:
    """The hour's photo scaled to COVER ``size`` (centre cropped), or None.

    ``None`` means "no asset for this hour", and the caller falls back to the
    original gradient — so a missing or unreadable file is never a crash.
    """
    path = HOUR_BACKGROUNDS.get(hora)
    if path is None or not path.exists():
        return None
    key = (hora, size.width(), size.height())
    hit = _BACKGROUND_CACHE.get(key)
    if hit is not None:
        return hit
    source = QPixmap(str(path))
    if source.isNull():
        return None
    scaled = source.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    covered = scaled.copy(
        max(0, (scaled.width() - size.width()) // 2),
        max(0, (scaled.height() - size.height()) // 2),
        size.width(),
        size.height(),
    )
    if len(_BACKGROUND_CACHE) >= _BACKGROUND_CACHE_LIMIT:
        _BACKGROUND_CACHE.clear()
    _BACKGROUND_CACHE[key] = covered
    return covered


class _MessageLabel(QLabel):
    """Status/error line that occupies NO height while empty (the two
    unused white rows under Cargar JSON, reported by the owner).

    Optionally notifies a host callback on every change so a floating
    container can stay in sync (SynopticPage's top-right toast).
    """

    def __init__(self, parent: QWidget | None = None,
                 on_change: Callable[[], None] | None = None) -> None:
        super().__init__("", parent)
        self.setWordWrap(True)
        self._on_change = on_change
        self.setVisible(False)  # auto-shows on the first real message

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setVisible(bool(text))
        if self._on_change is not None:
            self._on_change()


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
    """The 8-hour observation grid with drafts, review and structured errors.

    Visual contract: IMG/Modulo OBS 1-2 recreation (dark hourly gradient,
    white cards, lucide icons); behavior contract: SynopticPage.jsx.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        config_dir: str | None = None,
        role: str = "observador",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._config_dir = config_dir
        self._loading_day = False
        self._cli_phenomena: dict[str, object] = {}
        self._role = role  # oracle: Cargar JSON is admin-only
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
        self._primary_headers: list[QLabel] = []  # accent chips (hour theme)

        self._build_ui()
        self._install_shortcuts()
        self._apply_hour_theme()  # gradient + accents follow the hour
        self._observer_prefill()

    def paintEvent(self, event) -> None:
        """The hour's photograph, with the gradient as the fallback.

        A dark scrim is painted over the photo so the white header and titles
        stay readable whatever the picture looks like.
        """
        theme = HOUR_THEMES.get(self.active_hour, HOUR_THEMES["06Z"])
        painter = QPainter(self)
        photo = hour_background(self.active_hour, self.size())
        if photo is not None:
            painter.drawPixmap(0, 0, photo)
            # A whisper of shade so the cards never float on raw pixels...
            painter.fillRect(self.rect(), QColor(0, 0, 0, 30))
            # ...and a darker band at the top, which is where the title lives.
            band_height = 96  # just the title strip, not a quarter of the page
            band = QLinearGradient(0.0, 0.0, 0.0, float(band_height))
            band.setColorAt(0.0, QColor(0, 0, 0, 135))
            band.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.fillRect(0, 0, self.width(), band_height, band)
        else:
            gradient = QLinearGradient(0.0, 0.0, float(self.width()), float(self.height()))
            gradient.setColorAt(0.0, QColor(theme["from"]))
            gradient.setColorAt(1.0, QColor(theme["to"]))
            painter.fillRect(self.rect(), gradient)
        painter.end()
        super().paintEvent(event)

    # ------------------------------------------------------------ theme

    def resizeEvent(self, event) -> None:
        """Keep the floating toast pinned to the top-right on resizes."""
        super().resizeEvent(event)
        self._place_toast()

    def showEvent(self, event) -> None:
        """Scope the toast click-dismiss filter to THIS page while visible:
        an app-wide filter installed once leaked across page instances
        (every dead page kept eating every event — the suite ran ~10x
        slower as pages accumulated in pytest)."""
        super().showEvent(event)
        QApplication.instance().installEventFilter(self)
        self._place_toast()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        QApplication.instance().removeEventFilter(self)

    def _place_toast(self) -> None:
        """Top-right of the window, inside the header band."""
        if self._toast is None or self._toast.width() == 0:
            return
        self._toast.move(
            max(0, self.width() - self._toast.width() - 20), 16
        )
        self._toast.raise_()

    def _dismiss_toast(self) -> None:
        """Owner round 6: EVERY notification dies after 5s (or on click)."""
        self._status_timer.stop()
        self.error_label.setText("")
        self.status_label.setText("")

    def eventFilter(self, watched, event) -> bool:
        """A click anywhere in the app dismisses the toast (no consumption)."""
        if event.type() == event.Type.MouseButtonPress and (
            self.error_label.text() or self.status_label.text()
        ):
            self._dismiss_toast()
        return super().eventFilter(watched, event)

    def _refresh_toast(self) -> None:
        """Show the toast only while a message lives; status auto-dismisses.

        Decided on TEXT emptiness, not isVisible(): a hidden parent makes
        every child's isVisible() False (the label/toast catch-22).
        """
        if self._toast is None:
            return
        has_text = bool(self.error_label.text()) or bool(self.status_label.text())
        self.error_label.setVisible(bool(self.error_label.text()))
        self.status_label.setVisible(bool(self.status_label.text()))
        self._toast.setVisible(has_text)
        if has_text:
            self._toast.adjustSize()
            self._place_toast()
            self._status_timer.start()

    def _style_hour_button(self, hora: str, accent: str) -> None:
        """One hour button: active gets the accent, others keep the fill tint"""
        button = self.hour_buttons[hora]
        active = hora == self.active_hour
        if active:
            button.setStyleSheet(
                f"QPushButton {{ background-color: {accent}; color: #ffffff;"
                "border: none; border-radius: 8px; padding: 8px 6px;"
                "font-weight: 700; font-size: 12px; }"
            )
        else:
            fill = button.property("fill") or "empty"
            tint = {"part": "#fffbeb", "ok": "#ecfdf5"}.get(str(fill), "#f8fafc")
            button.setStyleSheet(_hour_button_qss(tint))
        icon_name, base_color = HOUR_ICONS[hora]
        button.setIcon(lucide_icon(
            icon_name, "#ffffff" if active else base_color, 14
        ))
        button.setIconSize(QSize(14, 14))

    def _hour_has_photo(self) -> bool:
        path = HOUR_BACKGROUNDS.get(self.active_hour)
        return path is not None and path.exists()

    def _apply_hour_theme(self) -> None:
        """Accent chips, title color and active-hour button follow the hour."""
        theme = HOUR_THEMES.get(self.active_hour, HOUR_THEMES["06Z"])
        accent = theme["accent"]
        # over a photograph the title is always white; the gradient themes keep
        # their per-hour ink colour
        text_color = "#ffffff" if self._hour_has_photo() else theme["text"]
        self.title_label.setText(f"Observación Sinóptica {self.active_hour}")
        self.title_label.setStyleSheet(
            f"background: transparent; color: {text_color};"
            "font-size: 22px; font-weight: 700;"
        )
        chip_qss = (
            f"background-color: {accent}; color: #ffffff; font-weight: 700;"
            "font-size: 12px; padding: 8px 14px; border: none; border-radius: 10px;"
        )
        for chip in (self.observer_label, *self._primary_headers):
            chip.setStyleSheet(chip_qss)
        for hora in self.hour_buttons:
            self._style_hour_button(hora, accent)
        self.save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {accent}; color: #ffffff;"
            "border: none; border-radius: 12px; padding: 10px 12px;"
            "font-weight: 700; font-size: 13px; }"
            "QPushButton:hover { opacity: 0.95; }"
        )
        self.save_btn.setIcon(lucide_icon("save", "#ffffff", 16))
        self.update()  # repaint the gradient (hour themes change with the hour)

    # ------------------------------------------------------------ building

    def _grid_header(self, grid: QGridLayout, row: int, cells: list,
                     accent: str | None = None) -> None:
        """Slate header row (oracle tableHeader); cells are (text, span).

        ``accent`` renders the oracle primaryHeader chips (hour accent) and
        registers them for the per-hour theme application.
        """
        col = 0
        for text, span in cells:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            if accent is None:
                label.setStyleSheet(_HEADER_QSS)
            else:
                label.setStyleSheet(
                    f"background-color: {accent}; color: #ffffff;"
                    "font-weight: 700; font-size: 12px; padding: 7px 6px;"
                )
                self._primary_headers.append(label)
            grid.addWidget(label, row, col, 1, span)
            col += span

    def _grid_header_text(self, grid: QGridLayout, row: int, texts: list) -> None:
        """Slate header row from plain labels (one column each)."""
        self._grid_header(grid, row, [(text, 1) for text in texts])

    def _card(self) -> QFrame:
        """One oracle sidebar/panel card: white rounded-2xl, slate-200 hairline."""
        frame = QFrame()
        frame.setProperty("card", True)  # marker for tests/probes
        frame.setStyleSheet(CARD_QSS)
        return frame

    def _grid_const(self, grid: QGridLayout, row: int, col: int, text: str) -> None:
        """Readonly slate constant cell (AAXX/333/555, oracle constantClass)."""
        cell = QLineEdit(text)
        cell.setReadOnly(True)
        cell.setStyleSheet(CONST_QSS)
        cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(cell, row, col)

    def _grid_auto(self, grid: QGridLayout, row: int, col: int, key: str) -> None:
        """Readonly blue computed cell (oracle readonlyClass groups)."""
        cell = QLineEdit()
        cell.setReadOnly(True)
        cell.setStyleSheet(RO_QSS)
        cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(cell, row, col)
        self.auto_cells[key] = cell

    def _grid_field(self, grid: QGridLayout, row: int, col: int, key: str,
                    colspan: int = 1) -> None:
        widget = self._make_grid_input(key)
        grid.addWidget(widget, row, col, 1, colspan)

    def _build_ui(self) -> None:
        """OBS 1:1: dark hourly gradient with white cards + icon sidebar."""
        self.setWindowTitle("Observación Sinóptica")

        # the CLI sheets live in the SAME window: a view stack holds the
        # grid host (view 0) and the lazily built CLI views (owner round 5)
        self._grid_host = QWidget()
        # transparent: the page's hourly gradient shows through (owner
        # round 6/8 — otherwise the theme paints flat gray over it)
        self._grid_host.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self._grid_host)
        outer.setContentsMargins(24, 20, 24, 16)
        outer.setSpacing(14)

        # opening title on the dark page band (the old round back arrow is
        # gone — the shell's Inicio rail entry already routes there)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addSpacing(12)
        self.title_label = QLabel("Observación Sinóptica")
        header.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)
        outer.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(16)
        outer.addLayout(content, 1)

        left_column = QWidget()
        left = QVBoxLayout(left_column)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(16)

        # observation card: observer chip row + full data grid -------------
        obs_card = self._card()
        obs_l = QVBoxLayout(obs_card)
        obs_l.setContentsMargins(20, 16, 20, 20)
        obs_l.setSpacing(12)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        self.observer_label = QLabel("Observador")
        self.observer_label.setMinimumWidth(112)
        self.observer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.observer_edit = QLineEdit()
        self.observer_edit.setPlaceholderText("Nombre del Observador...")
        self.observer_edit.setStyleSheet(FIELD_QSS)
        self.observer_edit.setMinimumHeight(32)
        self.observer_label.setBuddy(self.observer_edit)
        meta_row.addWidget(self.observer_label)
        meta_row.addWidget(self.observer_edit, 1)
        obs_l.addLayout(meta_row)

        # station/date/alt live in the grid (row 2) and the calc panel;
        # the widgets stay alive here so setters/tests keep working
        self.station_combo = StyledComboBox()
        for station in self._stations.values():
            # IIiii muestra solo el código (owner round 6); el nombre queda
            # como tooltip del item y vive en dashboard/cards CLI
            self.station_combo.addItem(station.id, station.id)
            self.station_combo.setItemData(
                self.station_combo.count() - 1, station.name,
                Qt.ItemDataRole.ToolTipRole,
            )
        # the IIiii column must not inflate from its longest item name
        self.station_combo.setSizeAdjustPolicy(
            StyledComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.station_combo.setMinimumContentsLength(9)
        self.station_combo.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        # nothing selected until the user (or an observation) picks a station
        if self.station_combo.count():
            self.station_combo.setCurrentIndex(-1)
        self.station_combo.setStyleSheet(
            "QComboBox { background-color: #ffffff; border: 1px solid #cbd5e1;"
            "border-radius: 4px; padding: 4px 8px; }"
            "QComboBox:item { color: #1e293b; }"
            "QComboBox::drop-down { border: none; width: 22px; }"
        )
        self.station_combo.setMinimumHeight(32)

        self.fecha_edit = QDateEdit()
        self.fecha_edit.setDisplayFormat("dd/MM/yyyy")
        self.fecha_edit.setCalendarPopup(False)
        self.fecha_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fecha_edit.setStyleSheet(
            "QDateEdit { background-color: #ffffff; border: 1px solid #cbd5e1;"
            "border-radius: 4px; padding: 4px 8px; color: #1e293b; }"
        )
        self.fecha_edit.setMinimumHeight(32)

        self.correc_alt_edit = QLineEdit()
        self.correc_alt_edit.setReadOnly(True)
        self.correc_alt_edit.setStyleSheet(RO_QSS)
        self.correc_alt_edit.setPlaceholderText("hPa")
        self.correc_alt_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(10)
        self._grid_header(grid, 0, [("MiMiMjMj", 1), ("YYGGIw", 1),
                                    ("IIiii", 1), ("Fecha", 4)])
        self._grid_const(grid, 1, 0, "AAXX")
        self._grid_field(grid, 1, 1, "meteo_2_1")
        grid.addWidget(self.station_combo, 1, 2)
        grid.addWidget(self.fecha_edit, 1, 3, 1, 4)
        self._grid_header(grid, 2, [("IrIXHVV", 1), ("Nddff", 1),
                                    ("1snTTT", 1), ("2snTdTdTd", 1),
                                    ("4PPPP", 1), ("5aPPP", 1),
                                    ("7wwW1W2", 1)])
        self._grid_field(grid, 3, 0, "meteo_4_irixhvv")
        self._grid_field(grid, 3, 1, "meteo_4_1")
        self._grid_auto(grid, 3, 2, "grupo_1sn_ttt")
        self._grid_auto(grid, 3, 3, "grupo_2sn_td")
        self._grid_auto(grid, 3, 4, "grupo_4pppp")
        self._grid_auto(grid, 3, 5, "grupo_5appp")
        self._grid_field(grid, 3, 6, "meteo_4_6")
        self._grid_header(grid, 4, [("8NhCLCMCH", 1), ("333", 1),
                                    ("0CSDLDMDH", 1), ("1snTxTxTx", 1),
                                    ("2snTnTnTn", 1), ("3Ejjj", 1),
                                    ("5EEEjE", 1)])
        self._grid_field(grid, 5, 0, "meteo_6_0")
        self._grid_const(grid, 5, 1, "333")
        self._grid_field(grid, 5, 2, "meteo_6_2")
        self._grid_field(grid, 5, 3, "meteo_6_3")
        self._grid_field(grid, 5, 4, "meteo_6_4")
        self._grid_field(grid, 5, 5, "meteo_6_5")
        self._grid_field(grid, 5, 6, "meteo_6_6")
        self._grid_header(grid, 6, [("5nFnFnFn", 1), ("56DLDMDH", 1),
                                    ("58/59P24P24P24", 1), ("6RRRtr", 1),
                                    ("7R24R24R24R24", 1), ("8NsChshs", 1),
                                    ("8NsChshs", 1)])
        self._grid_field(grid, 7, 0, "meteo_8_0")
        self._grid_field(grid, 7, 1, "meteo_8_1")
        self._grid_auto(grid, 7, 2, "grupo_58_59_p24")
        self._grid_field(grid, 7, 3, "meteo_8_3")
        self._grid_field(grid, 7, 4, "meteo_8_4")
        self._grid_field(grid, 7, 5, "meteo_8_5")
        self._grid_field(grid, 7, 6, "meteo_8_6")

        # 8NsChshs/9SpSpSpSp station rows: plain group names only — the
        # user's spec dropped every per-station numeric label on headers
        for base, field_row in ((8, 10), (10, 12), (12, 14)):
            cells: list[tuple[str, int]] = (
                [("8NsChshs", 1)] * 2 if base == 8 else []
            )
            cells.extend([("9SpSpSpSp", 1)] * (5 if base == 8 else 7))
            self._grid_header(grid, base, cells)
            for col in range(7):
                self._grid_field(grid, base + 1, col, f"meteo_{field_row}_{col}")
        final_cells: list[tuple[str, int]] = [
            ("9SpSpSpSp", 1),
        ] * 5 + [("555", 1), ("29UUU", 1)]
        self._grid_header(grid, 14, final_cells)
        for col in range(5):
            self._grid_field(grid, 15, col, f"meteo_16_{col}")
        self._grid_const(grid, 15, 5, "555")
        self._grid_auto(grid, 15, 6, "grupo_29uuu")
        for col in range(7):  # columnas equilibradas; la grilla llena la card
            grid.setColumnStretch(col, 1)
        obs_l.addLayout(grid, 1)
        self.grid = grid
        left.addWidget(obs_card, 1)

        # calculations card: 7-column checkerboard per IMG 2 — LEFT pair
        # reads label(cell0)/value(cell1) down its rows; every other column
        # stacks its slate header on TOP of the fill cell. Explicit (row,
        # col) cells: no widget ever shares a grid position.
        calc_card = self._card()
        calc_l = QVBoxLayout(calc_card)
        calc_l.setContentsMargins(16, 14, 16, 16)
        calc = QGridLayout()
        calc.setHorizontalSpacing(6)
        calc.setVerticalSpacing(8)
        for col in range(7):
            calc.setColumnStretch(col, 1)
        calc_l.addLayout(calc)

        def clabel(row: int, col: int, text: str) -> None:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setStyleSheet(_HEADER_QSS)
            calc.addWidget(label, row, col)

        def cfield(row: int, col: int, key: str) -> None:
            calc.addWidget(self._make_grid_input(key), row, col)

        def cro(row: int, col: int, store: dict, key: str,
                placeholder: str = "") -> None:
            cell = QLineEdit()
            cell.setReadOnly(True)
            cell.setStyleSheet(RO_QSS)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if placeholder:
                cell.setPlaceholderText(placeholder)
            calc.addWidget(cell, row, col)
            store[key] = cell

        self._grid_header(
            calc, 0,
            [("Cálculos de Estación", 2), ("Presión de la Estación", 1),
             ("P 3 Horas", 1), ("P 24 Horas", 1), ("Máx. / Mín.", 1),
             ("Máx. / Mín. 24 H", 1)],
            accent=HOUR_THEMES.get(self.active_hour, HOUR_THEMES["06Z"])["accent"],
        )

        # left pair (Cálculos de Estación): label left, fill cell right
        clabel(1, 0, "Ts.")
        cfield(1, 1, "ts")
        clabel(2, 0, "Pr.")
        cro(2, 1, self.readouts, "punto_rocio", "°C")
        clabel(3, 0, "Th.")
        cfield(3, 1, "th")
        clabel(4, 0, "Tv.")
        cro(4, 1, self.readouts, "tension_vapor", "hPa")
        clabel(5, 0, "Dif.")
        cro(5, 1, self.readouts, "diferencia", "°C")
        clabel(6, 0, "Hr.")
        cro(6, 1, self.readouts, "humedad_relativa", "%")

        # Presión de la Estación column (col2): grease header, data below
        clabel(1, 2, "Let. Barom.")
        cfield(2, 2, "let_barom")
        clabel(3, 2, "Correc. Temp.")
        cfield(4, 2, "correc_temp")
        clabel(5, 2, "Pres. Est.")
        cfield(6, 2, "pres_est")
        clabel(7, 2, "Correc. Alt.")
        calc.addWidget(self.correc_alt_edit, 8, 2)
        clabel(9, 2, "Pres. NMM")
        cro(10, 2, self.readouts, "pres_nmm", "hPa")

        # P 3 Horas column (col3)
        clabel(1, 3, "P 3")
        cfield(2, 3, "p3")
        clabel(3, 3, "Let.")
        cro(4, 3, self.auto_cells, "p3_let", "hPa")
        clabel(5, 3, "Dif.")
        cro(6, 3, self.auto_cells, "p3_dif", "hPa")

        # P 24 Horas column (col4)
        clabel(1, 4, "P 24")
        cfield(2, 4, "p24")
        clabel(3, 4, "Let.")
        cro(4, 4, self.auto_cells, "p24_let", "hPa")
        clabel(5, 4, "Dif.")
        cro(6, 4, self.auto_cells, "p24_dif", "hPa")

        # Máx. / Mín. (col5) and the 24h twin (col6)
        clabel(1, 5, "T Máx.")
        clabel(1, 6, "T Máx. 24 H")
        cfield(2, 5, "t_max")
        cfield(2, 6, "t_max_24h")
        clabel(3, 5, "T Mín.")
        clabel(3, 6, "T Mín. 24 H")
        cfield(4, 5, "t_min")
        cfield(4, 6, "t_min_24h")
        clabel(5, 5, "LL")
        clabel(5, 6, "LL 24 H")
        cfield(6, 5, "ll")
        cfield(6, 6, "ll_24h")
        left.addWidget(calc_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.viewport().setAutoFillBackground(False)
        left_column.setStyleSheet("background: transparent;")
        scroll.setWidget(left_column)
        content.addWidget(scroll, 1)

        # right column: stacked cards, deliberately slimmer than the oracle's
        # 256px to give the form protagonism; scroll-wrapped so no card is
        # crushed or clipped at 1366x768
        side = QWidget()
        side.setMinimumWidth(198)
        side.setMaximumWidth(204)
        side.setStyleSheet("background: transparent;")
        right = QVBoxLayout(side)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)

        # card 1: hours of observation + completion bar + day navigation
        hours_card = self._card()
        hours_l = QVBoxLayout(hours_card)
        hours_l.setContentsMargins(10, 8, 10, 10)
        hours_l.setSpacing(6)
        hours_head = QHBoxLayout()
        hours_head.setSpacing(6)
        clock_icon = QLabel()
        clock_icon.setPixmap(icon_pixmap("clock", "#94a3b8", 14))
        hours_head.addWidget(clock_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        hours_title = QLabel("HORAS DE OBSERVACIÓN")
        hours_title.setProperty("cardhead", True)
        hours_title.setStyleSheet(CARDHEAD_QSS)
        hours_head.addWidget(hours_title, 0, Qt.AlignmentFlag.AlignVCenter)
        hours_head.addStretch(1)
        hours_l.addLayout(hours_head)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(6)
        self.progress_label = QLabel("0/21 campos")
        self.progress_label.setStyleSheet(
            "color: #64748b; font-size: 11px; font-weight: 600;"
            "background: transparent;"
        )
        progress_row.addWidget(self.progress_label)
        progress_row.addStretch(1)
        hours_l.addLayout(progress_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setProperty("fillcls", "empty")
        hours_l.addWidget(self.progress)

        hours_grid = QGridLayout()
        hours_grid.setHorizontalSpacing(8)
        hours_grid.setVerticalSpacing(8)
        for index, hora in enumerate(synoptic_service.HOURS):
            row, col = divmod(index, 2)
            button = QPushButton(hora)
            button.setProperty("hourbtn", True)  # marker for tests/probes
            button.setProperty("fill", "empty")
            button.setStyleSheet(HOURBTN_QSS)
            button.setIconSize(QSize(14, 14))
            button.setMinimumHeight(26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, h=hora: self.select_hour(h))
            self.hour_buttons[hora] = button
            hours_grid.addWidget(button, row, col)
        hours_l.addLayout(hours_grid)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #f1f5f9; border: none;")
        divider.setFixedHeight(1)
        hours_l.addWidget(divider)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        self.prev_btn = QPushButton()
        self.prev_btn.setProperty("daynav", "back")
        self.prev_btn.setStyleSheet(DAYNAV_BACK_QSS)
        self.prev_btn.setIcon(lucide_icon("arrow-left", "#0369a1", 16))
        self.prev_btn.setIconSize(QSize(16, 16))
        self.prev_btn.setToolTip("Guardar y cargar día anterior")
        self.prev_btn.setMinimumHeight(26)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(lambda: self.navigate_to_day(-1))
        self.next_btn = QPushButton()
        self.next_btn.setProperty("daynav", "forward")
        self.next_btn.setStyleSheet(DAYNAV_FORWARD_QSS)
        self.next_btn.setIcon(lucide_icon("arrow-right", "#15803d", 16))
        self.next_btn.setIconSize(QSize(16, 16))
        self.next_btn.setToolTip("Guardar y avanzar al siguiente día")
        self.next_btn.setMinimumHeight(26)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(lambda: self.navigate_to_day(1))
        nav_row.addWidget(self.prev_btn, 1)
        nav_row.addWidget(self.next_btn, 1)
        hours_l.addLayout(nav_row)
        right.addWidget(hours_card)

        # card 2: CLI modules with icon-over-number buttons ----------------
        cli_card = self._card()
        cli_l = QVBoxLayout(cli_card)
        cli_l.setContentsMargins(10, 8, 10, 10)
        cli_l.setSpacing(6)
        cli_head = QHBoxLayout()
        cli_head.setSpacing(6)
        file_icon = QLabel()
        file_icon.setPixmap(icon_pixmap("file-text", "#94a3b8", 14))
        cli_head.addWidget(file_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        cli_title = QLabel("MÓDULOS CLI")
        cli_title.setProperty("cardhead", True)
        cli_title.setStyleSheet(CARDHEAD_QSS)
        cli_head.addWidget(cli_title, 0, Qt.AlignmentFlag.AlignVCenter)
        cli_head.addStretch(1)
        cli_l.addLayout(cli_head)
        self._cli_buttons: dict[str, QToolButton] = {}
        cli_row = QHBoxLayout()
        cli_row.setSpacing(8)
        for module_key, label in (
            ("cli3074", "3074"),
            ("cli4074", "4074"),
            ("cli5074", "5074"),
        ):
            button = QToolButton()
            button.setText(label)
            button.setStyleSheet(CLI_BTN_QSS)
            button.setIcon(lucide_icon("file-text", "#94a3b8", 14))
            button.setIconSize(QSize(14, 14))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, m=module_key: self._open_cli(m))
            cli_row.addWidget(button, 1)
            self._cli_buttons[module_key] = button
        cli_l.addLayout(cli_row)
        right.addWidget(cli_card)

        # card 3: extra cloud fields ----------------------------------------
        extra_card = self._card()
        extra_l = QVBoxLayout(extra_card)
        extra_l.setContentsMargins(10, 8, 10, 10)
        extra_l.setSpacing(4)
        extra_head = QHBoxLayout()
        extra_head.setSpacing(6)
        cloud_icon = QLabel()
        cloud_icon.setPixmap(icon_pixmap("cloud", "#94a3b8", 14))
        extra_head.addWidget(cloud_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        extra_title = QLabel("NUBOSIDAD EXTRA")
        extra_title.setProperty("cardhead", True)
        extra_title.setStyleSheet(CARDHEAD_QSS)
        extra_head.addWidget(extra_title, 0, Qt.AlignmentFlag.AlignVCenter)
        extra_head.addStretch(1)
        extra_l.addLayout(extra_head)
        for key, label in (
            ("extra_8ns_1", "GRUPO EXTRA 1 8NS"),
            ("extra_8ns_2", "GRUPO EXTRA 2 8NS"),
        ):
            title = QLabel(label)
            title.setProperty("minilabel", True)
            title.setStyleSheet(MINILABEL_QSS)
            extra_l.addWidget(title)
            extra_input = self._make_grid_input(key)
            extra_input.setMinimumHeight(26)  # sidebar compactness
            extra_l.addWidget(extra_input)
        right.addWidget(extra_card)

        # card 4: actions (Guardar accent per hour + Cargar JSON) -----------
        # notifications float at the top-right of the window (a toast in the
        # header band): they must never squeeze the hour buttons again and
        # carry a 6s auto-dismiss for status lines (owner round 4)
        self._toast = QWidget(self)
        toast_l = QVBoxLayout(self._toast)
        toast_l.setContentsMargins(12, 8, 12, 8)
        self._toast.setObjectName("syntoast")
        self._toast.setStyleSheet(
            "QWidget#syntoast { background-color: rgba(15, 23, 42, 0.94);"
            "border: 1px solid #334155; border-radius: 10px; }"
            "QWidget#syntoast QLabel { background: transparent; border: none; }"
        )
        self.error_label = _MessageLabel(on_change=self._refresh_toast)
        self.error_label.setStyleSheet(
            "color: #fecaca; font-weight: bold; background: transparent;"
        )
        self.status_label = _MessageLabel(on_change=self._refresh_toast)
        self.status_label.setStyleSheet(
            "color: #6ee7b7; font-weight: bold; background: transparent;"
        )
        toast_l.addWidget(self.error_label)
        toast_l.addWidget(self.status_label)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(STATUS_TOAST_MS)
        self._status_timer.timeout.connect(self._dismiss_toast)
        # any click on the page dismisses the toast (owner round 6). Scoped
        # to THIS widget on purpose: an app-wide filter leaks across page
        # instances (every dead page kept eating every event — the suite
        # ran 10x slower as pages accumulated)
        self._refresh_toast()
        actions_card = self._card()
        actions_l = QVBoxLayout(actions_card)
        actions_l.setContentsMargins(10, 8, 10, 10)
        actions_l.setSpacing(5)
        self.save_btn = QPushButton("Guardar Observación")
        self.save_btn.setIconSize(QSize(16, 16))
        self.save_btn.setProperty("dark", True)  # contrato Lotes-C se conserva
        self.save_btn.setDefault(True)
        self.save_btn.setMinimumHeight(32)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_clicked)
        self.cargar_btn = QPushButton("Cargar JSON")
        self.cargar_btn.setProperty("secondaryaction", True)  # marker
        self.cargar_btn.setStyleSheet(SECONDARY_BTN_QSS)
        self.cargar_btn.setIcon(lucide_icon("upload", "#475569", 15))
        self.cargar_btn.setIconSize(QSize(15, 15))
        self.cargar_btn.setMinimumHeight(28)
        self.cargar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # clicked carries checked=False: never let it become the path
        self.cargar_btn.clicked.connect(lambda: self._load_json_file())
        actions_l.addWidget(self.save_btn)
        actions_l.addWidget(self.cargar_btn)
        right.addWidget(actions_card)
        right.addStretch(1)

        content.addWidget(side, 0, Qt.AlignmentFlag.AlignTop)
        # wiring -----------------------------------------------------------
        self.station_combo.currentIndexChanged.connect(self._on_station_changed)
        self.fecha_edit.dateChanged.connect(self._on_date_changed)
        self.observer_edit.textChanged.connect(self._on_observer_changed)

        self._cli_views: dict[str, QWidget] = {}
        self._stack = QStackedWidget(self)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self._stack)
        self._stack.addWidget(self._grid_host)
        # structural transparency: the theme paints QWidget/viewport gray
        # over the hourly gradient — the stack and every scroll host in the
        # CLI views must let the gradient through (owner round 8)
        self.setStyleSheet(
            "QStackedWidget { background: transparent; }"
            "QScrollArea { background: transparent; }"
            "QScrollArea > QWidget { background: transparent; }"
            "QAbstractScrollArea > QWidget > QWidget { background: transparent; }"
        )

    def _open_cli(self, module_key: str) -> None:
        """Swap to the CLI view INSIDE this window (owner round 5: no extra
        windows); back returns to the last open synoptic hour."""
        if not self.station_id or not self.fecha_iso:
            self.clear_error_state()
            self.error_label.setText(
                "Elegí estación y fecha antes de abrir el módulo CLI"
            )
            return
        view = self._cli_views.get(module_key)
        if view is None:
            view = self._make_cli_view(module_key)
            self._cli_views[module_key] = view
            self._stack.addWidget(view)
        elif (view.station, view.fecha) != (self.station_id, self.fecha_iso):
            view.station = self.station_id
            view.fecha = self.fecha_iso
            view.load_data()  # context moved: reload the stored sheet
        self._stack.setCurrentWidget(view)

    def _make_cli_view(self, module_key: str) -> QWidget:
        from oms_ui.pages import cli3074, cli4074, cli5074

        classes = {
            "cli3074": cli3074.Cli3074View,
            "cli4074": cli4074.Cli4074View,
            "cli5074": cli5074.Cli5074View,
        }
        view = classes[module_key](
            self._conn, station=self.station_id or "", fecha=self.fecha_iso or ""
        )
        view.back_requested.connect(self._back_from_cli)
        view.switch_requested.connect(self._open_cli)
        view.synop_hour_requested.connect(self._jump_to_synop_hour)
        return view

    def _back_from_cli(self) -> None:
        """Return to the grid: the active hour was never touched — the last
        synoptic hour the user had open stays exactly as it was."""
        self._stack.setCurrentWidget(self._grid_host)

    def _jump_to_synop_hour(self, hora: str) -> None:
        """VER HORA SYNOP: select that hour on the grid and go back to it."""
        self.select_hour(hora)
        self._stack.setCurrentWidget(self._grid_host)

    def navigate_to_day(self, delta: int) -> None:
        """Oracle navigateToDay: silent-save, load/create the target day.

        - saves the current day first (best effort, failures tolerated);
        - loads the target day flat data from the diario document;
        - backwards with no stored day: blocked with a message (never navigates);
        - forwards with no stored day: creates a fresh day seeded with the
          station, date, correction and remembered observer;
        - keeps the active hour between days; invalid drafts never revive.
        """
        station = self.station_id
        fecha = self.fecha_iso
        if not station or not fecha:
            self.clear_error_state()
            self.error_label.setText(
                "Elegí estación y fecha antes de navegar entre días"
            )
            return
        # 1) persist the current day quietly; a validation failure must not
        # block navigation (oracle try/catch around the save, console.error).
        # Only user-touched data triggers the save: walking through empty
        # days must not fabricate diario documents.
        if self._dirty:
            try:
                self.do_save()
            except Exception:
                _LOGGER.exception("Error al guardar día actual antes de navegar")
        # 2) target date (calendar math, not string math)
        target_date: QDate = self.fecha_edit.date().addDays(delta)
        target = target_date.toString("yyyy-MM-dd")
        # 3) load or create
        try:
            # A2: the whole day comes from the single document object, so the
            # grid, the observer slots and the CLI views share one source.
            from oms_core.services import document as document_service

            day_doc = document_service.load_day_document(self._conn, station, target)
            loaded = day_doc.horas if day_doc is not None else None
        except synoptic_service.SaveError as exc:
            self.error_label.setText(f"Error al cargar el día: {exc}")
            return
        base = {
            "station_id": station,
            "fecha": target,
            "correc_alt": self.correc_alt_edit.text(),
        }
        if loaded is None:
            if delta < 0:
                self.error_label.setText(f"No hay observación para {target}")
                return  # backwards never invents a day (oracle)
            remembered = synoptic_service.observer_for(self._conn, station)
            self.observations = {
                hora: dict(base) for hora in synoptic_service.HOURS
            }
            if remembered:
                for hour_data in self.observations.values():
                    hour_data["nombre_observador"] = remembered
        else:
            self.observations = {}
            for hora in synoptic_service.HOURS:
                merged = dict(base)
                merged.update(loaded.get(hora) or {})  # stored data wins
                self.observations[hora] = merged
        # 4) repaint the form for the new day (active hour is preserved)
        self._refresh_cli_phenomena()
        self.fecha_edit.setDate(target_date)
        _LOGGER.debug("día cargado: estación %s fecha %s", station, target)
        self._load_hour_into_fields()
        self._refresh_hour_mode()
        self.refresh_progress()
        self._update_readouts()
        self._dirty = False
        self.status_label.setText(
            f"Día: {target_date.toString('dd/MM/yyyy')}"
        )

    def _load_json_file(self, path: str | None = None) -> None:
        """Load a diario JSON file into the form (OBS Cargar JSON)."""
        from PySide6.QtWidgets import QFileDialog

        from oms_core.services import ingest as ingest_service

        if path is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self, "Cargar JSON", "", "JSON (*.json)"
            )
            if not chosen:
                return
            path = chosen
        if not path:
            return
        try:
            day = ingest_service.load_hours(path)
        except (OSError, ValueError) as exc:  # bad files show inline
            self.error_label.setText(f"JSON inválido: {exc}")
            return
        self.error_label.setText("")
        if day.station:
            self.set_station(day.station)
        if day.fecha:
            self.set_date(day.fecha)
        count = 0
        for hora, hour_data in day.hours.items():
            if hora not in synoptic_service.HOURS:
                continue
            # a loaded document REPLACES the hours it carries: merging would
            # leave values from whatever was on screen before
            entry = self.observations.setdefault(hora, {})
            entry.clear()
            for key, value in hour_data.items():
                if value is None:
                    continue
                entry[str(key)] = str(value)
            count += 1
        _LOGGER.info("JSON cargado desde %s: %s horas, estación %s, fecha %s",
                     path, count, day.station, day.fecha)
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
        widget.setStyleSheet(FIELD_QSS)  # oracle fieldClass token, inline
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setMinimumHeight(32)
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
        self._apply_hour_theme()  # gradient + accents follow the hour

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
            widget.setStyleSheet(FIELD_QSS)
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
        """Picking a date in the editor loads that day, silently.

        It used to only refresh the readouts, so choosing a date showed the
        previous day's data (and the group fields never arrived). This path
        never saves and never opens a dialog, so it cannot disturb the draft.
        """
        if self.station_id and not self._loading_day:
            self._load_day_silently(self.fecha_iso)
        self._refresh_dynamic_states()
        self._schedule_draft_autosave()

    def _load_day_silently(self, target: str) -> None:
        """Read a day from the database into the form, without any side effect."""
        from oms_core.services import document as document_service

        self._loading_day = True
        try:
            day_doc = document_service.load_day_document(
                self._conn, self.station_id, target
            )
            base = {
                "station_id": self.station_id,
                "fecha": target,
                "correc_alt": self.correc_alt_edit.text(),
            }
            if day_doc is None:
                remembered = synoptic_service.observer_for(self._conn, self.station_id)
                self.observations = {
                    hora: dict(base) for hora in synoptic_service.HOURS
                }
                if remembered:
                    for hour_data in self.observations.values():
                        hour_data["nombre_observador"] = remembered
            else:
                self.observations = {}
                for hora in synoptic_service.HOURS:
                    merged = dict(base)
                    merged.update(day_doc.horas.get(hora) or {})
                    self.observations[hora] = merged
            self._load_hour_into_fields()
            self._refresh_hour_mode()
            self.refresh_progress()
            self._update_readouts()
            self._dirty = False
            self._refresh_cli_phenomena()
            _LOGGER.debug("día cargado por fecha: %s %s", self.station_id, target)
        except synoptic_service.SaveError as exc:
            self.error_label.setText(f"Error al cargar el día: {exc}")
        finally:
            self._loading_day = False
        self._cli_phenomena: dict[str, object] = {}

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
                self._style_hour_button(hora, HOUR_THEMES.get(self.active_hour, HOUR_THEMES["06Z"])["accent"])
        active = synoptic_service.hour_completion(
            self.observations.get(self.active_hour) or {}, self.active_hour
        )
        self.progress.setRange(0, active["total"])
        self.progress.setValue(int(active["done"]))
        fillcls = (
            "empty" if active["done"] == 0
            else "ok" if active["ratio"] == 1.0
            else "part"
        )
        chunk = {"empty": "#e2e8f0", "part": "#fbbf24", "ok": "#10b981"}[fillcls]
        self.progress.setStyleSheet(_progress_qss(chunk))
        self.progress_label.setText(
            f"{self.active_hour}: {active['done']}/{active['total']} campos"
        )

    def _update_readouts(self) -> None:
        derived = self._derive_active()
        self._refresh_w1w2_suggestion(derived)
        self.results_per_hour[self.active_hour] = derived
        for key, widget in self.readouts.items():
            widget.blockSignals(True)
            widget.setText(derived.get(key, ""))
            widget.blockSignals(False)
        self._update_autos()

    def _refresh_w1w2_suggestion(self, derived: dict) -> None:
        """Show the computed 7wwW1W2 as a hint while the field is empty.

        Regla 12.2.6.6.1 fixes the window per hour; the figures come from the
        phenomena marked in the CLI 3074 within it. It is a placeholder, never
        stored data: accepting it is still the observer's decision.
        """
        widget = self.field_widgets.get("meteo_4_6")
        if widget is None or widget.text().strip():
            return
        ww = str((derived or {}).get("tiempo_presente") or "")
        past = past_weather.compute_w1w2(
            self.active_hour, self.observations, self._cli_phenomena
        )
        if past == "//" and not ww:
            # nothing to suggest: keep the oracle's placeholder
            widget.setPlaceholderText(_PLACEHOLDERS.get("meteo_4_6", "7"))
            return
        widget.setPlaceholderText(f"7{ww or '//'}{past}")

    def _refresh_cli_phenomena(self) -> None:
        """Per synoptic hour, the phenomena marked in the CLI 3074 sheet."""
        self._cli_phenomena = {}
        if not self.station_id or not self.fecha_iso:
            return
        try:
            from oms_core.services import cli as cli_service

            doc = cli_service.load_cli(
                self._conn, self.station_id, self.fecha_iso, "cli3074"
            )
        except Exception:  # noqa: BLE001 - a hint must never break the page
            _LOGGER.debug("sin fenómenos del CLI 3074 para la sugerencia")
            return
        if not isinstance(doc, dict):
            return
        rows = doc.get("horas") if isinstance(doc.get("horas"), dict) else doc
        if not isinstance(rows, dict):
            return
        for hora, row_key in cli_service.SYNOP_ROWS:
            row = rows.get(row_key)
            if isinstance(row, dict):
                self._cli_phenomena[hora] = row.get("fenomenos") or {}

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
                widget.setStyleSheet(FIELD_QSS)
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
            widget.setStyleSheet(FIELD_ERROR_QSS)
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
        # rule R4: the day closes at 06Z of the next day; afterwards only the
        # audit roles may correct it (and the change is versioned).
        from oms_core.services import closure

        if fecha and not closure.can_edit(self._role, fecha):
            self.error_label.setText(closure.closed_message(fecha))
            return
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
        """Debounced background autosave: silent like the CLI saves — a
        timer that fires after the DB went away must never surface."""
        station = self.station_id
        fecha = self.fecha_iso
        if not station or not fecha:
            return
        try:
            draft = synoptic_service.bind_draft(
                self.observations, self.active_hour, self.results_per_hour,
                station, fecha,
            )
            synoptic_service.save_draft(self._config_dir, draft)
        except (synoptic_service.SaveError, sqlite3.Error):
            _LOGGER.exception("Draft autosave falló")
        else:
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
