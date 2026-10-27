"""Regla del dueño: nada de degradados, y nada de propiedades que Qt ignora.

«NADA DE DEGRADADO DE COLORES, eso se ve muy IA y muy genérico, es horrible.»
(docs/DISENO_OMS.md §0)

Esta prueba recorre el código fuente porque el defecto no es de comportamiento:
un degradado no rompe ningún test, simplemente hace que la pantalla se vea mal.
La misma barrera cubre `opacity`, que Qt descarta en silencio y por eso dejó el
botón Guardar sin feedback de hover durante meses (UI-05).
"""

from __future__ import annotations

import re
from pathlib import Path

OMS_UI = Path(__file__).resolve().parents[1] / "oms_ui"

PROHIBIDO = (
    "qlineargradient",
    "qradialgradient",
    "qconicalgradient",
    "QLinearGradient",
    "QRadialGradient",
    "QConicalGradient",
)

#: Propiedades que Qt Style Sheets no implementa y descarta sin avisar.
PROPIEDADES_FANTASMA = ("opacity", "outline", "letter-spacing", "text-transform")


def _fuentes() -> list[Path]:
    return sorted(
        [p for p in OMS_UI.rglob("*.py") if "__pycache__" not in p.parts]
        + [p for p in OMS_UI.rglob("*.qss")]
    )


def test_no_quedan_degradados_en_el_programa():
    culpables = []
    for archivo in _fuentes():
        texto = archivo.read_text(encoding="utf-8", errors="ignore")
        for aguja in PROHIBIDO:
            if aguja in texto:
                culpables.append(f"{archivo.relative_to(OMS_UI)}: {aguja}")

    assert culpables == [], f"degradados prohibidos: {culpables}"


def test_no_quedan_propiedades_que_qt_ignora():
    culpables = []
    # Sin anclaje a la línea: la mayoría están dentro de f-strings inline,
    # que es justo donde más se cuelan.
    patron = re.compile(rf"\b(?:{'|'.join(PROPIEDADES_FANTASMA)})\s*:")
    for archivo in _fuentes():
        texto = archivo.read_text(encoding="utf-8", errors="ignore")
        for coincidencia in patron.finditer(texto):
            linea = texto[: coincidencia.start()].count("\n") + 1
            culpables.append(
                f"{archivo.relative_to(OMS_UI)}:{linea}: {coincidencia.group(0).strip()}"
            )

    assert culpables == [], f"propiedades que Qt descarta: {culpables}"


def test_el_sinoptico_pinta_un_fondo_plano(fresh_db, tmp_path, qapp):
    """La página no dibuja fotografía ni degradado: un solo color de la paleta."""
    from oms_ui import theme
    from oms_ui.pages.synoptic import SynopticPage

    theme.apply_theme(qapp, "claro")
    pagina = SynopticPage(fresh_db, config_dir=str(tmp_path), role="admin")

    assert pagina._page_bg == theme.PALETTE_CLARO["fondo"]
    # El título ya no es blanco: sin fotografía detrás sería invisible.
    assert theme.PALETTE_CLARO["texto"] in pagina.title_label.styleSheet()


def test_los_titulos_de_los_cli_son_legibles_sobre_fondo_plano(fresh_db):
    """El título de los CLI era blanco porque vivía sobre el degradado por hora.

    Sin degradado quedaba invisible; esta barrera impide que vuelva.
    """
    from PySide6.QtWidgets import QApplication

    from oms_ui import theme
    from oms_ui.pages.cli3074 import Cli3074View
    from oms_ui.pages.cli4074 import Cli4074View
    from oms_ui.pages.cli5074 import Cli5074View

    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, "claro")

    from PySide6.QtWidgets import QWidget

    for vista in (Cli3074View, Cli4074View, Cli5074View):
        widget = vista(fresh_db, station="78485", fecha="2025-12-08")
        hojas = " ".join(h.styleSheet() for h in widget.findChildren(QWidget))
        # Ningún texto de la cabecera puede ser blanco puro: el fondo ya no es oscuro.
        assert "color: #ffffff; font-weight: 800" not in hojas, vista.__name__
        widget.deleteLater()
