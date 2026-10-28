"""S4: el riel declara estado y el QSS lo pinta.

Antes, `_refresh_rail_selection` concatenaba `" QPushButton { background-color:
#dbeafe; }"` a la hoja del botón y la recortaba con `str.replace`: cada llamada
dejaba una hoja distinta y un hex más. Ahora el estado va por propiedad y el
color sale de la paleta.
"""

from __future__ import annotations

import re
from pathlib import Path

from oms_ui import theme

_SRC = Path(__file__).resolve().parents[1] / "oms_ui" / "main_window.py"
_QSS = Path(__file__).resolve().parents[1] / "oms_ui" / "theme.qss"


def _fuente() -> str:
    return _SRC.read_text(encoding="utf-8")


def test_el_riel_ya_no_concatena_hojas_de_estilo():
    fuente = _fuente()
    assert "#dbeafe" not in fuente
    assert 'rail.setStyleSheet' not in fuente
    assert 'styleSheet().replace' not in fuente


def test_los_botones_del_riel_declaran_su_rol():
    fuente = _fuente()
    assert 'setProperty("rail", "nav")' in fuente
    assert 'setProperty("active"' in fuente
    assert 'setProperty("collapsed"' in fuente


def test_el_qss_pinta_los_cuatro_estados_del_riel():
    hoja = theme.load_stylesheet("claro")
    for selector in (
        "#rail {",
        'QPushButton[rail="nav"] {',
        'QPushButton[rail="nav"][active="true"] {',
        'QPushButton[rail="nav"][collapsed="true"] {',
        'QPushButton[rail="nav"][collapsed="true"][active="true"] {',
    ):
        assert selector in hoja, selector


def test_el_bloque_del_riel_no_tiene_colores_literales():
    """Sobre la plantilla: en la hoja renderizada los $roles ya son hex."""
    plantilla = _QSS.read_text(encoding="utf-8")
    bloque = plantilla[plantilla.index("Riel de navegación") :]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", bloque)
