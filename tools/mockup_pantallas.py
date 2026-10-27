"""Mockups de las pantallas de OMS con el trazo de la fase 1.

Regla del dueño: la FORMA se queda exacta (mismo orden, mismas filas, mismos
bloques del riel); lo que cambia es el trazo — fuera los chips oscuros, los
cuadros bordados y los degradados. Los colores salen de `PALETTE`, así que un
mockup no puede inventar un tono que el programa no tenga.

No toca la aplicación: es un script de previsualización.

    QT_QPA_PLATFORM=offscreen .venv-gil/bin/python tools/mockup_pantallas.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from oms_ui.theme import PALETTES  # noqa: E402

ANCHO, ALTO = 1366, 768
SALIDA = Path("Migración/evidencias/DISENO_NUEVO")

HORAS = ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z")
HORA_ACTIVA = "12Z"
#: Filas del formulario tal como están hoy en SynopticPage._build (mismo orden).
FILAS = (
    (("MiMiMjMj", 1), ("YYGGIw", 1), ("IIiii", 1), ("Fecha", 4)),
    (("IrIXHVV", 1), ("Nddff", 1), ("1snTTT", 1), ("2snTdTdTd", 1),
     ("4PPPP", 1), ("5aPPP", 1), ("7wwW1W2", 1)),
    (("8NhCLCMCH", 1), ("333", 1), ("0CSDLDMDH", 1), ("1snTxTxTx", 1),
     ("2snTnTnTn", 1), ("3Ejjj", 1), ("5EEEjE", 1)),
    (("5nFnFnFn", 1), ("56DLDMDH", 1), ("58/59P24P24P24", 1), ("6RRRtr", 1),
     ("7R24R24R24R24", 1), ("8NsChshs", 1), ("8NsChshs", 1)),
    (("8NsChshs", 1), ("8NsChshs", 1), ("9SpSpSpSp", 1), ("9SpSpSpSp", 1),
     ("9SpSpSpSp", 1), ("9SpSpSpSp", 1), ("9SpSpSpSp", 1)),
    (("9SpSpSpSp", 1),) * 7,
    (("9SpSpSpSp", 1),) * 7,
    (("9SpSpSpSp", 1),) * 5 + (("555", 1), ("29UUU", 1)),
)
#: Valores de ejemplo, alineados con las filas de arriba.
VALORES = (
    ("AAXX", "08124", "78485", "08/12/2025"),
    ("82412", "82618", "10298", "20186", "40134", "5310102", "7"),
    ("8", "333", "0", "10", "20", "3///", ""),
    ("", "56", "5810104", "6", "7", "8", "8"),
    ("8", "", "9Sp", "9Sp", "9Sp", "9Sp", "9Sp"),
    ("", "", "", "", "", "", ""),
    ("", "", "", "", "", "", ""),
    ("", "", "", "", "", "555", "29UUU"),
)
CONSTANTES = {"AAXX", "555"}


def mono(px: int = 12) -> QFont:
    for familia in ("JetBrains Mono", "IBM Plex Mono", "DejaVu Sans Mono"):
        if familia in QFontDatabase.families():
            f = QFont(familia)
            f.setPixelSize(px)
            return f
    return QFont("monospace")


def ui(px: int = 13, peso: int = 400) -> QFont:
    f = QFont()
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(peso))
    return f


def fila_formulario(p: dict, celdas) -> list[QWidget]:
    """Etiqueta arriba y su campo debajo, sin caja alrededor del grupo."""
    salida: list[QWidget] = []
    for etiqueta, tramo in celdas:
        celda = QWidget()
        v = QVBoxLayout(celda)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        lab = QLabel(etiqueta)
        lab.setFont(ui(11, 600))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;")
        v.addWidget(lab)
        campo = QLabel("")
        campo.setProperty("tramo", tramo)
        campo.setFont(mono(12))
        campo.setFixedHeight(30)
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 7px;"
        )
        campo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        v.addWidget(campo)
        salida.append(celda)
    return salida


def _valor_de(fila: int, columna: int) -> str:
    """Valor de ejemplo para la celda (fila del formulario, columna 0..6)."""
    valores = VALORES[fila]
    return valores[columna] if columna < len(valores) else ""


def _campo_valor(p: dict, texto: str, *, constante: bool = False) -> QLabel:
    campo = QLabel(texto)
    campo.setFont(mono(12))
    campo.setFixedHeight(30)
    if constante:
        campo.setStyleSheet(
            f"background:{p['panel']};color:{p['suave']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 7px;"
        )
    else:
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 7px;"
        )
    campo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return campo


def tarjeta_formulario(p: dict) -> QWidget:
    """El bloque blanco del formulario: observador arriba y la grilla debajo."""
    tarjeta = QWidget()
    tarjeta.setObjectName("tarjeta")
    tarjeta.setStyleSheet(
        f"QWidget#tarjeta {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    v = QVBoxLayout(tarjeta)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(10)

    # Observador: igual que hoy, primera fila del bloque.
    obs = QHBoxLayout()
    obs.setSpacing(10)
    lab = QLabel("Observador")
    lab.setFont(ui(11, 600))
    lab.setStyleSheet(f"color:{p['suave']};background:transparent;")
    lab.setFixedWidth(96)
    obs.addWidget(lab)
    campo_obs = QLabel("A. Pérez")
    campo_obs.setFont(mono(12))
    campo_obs.setFixedHeight(30)
    campo_obs.setStyleSheet(
        f"background:{p['superficie']};color:{p['texto']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:0 7px;"
    )
    obs.addWidget(campo_obs, 1)
    v.addLayout(obs)

    grilla = QGridLayout()
    grilla.setHorizontalSpacing(8)
    grilla.setVerticalSpacing(3)
    for indice, celdas in enumerate(FILAS):
        columna = 0
        for etiqueta, tramo in celdas:
            lab = QLabel(etiqueta)
            lab.setFont(ui(11, 600))
            lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
            grilla.addWidget(lab, indice * 2, columna, 1, tramo)
            grilla.addWidget(
                _campo_valor(p, _valor_de(indice, columna), constante=etiqueta in CONSTANTES),
                indice * 2 + 1, columna, 1, tramo,
            )
            columna += tramo
        grilla.setRowMinimumHeight(indice * 2 + 1, 30)
    for col in range(7):
        grilla.setColumnStretch(col, 1)
    v.addLayout(grilla)
    v.addStretch(1)
    return tarjeta


def titulo_seccion(p: dict, texto: str) -> QLabel:
    lab = QLabel(texto)
    lab.setFont(ui(11, 700))
    lab.setStyleSheet(
        f"color:{p['suave']};background:transparent;"
        f"border-bottom:1px solid {p['borde']};padding-bottom:5px;"
    )
    return lab


def riel_derecho(p: dict) -> QWidget:
    riel = QWidget()
    riel.setFixedWidth(252)
    v = QVBoxLayout(riel)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(14)

    v.addWidget(titulo_seccion(p, "HORAS DE OBSERVACIÓN"))
    rejilla = QGridLayout()
    rejilla.setSpacing(4)
    for indice, hora in enumerate(HORAS):
        activa = hora == HORA_ACTIVA
        celda = QLabel(f"{hora}   {11 if activa else 21}/21")
        celda.setFont(mono(11))
        celda.setFixedHeight(28)
        celda.setAlignment(Qt.AlignCenter)
        celda.setStyleSheet(
            f"background:{p['acento_suave'] if activa else p['superficie']};"
            f"color:{p['acento'] if activa else p['texto']};"
            f"border:1px solid {p['acento'] if activa else p['borde']};"
            "border-radius:4px;"
        )
        rejilla.addWidget(celda, indice // 2, indice % 2)
    v.addLayout(rejilla)

    barra = QProgressBar()
    barra.setFixedHeight(3)
    barra.setRange(0, 21)
    barra.setValue(11)
    barra.setTextVisible(False)
    barra.setStyleSheet(
        f"QProgressBar{{background:{p['borde']};border:none;border-radius:2px;}}"
        f"QProgressBar::chunk{{background:{p['acento']};border-radius:2px;}}"
    )
    v.addWidget(barra)

    v.addWidget(titulo_seccion(p, "MÓDULOS CLI"))
    modulos = QHBoxLayout()
    modulos.setSpacing(4)
    for nombre in ("3074", "4074", "5074"):
        boton = QLabel(nombre)
        boton.setFont(mono(11))
        boton.setFixedHeight(28)
        boton.setAlignment(Qt.AlignCenter)
        boton.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;"
        )
        modulos.addWidget(boton)
    v.addLayout(modulos)

    v.addWidget(titulo_seccion(p, "NUBOSIDAD EXTRA"))
    for etiqueta in ("Grupo extra 1 8Ns", "Grupo extra 2 8Ns"):
        lab = QLabel(etiqueta)
        lab.setFont(ui(11, 600))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;")
        v.addWidget(lab)
        v.addWidget(_campo_valor(p, ""))

    v.addStretch(1)

    guardar = QLabel("Guardar observación")
    guardar.setFont(ui(13, 700))
    guardar.setFixedHeight(34)
    guardar.setAlignment(Qt.AlignCenter)
    guardar.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};"
        "border:none;border-radius:4px;"
    )
    v.addWidget(guardar)
    cargar = QLabel("Cargar observación")
    cargar.setFont(ui(13, 600))
    cargar.setFixedHeight(32)
    cargar.setAlignment(Qt.AlignCenter)
    cargar.setStyleSheet(
        f"background:{p['superficie']};color:{p['texto']};"
        f"border:1px solid {p['borde']};border-radius:4px;"
    )
    v.addWidget(cargar)
    return riel


def pantalla_synop(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(20, 16, 20, 16)
    v.setSpacing(12)

    cab = QHBoxLayout()
    titulo = QLabel(f"Observación Sinóptica {HORA_ACTIVA}")
    titulo.setFont(ui(24, 800))
    titulo.setStyleSheet(f"color:{p['texto']};background:transparent;")
    cab.addWidget(titulo)
    cab.addStretch(1)
    cab.addWidget(QLabel(""))
    v.addLayout(cab)

    cuerpo = QHBoxLayout()
    cuerpo.setSpacing(16)
    cuerpo.addWidget(tarjeta_formulario(p), 1)
    cuerpo.addWidget(riel_derecho(p))
    v.addLayout(cuerpo, 1)
    return pagina


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    for nombre, paleta in PALETTES.items():
        w = pantalla_synop(paleta)
        w.resize(QSize(ANCHO, ALTO))
        w.show()
        app.processEvents()
        destino = SALIDA / f"mock-synop-{nombre}.png"
        w.grab().save(str(destino))
        print(f"  {destino}  ({destino.stat().st_size // 1024} KB)")
        w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
