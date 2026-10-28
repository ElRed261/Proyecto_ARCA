"""S2 y S3: paletas de serie y fuente de datos con cifras tabulares.

La familia empaquetada tiene cifras proporcionales, así que la alineación de
columnas numéricas depende de `tnum`. Sin este test, un cambio de fuente o una
regresión en `data_font` rompe todas las tablas sin que nada lo note.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QFont, QFontMetricsF

from oms_ui import theme

#: Series que dibuja cada grupo del Resumen (docs/DISENO_OMS.md §5.6).
SERIES_POR_GRUPO = {
    "temp": ("tmax", "tmin", "tmedia"),
    "pressure": ("pmax", "pmin", "pmedia", "pest"),
    "humidity": ("hrmedia", "hrmax", "hrmin", "rocio"),
    "rain": ("lluvia",),
    "wind": ("viento", "recorrido"),
    "clouds": ("nubmedia", "nubdia", "nubnoche"),
}

#: Las ocho clases de color de Okabe–Ito, distinguibles con cualquier daltonismo.
OKABE_ITO = {
    "#d55e00",
    "#0072b2",
    "#e69f00",
    "#009e73",
    "#56b4e9",
    "#cc79a7",
    "#999999",
}


def _anchos(font: QFont) -> set[float]:
    fm = QFontMetricsF(font)
    return {round(fm.horizontalAdvance(s), 2) for s in ("1111", "8888", "0000", "2345")}


def test_las_dos_paletas_de_serie_cubren_los_seis_grupos():
    for nombre, paleta in theme.SERIES_PALETTES.items():
        faltan = [
            clave
            for claves in SERIES_POR_GRUPO.values()
            for clave in claves
            if clave not in paleta
        ]
        assert not faltan, f"{nombre} no define {faltan}"


def test_las_dos_paletas_de_serie_tienen_las_mismas_claves():
    normal = set(theme.SERIES_NORMAL)
    accesible = set(theme.SERIES_ACCESIBLE)
    assert normal == accesible


def test_la_paleta_accesible_es_okabe_ito():
    assert set(theme.SERIES_ACCESIBLE.values()) <= OKABE_ITO


def test_series_palette_normaliza_y_no_expone_el_dict_interno():
    assert theme.series_palette("accesible") == theme.SERIES_ACCESIBLE
    assert theme.series_palette("basura") == theme.SERIES_NORMAL
    copia = theme.series_palette()
    copia["tmax"] = "#000000"
    assert theme.SERIES_NORMAL["tmax"] != "#000000"


def test_la_fuente_de_datos_alinea_las_cifras(qtbot):
    assert len(_anchos(theme.data_font(11))) == 1


def test_sin_tnum_las_cifras_no_alinean(qtbot):
    """Control: si esto pasara, el test de arriba no probaría nada."""
    familia = theme.font_family()
    if not familia:
        pytest.skip("no hay familia empaquetada en este entorno")
    proposicional = QFont(familia, 11)
    assert len(_anchos(proposicional)) > 1


def test_no_quedan_roles_transitorios():
    retirados = {"acento_debil", "acento_debil_alt"}
    for nombre, paleta in theme.PALETTES.items():
        assert not (retirados & set(paleta)), f"{nombre} conserva roles retirados"
        assert not [rol for rol in paleta if rol.startswith("violeta")], nombre


def test_el_qss_no_pide_ningun_rol_retirado():
    for nombre in theme.THEMES:
        hoja = theme.load_stylesheet(nombre)
        assert hoja
        assert "acento_debil" not in hoja
        assert "violeta" not in hoja
