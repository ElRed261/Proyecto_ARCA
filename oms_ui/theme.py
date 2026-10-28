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

from PySide6.QtGui import QFont, QFontDatabase
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
#:
#: `acento_suave` es el rol del documento. Los literales viejos que sólo existían
#: para mapear el QSS anterior (`acento_debil`, `violeta_*`) ya no están: el
#: trazo nuevo usa un solo acento (S2).
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
    "acento_suave": "#e0f2fe",
    "acento_deshabilitado": "#93c5fd",
    "acento_texto": "#1e40af",
    "acento_fondo": "#eff6ff",
    "error": "#ef4444",
    "error_fuerte": "#dc2626",
    "error_suave": "#fee2e2",
    "ok": "#16a34a",
    "ok_fuerte": "#15803d",
    "ok_fondo": "#dcfce7",
    "banda": "#475569",
    "banda_texto": "#f8fafc",
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
    "acento_suave": "#123241",
    "acento_deshabilitado": "#1c4b5e",
    "acento_texto": "#a5f3fc",
    "acento_fondo": "#0f2338",
    "error": "#f87171",
    "error_fuerte": "#ef4444",
    "error_suave": "#3b1416",
    "ok": "#4ade80",
    "ok_fuerte": "#22c55e",
    "ok_fondo": "#12281c",
    "banda": "#243044",
    "banda_texto": "#e2e8f0",
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

#: Color de cada serie de las gráficas (docs/DISENO_OMS.md §5.6). Las claves son
#: las mismas que usa el Resumen; el color va **siempre acompañado de forma**
#: (área, sólida, punteada, barra), nunca solo (S13).
SERIES_NORMAL: dict[str, str] = {
    "tmax": "#ef4444",
    "tmin": "#3b82f6",
    "tmedia": "#f59e0b",
    "pmax": "#ef4444",
    "pmin": "#3b82f6",
    "pmedia": "#8b5cf6",
    "pest": "#64748b",
    "hrmedia": "#0d9488",
    "hrmax": "#3b82f6",
    "hrmin": "#22d3ee",
    "rocio": "#10b981",
    "lluvia": "#3b82f6",
    "viento": "#06b6d4",
    "recorrido": "#6366f1",
    "nubmedia": "#f59e0b",
    "nubdia": "#3b82f6",
    "nubnoche": "#64748b",
}

#: Okabe–Ito: las ocho clases de color que se distinguen bajo cualquier tipo de
#: daltonismo. Es la «paleta accesible» de Configuración → Apariencia (S13).
SERIES_ACCESIBLE: dict[str, str] = {
    "tmax": "#d55e00",
    "tmin": "#0072b2",
    "tmedia": "#e69f00",
    "pmax": "#d55e00",
    "pmin": "#0072b2",
    "pmedia": "#cc79a7",
    "pest": "#999999",
    "hrmedia": "#009e73",
    "hrmax": "#0072b2",
    "hrmin": "#56b4e9",
    "rocio": "#cc79a7",
    "lluvia": "#0072b2",
    "viento": "#0072b2",
    "recorrido": "#e69f00",
    "nubmedia": "#e69f00",
    "nubdia": "#0072b2",
    "nubnoche": "#999999",
}

SERIES_PALETTES: dict[str, dict[str, str]] = {
    "normal": SERIES_NORMAL,
    "accesible": SERIES_ACCESIBLE,
}
SERIES_ETIQUETAS = {"normal": "Normal", "accesible": "Accesible"}
DEFAULT_SERIES = "normal"

#: Nombre de la característica OpenType de cifras tabulares.
TABULAR_FEATURE = "tnum"

_familia: str | None = None
_familia_leida = False
_aplicado: str | None = None


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


def font_family() -> str | None:
    """Familia empaquetada, registrada una sola vez por proceso."""
    global _familia, _familia_leida
    if not _familia_leida:
        _familia = load_fonts()
        _familia_leida = True
    return _familia


def data_font(size: float = 11, weight: int = 500) -> QFont:
    """Fuente para datos: la familia empaquetada con cifras tabulares (S3).

    Jakarta Sans trae **cifras proporcionales**: `1111` mide 22,25 px y `0000`
    43,88 px, así que sin `tnum` ninguna columna numérica puede alinear. Con
    `tnum` las cinco combinaciones medidas miden 36,0 px.
    """
    font = QFont()
    family = font_family()
    if family:
        font.setFamily(family)
    font.setPointSizeF(size)
    font.setWeight(QFont.Weight(weight))
    try:
        font.setFeature(QFont.Tag(TABULAR_FEATURE), 1)
    except (AttributeError, TypeError, ValueError):  # Qt viejo o tag inválido
        pass
    return font


def normalize_series(name: str | None) -> str:
    """Paleta de serie válida; desconocida o vacía -> la de fábrica."""
    return name if name in SERIES_PALETTES else DEFAULT_SERIES  # type: ignore[return-value]


def series_palette(name: str | None = None) -> dict[str, str]:
    """Colores de serie resueltos (normal o accesible)."""
    return dict(SERIES_PALETTES[normalize_series(name)])


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


def repolish(widget) -> None:
    """Reevalúa el QSS de un widget tras cambiar una propiedad dinámica.

    Qt no reaplica los selectores por propiedad solo: hay que despulir y pulir.
    """
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)


def applied_theme() -> str:
    """Tema realmente aplicado a la app (cae al guardado si aún no se aplicó)."""
    return _aplicado or current_theme()


def palette_actual() -> dict[str, str]:
    """Paleta del tema aplicado, no de la preferencia guardada."""
    return dict(PALETTES[applied_theme()])


def apply_theme(app: QApplication, theme: str | None = None) -> str | None:
    """Apply fonts + stylesheet to the application; return family or None."""
    global _aplicado

    elegido = normalize_theme(theme or current_theme())
    family = load_fonts()
    if family:
        font = app.font()
        font.setFamily(family)
        app.setFont(font)
    stylesheet = load_stylesheet(elegido)
    if stylesheet:
        app.setStyleSheet(stylesheet)
    _aplicado = elegido
    return family


def apply_saved_theme(app: QApplication) -> tuple[str, str | None]:
    """Aplica el tema guardado; devuelve (tema, familia) para poder mostrarlo."""
    elegido = current_theme()
    return elegido, apply_theme(app, elegido)
