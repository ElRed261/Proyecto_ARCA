"""S10: las cadenas de interfaz no llevan emojis.

Las fuentes empaquetadas no traen emojis: cada uno se dibuja como un cuadro
vacío. El candado del pie del login salía así en la captura real.
"""

from __future__ import annotations

import re
from pathlib import Path

_UI = Path(__file__).resolve().parents[1] / "oms_ui"

#: Emojis propiamente dichos (plano astral) y selectores de variación. Las
#: flechas y los signos de check/cruz NO entran: la familia empaquetada los
#: dibuja bien, y las capturas lo confirman.
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\uFE0F]")


def test_ninguna_cadena_de_interfaz_lleva_emojis():
    culpables = []
    for archivo in _UI.rglob("*.py"):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if _EMOJI.search(linea):
                culpables.append(f"{archivo.name}:{numero}: {linea.strip()[:70]}")
    assert not culpables, "emojis en la UI:\n" + "\n".join(culpables)
