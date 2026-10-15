"""Lucide icon renderer — drawn icons, one system, one stroke weight.

Inner elements copied from lucide-static v1.57.0 (ISC license);
``stroke="currentColor"`` is substituted by the requested color at render
time. The OBS 1:1 recreation uses the exact lucide set of the oracle
(Sunrise, Sun, Sunset, Moon, Clock, FileText, Cloud, Save, Upload,
ArrowLeft/Right).
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
    }.get(name)
    if inner is None:
        raise LookupError(f"unknown lucide icon: {name}")
    body = inner.replace("currentColor", color)
    source = QByteArray(f"<svg {_SVG_HEADER}>{body}</svg>".encode())
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
