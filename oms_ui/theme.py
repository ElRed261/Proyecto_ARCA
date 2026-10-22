"""Theme + font loading for Neo Arca (PRD F7.5).

Plus Jakarta Sans is bundled (copied from the OLD web app, offline-first:
no CDN, no system dependency) and registered via QFontDatabase with a
system-sans fallback when the files are missing.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

_ASSETS = Path(__file__).resolve().parent / "assets"
_FONTS_DIR = _ASSETS / "fonts"
_QSS_FILE = Path(__file__).resolve().parent / "theme.qss"

#: Weights shipped with the app (filename suffix -> family is one family).
_FONT_FILES = (
    "plus-jakarta-sans-400.woff2",
    "plus-jakarta-sans-500.woff2",
    "plus-jakarta-sans-600.woff2",
    "plus-jakarta-sans-700.woff2",
    "plus-jakarta-sans-800.woff2",
)

FALLBACK_FAMILIES = ("Inter", "Segoe UI", "Noto Sans", "DejaVu Sans")


def load_fonts() -> str | None:
    """Register bundled Jakarta Sans; return the family name or None."""
    if not _FONTS_DIR.is_dir():
        return None
    families: list[str] = []
    for filename in _FONT_FILES:
        path = _FONTS_DIR / filename
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    for family in families:
        if "Jakarta" in family:
            return family
    return families[0] if families else None


def load_stylesheet() -> str:
    """Read the versioned theme.qss (empty string when missing)."""
    try:
        return _QSS_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""


def apply_theme(app: QApplication) -> str | None:
    """Apply fonts + stylesheet to the application; return family or None."""
    family = load_fonts()
    if family:
        font = app.font()
        font.setFamily(family)
        app.setFont(font)
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
    return family
