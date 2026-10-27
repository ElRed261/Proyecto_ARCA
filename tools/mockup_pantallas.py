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
#: Una carpeta por módulo: así la evidencia no se mezcla.
MODULOS = ("synop", "cli", "audit", "summary", "estados")

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


# ---------------------------------------------------------------- Auditoría
# Estructura leída de audit.py (header + breadcrumbs + panel por pasos y filas
# de día con badges), audit_observation.py (header, horas, cuerpo en 3:1) y
# audit_report.py (filtros, notas, tres pestañas de tabla, exportar).

ESTACIONES = (
    "Las Américas (78485)", "Central (78486)", "Barahona (78482)",
    "Cabrera (78481)", "El Catey (MDCY)", "Higuero (78484)",
    "Santiago (78483)", "Puerto Plata (78487)", "La Romana (78488)",
    "Punta Cana (78489)", "San Isidro (78490)", "Monte Cristi (78491)",
)


def _card_audit(p: dict) -> tuple[QWidget, QVBoxLayout]:
    caja = QWidget()
    caja.setObjectName("cardA")
    caja.setStyleSheet(
        f"QWidget#cardA {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    cv = QVBoxLayout(caja)
    cv.setContentsMargins(14, 12, 14, 12)
    cv.setSpacing(6)
    return caja, cv


def _badge(p: dict, texto: str, tipo: str = "muted") -> QLabel:
    colores = {
        "error": (p["error_suave"], p["error"], p["error"]),
        "ok": (p["ok_fondo"], p["ok"], p["ok"]),
        "muted": (p["panel"], p["tenue"], p["borde"]),
    }[tipo]
    fondo, tinta, borde = colores
    lab = QLabel(texto)
    lab.setFont(ui(11, 700))
    lab.setStyleSheet(
        f"background:{fondo};color:{tinta};border:1px solid {borde};"
        "border-radius:9px;padding:3px 9px;"
    )
    return lab


def _cabecera_audit(p: dict, con_reporte: bool = True) -> QHBoxLayout:
    cab = QHBoxLayout()
    titulos = QVBoxLayout()
    titulos.setSpacing(0)
    t = QLabel("Módulo de Auditoría")
    t.setFont(ui(22, 800))
    t.setStyleSheet(f"color:{p['texto']};background:transparent;")
    sub = QLabel(
        "Control de Calidad, Marcado de Errores y Superposición de Correcciones"
    )
    sub.setFont(ui(12))
    sub.setStyleSheet(f"color:{p['suave']};background:transparent;")
    titulos.addWidget(t)
    titulos.addWidget(sub)
    cab.addLayout(titulos, 1)
    if con_reporte:
        boton = QLabel("Reporte General de Errores")
        boton.setFont(ui(12, 700))
        boton.setFixedHeight(32)
        boton.setStyleSheet(
            f"background:{p['acento']};color:{p['superficie']};"
            "border:none;border-radius:4px;padding:0 14px;"
        )
        cab.addWidget(boton, 0, Qt.AlignVCenter)
    return cab


def _crumbs(p: dict, pasos: tuple[str, ...]) -> QWidget:
    barra = QWidget()
    barra.setObjectName("crumbA")
    barra.setStyleSheet(
        f"QWidget#crumbA {{ background:{p['panel']};"
        f" border:1px solid {p['borde']}; border-radius:6px; }}"
    )
    row = QHBoxLayout(barra)
    row.setContentsMargins(12, 8, 12, 8)
    row.setSpacing(6)
    for indice, texto in enumerate(pasos):
        if indice:
            sep = QLabel("›")
            sep.setStyleSheet(f"color:{p['tenue']};background:transparent;")
            row.addWidget(sep)
        activo = indice == len(pasos) - 1
        lab = QLabel(texto)
        lab.setFont(ui(11, 700 if activo else 400))
        lab.setStyleSheet(
            f"color:{p['texto'] if activo else p['suave']};background:transparent;"
        )
        row.addWidget(lab)
    row.addStretch(1)
    return barra


def _titulo_paso(p: dict, texto: str) -> QLabel:
    lab = QLabel(f"◉  {texto}")
    lab.setFont(ui(15, 700))
    lab.setStyleSheet(f"color:{p['texto']};background:transparent;")
    return lab


def pantalla_audit_estaciones(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(20, 16, 20, 16)
    v.setSpacing(12)
    v.addLayout(_cabecera_audit(p))
    v.addWidget(_crumbs(p, ("Estaciones",)))

    panel, cv = _card_audit(p)
    cv.addWidget(_titulo_paso(p, "Seleccione una Estación Meteorológica"))
    grilla = QGridLayout()
    grilla.setHorizontalSpacing(12)
    grilla.setVerticalSpacing(12)
    for indice, nombre in enumerate(ESTACIONES):
        tarjeta = QWidget()
        tarjeta.setObjectName("tarjA")
        tarjeta.setStyleSheet(
            f"QWidget#tarjA {{ background:{p['superficie']};"
            f" border:1px solid {p['borde']}; border-radius:8px; }}"
        )
        tc = QVBoxLayout(tarjeta)
        tc.setContentsMargins(14, 12, 14, 12)
        tc.setSpacing(4)
        hint = QLabel("ESTACIÓN")
        hint.setFont(ui(9, 700))
        hint.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
        nombre_lab = QLabel(nombre)
        nombre_lab.setFont(ui(14, 700))
        nombre_lab.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
        pie = QHBoxLayout()
        explorar = QLabel("Explorar años")
        explorar.setFont(ui(11, 600))
        explorar.setStyleSheet(f"color:{p['acento']};background:transparent;border:none;")
        flecha = QLabel("›")
        flecha.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
        pie.addWidget(explorar)
        pie.addStretch(1)
        pie.addWidget(flecha)
        tc.addWidget(hint)
        tc.addWidget(nombre_lab)
        tc.addLayout(pie)
        grilla.addWidget(tarjeta, indice // 4, indice % 4)
    for col in range(4):
        grilla.setColumnStretch(col, 1)
    cv.addLayout(grilla)
    cv.addStretch(1)
    v.addWidget(panel, 1)
    estado = QLabel("12 estaciones disponibles · el panel se llena desde summary_logs y el árbol")
    estado.setFont(ui(11))
    estado.setStyleSheet(f"color:{p['tenue']};background:transparent;")
    v.addWidget(estado)
    return pagina


def pantalla_audit_dias(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(20, 16, 20, 16)
    v.setSpacing(12)
    v.addLayout(_cabecera_audit(p))
    v.addWidget(_crumbs(p, ("Estaciones", "Estación Las Américas", "2025", "Diciembre")))

    panel, cv = _card_audit(p)
    cv.addWidget(
        _titulo_paso(p, "Listado de Días — Estación Las Américas (Diciembre 2025)")
    )
    dias = (
        ("31", "2025-12-31", "JUAN RODRIGUEZ", 0, 0, 0, True),
        ("30", "2025-12-30", "MENDEZ", 2, 0, 0, True),
        ("29", "2025-12-29", "FELIPE", 0, 1, 0, True),
        ("28", "2025-12-28", "JUAN RODRIGUEZ", 3, 2, 0, False),
        ("27", "2025-12-27", "MENDEZ", 0, 0, 0, False),
        ("26", "2025-12-26", "FELIPE", 1, 0, 1, False),
        ("25", "2025-12-25", "JUAN RODRIGUEZ", 0, 0, 0, False),
        ("21", "2025-12-21", "MENDEZ", 4, 4, 0, False),
    )
    for numero, fecha, obs, errores, correcciones, revisados, cerrado in dias:
        fila = QWidget()
        fila.setObjectName("filaD")
        fila.setStyleSheet(
            f"QWidget#filaD {{ background:{p['superficie']};"
            f" border:1px solid {p['borde']}; border-radius:8px; }}"
        )
        fl = QHBoxLayout(fila)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(12)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        titulo = QLabel(f"Día {numero} ({fecha})")
        titulo.setFont(ui(14, 700))
        titulo.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
        textos.addWidget(titulo)
        meta = QHBoxLayout()
        meta.setSpacing(14)
        for texto in (f"Obs: {obs}", f"Horas: {5 if cerrado else 0}"):
            lab = QLabel(texto)
            lab.setFont(ui(11))
            lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
            meta.addWidget(lab)
        meta.addStretch(1)
        textos.addLayout(meta)
        fl.addLayout(textos, 1)
        badges = QHBoxLayout()
        badges.setSpacing(6)
        if errores:
            badges.addWidget(_badge(p, f"{errores} Error{'es' if errores > 1 else ''}", "error"))
        if correcciones:
            badges.addWidget(
                _badge(p, f"{correcciones} Correcci{'ones' if correcciones > 1 else 'ón'}", "ok")
            )
        if revisados:
            badges.addWidget(_badge(p, "Revisado", "muted"))
        if cerrado:
            badges.addWidget(_badge(p, "Cerrado", "muted"))
        fl.addLayout(badges)
        cv.addWidget(fila)
    cv.addStretch(1)
    v.addWidget(panel, 1)
    estado = QLabel("8 días en el mes · los badges salen del conteo real de marcas y correcciones")
    estado.setFont(ui(11))
    estado.setStyleSheet(f"color:{p['tenue']};background:transparent;")
    v.addWidget(estado)
    return pagina


def pantalla_audit_reporte(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(20, 16, 20, 16)
    v.setSpacing(10)

    titulos = QVBoxLayout()
    titulos.setSpacing(0)
    t = QLabel("Reporte General de Errores")
    t.setFont(ui(22, 900))
    t.setStyleSheet(f"color:{p['texto']};background:transparent;")
    sub = QLabel("Detalle de inconsistencias, resumen por persona y conteo por observador")
    sub.setFont(ui(12))
    sub.setStyleSheet(f"color:{p['suave']};background:transparent;")
    titulos.addWidget(t)
    titulos.addWidget(sub)
    v.addLayout(titulos)

    filtros, filtros_cv = _card_audit(p)
    filtros_cv.setContentsMargins(12, 10, 12, 10)
    fila = QHBoxLayout()
    fila.setSpacing(8)
    for etiqueta, marcador, ancho in (
        ("Estación", "Código de estación (opcional)", 200),
        ("Año", "AAAA", 80),
        ("Mes", "(Todos) ▾", 130),
    ):
        lab = QLabel(etiqueta)
        lab.setFont(ui(11, 700))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        fila.addWidget(lab)
        campo = QLabel(marcador)
        campo.setFont(ui(11))
        campo.setFixedHeight(28)
        campo.setFixedWidth(ancho)
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['tenue']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 6px;"
        )
        fila.addWidget(campo)
    filtrar = QLabel("Filtrar")
    filtrar.setFont(ui(12, 700))
    filtrar.setFixedHeight(28)
    filtrar.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};"
        "border:none;border-radius:4px;padding:0 14px;"
    )
    fila.addWidget(filtrar)
    fila.addStretch(1)
    filtros_cv.addLayout(fila)
    v.addWidget(filtros)

    notas, notas_cv = _card_audit(p)
    notas_cv.setContentsMargins(12, 10, 12, 10)
    lab_notas = QLabel("Notas Generales del Reporte")
    lab_notas.setFont(ui(11, 700))
    lab_notas.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
    notas_cv.addWidget(lab_notas)
    caja_notas = QLabel("Notas generales del reporte (salen en el PDF)")
    caja_notas.setFont(ui(10))
    caja_notas.setFixedHeight(48)
    caja_notas.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    caja_notas.setStyleSheet(
        f"background:{p['superficie']};color:{p['tenue']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:6px;"
    )
    notas_cv.addWidget(caja_notas)
    v.addWidget(notas)

    pestanas = QHBoxLayout()
    pestanas.setSpacing(4)
    for indice, texto in enumerate(
        ("Por observador", "Detalle de Inconsistencias", "Resumen por Persona")
    ):
        activa = indice == 0
        pestana = QLabel(texto)
        pestana.setFont(ui(11, 700))
        pestana.setFixedHeight(30)
        pestana.setStyleSheet(
            f"background:{p['acento'] if activa else p['superficie']};"
            f"color:{p['superficie'] if activa else p['suave']};"
            f"border:1px solid {p['acento'] if activa else p['borde']};"
            "border-top-left-radius:6px;border-top-right-radius:6px;padding:0 14px;"
        )
        pestanas.addWidget(pestana)
    pestanas.addStretch(1)
    v.addLayout(pestanas)

    tabla, tabla_cv = _card_audit(p)
    tabla_cv.setContentsMargins(0, 0, 0, 0)
    grilla = QGridLayout()
    grilla.setContentsMargins(10, 8, 10, 8)
    grilla.setHorizontalSpacing(0)
    grilla.setVerticalSpacing(0)
    cabeceras = ("OBSERVADOR", "MARCADOS", "CORREGIDOS", "APROBADOS", "TOTAL")
    for col, texto in enumerate(cabeceras):
        cab = QLabel(texto)
        cab.setFont(ui(10, 700))
        cab.setStyleSheet(
            f"color:{p['suave']};background:transparent;"
            f"border-bottom:1px solid {p['borde']};padding:4px;"
        )
        cab.setAlignment(Qt.AlignLeft if col == 0 else Qt.AlignRight)
        grilla.addWidget(cab, 0, col)
    datos = (
        ("JUAN RODRIGUEZ", "14", "9", "7", "30"),
        ("MENDEZ", "8", "6", "6", "20"),
        ("FELIPE", "5", "4", "3", "12"),
        ("MiMi MjMj", "1", "0", "0", "1"),
    )
    for fila_i, valores in enumerate(datos, start=1):
        for col, valor in enumerate(valores):
            celda = QLabel(valor)
            celda.setFont(mono(11) if col else ui(11, 600))
            celda.setStyleSheet(
                f"color:{p['texto']};background:transparent;"
                f"border-bottom:1px solid {p['borde']};padding:5px 4px;"
            )
            celda.setAlignment(Qt.AlignLeft if col == 0 else Qt.AlignRight)
            grilla.addWidget(celda, fila_i, col)
    for col in range(len(cabeceras)):
        grilla.setColumnStretch(col, 1)
    tabla_cv.addLayout(grilla)
    tabla_cv.addStretch(1)
    v.addWidget(tabla, 1)

    pie = QHBoxLayout()
    pie.addStretch(1)
    exportar = QLabel("Exportar PDF")
    exportar.setFont(ui(12, 700))
    exportar.setFixedHeight(30)
    exportar.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};"
        "border:none;border-radius:4px;padding:0 16px;"
    )
    pie.addWidget(exportar)
    v.addLayout(pie)

    fila_nota = QHBoxLayout()
    lab_nota = QLabel("Nota de la fila")
    lab_nota.setFont(ui(11))
    lab_nota.setStyleSheet(f"color:{p['suave']};background:transparent;")
    fila_nota.addWidget(lab_nota)
    campo_nota = QLabel("")
    campo_nota.setFixedHeight(28)
    campo_nota.setStyleSheet(
        f"background:{p['superficie']};border:1px solid {p['borde']};"
        "border-radius:4px;"
    )
    fila_nota.addWidget(campo_nota, 1)
    guardar_nota = QLabel("Guardar Nota")
    guardar_nota.setFont(ui(11, 600))
    guardar_nota.setFixedHeight(28)
    guardar_nota.setStyleSheet(
        f"background:{p['superficie']};color:{p['texto']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:0 12px;"
    )
    fila_nota.addWidget(guardar_nota)
    v.addLayout(fila_nota)
    return pagina


# ------------------------------------------- Auditoría sobre el Sinóptico (A+D+B)
# A: la misma grilla de 16 filas del Sinóptico, en lectura, con el estado en el
#    propio campo. D: cola de pendientes con «Siguiente pendiente». B: riel de
#    historial guardado -> propuesto, plegable.

#: estado por (fila del formulario, columna): "marcado" | "corregido" | "limpio"
ESTADOS_CAMPO = {
    (1, 3): "marcado",   # 15Z · 2snTdTdTd
    (2, 1): "corregido", # 21Z · Nddff
    (3, 0): "marcado",   # 00Z · 5nFnFnFn
    (0, 1): "corregido", # 06Z · YYGGIw
}
CAMPO_ACTIVO = (1, 3)


def _formulario_auditado(p: dict) -> QWidget:
    tarjeta = QWidget()
    tarjeta.setObjectName("tarjeta")
    tarjeta.setStyleSheet(
        f"QWidget#tarjeta {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    v = QVBoxLayout(tarjeta)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(10)

    obs = QHBoxLayout()
    lab = QLabel("Observador")
    lab.setFont(ui(11, 600))
    lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
    lab.setFixedWidth(104)
    obs.addWidget(lab)
    campo = QLabel("JUAN RODRIGUEZ")
    campo.setFont(mono(12))
    campo.setFixedHeight(34)
    campo.setStyleSheet(
        f"background:{p['panel']};color:{p['suave']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:0 8px;"
    )
    obs.addWidget(campo, 1)
    v.addLayout(obs)

    grilla = QGridLayout()
    grilla.setHorizontalSpacing(8)
    grilla.setVerticalSpacing(3)
    colores = {
        "marcado": p["error"],
        "corregido": p["ok"],
        "limpio": p["borde"],
    }
    for indice, celdas in enumerate(FILAS):
        columna = 0
        for etiqueta, tramo in celdas:
            estado = ESTADOS_CAMPO.get((indice, columna), "limpio")
            activo = (indice, columna) == CAMPO_ACTIVO
            cab = QWidget()
            cab.setObjectName("cab")
            cab.setStyleSheet("QWidget#cab { background:transparent; border:none; }")
            ch = QHBoxLayout(cab)
            ch.setContentsMargins(0, 0, 0, 0)
            ch.setSpacing(4)
            lab = QLabel(etiqueta)
            lab.setFont(ui(11, 600))
            lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
            ch.addWidget(lab)
            if estado != "limpio":
                punto = QLabel("●")
                punto.setFont(ui(8))
                punto.setStyleSheet(
                    f"color:{colores[estado]};background:transparent;border:none;"
                )
                ch.addWidget(punto)
            ch.addStretch(1)
            grilla.addWidget(cab, indice * 2, columna, 1, tramo)

            valor = _valor_de(indice, columna)
            caja = QWidget()
            caja.setObjectName("caja")
            caja.setStyleSheet("QWidget#caja { background:transparent; border:none; }")
            caj = QHBoxLayout(caja)
            caj.setContentsMargins(0, 0, 0, 0)
            caj.setSpacing(0)
            texto = QLabel(valor)
            texto.setFont(mono(12))
            texto.setFixedHeight(34)
            texto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            borde = p["acento"] if activo else colores[estado]
            grosor = 2 if activo else 1
            texto.setStyleSheet(
                f"background:{p['superficie']};color:{p['texto']};"
                f"border:{grosor}px solid {borde};border-radius:4px;padding:0 8px;"
            )
            caj.addWidget(texto, 1)
            if activo:
                # Las dos acciones viven fuera del campo, con aire: dentro
                # quedaban apretadas contra el valor.
                acciones = QVBoxLayout()
                acciones.setContentsMargins(0, 0, 0, 0)
                acciones.setSpacing(2)
                for glifo, tip in (("✎", "corregir"), ("⚑", "marcar")):
                    boton = QLabel(glifo)
                    boton.setFont(ui(11))
                    boton.setFixedSize(22, 16)
                    boton.setAlignment(Qt.AlignCenter)
                    boton.setToolTip(tip)
                    boton.setStyleSheet(
                        f"background:{p['acento_suave']};color:{p['acento']};"
                        "border:none;border-radius:3px;"
                    )
                    acciones.addWidget(boton)
                caj.addSpacing(4)
                caj.addLayout(acciones, 0)
            grilla.addWidget(caja, indice * 2 + 1, columna, 1, tramo)
            columna += tramo
        grilla.setRowMinimumHeight(indice * 2 + 1, 34)
    for col in range(7):
        grilla.setColumnStretch(col, 1)
    for fila in range(len(FILAS) * 2):
        grilla.setRowStretch(fila, 1)
    v.addLayout(grilla, 1)
    return tarjeta


def pantalla_audit_sinoptico(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(20, 14, 20, 14)
    v.setSpacing(10)

    # ---- cabecera --------------------------------------------------------
    cab = QHBoxLayout()
    izq = QVBoxLayout()
    izq.setSpacing(4)
    pastillas = QHBoxLayout()
    pastillas.setSpacing(6)
    for texto, tipo in (("ESTACIÓN 78485", "acento"), ("08/12/2025 · 15Z", "panel")):
        lab = QLabel(texto)
        lab.setFont(ui(11, 700))
        if tipo == "acento":
            lab.setStyleSheet(
                f"background:{p['naranja_fondo']};color:{p['naranja_fuerte']};"
                f"border:1px solid {p['naranja_debil']};border-radius:9px;padding:3px 9px;"
            )
        else:
            lab.setStyleSheet(
                f"background:{p['panel']};color:{p['suave']};"
                f"border:1px solid {p['borde']};border-radius:9px;padding:3px 9px;"
            )
        pastillas.addWidget(lab)
    pastillas.addStretch(1)
    izq.addLayout(pastillas)
    titulo = QLabel("Auditoría · Sinóptico")
    titulo.setFont(ui(22, 800))
    titulo.setStyleSheet(f"color:{p['texto']};background:transparent;")
    izq.addWidget(titulo)
    cab.addLayout(izq, 1)

    der = QVBoxLayout()
    der.setSpacing(6)
    acciones = QHBoxLayout()
    acciones.setSpacing(6)
    siguiente = QLabel("Siguiente pendiente  ·  3")
    siguiente.setFont(ui(12, 700))
    siguiente.setFixedHeight(32)
    siguiente.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};"
        "border:none;border-radius:4px;padding:0 14px;"
    )
    acciones.addWidget(siguiente)
    for texto in ("Guardar correcciones", "Terminar auditoría"):
        boton = QLabel(texto)
        boton.setFont(ui(11, 600))
        boton.setFixedHeight(32)
        boton.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 12px;"
        )
        acciones.addWidget(boton)
    der.addLayout(acciones)
    resumen = QLabel("3 marcas sin corregir · 1 corrección por aprobar · 12 campos sin revisar")
    resumen.setFont(ui(11))
    resumen.setAlignment(Qt.AlignRight)
    resumen.setStyleSheet(f"color:{p['suave']};background:transparent;")
    der.addWidget(resumen)
    cab.addLayout(der, 0)
    v.addLayout(cab)

    # ---- tira de horas + leyenda ----------------------------------------
    barra = QWidget()
    barra.setObjectName("barra")
    barra.setStyleSheet(
        f"QWidget#barra {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:8px; }}"
    )
    fila = QHBoxLayout(barra)
    fila.setContentsMargins(10, 8, 10, 8)
    fila.setSpacing(6)
    for hora in HORAS:
        activa = hora == HORA_ACTIVA
        boton = QLabel(hora)
        boton.setFont(mono(10))
        boton.setFixedHeight(26)
        boton.setMinimumWidth(48)
        boton.setAlignment(Qt.AlignCenter)
        boton.setStyleSheet(
            f"background:{p['acento_suave'] if activa else p['superficie']};"
            f"color:{p['acento'] if activa else p['suave']};"
            f"border:1px solid {p['acento'] if activa else p['borde']};border-radius:4px;"
        )
        fila.addWidget(boton)
        punto = QLabel("●")
        punto.setFont(ui(7))
        punto.setStyleSheet(
            f"color:{p['error'] if hora in ('15Z', '21Z', '00Z') else p['borde']};"
            "background:transparent;"
        )
        fila.addWidget(punto)
    fila.addStretch(1)
    for glifo, texto, color in (
        ("●", "marcado", p["error"]),
        ("●", "corregido", p["ok"]),
        ("○", "limpio", p["tenue"]),
    ):
        punto = QLabel(glifo)
        punto.setFont(ui(10))
        punto.setStyleSheet(f"color:{color};background:transparent;")
        fila.addWidget(punto)
        etiqueta = QLabel(texto)
        etiqueta.setFont(ui(10))
        etiqueta.setStyleSheet(f"color:{p['suave']};background:transparent;")
        fila.addWidget(etiqueta)
        fila.addSpacing(8)
    v.addWidget(barra)

    # ---- cuerpo: formulario | cola + historial ---------------------------
    cuerpo = QHBoxLayout()
    cuerpo.setSpacing(12)
    cuerpo.addWidget(_formulario_auditado(p), 62)

    derecha = QVBoxLayout()
    derecha.setSpacing(10)

    cola, cola_cv = _card_audit(p)
    titulo_cola = QLabel("Cola de pendientes")
    titulo_cola.setFont(ui(12, 800))
    titulo_cola.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
    cola_cv.addWidget(titulo_cola)
    for etiqueta, valor, tipo in (
        ("Marcas sin corregir", "3", "error"),
        ("Correcciones por aprobar", "1", "ok"),
        ("Campos sin revisar", "12", "muted"),
    ):
        fila_cola = QHBoxLayout()
        nom = QLabel(etiqueta)
        nom.setFont(ui(11))
        nom.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        fila_cola.addWidget(nom, 1)
        fila_cola.addWidget(_badge(p, valor, tipo))
        cola_cv.addLayout(fila_cola)
    pista = QLabel("Enter va al siguiente pendiente; N marca, C corrige")
    pista.setFont(ui(10))
    pista.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
    cola_cv.addWidget(pista)
    derecha.addWidget(cola, 0)

    hist, hist_cv = _card_audit(p)
    cab_hist = QHBoxLayout()
    titulo_hist = QLabel("Historial del campo")
    titulo_hist.setFont(ui(12, 800))
    titulo_hist.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
    cab_hist.addWidget(titulo_hist, 1)
    plegar = QLabel("▾ 2snTdTdTd")
    plegar.setFont(ui(10, 600))
    plegar.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
    cab_hist.addWidget(plegar)
    hist_cv.addLayout(cab_hist)
    for campo, antes, ahora, quien, hora in (
        ("2snTdTdTd", "20186", "20185", "MENDEZ", "10:42"),
        ("Nddff", "82506", "82516", "FELIPE", "11:05"),
        ("YYGGIw", "08124", "08125", "JUAN R.", "09:18"),
    ):
        fila_h = QWidget()
        fila_h.setObjectName("histF")
        fila_h.setStyleSheet(
            f"QWidget#histF {{ background:{p['panel']}; border-radius:6px; }}"
        )
        fh = QVBoxLayout(fila_h)
        fh.setContentsMargins(8, 6, 8, 6)
        fh.setSpacing(2)
        nombre = QLabel(campo)
        nombre.setFont(ui(10, 700))
        nombre.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
        fh.addWidget(nombre)
        cambio = QHBoxLayout()
        v1 = QLabel(antes)
        v1.setFont(mono(11))
        v1.setStyleSheet(
            f"color:{p['suave']};background:transparent;border:none;"
        )
        flecha = QLabel("→")
        flecha.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
        v2 = QLabel(ahora)
        v2.setFont(mono(11))
        v2.setStyleSheet(f"color:{p['ok']};background:transparent;border:none;")
        quien_lab = QLabel(f"{quien} · {hora}")
        quien_lab.setFont(ui(9))
        quien_lab.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
        cambio.addWidget(v1)
        cambio.addWidget(flecha)
        cambio.addWidget(v2)
        cambio.addStretch(1)
        cambio.addWidget(quien_lab)
        fh.addLayout(cambio)
        hist_cv.addWidget(fila_h)
    hist_cv.addStretch(1)
    derecha.addWidget(hist, 1)
    cuerpo.addLayout(derecha, 38)
    v.addLayout(cuerpo, 1)
    return pagina


# ---------------------------------------------------------------- Resumen
# Estructura leída de summary.py: header con título/subtítulo y las pastillas
# Historial/Tabla + «Importar manual»; card blanca con el panel de carga
# (gauge + leyenda, Estación/Mes/Año, casilla de correcciones, Generar), la
# línea de estado y el stack historial|tabla. La tabla son los 21 HEADERS del
# servicio; el historial son tarjetas con badge de período, estación, días,
# «SYNOP», papelera y flecha.

#: summary_service.HEADERS, en su orden real.
HEADERS_RESUMEN = (
    "Dias", "Mayor temperatura máxima", "Menor temperatura minima",
    "Media temperatura", "MAxima presión nivel medio del mar",
    "Minima presión nivel medio del mar", "Media presión nivel medio del mar",
    "Media presion en la estación", "Lluvia", "Dirección del viento",
    "Velocidad media del viento", "Velocidad máxima y direccion",
    "Recorrido del viento", "Nuvocidad dia", "Nuvocidad noche",
    "Media de nuvocidad", "Humedad maxima", "Humedad minima", "Humedad media",
    "Punto de rocio", "Tensión de vapor",
)


def _cabecera_resumen(p: dict) -> QHBoxLayout:
    fila = QHBoxLayout()
    fila.setSpacing(12)
    titulos = QVBoxLayout()
    titulos.setSpacing(2)
    t = QLabel("Resumen Mensual SYNOP")
    t.setFont(ui(24, 800))
    t.setStyleSheet(f"color:{p['texto']};background:transparent;")
    sub = QLabel("Generación y visualización de resúmenes climáticos")
    sub.setFont(ui(13))
    sub.setStyleSheet(f"color:{p['suave']};background:transparent;")
    titulos.addWidget(t)
    titulos.addWidget(sub)
    fila.addLayout(titulos)
    fila.addStretch(1)
    for texto, activo in (("Historial", True), ("Tabla", False)):
        pill = QLabel(texto)
        pill.setFont(ui(11, 700))
        pill.setFixedHeight(30)
        pill.setStyleSheet(
            f"background:{p['acento_suave'] if activo else p['superficie']};"
            f"color:{p['acento'] if activo else p['suave']};"
            f"border:1px solid {p['acento'] if activo else p['borde']};"
            "border-radius:15px;padding:0 14px;"
        )
        fila.addWidget(pill)
    manual = QLabel("Importar manual")
    manual.setFont(ui(11, 600))
    manual.setFixedHeight(30)
    manual.setStyleSheet(
        f"background:{p['superficie']};color:{p['texto']};"
        f"border:1px solid {p['borde']};border-radius:15px;padding:0 14px;"
    )
    fila.addWidget(manual)
    return fila


def _panel_carga(p: dict) -> QWidget:
    panel = QWidget()
    panel.setObjectName("panelC")
    panel.setStyleSheet(
        f"QWidget#panelC {{ background:{p['panel']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    cv = QVBoxLayout(panel)
    cv.setContentsMargins(18, 14, 18, 14)
    cv.setSpacing(10)
    leyenda = QLabel("◔  CARGA AUTOMÁTICA POR ESTACIÓN Y PERÍODO")
    leyenda.setFont(ui(10, 800))
    leyenda.setStyleSheet(f"color:{p['acento']};background:transparent;border:none;")
    cv.addWidget(leyenda)

    fila = QHBoxLayout()
    fila.setSpacing(14)
    for etiqueta, valor, ancho in (
        ("Estación Meteorológica", "Las Américas (78485)  ▾", 260),
        ("Mes", "Diciembre  ▾", 140),
        ("Año", "2025  ▾", 100),
    ):
        celda = QVBoxLayout()
        celda.setSpacing(4)
        lab = QLabel(etiqueta)
        lab.setFont(ui(11, 600))
        lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        celda.addWidget(lab)
        campo = QLabel(valor)
        campo.setFont(ui(11))
        campo.setFixedHeight(30)
        campo.setFixedWidth(ancho)
        campo.setStyleSheet(
            f"background:{p['superficie']};color:{p['texto']};"
            f"border:1px solid {p['borde']};border-radius:4px;padding:0 8px;"
        )
        celda.addWidget(campo)
        fila.addLayout(celda)
    casilla = QLabel("☑  Incluir correcciones")
    casilla.setFont(ui(11, 600))
    casilla.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
    fila.addWidget(casilla, 0, Qt.AlignBottom)
    generar = QLabel("Generar resumen")
    generar.setFont(ui(12, 700))
    generar.setFixedHeight(30)
    generar.setStyleSheet(
        f"background:{p['acento']};color:{p['superficie']};"
        "border:none;border-radius:4px;padding:0 16px;"
    )
    fila.addWidget(generar, 0, Qt.AlignBottom)
    fila.addStretch(1)
    cv.addLayout(fila)
    return panel


def _valor_resumen(dia: int, columna: int) -> str:
    """Valores coherentes de ejemplo (media = (máx+mín)/2, etc.)."""
    tmax = 29.6 + (dia % 5) * 0.4
    tmin = 21.8 + (dia % 4) * 0.5
    media = (tmax + tmin) / 2
    lluvia = 0.0 if dia % 7 else round(3.4 + (dia % 5), 1)
    tabla = (
        f"{dia}",
        f"{tmax:.1f}", f"{tmin:.1f}", f"{media:.1f}",
        f"{1014.2 + (dia % 6) * 0.3:.1f}", f"{1009.8 + (dia % 4) * 0.4:.1f}",
        f"{1012.0 + (dia % 5) * 0.2:.1f}", f"{1011.4 + (dia % 3) * 0.3:.1f}",
        f"{lluvia:.1f}",
        f"{(90 + dia * 10) % 360:03d}", f"{8 + dia % 9}",
        f"{24 + dia % 6} / {110 + (dia % 8) * 5}",
        f"{180 + (dia % 10) * 12}",
        f"{7 if dia % 3 else 6}", f"{5 if dia % 4 else 4}",
        f"{6.2 + (dia % 3) * 0.2:.1f}",
        f"{94 - dia % 5}", f"{58 + dia % 7}",
        f"{76 + (dia % 4) * 0.5:.1f}", f"{20.1 + (dia % 5) * 0.4:.1f}",
        f"{23.4 + (dia % 4) * 0.5:.1f}",
    )
    return tabla[columna] if columna < len(tabla) else ""


def pantalla_summary_tabla(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(28, 20, 28, 20)
    v.setSpacing(14)
    v.addLayout(_cabecera_resumen(p))
    v.addWidget(_panel_carga(p))

    meta = QHBoxLayout()
    t = QLabel("Las Américas (78485)")
    t.setFont(ui(16, 800))
    t.setStyleSheet(f"color:{p['texto']};background:transparent;")
    det = QLabel("Período: Diciembre 2025   ·   Días analizados: 31")
    det.setFont(ui(12))
    det.setStyleSheet(f"color:{p['suave']};background:transparent;")
    meta.addWidget(t)
    meta.addWidget(det)
    meta.addStretch(1)
    exportar = QLabel("Exportar a Excel")
    exportar.setFont(ui(11, 600))
    exportar.setFixedHeight(28)
    exportar.setStyleSheet(
        f"background:{p['superficie']};color:{p['texto']};"
        f"border:1px solid {p['borde']};border-radius:4px;padding:0 12px;"
    )
    meta.addWidget(exportar)
    v.addLayout(meta)

    tabla = QWidget()
    tabla.setObjectName("tablaS")
    tabla.setStyleSheet(
        f"QWidget#tablaS {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    grilla = QGridLayout(tabla)
    grilla.setContentsMargins(8, 6, 8, 6)
    grilla.setHorizontalSpacing(0)
    grilla.setVerticalSpacing(0)
    for col, texto in enumerate(HEADERS_RESUMEN):
        cab = QLabel(texto)
        cab.setFont(ui(8, 700))
        cab.setWordWrap(True)
        cab.setAlignment(Qt.AlignCenter)
        cab.setMinimumHeight(46)  # sin alto propio los rótulos largos se cortan
        cab.setStyleSheet(
            f"color:{p['suave']};background:{p['panel']};"
            f"border-bottom:1px solid {p['borde']};"
            f"border-right:1px solid {p['borde']};padding:3px 2px;"
        )
        grilla.addWidget(cab, 0, col)
    for dia in range(1, 32):
        for col in range(len(HEADERS_RESUMEN)):
            num = QLabel(_valor_resumen(dia, col))
            num.setFont(mono(9) if col else ui(9, 700))
            num.setFixedHeight(17)
            num.setAlignment(Qt.AlignLeft if col == 0 else Qt.AlignRight)
            num.setStyleSheet(
                f"color:{p['texto']};background:transparent;"
                f"border-bottom:1px solid {p['borde']};"
                f"border-right:1px solid {p['borde']};padding:0 3px;"
            )
            grilla.addWidget(num, dia, col)
        grilla.setRowStretch(dia, 1)
    grilla.setRowStretch(0, 0)
    grilla.setRowMinimumHeight(0, 46)
    for col in range(len(HEADERS_RESUMEN)):
        grilla.setColumnStretch(col, 2 if col == 0 else 1)
    v.addWidget(tabla, 1)

    estado = QLabel("Resumen cargado desde summary_logs · 31 días · correcciones aplicadas")
    estado.setFont(ui(10))
    estado.setStyleSheet(f"color:{p['tenue']};background:transparent;")
    v.addWidget(estado)
    return pagina


def pantalla_summary_historial(p: dict) -> QWidget:
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(28, 20, 28, 20)
    v.setSpacing(14)
    v.addLayout(_cabecera_resumen(p))
    v.addWidget(_panel_carga(p))

    seccion = QHBoxLayout()
    titulo = QLabel("Historial de Reportes Guardados")
    titulo.setFont(ui(19, 900))
    titulo.setStyleSheet(f"color:{p['texto']};background:transparent;")
    seccion.addWidget(titulo)
    seccion.addStretch(1)
    v.addLayout(seccion)

    for periodo, estacion, dias in (
        ("DICIEMBRE 2025", "Las Américas (78485)", 31),
        ("NOVIEMBRE 2025", "Las Américas (78485)", 30),
        ("OCTUBRE 2025", "Central (78486)", 31),
        ("SEPTIEMBRE 2025", "Central (78486)", 30),
    ):
        tarjeta = QWidget()
        tarjeta.setObjectName("histC")
        tarjeta.setStyleSheet(
            f"QWidget#histC {{ background:{p['superficie']};"
            f" border:1px solid {p['borde']}; border-radius:10px; }}"
        )
        fila = QHBoxLayout(tarjeta)
        fila.setContentsMargins(16, 12, 12, 12)
        fila.setSpacing(14)
        badge = QLabel(periodo)
        badge.setFont(ui(10, 800))
        badge.setStyleSheet(
            f"background:{p['acento_suave']};color:{p['acento']};"
            f"border:1px solid {p['borde']};border-radius:6px;padding:4px 10px;"
        )
        fila.addWidget(badge)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        nombre = QLabel(estacion)
        nombre.setFont(ui(14, 800))
        nombre.setStyleSheet(f"color:{p['texto']};background:transparent;border:none;")
        dias_lab = QLabel(f"{dias} días analizados")
        dias_lab.setFont(ui(11))
        dias_lab.setStyleSheet(f"color:{p['suave']};background:transparent;border:none;")
        textos.addWidget(nombre)
        textos.addWidget(dias_lab)
        fila.addLayout(textos)
        fila.addStretch(1)
        tipo = QLabel("SYNOP")
        tipo.setFont(ui(9, 800))
        tipo.setStyleSheet(f"color:{p['tenue']};background:transparent;border:none;")
        fila.addWidget(tipo)
        borrar = QLabel("🗑")
        borrar.setFont(ui(12))
        borrar.setFixedSize(30, 30)
        borrar.setAlignment(Qt.AlignCenter)
        borrar.setStyleSheet(
            f"color:{p['tenue']};background:transparent;border:none;"
        )
        fila.addWidget(borrar)
        flecha = QLabel("→")
        flecha.setFont(ui(13, 700))
        flecha.setStyleSheet(f"color:{p['acento']};background:transparent;border:none;")
        fila.addWidget(flecha)
        v.addWidget(tarjeta)
    v.addStretch(1)
    estado = QLabel("4 reportes guardados · clic en una tarjeta para abrirla")
    estado.setFont(ui(10))
    estado.setStyleSheet(f"color:{p['tenue']};background:transparent;")
    v.addWidget(estado)
    return pagina


# ------------------------------------------------ Resumen: meteograma
# Referencia: el meteograma de MetPy (unidata.github.io) apila paneles que
# comparten el eje de tiempo — viento (velocidad y dirección), temperatura con
# punto de rocío, humedad relativa y presión. Aquí son cinco filas con las
# variables del Resumen Mensual, en datos diarios (día 1..31).


def _series_resumen() -> dict[str, list[float]]:
    """Series de 31 días coherentes con la tabla del mockup."""
    tmax, tmin, tmed, pmed, pmax, pmin, lluvia, vel, velmax, dirv = (
        [], [], [], [], [], [], [], [], [], []
    )
    hummax, hummin, hummed, rocio, nubdia, nubnoche, nubmed = (
        [], [], [], [], [], [], []
    )
    for dia in range(1, 32):
        tx = 29.6 + (dia % 5) * 0.4
        tn = 21.8 + (dia % 4) * 0.5
        tmax.append(tx)
        tmin.append(tn)
        tmed.append((tx + tn) / 2)
        rocio.append(20.1 + (dia % 5) * 0.4)
        pmed.append(1012.0 + (dia % 5) * 0.2)
        pmax.append(1014.2 + (dia % 6) * 0.3)
        pmin.append(1009.8 + (dia % 4) * 0.4)
        lluvia.append(0.0 if dia % 7 else 3.4 + (dia % 5))
        vel.append(8 + dia % 9)
        velmax.append(24 + dia % 6)
        dirv.append((90 + dia * 10) % 360)
        hummax.append(94 - dia % 5)
        hummin.append(58 + dia % 7)
        hummed.append(76 + (dia % 4) * 0.5)
        nubdia.append(7 if dia % 3 else 6)
        nubnoche.append(5 if dia % 4 else 4)
        nubmed.append(6.2 + (dia % 3) * 0.2)
    return {
        "tmax": tmax, "tmin": tmin, "tmed": tmed, "rocio": rocio,
        "pmax": pmax, "pmin": pmin, "pmed": pmed,
        "lluvia": lluvia, "vel": vel, "velmax": velmax, "dir": dirv,
        "hummax": hummax, "hummin": hummin, "hummed": hummed,
        "nubdia": nubdia, "nubnoche": nubnoche, "nubmed": nubmed,
    }


class _Meteograma(QWidget):
    """Cinco paneles diarios con el eje de tiempo compartido."""

    def __init__(
        self,
        paleta: dict,
        series: dict[str, list[float]],
        paneles: tuple | None = None,
    ) -> None:
        super().__init__()
        self.p = paleta
        self.s = series
        self.paneles = paneles

    def _panel_viento(self, painter, x0, y0, ancho, alto) -> None:
        """Barras de velocidad media, punto del máximo y flechas de dirección.

        Las flechas van en una franja arriba del panel: dibujadas al pie las
        tapaban las barras y no se leían.
        """
        import math

        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QBrush, QColor, QPen

        franja = 16
        base = y0 + alto
        tope = y0 + franja
        alto_util = base - tope
        vel = self.s["vel"]
        velmax = self.s["velmax"]
        vmax = max(velmax) + 2
        paso = ancho / (len(vel) - 1)

        relleno = QColor(self.p["suave"])
        relleno.setAlpha(150)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(relleno))
        for i, valor in enumerate(vel):
            x = x0 + i * paso
            h = valor / vmax * alto_util
            painter.drawRect(QRectF(x - 3, base - h, 6, h))

        painter.setBrush(QBrush(QColor(self.p["acento"])))
        for i, valor in enumerate(velmax):
            x = x0 + i * paso
            painter.drawEllipse(QPointF(x, base - valor / vmax * alto_util), 1.9, 1.9)
        painter.setBrush(Qt.NoBrush)

        painter.setPen(QPen(QColor(self.p["suave"]), 1.1))
        for i, grados in enumerate(self.s["dir"]):
            x = x0 + i * paso
            centro = y0 + franja / 2
            rad = math.radians(grados)
            painter.drawLine(
                QPointF(x - 3.2 * math.sin(rad), centro + 3.2 * math.cos(rad)),
                QPointF(x + 3.2 * math.sin(rad), centro - 3.2 * math.cos(rad)),
            )

    def _panel(self, painter, x0, y0, ancho, alto, valores, color, *, relleno=False,
               minimo=None, maximo=None, barras=False, puntos=None, flechas=None,
               banda=None) -> None:
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF

        todos = list(valores) + (banda[0] + banda[1] if banda else [])
        vmin = minimo if minimo is not None else min(todos)
        vmax = maximo if maximo is not None else max(todos)
        if vmax == vmin:
            vmax = vmin + 1

        def y_de(valor):
            return y0 + alto - (valor - vmin) / (vmax - vmin) * alto

        # rejilla horizontal
        pintor_rejilla = QPen(QColor(self.p["borde"]))
        pintor_rejilla.setStyle(Qt.DashLine)
        painter.setPen(pintor_rejilla)
        for paso in range(4):
            y = y0 + alto * paso / 3
            painter.drawLine(QPointF(x0, y), QPointF(x0 + ancho, y))

        # banda (máx/mín)
        if banda:
            superior, inferior = banda
            poligono = QPolygonF()
            for i, valor in enumerate(superior):
                poligono.append(QPointF(x0 + i * ancho / (len(superior) - 1), y_de(valor)))
            for i in range(len(inferior) - 1, -1, -1):
                poligono.append(QPointF(x0 + i * ancho / (len(inferior) - 1), y_de(inferior[i])))
            relleno_banda = QColor(color)
            relleno_banda.setAlpha(38)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(relleno_banda))
            painter.drawPolygon(poligono)
            painter.setBrush(Qt.NoBrush)

        # barras
        if barras:
            ancho_barra = max(2.0, ancho / len(valores) * 0.6)
            painter.setPen(Qt.NoPen)
            relleno_barra = QColor(color)
            relleno_barra.setAlpha(170)
            painter.setBrush(QBrush(relleno_barra))
            for i, valor in enumerate(valores):
                x = x0 + i * ancho / (len(valores) - 1)
                painter.drawRect(QRectF(x - ancho_barra / 2, y_de(valor), ancho_barra, y0 + alto - y_de(valor)))
            painter.setBrush(Qt.NoBrush)

        # línea
        if not barras:
            lapiz = QPen(QColor(color), 1.6)
            painter.setPen(lapiz)
            for i in range(len(valores) - 1):
                painter.drawLine(
                    QPointF(x0 + i * ancho / (len(valores) - 1), y_de(valores[i])),
                    QPointF(x0 + (i + 1) * ancho / (len(valores) - 1), y_de(valores[i + 1])),
                )

        # puntos de máximo
        if puntos:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(color)))
            for i, valor in enumerate(puntos):
                x = x0 + i * ancho / (len(puntos) - 1)
                painter.drawEllipse(QPointF(x, y_de(valor)), 1.8, 1.8)
            painter.setBrush(Qt.NoBrush)

        # flechas de dirección
        if flechas:
            painter.setPen(QPen(QColor(self.p["tenue"]), 1))
            for i, grados in enumerate(flechas):
                x = x0 + i * ancho / (len(flechas) - 1)
                y = y0 + alto - 6
                import math

                rad = math.radians(grados)
                painter.drawLine(
                    QPointF(x - 3 * math.sin(rad), y + 3 * math.cos(rad)),
                    QPointF(x + 3 * math.sin(rad), y - 3 * math.cos(rad)),
                )

    def paintEvent(self, event) -> None:  # noqa: N802 - API de Qt
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QFont, QPainter, QPen

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.p["superficie"]))

        izq, der, arriba, abajo, hueco = 132, 16, 10, 26, 12
        paneles = self.paneles or (
            ("Temperatura (°C)", "tmed", self.p["acento"],
             {"banda": (self.s["tmax"], self.s["tmin"])}),
            ("Humedad (%)", "hummed", self.p["ok"],
             {"banda": (self.s["hummax"], self.s["hummin"]), "minimo": 40, "maximo": 100}),
            ("Presión NMM (hPa)", "pmed", self.p["naranja"],
             {"banda": (self.s["pmax"], self.s["pmin"])}),
            ("Viento (m/s) · dirección", "vel", self.p["suave"], {"viento": True}),
            ("Lluvia (mm)", "lluvia", self.p["acento"],
             {"barras": True, "minimo": 0, "maximo": max(self.s["lluvia"]) + 1}),
        )
        alto_panel = (self.height() - arriba - abajo - hueco * (len(paneles) - 1)) / len(paneles)
        fuente = QFont()
        fuente.setPixelSize(9)
        fuente.setWeight(QFont.Weight.DemiBold)

        for indice, (titulo, clave, color, opciones) in enumerate(paneles):
            y0 = arriba + indice * (alto_panel + hueco)
            painter.setPen(QPen(QColor(self.p["suave"])))
            painter.setFont(fuente)
            painter.drawText(8, int(y0 + alto_panel / 2), titulo)
            if opciones.get("viento"):
                self._panel_viento(
                    painter, izq, y0, self.width() - izq - der, alto_panel
                )
            else:
                self._panel(
                    painter, izq, y0, self.width() - izq - der, alto_panel,
                    self.s[clave], color, **opciones,
                )

        # eje de días compartido
        painter.setPen(QPen(QColor(self.p["tenue"])))
        for dia in range(1, 32, 5):
            x = izq + (dia - 1) * (self.width() - izq - der) / 30
            painter.drawText(QPointF(x - 4, self.height() - 8), str(dia))
        painter.drawText(QPointF(self.width() - 46, self.height() - 8), "día")
        painter.end()


#: Paneles de la variante B: dos fijos y uno conmutable.
PANELES_B = {
    "humedad": ("Humedad (%)", "hummed", "ok",
                {"banda": ("hummax", "hummin"), "minimo": 40, "maximo": 100}),
    "viento": ("Viento (m/s) · dirección", "vel", "suave", {"viento": True}),
    "nubosidad": ("Nubosidad (octavos)", "nubmed", "violeta",
                  {"banda": ("nubdia", "nubnoche"), "minimo": 0, "maximo": 8}),
    "lluvia": ("Lluvia (mm)", "lluvia", "acento",
               {"barras": True, "minimo": 0}),
}


def pantalla_summary_graficas_b(p: dict, variable: str = "viento") -> QWidget:
    """Meteograma del Resumen: dos paneles fijos y el tercero con selector."""
    pagina = QWidget()
    pagina.setObjectName("pagina")
    pagina.setStyleSheet(f"QWidget#pagina {{ background:{p['fondo']}; }}")
    v = QVBoxLayout(pagina)
    v.setContentsMargins(28, 20, 28, 20)
    v.setSpacing(12)

    fila = QHBoxLayout()
    titulos = QVBoxLayout()
    titulos.setSpacing(2)
    t = QLabel("Resumen Mensual SYNOP")
    t.setFont(ui(24, 800))
    t.setStyleSheet(f"color:{p['texto']};background:transparent;")
    sub = QLabel("Generación y visualización de resúmenes climáticos")
    sub.setFont(ui(13))
    sub.setStyleSheet(f"color:{p['suave']};background:transparent;")
    titulos.addWidget(t)
    titulos.addWidget(sub)
    fila.addLayout(titulos)
    fila.addStretch(1)
    for texto, activo in (("Historial", False), ("Tabla", False), ("Gráficas", True)):
        pill = QLabel(texto)
        pill.setFont(ui(11, 700))
        pill.setFixedHeight(30)
        pill.setStyleSheet(
            f"background:{p['acento_suave'] if activo else p['superficie']};"
            f"color:{p['acento'] if activo else p['suave']};"
            f"border:1px solid {p['acento'] if activo else p['borde']};"
            "border-radius:15px;padding:0 14px;"
        )
        fila.addWidget(pill)
    v.addLayout(fila)
    v.addWidget(_panel_carga(p))

    meta = QHBoxLayout()
    nombre = QLabel("Las Américas (78485) · Diciembre 2025")
    nombre.setFont(ui(15, 800))
    nombre.setStyleSheet(f"color:{p['texto']};background:transparent;")
    meta.addWidget(nombre)
    meta.addStretch(1)
    # selector de la tercera variable
    for clave, etiqueta in (
        ("humedad", "Humedad"), ("viento", "Viento"),
        ("nubosidad", "Nubosidad"), ("lluvia", "Lluvia"),
    ):
        activo = clave == variable
        pill = QLabel(etiqueta)
        pill.setFont(ui(10, 700))
        pill.setFixedHeight(26)
        pill.setStyleSheet(
            f"background:{p['acento_suave'] if activo else p['superficie']};"
            f"color:{p['acento'] if activo else p['suave']};"
            f"border:1px solid {p['acento'] if activo else p['borde']};"
            "border-radius:13px;padding:0 12px;"
        )
        meta.addWidget(pill)
    v.addLayout(meta)

    series = _series_resumen()
    # el espec del tercer panel resuelve los nombres de serie a listas
    titulo3, clave3, rol3, opciones3 = PANELES_B[variable]
    opciones3 = {
        k: (series[v] if isinstance(v, str) else v) for k, v in opciones3.items()
    } if "banda" not in opciones3 else {
        **{k: v for k, v in opciones3.items() if k != "banda"},
        "banda": tuple(series[n] for n in opciones3["banda"]),
    }
    paneles = (
        ("Temperatura (°C)", "tmed", p["acento"],
         {"banda": (series["tmax"], series["tmin"])}),
        ("Presión NMM (hPa)", "pmed", p["naranja"],
         {"banda": (series["pmax"], series["pmin"])}),
        (titulo3, clave3, p[rol3], opciones3),
    )

    tarjeta = QWidget()
    tarjeta.setObjectName("meteoC")
    tarjeta.setStyleSheet(
        f"QWidget#meteoC {{ background:{p['superficie']};"
        f" border:1px solid {p['borde']}; border-radius:10px; }}"
    )
    tv = QVBoxLayout(tarjeta)
    tv.setContentsMargins(8, 8, 8, 8)
    tv.addWidget(_Meteograma(p, series, paneles))
    v.addWidget(tarjeta, 1)

    pie = QLabel(
        "Dos paneles fijos (temperatura y presión) y el tercero según el selector · "
        "eje de días compartido"
    )
    pie.setFont(ui(10))
    pie.setStyleSheet(f"color:{p['tenue']};background:transparent;")
    v.addWidget(pie)
    return pagina


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for modulo in MODULOS:
        (SALIDA / modulo).mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    for nombre, paleta in PALETTES.items():
        w = pantalla_synop(paleta)
        w.resize(QSize(ANCHO, ALTO))
        w.show()
        app.processEvents()
        (SALIDA / "synop").mkdir(parents=True, exist_ok=True)
        destino = SALIDA / "synop" / f"mock-synop-{nombre}.png"
        w.grab().save(str(destino))
        print(f"  {destino}  ({destino.stat().st_size // 1024} KB)")
        w.close()

        for carpeta, clave, constructor in (
            ("cli", "cli3074", pantalla_cli3074),
            ("cli", "cli4074", pantalla_cli4074),
            ("cli", "cli5074", pantalla_cli5074),
            ("audit", "audit-estaciones", pantalla_audit_estaciones),
            ("audit", "audit-dias", pantalla_audit_dias),
            ("audit", "audit-sinoptico", pantalla_audit_sinoptico),
            ("audit", "audit-reporte", pantalla_audit_reporte),
            ("summary", "summary-tabla", pantalla_summary_tabla),
            ("summary", "summary-historial", pantalla_summary_historial),
            ("summary", "summary-graficas", pantalla_summary_graficas_b),
        ):
            w = constructor(paleta)
            w.resize(QSize(ANCHO, ALTO))
            w.show()
            app.processEvents()
            (SALIDA / carpeta).mkdir(parents=True, exist_ok=True)
            destino = SALIDA / carpeta / f"mock-{clave}-{nombre}.png"
            w.grab().save(str(destino))
            print(f"  {destino}  ({destino.stat().st_size // 1024} KB)")
            w.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
