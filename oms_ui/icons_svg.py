"""Iconos SVG del riel (Lucide v0.460.0, licencia ISC).

Placeholders hasta que el dueño elija el set definitivo: se tiñen con el acento
de la paleta activa, así el mismo archivo sirve para claro y oscuro.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_DIR = Path(__file__).resolve().parent / "assets" / "icons" / "rail"


def rail_icon(nombre: str, color: str, tamano: int = 18) -> QIcon:
    """Icono del riel teñido con ``color``; QIcon vacío si falta el archivo."""
    ruta = _DIR / f"{nombre}.svg"
    if not ruta.is_file():
        return QIcon()
    renderer = QSvgRenderer(str(ruta))
    if not renderer.isValid():
        return QIcon()
    lado = tamano * 2  # 2x: en pantallas densas no se ve borroso
    pixmap = QPixmap(lado, lado)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    renderer.render(pintor, QRectF(0, 0, lado, lado))
    pintor.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    pintor.fillRect(pixmap.rect(), QColor(color))
    pintor.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
