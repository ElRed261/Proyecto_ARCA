"""S1: ningún color literal en oms_ui salvo las paletas de theme.py.

Es la barrera que sostiene el trabajo de las nueve fases: los colores viven en
`PALETTE_CLARO`/`PALETTE_OSCURO` y todo lo demás los pide por rol. Si un archivo
vuelve a escribir un hex, el tema oscuro deja de aplicarse en silencio.
"""

from __future__ import annotations

import re
from pathlib import Path

_OMS_UI = Path(__file__).resolve().parents[1] / "oms_ui"

#: El único archivo que puede contener hex: es el mapa de la paleta.
_PERMITIDO = {"theme.py"}

_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def test_ningun_archivo_de_oms_ui_lleva_colores_literales():
    culpables = []
    for archivo in sorted(_OMS_UI.rglob("*.py")):
        if archivo.name in _PERMITIDO:
            continue
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            encontrados = _LITERAL.findall(linea)
            if encontrados:
                culpables.append(f"{archivo.relative_to(_OMS_UI)}:{numero}: {encontrados}")
    assert not culpables, "colores literales en la UI:\n" + "\n".join(culpables)


def test_la_plantilla_no_tiene_literales():
    plantilla = (_OMS_UI / "theme.qss").read_text(encoding="utf-8")
    assert not _LITERAL.findall(plantilla)


def test_la_paleta_define_ambos_temas_con_los_mismos_roles():
    from oms_ui import theme

    claro, oscuro = set(theme.PALETTE_CLARO), set(theme.PALETTE_OSCURO)
    assert claro == oscuro, f"roles desparejos: {claro ^ oscuro}"
