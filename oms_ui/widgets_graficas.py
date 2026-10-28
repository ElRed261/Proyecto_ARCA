"""Gráficas del Resumen: un widget propio, sin dependencias nuevas (D2).

Reemplaza al stub de la pestaña Gráficas. Conserva el esquema de OLD —sidebar de
variables, tres tarjetas de estadísticas y una caja de gráfico por variable— y
las series, colores y tipos de cada grupo (docs/DISENO_OMS.md §5.6).

Dos reglas del documento que este widget hace cumplir:

- **Una unidad por eje.** Cuando el grupo mezcla unidades (rocío en °C dentro de
  humedad en %, recorrido en km con velocidad en km/h) la serie distinta va al
  eje derecho con su propia escala.
- **Ninguna serie se distingue sólo por color** (S13): forma (área, línea,
  punteada, barra) además de color, y paleta accesible conmutable.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from oms_ui import theme

#: Series de cada grupo: (forma, etiqueta, clave, rol o None para el color de
#: la paleta de series). El secundario de cada grupo define el eje derecho.
GRUPOS: dict[str, dict] = {
    "temp": {
        "titulo": "Temperatura",
        "unidad": "°C",
        "series": (
            ("area", "Temp Máxima", "tmax", "tmax"),
            ("area", "Temp Mínima", "tmin", "tmin"),
            ("linea", "Temp Media", "tmed", "tmedia"),
        ),
        "secundario": None,
    },
    "pressure": {
        "titulo": "Presión Atmosférica",
        "unidad": "hPa",
        "series": (
            ("linea", "NMM Máx", "pmax", "tmax"),
            ("linea", "NMM Mín", "pmin", "tmin"),
            ("linea", "NMM Media", "pmed", "pmedia"),
            ("punteada", "Pres. Estación", "pest", "pest"),
        ),
        "secundario": None,
    },
    "humidity": {
        "titulo": "Humedad y Rocío",
        "unidad": "%",
        "series": (
            ("area", "HR Media", "hummed", "hrmedia"),
            ("linea", "HR Máx", "hrmax", "hrmax"),
            ("linea", "HR Mín", "hrmin", "hrmin"),
            ("punteada", "Pto. Rocío (°C)", "rocio", "rocio"),
        ),
        "secundario": "rocio",
        "unidad_secundaria": "°C",
    },
    "rain": {
        "titulo": "Precipitación",
        "unidad": "mm",
        "series": (("barra", "Lluvia", "lluvia", "lluvia"),),
        "secundario": None,
    },
    "wind": {
        "titulo": "Viento",
        "unidad": "km/h",
        "series": (
            ("linea", "Velocidad", "vel", "viento"),
            ("punteada", "Recorrido (km)", "recorrido", "recorrido"),
        ),
        "secundario": "recorrido",
        "unidad_secundaria": "km",
    },
    "clouds": {
        "titulo": "Nubosidad",
        "unidad": "octavos",
        "series": (
            ("area", "Nub. Media", "nubmed", "nubmedia"),
            ("linea", "Nub. Día", "nubdia", "nubdia"),
            ("linea", "Nub. Tarde", "nubnoche", "nubnoche"),
        ),
        "secundario": None,
        "tope": 8.0,
    },
}

#: Nombre visible de cada grupo, en el orden del sidebar.
ORDEN = ("temp", "pressure", "humidity", "rain", "wind", "clouds")


def paso_lindo(rango: float, cortes: int = 5) -> float:
    """Paso de eje con números redondos para ``cortes`` divisiones.

    Sin esto, un rango chico como 19–22 °C redondea los cinco cortes al mismo
    entero y el eje repite etiquetas (defecto L7 del plan de diseño).
    """
    if rango <= 0 or cortes <= 0:
        return 1.0
    crudo = rango / cortes
    magnitud = 10 ** math.floor(math.log10(crudo))
    for factor in (1, 2, 2.5, 5, 10):
        if crudo <= factor * magnitud:
            return factor * magnitud
    return 10 * magnitud


def cortes_eje(minimo: float, maximo: float, divisiones: int = 5) -> list[float]:
    """Valores de corte, sin etiquetas repetidas."""
    if maximo <= minimo:
        maximo = minimo + 1.0
    paso = paso_lindo(maximo - minimo, divisiones)
    desde = math.floor(minimo / paso) * paso
    hasta = math.ceil(maximo / paso) * paso
    valores, valor = [], desde
    while valor <= hasta + paso / 2:
        valores.append(round(valor, 6))
        valor += paso
    return valores


class GraficoGrupo(QWidget):
    """Un gráfico del grupo activo, con sus ejes y su leyenda."""

    def __init__(self, grupo: str, datos: dict[str, list[float]], parent=None) -> None:
        super().__init__(parent)
        self.grupo = grupo if grupo in GRUPOS else ORDEN[0]
        self.datos = datos or {}
        self.setMinimumHeight(260)

    # -- datos ------------------------------------------------------------

    def _config(self) -> dict:
        return GRUPOS[self.grupo]

    def _serie(self, clave: str) -> list[float]:
        return [float(v) for v in (self.datos.get(clave) or [])]

    # -- pintura ----------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 - API de Qt
        paleta = theme.palette_actual()
        colores = theme.series_palette()
        config = self._config()
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.fillRect(self.rect(), QColor(paleta["superficie"]))

        dias = max((len(self._serie(c)) for _f, _n, c, _r in config["series"]), default=0)
        if dias == 0:
            pintor.setPen(QColor(paleta["tenue"]))
            pintor.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos del período")
            return

        secundaria = config.get("secundario")
        izquierda, derecha = 52, 62 if secundaria else 18
        arriba, abajo = 14, 46
        caja = QRectF(
            izquierda, arriba,
            max(10.0, self.width() - izquierda - derecha),
            max(10.0, self.height() - arriba - abajo),
        )

        # escala del eje izquierdo: sólo las series principales
        principales = [s for s in config["series"] if s[2] != secundaria]
        valores = [v for _f, _n, clave, _r in principales for v in self._serie(clave)]
        if not valores:
            valores = [0.0]
        tope = config.get("tope")
        minimo, maximo = min(valores), max(valores)
        if tope is not None:
            minimo, maximo = 0.0, max(tope, maximo)
        if maximo == minimo:
            maximo = minimo + 1.0
        cortes = cortes_eje(minimo, maximo)

        def y_de(valor: float, propios=cortes) -> float:
            bajo, alto = propios[0], propios[-1]
            return caja.bottom() - (valor - bajo) / (alto - bajo) * caja.height()

        # guías y etiquetas del eje izquierdo
        fuente = QFont()
        fuente.setPointSizeF(8.0)
        pintor.setFont(fuente)
        for corte in cortes:
            y = y_de(corte)
            pintor.setPen(QPen(QColor(paleta["borde"]), 1, Qt.PenStyle.DotLine))
            pintor.drawLine(QPointF(caja.left(), y), QPointF(caja.right(), y))
            pintor.setPen(QColor(paleta["tenue"]))
            pintor.drawText(
                QRectF(0, y - 8, izquierda - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{corte:g}",
            )

        # eje derecho (segunda unidad)
        if secundaria:
            valores_sec = [v for v in self._serie(secundaria)]
            cortes_sec = cortes_eje(min(valores_sec), max(valores_sec)) if valores_sec else cortes
            for corte in cortes_sec:
                bajo, alto = cortes_sec[0], cortes_sec[-1]
                y = caja.bottom() - (corte - bajo) / (alto - bajo) * caja.height()
                pintor.setPen(QColor(paleta["tenue"]))
                pintor.drawText(
                    QRectF(caja.right() + 6, y - 8, derecha - 8, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"{corte:g}",
                )

        ancho_dia = caja.width() / max(1, dias - 1)

        def punto(indice: int, valor: float, propios=cortes) -> QPointF:
            bajo, alto = propios[0], propios[-1]
            y = caja.bottom() - (valor - bajo) / (alto - bajo) * caja.height()
            return QPointF(caja.left() + indice * ancho_dia, y)

        for forma, _nombre, clave, rol in config["series"]:
            serie = self._serie(clave)
            if not serie:
                continue
            color = QColor(colores.get(rol) or paleta["acento"])
            propios = cortes
            if clave == secundaria:
                propios = cortes_eje(min(serie), max(serie))
            poligono = [punto(i, v, propios) for i, v in enumerate(serie)]

            if forma == "barra":
                ancho = max(2.0, ancho_dia * 0.55)
                pintor.setPen(Qt.PenStyle.NoPen)
                relleno = QColor(color)
                relleno.setAlpha(180)
                pintor.setBrush(QBrush(relleno))
                base = y_de(0.0, propios) if propios[0] <= 0 <= propios[-1] else caja.bottom()
                for p in poligono:
                    pintor.drawRect(QRectF(p.x() - ancho / 2, p.y(), ancho, base - p.y()))
            elif forma == "area":
                relleno = QColor(color)
                relleno.setAlpha(26)
                area = QPolygonF(poligono + [
                    QPointF(poligono[-1].x(), caja.bottom()),
                    QPointF(poligono[0].x(), caja.bottom()),
                ])
                pintor.setPen(Qt.PenStyle.NoPen)
                pintor.setBrush(QBrush(relleno))
                pintor.drawPolygon(area)
                pintor.setPen(QPen(color, 1.6))
                pintor.setBrush(Qt.BrushStyle.NoBrush)
                pintor.drawPolyline(QPolygonF(poligono))
            else:
                estilo = Qt.PenStyle.DashLine if forma == "punteada" else Qt.PenStyle.SolidLine
                pintor.setPen(QPen(color, 1.8, estilo))
                pintor.setBrush(Qt.BrushStyle.NoBrush)
                pintor.drawPolyline(QPolygonF(poligono))

        # leyenda al pie: forma + color, nunca sólo color (S13)
        y_leyenda = self.height() - 24
        x = caja.left()
        for forma, nombre, _clave, rol in config["series"]:
            color = QColor(colores.get(rol) or paleta["acento"])
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QBrush(color))
            pintor.drawEllipse(QPointF(x + 4, y_leyenda + 6), 4, 4)
            pintor.setPen(QColor(paleta["suave"]))
            pintor.drawText(QPointF(x + 13, y_leyenda + 10), nombre)
            x += 16 + pintor.fontMetrics().horizontalAdvance(nombre) + 14

        # títulos de eje con su unidad
        pintor.setPen(QColor(paleta["suave_alt"]))
        pintor.drawText(
            QRectF(caja.left(), caja.top() - 12, caja.width(), 12),
            Qt.AlignmentFlag.AlignLeft,
            f"({config['unidad']})",
        )
        if secundaria:
            pintor.drawText(
                QRectF(caja.left(), caja.top() - 12, caja.width(), 12),
                Qt.AlignmentFlag.AlignRight,
                f"({config.get('unidad_secundaria', '')})",
            )
