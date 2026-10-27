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
        campo.setFixedHeight(34)
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 8px;"
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
    campo.setFixedHeight(34)
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
    lab.setFixedWidth(104)
    obs.addWidget(lab)
    campo_obs = QLabel("A. Pérez")
    campo_obs.setFont(mono(12))
    campo_obs.setFixedHeight(34)
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
    # Las 16 filas se reparten el alto de la tarjeta: sin esto quedaba un
    # tercio de la pantalla vacío y todo apelotonado arriba.
    for fila in range(len(FILAS) * 2):
        grilla.setRowStretch(fila, 1)
    v.addLayout(grilla, 1)
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
    riel.setFixedWidth(284)
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


# ---------------------------------------------------------------- CLI 3074
#: Columnas reales de la hoja 3074 (cli3074.py: "columns verbatim"): el grid no
#: se toca; lo único que cambia es el trazo.
GRUPOS_3074 = (
    ("PRESIÓN (hPa)", ("Esta.", "NMM", "Altímetro")),
    ("3 H. TEND", ("C.A.R", "Dif")),
    ("TEMPERATURA", ("Seco", "Húmedo")),
    ("HUMEDAD", ("Pto R (°C)", "T Vap (hPa)", "HR %")),
    ("VIENTO", ("DIR (16P)", "VEL (m/s)")),
    ("VISIBILIDAD", ("(km)",)),
    ("T.PRES.", ("",)),
)
FENOMENOS = ("OR", "SQ", "FC", "TS", "LT", "RD", "DS", "HZ", "FG", "EC")
FILAS_CLI = 24


def _celda_trazo(
    p: dict, texto: str, *, ancho: int = 0, cabecera: bool = False, alto: int | None = None
) -> QLabel:
    lab = QLabel(texto)
    lab.setFont(ui(11, 700) if cabecera else mono(11))
    if alto is not None:
        lab.setFixedHeight(alto)
    else:
        lab.setMinimumHeight(20)
    if ancho:
        lab.setFixedWidth(ancho)
    lab.setAlignment(Qt.AlignCenter if cabecera else (Qt.AlignRight | Qt.AlignVCenter))
    lab.setStyleSheet(
        f"color:{p['suave'] if cabecera else p['texto']};background:transparent;"
        + (f"border-bottom:1px solid {p['borde']};" if cabecera else "")
        + "padding:0 4px;"
    )
    return lab


def pantalla_cli3074(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(10)

    # ---- banda superior: volver, título, módulos, horas, guardar -----------
    banda = QHBoxLayout()
    banda.setSpacing(10)
    volver = QLabel("←")
    volver.setFont(ui(15, 600))
    volver.setFixedSize(28, 28)
    volver.setAlignment(Qt.AlignCenter)
    volver.setStyleSheet(
        f"color:{p['texto']};background:{p['superficie']};"
        f"border:1px solid {p['borde']};border-radius:4px;"
    )
    banda.addWidget(volver)
    titulo = QLabel("CLI 3074 · Observaciones de superficie")
    titulo.setFont(ui(15, 800))
    titulo.setStyleSheet(f"color:{p['texto']};background:transparent;")
    banda.addWidget(titulo)
    banda.addStretch(1)
    for nombre in ("3074", "4074", "5074"):
        activo = nombre == "3074"
        tab = QLabel(nombre)
        tab.setFont(mono(11))
        tab.setFixedHeight(26)
        tab.setAlignment(Qt.AlignCenter)
        tab.setMinimumWidth(52)
        tab.setStyleSheet(
            f"background:{p['acento_suave'] if activo else p['superficie']};"
            f"color:{p['acento'] if activo else p['suave']};"
            f"border:1px solid {p['acento'] if activo else p['borde']};border-radius:4px;"
        )
        banda.addWidget(tab)
    etiqueta_h = QLabel("VER HORA SYNOP")
    etiqueta_h.setFont(ui(9, 700))
    etiqueta_h.setStyleSheet(f"color:{p['suave']};background:transparent;")
    banda.addWidget(etiqueta_h)
    for hora in HORAS:
        chip = QLabel(hora)
        chip.setFont(mono(10))
        chip.setFixedHeight(26)
        chip.setAlignment(Qt.AlignCenter)
        chip.setMinimumWidth(42)
        chip.setStyleSheet(
            f"background:{p['superficie']};color:{p['suave']};"
            f"border:1px solid {p['borde']};border-radius:4px;"
        )
        banda.addWidget(chip)
    guardar = QLabel("Guardar")
    guardar.setFont(ui(12, 700))
    guardar.setFixedHeight(28)
    guardar.setAlignment(Qt.AlignCenter)
    guardar.setMinimumWidth(84)
    guardar.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};border:none;border-radius:4px;"
    )
    banda.addWidget(guardar)
    v.addLayout(banda)

    # ---- banda de estación: mismas etiquetas y el mismo orden -------------
    datos = QHBoxLayout()
    datos.setSpacing(10)
    for etiqueta, valor, ancho in (
        ("ESTACIÓN", "Las Américas (78485)", 210),
        ("LATITUD", "18.4331", 110),
        ("LONGITUD", "-69.6796", 110),
        ("ALTURA", "2.0", 80),
        ("FECHA", "08/12/2025", 130),
    ):
        celda = QWidget()
        celda.setObjectName("celda")
        celda.setStyleSheet("QWidget#celda { background:transparent; }")
        cv = QVBoxLayout(celda)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(3)
        lab = QLabel(etiqueta)
        lab.setFont(ui(10, 700))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        cv.addWidget(lab)
        campo = QLabel(valor)
        campo.setFont(mono(11))
        campo.setFixedHeight(28)
        campo.setFixedWidth(ancho)
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 6px;"
        )
        cv.addWidget(campo)
        datos.addWidget(celda)
    datos.addStretch(1)
    v.addLayout(datos)

    # ---- la hoja: 24 filas y las mismas columnas -------------------------
    hoja = QWidget()
    hoja.setObjectName("hoja")
    hoja.setStyleSheet(
        f"QWidget#hoja {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    grilla = QGridLayout(hoja)
    grilla.setContentsMargins(10, 8, 10, 8)
    grilla.setHorizontalSpacing(2)
    grilla.setVerticalSpacing(1)

    columna = 0
    grilla.addWidget(_celda_trazo(p, "H", cabecera=True), 0, columna, 2, 1)
    columna += 1
    for grupo, subs in GRUPOS_3074:
        cab = _celda_trazo(p, grupo, cabecera=True)
        grilla.addWidget(cab, 0, columna, 1, len(subs))
        for sub in subs:
            grilla.addWidget(_celda_trazo(p, sub, cabecera=True), 1, columna)
            columna += 1
    cab = _celda_trazo(p, "FENÓMENOS", cabecera=True)
    grilla.addWidget(cab, 0, columna, 1, len(FENOMENOS))
    inicio_fenomenos = columna
    for nombre in FENOMENOS:
        grilla.addWidget(_celda_trazo(p, nombre, cabecera=True), 1, columna)
        columna += 1
    fin_fenomenos = columna - 1
    grilla.addWidget(_celda_trazo(p, "OBS.", cabecera=True), 0, columna, 2, 1)
    for fila in range(FILAS_CLI):
        grilla.setRowStretch(fila + 2, 1)
    _estirar_columnas(grilla, columna + 1, fijas=range(inicio_fenomenos, fin_fenomenos + 1))

    # Cuerpo de la hoja: mismo helper que 4074/5074 (línea de celda + separador).
    for fila in range(FILAS_CLI):
        numero = _celda_cuerpo(p, str(fila + 1))
        numero.setAlignment(Qt.AlignCenter)
        grilla.addWidget(numero, fila + 2, 0)
        for col in range(1, columna):
            grilla.addWidget(_celda_cuerpo(p), fila + 2, col)
        grilla.setRowStretch(fila + 2, 1)
    _estirar_columnas(grilla, columna + 1, fijas=range(inicio_fenomenos, fin_fenomenos + 1))
    v.addWidget(hoja, 1)
    return pagina


GRUPOS_4074 = (
    ("CÚMULONIMBOS", ("Cant", "Tipo", "Altura")),
    ("NUBES BAJAS (CL)", ("Cant", "Tipo", "Dir", "Altura", "TOTAL")),
    ("NUBES MEDIAS (CM)", ("Cant", "Tipo", "Dir", "Altura", "TOTAL")),
    ("NUBES ALTAS (CH)", ("Cant", "Tipo", "Dir", "Altura", "TOTAL")),
)
#: Columnas de una sola celda que ocupan las dos filas de cabecera.
SUELTAS_4074 = ("N", "LLUVIA 6H (mm)", "EST. SUELO", "OBS.")

GRUPOS_5074 = (
    ("LECT. BAR (mmHg)", ()),
    ("TERM. ANEXO (°C)", ()),
    ("CORREC. TEMP.", ()),
    ("PRES. EST. (hPa)", ()),
    ("CORREC. ALT.", ()),
    ("PRES. NMM (hPa)", ()),
)


def banda_superior(p: dict, titulo_texto: str, activo: str) -> QHBoxLayout:
    """Volver + título + pestañas de módulo + VER HORA SYNOP + Guardar."""
    banda = QHBoxLayout()
    banda.setSpacing(10)
    volver = QLabel("←")
    volver.setFont(ui(15, 600))
    volver.setFixedSize(28, 28)
    volver.setAlignment(Qt.AlignCenter)
    volver.setStyleSheet(
        f"color:{p['texto']};background:{p['superficie']};"
        f"border:1px solid {p['borde']};border-radius:4px;"
    )
    banda.addWidget(volver)
    titulo = QLabel(titulo_texto)
    titulo.setFont(ui(15, 800))
    titulo.setStyleSheet(f"color:{p['texto']};background:transparent;")
    banda.addWidget(titulo)
    banda.addStretch(1)
    for nombre in ("3074", "4074", "5074"):
        on = nombre == activo
        tab = QLabel(nombre)
        tab.setFont(mono(11))
        tab.setFixedHeight(26)
        tab.setMinimumWidth(52)
        tab.setAlignment(Qt.AlignCenter)
        tab.setStyleSheet(
            f"background:{p['acento_suave'] if on else p['superficie']};"
            f"color:{p['acento'] if on else p['suave']};"
            f"border:1px solid {p['acento'] if on else p['borde']};border-radius:4px;"
        )
        banda.addWidget(tab)
    etiqueta_h = QLabel("VER HORA SYNOP")
    etiqueta_h.setFont(ui(9, 700))
    etiqueta_h.setStyleSheet(f"color:{p['suave']};background:transparent;")
    banda.addWidget(etiqueta_h)
    for hora in HORAS:
        chip = QLabel(hora)
        chip.setFont(mono(10))
        chip.setFixedHeight(26)
        chip.setMinimumWidth(42)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background:{p['superficie']};color:{p['suave']};"
            f"border:1px solid {p['borde']};border-radius:4px;"
        )
        banda.addWidget(chip)
    guardar = QLabel("Guardar")
    guardar.setFont(ui(12, 700))
    guardar.setFixedHeight(28)
    guardar.setMinimumWidth(84)
    guardar.setAlignment(Qt.AlignCenter)
    guardar.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};border:none;border-radius:4px;"
    )
    banda.addWidget(guardar)
    return banda


def banda_estacion(p: dict) -> QHBoxLayout:
    datos = QHBoxLayout()
    datos.setSpacing(10)
    for etiqueta, valor, ancho in (
        ("ESTACIÓN", "Las Américas (78485)", 210),
        ("LATITUD", "18.4331", 110),
        ("LONGITUD", "-69.6796", 110),
        ("ALTURA", "2.0", 80),
        ("FECHA", "08/12/2025", 130),
    ):
        celda = QWidget()
        celda.setObjectName("celda")
        celda.setStyleSheet("QWidget#celda { background:transparent; }")
        cv = QVBoxLayout(celda)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(3)
        lab = QLabel(etiqueta)
        lab.setFont(ui(10, 700))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        cv.addWidget(lab)
        campo = QLabel(valor)
        campo.setFont(mono(11))
        campo.setFixedHeight(28)
        campo.setFixedWidth(ancho)
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 6px;"
        )
        cv.addWidget(campo)
        datos.addWidget(celda)
    datos.addStretch(1)
    return datos


def _estirar_columnas(
    grilla: QGridLayout, columnas: int, fijas: range | tuple = ()
) -> None:
    """Hora sin estirar, carriles fijos al ancho de una casilla y el resto igual.

    Así lo hace cli3074: las columnas 1..14 comparten el estirón y los carriles
    de fenómenos van a ancho fijo. OBS. no es más ancha que una numérica.
    """
    fijas = set(fijas)
    for col in range(columnas):
        if col == 0 or col in fijas:
            grilla.setColumnStretch(col, 0)
        else:
            grilla.setColumnStretch(col, 1)
    for col in fijas:
        grilla.setColumnMinimumWidth(col, 34)


def _hoja(p: dict) -> tuple[QWidget, QGridLayout]:
    hoja = QWidget()
    hoja.setObjectName("hoja")
    hoja.setStyleSheet(
        f"QWidget#hoja {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    grilla = QGridLayout(hoja)
    grilla.setContentsMargins(10, 8, 10, 8)
    grilla.setHorizontalSpacing(2)
    grilla.setVerticalSpacing(1)
    return hoja, grilla


def _celda_cuerpo(p: dict, texto: str = "") -> QLabel:
    celda = _celda_trazo(p, texto, alto=None)
    celda.setStyleSheet(
        f"color:{p['texto']};background:transparent;"
        f"border-bottom:1px solid {p['borde']};"
        f"border-right:1px solid {p['borde']};padding:0 4px;"
    )
    return celda


def pantalla_cli4074(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(10)
    v.addLayout(banda_superior(p, "CLI 4074 · Nubosidad y temperatura", "4074"))
    v.addLayout(banda_estacion(p))

    hoja, grilla = _hoja(p)
    columna = 0
    grilla.addWidget(_celda_trazo(p, "H", cabecera=True), 0, columna, 2, 1)
    columna += 1
    for grupo, subs in GRUPOS_4074:
        grilla.addWidget(_celda_trazo(p, grupo, cabecera=True), 0, columna, 1, len(subs))
        for sub in subs:
            grilla.addWidget(_celda_trazo(p, sub, cabecera=True), 1, columna)
            columna += 1
    for nombre in SUELTAS_4074:
        grilla.addWidget(_celda_trazo(p, nombre, cabecera=True), 0, columna, 2, 1)
        columna += 1
    for fila in range(FILAS_CLI):
        numero = _celda_cuerpo(p, str(fila + 1))
        numero.setAlignment(Qt.AlignCenter)
        grilla.addWidget(numero, fila + 2, 0)
        for col in range(1, columna):
            grilla.addWidget(_celda_cuerpo(p), fila + 2, col)
        grilla.setRowStretch(fila + 2, 1)
    _estirar_columnas(grilla, columna)
    v.addWidget(hoja, 1)
    return pagina


def _tarjeta(p: dict, titulo_texto: str | None = None) -> tuple[QWidget, QVBoxLayout]:
    """Card del sistema: superficie, borde de 1 px, radio 10."""
    caja = QWidget()
    caja.setObjectName("caja")
    caja.setStyleSheet(
        f"QWidget#caja {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    cv = QVBoxLayout(caja)
    cv.setContentsMargins(12, 10, 12, 10)
    cv.setSpacing(6)
    if titulo_texto:
        t = QLabel(titulo_texto)
        t.setFont(ui(10, 700))
        t.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        cv.addWidget(t)
    return caja, cv


def _campo_plano(p: dict, alto: int = 26) -> QLabel:
    campo = QLabel("")
    campo.setFont(mono(11))
    campo.setFixedHeight(alto)
    campo.setStyleSheet(
        f"background:{p['superficie']};color:{p['texto']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:0 6px;"
    )
    return campo


def pantalla_cli5074(p: dict) -> QWidget:
    """Estructura real de cli5074._build: HORARIO (6 filas x 4 horas) + columna
    con subsuelo y [evap | iniciales] + FENÓMENOS a todo el ancho abajo."""
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(16, 12, 16, 12)
    v.setSpacing(10)
    v.addLayout(banda_superior(p, "CLI 5074 · Suelo y evaporación", "5074"))
    v.addLayout(banda_estacion(p))

    medio = QHBoxLayout()
    medio.setSpacing(10)

    # ---- tarjeta HORARIO: 6 filas de campos x las horas 2 / 8 / 14 / 20 ----
    caja_hor, cv_hor = _tarjeta(p, "HORARIO")
    grilla_hor = QGridLayout()
    grilla_hor.setHorizontalSpacing(3)
    grilla_hor.setVerticalSpacing(3)
    esquina = QLabel("HORA LOCAL")
    esquina.setFont(ui(10, 700))
    esquina.setAlignment(Qt.AlignCenter)
    esquina.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
    grilla_hor.addWidget(esquina, 0, 0)
    for indice, hora in enumerate((2, 8, 14, 20)):
        cab = QLabel(str(hora))
        cab.setFont(mono(11))
        cab.setAlignment(Qt.AlignCenter)
        cab.setStyleSheet(
            f"color:{p['acento']};background:{p['acento_suave']};"
            f"border-bottom:1px solid {p['borde']};"
        )
        grilla_hor.addWidget(cab, 0, indice + 1)
    for fila, etiqueta in enumerate(
        ("LECT. BAR (mmHg)", "TERM. ANEXO (°C)", "CORREC. TEMP.",
         "PRES. EST. (hPa)", "CORREC. ALT.", "PRES. NMM (hPa)")
    ):
        lab = QLabel(etiqueta)
        lab.setFont(ui(10, 600))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        grilla_hor.addWidget(lab, fila + 1, 0)
        for indice in range(4):
            grilla_hor.addWidget(_campo_plano(p), fila + 1, indice + 1)
    grilla_hor.setColumnStretch(0, 2)
    for indice in range(4):
        grilla_hor.setColumnStretch(indice + 1, 1)
    cv_hor.addLayout(grilla_hor)
    cv_hor.addStretch(1)
    medio.addWidget(caja_hor, 3)

    # ---- columna derecha: subsuelo arriba, [evap | iniciales] abajo -------
    derecha = QVBoxLayout()
    derecha.setSpacing(10)

    caja_sub, cv_sub = _tarjeta(p, "TEMPERATURA SUBSUELO")
    grilla_sub = QGridLayout()
    grilla_sub.setHorizontalSpacing(3)
    grilla_sub.setVerticalSpacing(3)
    cm = QLabel("(cm)")
    cm.setFont(ui(9, 600))
    cm.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
    grilla_sub.addWidget(cm, 0, 0)
    for indice, profundidad in enumerate((5, 10, 15, 20, 25, 50, 100)):
        cab = QLabel(str(profundidad))
        cab.setFont(mono(9))
        cab.setAlignment(Qt.AlignCenter)
        cab.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
        grilla_sub.addWidget(cab, 0, indice + 1)
    celsius = QLabel("(°C)")
    celsius.setFont(ui(9, 700))
    celsius.setStyleSheet(f"color:{p['error']};background:transparent;border:none;")
    grilla_sub.addWidget(celsius, 1, 0)
    for indice in range(7):
        grilla_sub.addWidget(_campo_plano(p), 1, indice + 1)
    for col in range(8):
        grilla_sub.setColumnStretch(col, 1)
    cv_sub.addLayout(grilla_sub)
    derecha.addWidget(caja_sub, 0)

    fila_abajo = QHBoxLayout()
    fila_abajo.setSpacing(10)

    caja_evap, cv_evap = _tarjeta(p, "EVAP. 0.00 A 0.00 HL")
    grilla_evap = QGridLayout()
    grilla_evap.setHorizontalSpacing(3)
    grilla_evap.setVerticalSpacing(3)
    for indice, etiqueta in enumerate(("PICHE", "TANQUE C.", "EVAPORÍGRAFO")):
        cab = QLabel(etiqueta)
        cab.setFont(ui(9, 600))
        cab.setAlignment(Qt.AlignCenter)
        cab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        grilla_evap.addWidget(cab, 0, indice)
        sub = QLabel("(mm)")
        sub.setFont(ui(9, 700))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{p['error']};background:transparent;border:none;")
        grilla_evap.addWidget(sub, 1, indice)
        grilla_evap.addWidget(_campo_plano(p), 2, indice)
        grilla_evap.setColumnStretch(indice, 1)
    cv_evap.addLayout(grilla_evap)
    fila_abajo.addWidget(caja_evap, 3)

    caja_ini, cv_ini = _tarjeta(p, None)
    lab_ini = QLabel("INICIALES OBS.")
    lab_ini.setFont(ui(11, 800))
    lab_ini.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
    cv_ini.addWidget(lab_ini)
    campo_ini = _campo_plano(p, alto=64)
    campo_ini.setAlignment(Qt.AlignCenter)
    cv_ini.addWidget(campo_ini)
    cv_ini.addStretch(1)
    fila_abajo.addWidget(caja_ini, 1)

    derecha.addLayout(fila_abajo, 0)
    derecha.addStretch(1)
    medio.addLayout(derecha, 2)
    v.addLayout(medio, 0)

    # ---- FENÓMENOS: a todo el ancho, observaciones a la izquierda ---------
    caja_feno = QWidget()
    caja_feno.setObjectName("caja")
    caja_feno.setStyleSheet(
        f"QWidget#caja {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    fila_feno = QHBoxLayout(caja_feno)
    fila_feno.setContentsMargins(12, 10, 12, 12)
    fila_feno.setSpacing(10)

    izquierda = QVBoxLayout()
    titulo_obs = QLabel("OBSERVACIONES Y DETALLES DEL FENÓMENO")
    titulo_obs.setFont(ui(11, 800))
    titulo_obs.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
    izquierda.addWidget(titulo_obs)
    caja_texto = QLabel("Espacio destinado a detallar más información de forma manual…")
    caja_texto.setWordWrap(True)
    caja_texto.setFont(ui(10))
    caja_texto.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    caja_texto.setStyleSheet(
        f"color:{p['tenue']};background:{p['fondo']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:6px;"
    )
    izquierda.addWidget(caja_texto, 1)
    fila_feno.addLayout(izquierda, 1)

    grupos_feno = (
        ("HORA LOCAL", ("HORAS", "MINUTOS")),
        ("RÁFAGAS DE VIENTO", ("dd 16-P", "ff (m/s)")),
        ("INTENSIDAD", ()),
        ("FENÓMENOS METEOROLÓGICOS", ()),
        ("INICIO (HH:MM)", ()),
        ("FINAL (HH:MM)", ()),
        ("DURACIÓN", ()),
        ("INICIALES OBSERV.", ()),
    )
    tabla_feno = QGridLayout()
    tabla_feno.setHorizontalSpacing(0)
    tabla_feno.setVerticalSpacing(0)
    columna = 0
    for titulo_grupo, subs in grupos_feno:
        cab = QLabel(titulo_grupo)
        cab.setFont(ui(9, 700))
        cab.setWordWrap(True)
        cab.setAlignment(Qt.AlignCenter)
        cab.setStyleSheet(
            f"color:{p['suave']};background:transparent;"
            f"border-bottom:1px solid {p['borde']};padding:2px;"
        )
        tabla_feno.addWidget(cab, 0, columna, 1 if subs else 2, max(1, len(subs)))
        for offset, sub in enumerate(subs):
            sub_lab = QLabel(sub)
            sub_lab.setFont(ui(8, 600))
            sub_lab.setAlignment(Qt.AlignCenter)
            sub_lab.setStyleSheet(
                f"color:{p['tenue']};background:transparent;"
                f"border-bottom:1px solid {p['borde']};"
            )
            tabla_feno.addWidget(sub_lab, 1, columna + offset)
        for fila_f in range(12):
            for offset in range(max(1, len(subs))):
                celda = QLabel("")
                celda.setMinimumHeight(18)
                celda.setStyleSheet(
                    f"background:transparent;border-bottom:1px solid {p['borde']};"
                    f"border-right:1px solid {p['borde']};"
                )
                tabla_feno.addWidget(celda, 2 + fila_f, columna + offset)
        columna += max(1, len(subs))
    for col in range(columna):
        tabla_feno.setColumnStretch(col, 1)
    fila_feno.addLayout(tabla_feno, 3)
    v.addWidget(caja_feno, 1)
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

        for clave, constructor in (
            ("cli3074", pantalla_cli3074),
            ("cli4074", pantalla_cli4074),
            ("cli5074", pantalla_cli5074),
        ):
            w = constructor(paleta)
            w.resize(QSize(ANCHO, ALTO))
            w.show()
            app.processEvents()
            destino = SALIDA / f"mock-{clave}-{nombre}.png"
            w.grab().save(str(destino))
            print(f"  {destino}  ({destino.stat().st_size // 1024} KB)")
            w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
