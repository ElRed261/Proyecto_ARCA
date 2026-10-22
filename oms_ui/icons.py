"""Lucide icon renderer — drawn icons, one system, one stroke weight.

Inner elements copied from lucide-static v1.57.0 (ISC license);
``stroke="currentColor"`` is substituted by the requested color at render
time. The OBS 1:1 recreation uses the exact lucide set of the oracle
(Sunrise, Sun, Sunset, Moon, Clock, FileText, Cloud, Save, Upload,
ArrowLeft/Right); the monthly summary adds Plus, Gauge, FileWarning,
Trash2, BarChart3, Table and Download from the same frozen set.
"""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG_HEADER = (
    'xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
)

#: inner SVG elements of lucide sunrise (lucide-static v1.57.0, ISC)
_SUNRISE_INNER = (
    '<path d="M12 2v8" />\n  <path d="m4.93 10.93 1.41 1.41" />\n  <path d="M2 18h2" />\n  <path d="M20 18h2" />\n  <path d="m19.07 10.93-1.41 1.41" />\n  <path d="M22 22H2" />\n  <path d="m8 6 4-4 4 4" />\n  <path d="M16 18a4 4 0 0 0-8 0" />'
)

#: inner SVG elements of lucide sun (lucide-static v1.57.0, ISC)
_SUN_INNER = (
    '<circle cx="12" cy="12" r="4" />\n  <path d="M12 2v2" />\n  <path d="M12 20v2" />\n  <path d="m4.93 4.93 1.41 1.41" />\n  <path d="m17.66 17.66 1.41 1.41" />\n  <path d="M2 12h2" />\n  <path d="M20 12h2" />\n  <path d="m6.34 17.66-1.41 1.41" />\n  <path d="m19.07 4.93-1.41 1.41" />'
)

#: inner SVG elements of lucide sunset (lucide-static v1.57.0, ISC)
_SUNSET_INNER = (
    '<path d="M12 10V2" />\n  <path d="m4.93 10.93 1.41 1.41" />\n  <path d="M2 18h2" />\n  <path d="M20 18h2" />\n  <path d="m19.07 10.93-1.41 1.41" />\n  <path d="M22 22H2" />\n  <path d="m16 6-4 4-4-4" />\n  <path d="M16 18a4 4 0 0 0-8 0" />'
)

#: inner SVG elements of lucide moon (lucide-static v1.57.0, ISC)
_MOON_INNER = (
    '<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401" />'
)

#: inner SVG elements of lucide clock (lucide-static v1.57.0, ISC)
_CLOCK_INNER = (
    '<circle cx="12" cy="12" r="10" />\n  <path d="M12 6v6l4 2" />'
)

#: inner SVG elements of lucide file-text (lucide-static v1.57.0, ISC)
_FILE_TEXT_INNER = (
    '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />\n  <path d="M14 2v5a1 1 0 0 0 1 1h5" />\n  <path d="M10 9H8" />\n  <path d="M16 13H8" />\n  <path d="M16 17H8" />'
)

#: inner SVG elements of lucide cloud (lucide-static v1.57.0, ISC)
_CLOUD_INNER = (
    '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />'
)

#: inner SVG elements of lucide save (lucide-static v1.57.0, ISC)
_SAVE_INNER = (
    '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />\n  <path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7" />\n  <path d="M7 3v4a1 1 0 0 0 1 1h7" />'
)

#: inner SVG elements of lucide upload (lucide-static v1.57.0, ISC)
_UPLOAD_INNER = (
    '<path d="M12 3v12" />\n  <path d="m17 8-5-5-5 5" />\n  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />'
)

#: inner SVG elements of lucide arrow-left (lucide-static v1.57.0, ISC)
_ARROW_LEFT_INNER = (
    '<path d="m12 19-7-7 7-7" />\n  <path d="M19 12H5" />'
)

#: inner SVG elements of lucide arrow-right (lucide-static v1.57.0, ISC)
_ARROW_RIGHT_INNER = (
    '<path d="M5 12h14" />\n  <path d="m12 5 7 7-7 7" />'
)

#: inner SVG elements of lucide plus (lucide-static v1.57.0, ISC)
_PLUS_INNER = '<path d="M5 12h14" />\n  <path d="M12 5v14" />'

#: inner SVG elements of lucide gauge (lucide-static v1.57.0, ISC)
_GAUGE_INNER = '<path d="m12 14 4-4" />\n  <path d="M3.34 19a10 10 0 1 1 17.32 0" />'

#: inner SVG elements of lucide file-warning (lucide-static v1.57.0, ISC)
_FILE_WARNING_INNER = (
    '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />\n  <path d="M14 2v5a1 1 0 0 0 1 1h5" />\n  <path d="M12 9v4" />\n  <path d="M12 17h.01" />'
)

#: inner SVG elements of lucide trash-2 (lucide-static v1.57.0, ISC)
_TRASH_2_INNER = (
    '<path d="M10 11v6" />\n  <path d="M14 11v6" />\n  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />\n  <path d="M3 6h18" />\n  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />'
)

#: inner SVG elements of lucide bar-chart-3 (lucide-static v1.57.0, ISC)
_BAR_CHART_3_INNER = (
    '<path d="M3 3v16a2 2 0 0 0 2 2h16" />\n  <path d="M18 17V9" />\n  <path d="M13 17V5" />\n  <path d="M8 17v-3" />'
)

#: inner SVG elements of lucide table (lucide-static v1.57.0, ISC)
_TABLE_INNER = (
    '<path d="M12 3v18" />\n  <rect x="3" y="3" width="18" height="18" rx="2" />\n  <path d="M3 9h18" />\n  <path d="M3 15h18" />'
)

#: inner SVG elements of lucide download (lucide-static v1.57.0, ISC)
_DOWNLOAD_INNER = (
    '<path d="M12 15V3" />\n  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />\n  <path d="m7 10 5 5 5-5" />'
)

#: inner SVG elements of lucide calendar-days (lucide-static v1.57.0, ISC)
_CALENDAR_DAYS_INNER = (
    '<path d="M8 2v4" />\n  <path d="M16 2v4" />\n  <rect width="18" height="18" x="3" y="4" rx="2" />'
    '\n  <path d="M3 10h18" />\n  <path d="M8 14h.01" />\n  <path d="M12 14h.01" />'
    '\n  <path d="M16 14h.01" />\n  <path d="M8 18h.01" />\n  <path d="M12 18h.01" />'
    '\n  <path d="M16 18h.01" />'
)

#: inner SVG elements of lucide calendar (lucide-static v1.57.0, ISC)
_CALENDAR_INNER = (
    '<path d="M8 2v4" />\n  <path d="M16 2v4" />\n  <rect width="18" height="18" x="3" y="4" rx="2" />'
    '\n  <path d="M3 10h18" />'
)

#: inner SVG elements of lucide folder (lucide-static v1.57.0, ISC)
_FOLDER_INNER = (
    '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />'
)

#: inner SVG elements of lucide chevron-right (lucide-static v1.57.0, ISC)
_CHEVRON_RIGHT_INNER = '<path d="m9 18 6-6-6-6" />'

#: inner SVG elements of lucide radio (lucide-static v1.57.0, ISC)
_RADIO_INNER = (
    '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9" />\n  <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5" />'
    '\n  <circle cx="12" cy="12" r="2" />\n  <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5" />'
    '\n  <path d="M19.1 4.9C23 8.8 23 15.1 19.1 19" />'
)

#: inner SVG elements of lucide user (lucide-static v1.57.0, ISC)
_USER_INNER = (
    '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />'
    '\n  <circle cx="12" cy="7" r="4" />'
)

#: inner SVG elements of lucide alert-triangle (lucide-static v1.57.0, ISC)
_ALERT_TRIANGLE_INNER = (
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />'
    '\n  <path d="M12 9v4" />\n  <path d="M12 17h.01" />'
)

#: inner SVG elements of lucide check-circle (lucide-static v1.57.0, ISC)
_CHECK_CIRCLE_INNER = (
    '<path d="M21.801 10A10 10 0 1 1 17 3.335" />\n  <path d="m9 11 3 3L22 4" />'
)

#: inner SVG elements of lucide book-open (lucide-static v1.57.0, ISC)
_BOOK_OPEN_INNER = (
    '<path d="M12 7v14" />\n  <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />'
)

_CACHE: dict[tuple[str, str, int], QIcon] = {}


def lucide_icon(name: str, color: str, size: int = 16) -> QIcon:
    """Render one lucide icon with ``color`` strokes; results are cached."""
    key = (name, color, size)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    inner = {
        "sunrise": _SUNRISE_INNER,
        "sun": _SUN_INNER,
        "sunset": _SUNSET_INNER,
        "moon": _MOON_INNER,
        "clock": _CLOCK_INNER,
        "file-text": _FILE_TEXT_INNER,
        "cloud": _CLOUD_INNER,
        "save": _SAVE_INNER,
        "upload": _UPLOAD_INNER,
        "arrow-left": _ARROW_LEFT_INNER,
        "arrow-right": _ARROW_RIGHT_INNER,
        "plus": _PLUS_INNER,
        "gauge": _GAUGE_INNER,
        "file-warning": _FILE_WARNING_INNER,
        "trash-2": _TRASH_2_INNER,
        "bar-chart-3": _BAR_CHART_3_INNER,
        "table": _TABLE_INNER,
        "download": _DOWNLOAD_INNER,
        "calendar": _CALENDAR_INNER,
        "calendar-days": _CALENDAR_DAYS_INNER,
        "folder": _FOLDER_INNER,
        "chevron-right": _CHEVRON_RIGHT_INNER,
        "radio": _RADIO_INNER,
        "user": _USER_INNER,
        "alert-triangle": _ALERT_TRIANGLE_INNER,
        "check-circle": _CHECK_CIRCLE_INNER,
        "book-open": _BOOK_OPEN_INNER,
    }.get(name)
    if inner is None:
        raise LookupError(f"unknown lucide icon: {name}")
    body = inner.replace("currentColor", color)
    # The stroke colour lives in the SVG header, so it is the header that
    # must be substituted; replacing it inside the body alone left every
    # icon rendering in SVG's default black.
    header = _SVG_HEADER.replace("currentColor", color)
    source = QByteArray(f"<svg {header}>{body}</svg>".encode())
    renderer = QSvgRenderer(source)
    if not renderer.isValid():
        raise ValueError(f"invalid lucide SVG: {name}")
    icon = QIcon()
    for scale in (1, 2):  # usuario hi-dpi + offscreen verificación
        pixmap = QPixmap(size * scale, size * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    _CACHE[key] = icon
    return icon


def icon_pixmap(name: str, color: str, size: int = 16) -> QPixmap:
    """Single pixmap variant for icon-beside-text labels."""
    return lucide_icon(name, color, size).pixmap(size, size)
