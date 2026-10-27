"""Tema y fuentes de OMS.

`PALETTE` es la única fuente de color: `theme.qss` es una plantilla con `$rol` y
aquí se sustituye (docs/DISENO_OMS.md §2). Ningún widget debe escribir un color
literal; los `setStyleSheet` inline que quedan son deuda de la fase 2.

Los valores de `PALETTE_CLARO` son **los colores que hoy se ven**: la fase 1
tokeniza sin cambiar la apariencia. La fase 2 los sustituye por la paleta del
documento (un solo acento `#0e7490`) cuando los inline ya no compitan con ella.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

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

#: Roles de la paleta clara. Ver docs/DISENO_OMS.md §2.
PALETTE_CLARO: dict[str, str] = {
    "fondo": "#f3f4f6",
    "superficie": "#ffffff",
    "panel": "#f1f5f9",
    "panel_alt": "#f8fafc",
    "borde": "#e2e8f0",
    "borde_input": "#cbd5e1",
    "texto": "#1e293b",
    "texto_alt": "#0f172a",
    "suave": "#475569",
    "suave_alt": "#64748b",
    "tenue": "#94a3b8",
    "acento": "#2563eb",
    "acento_hover": "#1d4ed8",
    "acento_foco": "#3b82f6",
    "acento_debil": "#bfdbfe",
    "acento_debil_alt": "#dbeafe",
    "acento_deshabilitado": "#93c5fd",
    "acento_texto": "#1e40af",
    "acento_fondo": "#eff6ff",
    "error": "#ef4444",
    "error_fuerte": "#dc2626",
    "ok": "#16a34a",
    "ok_fuerte": "#15803d",
    "ok_fondo": "#dcfce7",
    "violeta": "#7c3aed",
    "violeta_fuerte": "#6d28d9",
    "violeta_suave": "#a855f7",
    "violeta_debil": "#faf5ff",
    "violeta_borde": "#e9d5ff",
    "violeta_deshabilitado": "#c4b5fd",
    "violeta_fondo": "#f3e8ff",
    "teal": "#0d9488",
    "teal_borde": "#99f6e4",
    "teal_fondo": "#f0fdfa",
    "naranja": "#ea580c",
    "naranja_alt": "#f97316",
    "naranja_fuerte": "#c2410c",
    "naranja_debil": "#fed7aa",
    "naranja_fondo": "#fff7ed",
    "ambar": "#b45309",
    "ambar_fondo": "#fef3c7",
}

#: Mismos roles, equivalentes oscuros (docs/DISENO_OMS.md §2).
PALETTE_OSCURO: dict[str, str] = {
    "fondo": "#0b1220",
    "superficie": "#111c2e",
    "panel": "#16233a",
    "panel_alt": "#0f1a2b",
    "borde": "#243044",
    "borde_input": "#2f3d55",
    "texto": "#e2e8f0",
    "texto_alt": "#f1f5f9",
    "suave": "#94a3b8",
    "suave_alt": "#8496ad",
    "tenue": "#64748b",
    "acento": "#22d3ee",
    "acento_hover": "#67e8f9",
    "acento_foco": "#22d3ee",
    "acento_debil": "#123241",
    "acento_debil_alt": "#163a4d",
    "acento_deshabilitado": "#1c4b5e",
    "acento_texto": "#a5f3fc",
    "acento_fondo": "#0f2338",
    "error": "#f87171",
    "error_fuerte": "#ef4444",
    "ok": "#4ade80",
    "ok_fuerte": "#22c55e",
    "ok_fondo": "#12281c",
    "violeta": "#c4b5fd",
    "violeta_fuerte": "#ddd6fe",
    "violeta_suave": "#a78bfa",
    "violeta_debil": "#1e1b3a",
    "violeta_borde": "#2e2a52",
    "violeta_deshabilitado": "#3b3363",
    "violeta_fondo": "#1b1730",
    "teal": "#2dd4bf",
    "teal_borde": "#15403b",
    "teal_fondo": "#0d2a27",
    "naranja": "#fb923c",
    "naranja_alt": "#fdba74",
    "naranja_fuerte": "#f97316",
    "naranja_debil": "#4a2a12",
    "naranja_fondo": "#241408",
    "ambar": "#fbbf24",
    "ambar_fondo": "#2b2008",
}

PALETTES: dict[str, dict[str, str]] = {
    "claro": PALETTE_CLARO,
    "oscuro": PALETTE_OSCURO,
}
THEMES = ("claro", "oscuro")
ETIQUETAS = {"claro": "Claro", "oscuro": "Oscuro"}
DEFAULT_THEME = "claro"

#: Clave de QSettings; el resto del programa lee el tema por aquí.
_SETTINGS_KEY = "apariencia/tema"


def _settings():
    """QSettings de la app, con las mismas claves que el resto del programa."""
    from PySide6.QtCore import QSettings

    from oms_ui.startup import _SETTINGS_APP, _SETTINGS_ORG

    return QSettings(_SETTINGS_ORG, _SETTINGS_APP)


def normalize_theme(name: str | None) -> str:
    """Nombre válido de tema; desconocido o vacío -> el de fábrica."""
    if name in PALETTES:
        return name  # type: ignore[return-value]
    alias = {"light": "claro", "dark": "oscuro", "claro": "claro", "oscuro": "oscuro"}
    return alias.get((name or "").strip().lower(), DEFAULT_THEME)


def current_theme() -> str:
    """Tema guardado por el usuario (fábrica: claro)."""
    try:
        return normalize_theme(str(_settings().value(_SETTINGS_KEY, DEFAULT_THEME)))
    except Exception:  # noqa: BLE001 - sin QSettings se arranca con el de fábrica
        return DEFAULT_THEME


def set_theme(name: str) -> str:
    """Guarda el tema elegido y devuelve el nombre normalizado."""
    elegido = normalize_theme(name)
    try:
        _settings().setValue(_SETTINGS_KEY, elegido)
    except Exception:  # noqa: BLE001 - persistir es best-effort
        pass
    return elegido


def palette(theme: str | None = None) -> dict[str, str]:
    """Paleta resuelta para un tema (por defecto, el guardado)."""
    return dict(PALETTES[normalize_theme(theme or current_theme())])


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


def load_stylesheet(theme: str | None = None) -> str:
    """Render theme.qss with the palette of ``theme`` (empty when missing)."""
    try:
        plantilla = _QSS_FILE.read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        return Template(plantilla).substitute(palette(theme))
    except KeyError as exc:  # un $rol sin definir en la paleta es un bug de tema
        raise ValueError(f"theme.qss usa un rol sin paleta: {exc}") from exc


def apply_theme(app: QApplication, theme: str | None = None) -> str | None:
    """Apply fonts + stylesheet to the application; return family or None."""
    family = load_fonts()
    if family:
        font = app.font()
        font.setFamily(family)
        app.setFont(font)
    stylesheet = load_stylesheet(theme)
    if stylesheet:
        app.setStyleSheet(stylesheet)
    return family


def apply_saved_theme(app: QApplication) -> tuple[str, str | None]:
    """Aplica el tema guardado; devuelve (tema, familia) para poder mostrarlo."""
    elegido = current_theme()
    return elegido, apply_theme(app, elegido)
