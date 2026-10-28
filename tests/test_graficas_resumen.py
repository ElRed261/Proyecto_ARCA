"""S8 y S13: las gráficas del Resumen dibujan con la paleta y sin ejes repetidos."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from oms_ui import theme
from oms_ui.widgets_graficas import GRUPOS, ORDEN, GraficoGrupo, cortes_eje, paso_lindo


def test_los_cortes_del_eje_no_repiten_etiquetas():
    """L7: un rango chico redondeaba los cinco cortes al mismo entero."""
    for minimo, maximo in ((19, 22), (54, 98), (0, 8), (-3.5, 2.5), (1013, 1019)):
        valores = cortes_eje(minimo, maximo)
        assert len(valores) == len(set(valores)), (minimo, maximo, valores)


def test_el_paso_es_un_numero_redondo():
    assert paso_lindo(3, 5) in (0.5, 1.0)
    assert paso_lindo(44, 5) in (10.0, 20.0)


def test_cada_serie_tiene_color_de_la_paleta_de_series():
    """S13: color + forma, y el color sale de la paleta, no de un literal."""
    for nombre in ("normal", "accesible"):
        colores = theme.series_palette(nombre)
        for grupo in GRUPOS.values():
            for _forma, _etiqueta, _clave, rol in grupo["series"]:
                assert rol in colores, (nombre, rol)


def test_las_formas_se_distinguen_sin_color():
    for grupo in GRUPOS.values():
        formas = [forma for forma, *_ in grupo["series"]]
        if len(formas) > 1:
            assert len(set(formas)) > 1


def test_el_grafico_pinta_sin_datos_y_con_datos(qtbot):
    app = QApplication.instance()
    vacio = GraficoGrupo("temp", {})
    vacio.resize(600, 260)
    vacio.grab()  # sin datos: no debe reventar

    datos = {
        "tmax": [30, 31, 32], "tmin": [20, 21, 22], "tmed": [25, 26, 27],
    }
    lleno = GraficoGrupo("temp", datos)
    lleno.resize(600, 260)
    imagen = lleno.grab().toImage()
    colores = {imagen.pixelColor(x, y).name() for x in range(0, 600, 7) for y in range(0, 260, 7)}
    assert len(colores) > 3, "el gráfico no dibujó nada"


def test_el_resumen_expone_tres_pestanas(qtbot, fresh_db):
    from oms_ui.pages.summary import SummaryPage

    pagina = SummaryPage(fresh_db)
    qtbot.addWidget(pagina)
    assert pagina.stack.count() == 3  # historial, tabla y gráficas


def test_cambiar_de_grupo_actualiza_el_titulo(qtbot, fresh_db):
    from oms_ui.pages.summary import SummaryPage

    pagina = SummaryPage(fresh_db)
    qtbot.addWidget(pagina)
    pagina.select_chart_group("rain")
    assert "PRECIPITACIÓN" in pagina._chart_title.text()
    assert pagina._chart.grupo == "rain"
    for clave in ORDEN:
        pagina.select_chart_group(clave)
