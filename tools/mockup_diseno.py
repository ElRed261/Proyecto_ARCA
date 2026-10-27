"""Mockups Qt del rediseño (Opción D) — Sinóptico, cuatro variantes, dos temas.

Script desechable de decisión: no forma parte de la aplicación. Dibuja las
variantes con la MISMA distribución de tabla del módulo Synop (8 horas x grupos
en el orden de la clave OMM) y las guarda como PNG para elegir por ojo.

    .venv-gil/bin/python tools/mockup_diseno.py --salida Migración/evidencias/DISENO_NUEVO
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

ANCHO, ALTO = 1366, 768

TEMAS = {
    "claro": {
        "fondo": "#f8fafc",
        "superficie": "#ffffff",
        "borde": "#e2e8f0",
        "texto": "#0f172a",
        "suave": "#64748b",
        "tenue": "#94a3b8",
        "acento": "#0e7490",
        "acento_suave": "#e0f2fe",
        "error": "#b91c1c",
        "error_suave": "#fee2e2",
        "ok": "#15803d",
        "hora_activa": "#ecfeff",
        "fantasma": "#94a3b8",
    },
    "oscuro": {
        "fondo": "#0b1220",
        "superficie": "#111c2e",
        "borde": "#243044",
        "texto": "#e2e8f0",
        "suave": "#94a3b8",
        "tenue": "#64748b",
        "acento": "#22d3ee",
        "acento_suave": "#123241",
        "error": "#f87171",
        "error_suave": "#3b1416",
        "ok": "#4ade80",
        "hora_activa": "#0e2433",
        "fantasma": "#64748b",
    },
}

HORAS = ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z")

# Subconjunto de la clave que se ve en el libro: las columnas que un observador
# mira de reojo mientras tipea. El resto se alcanza con scroll horizontal.
COLS = (
    ("Ts", "°C"),
    ("Th", "°C"),
    ("Pres", "hPa"),
    ("P3", "hPa"),
    ("P24", "hPa"),
    ("Dir", "°"),
    ("Vel", ""),
    ("Vis", ""),
    ("LL", "mm"),
    ("Nddff", ""),
    ("7ww", ""),
)

# 8 horas x 11 columnas. "" = vacío (se renderiza como raya, nunca inventado).
DATOS = {
    "06Z": ["23.4", "19.8", "1013.2", "0.4", "-0.6", "090", "12", "18", "0.0", "82412", "80052"],
    "09Z": ["26.1", "20.4", "1012.6", "0.8", "0.2", "110", "16", "20", "0.0", "82515", "80252"],
    "12Z": ["29.8", "22.1", "1011.4", "1.2", "1.0", "120", "20", "22", "0.0", "82618", "80352"],
    "15Z": ["31.2", "23.5", "1010.2", "", "", "130", "24", "24", "0.0", "82721", "80652"],
    "18Z": ["29.5", "23.1", "1011.0", "0.7", "0.4", "140", "18", "16", "0.0", "82822", "80252"],
    "21Z": ["26.4", "22.4", "1012.8", "1.1", "0.8", "150", "10", "12", "0.0", "82506", "80052"],
    "00Z": ["24.2", "21.6", "1014.0", "0.9", "0.6", "080", "6", "10", "0.0", "82403", "80151"],
    "03Z": ["23.0", "20.9", "1013.6", "", "", "070", "4", "8", "0.0", "82401", "80051"],
}

COMPLETO = {"06Z": 21, "09Z": 21, "12Z": 18, "15Z": 14, "18Z": 20, "21Z": 9, "00Z": 0, "03Z": 0}
TOTAL_HORA = 21
HORA_ACTIVA = "12Z"


# ---------------------------------------------------------------- helpers


def mono(point: int = 12) -> QFont:
    for familia in ("JetBrains Mono", "IBM Plex Mono", "DejaVu Sans Mono", "monospace"):
        if familia in QFontDatabase.families():
            f = QFont(familia)
            f.setPointSize(point)
            f.setStyleHint(QFont.Monospace)
            return f
    return QFont("monospace")


def ui(point: int = 9, peso: int = 400) -> QFont:
    f = QFont()
    f.setPointSize(point)
    f.setWeight(QFont.Weight(peso))
    return f


def etiqueta(texto: str, color: str, fuente: QFont, *, bg: str | None = None) -> QLabel:
    lab = QLabel(texto)
    lab.setFont(fuente)
    lab.setStyleSheet(
        f"color:{color};" + (f"background:{bg};" if bg else "") + "background-color:transparent;"
        if not bg
        else f"color:{color};background:{bg};"
    )
    return lab


def _riel(t: dict, *, segmentado: bool = False) -> QWidget:
    """Riel de 8 horas: navega Y muestra completitud. Un solo control."""
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(1 if segmentado else 3)
    for hora in HORAS:
        activa = hora == HORA_ACTIVA
        completa = COMPLETO[hora] == TOTAL_HORA
        if segmentado:
            fondo = t["acento"] if activa else t["superficie"]
            color = ("#04222b" if t is TEMAS["oscuro"] else "#ffffff") if activa else t["suave"]
            borde = "none" if activa else f"1px solid {t['borde']}"
            radio = "0px"
            if hora == HORAS[0]:
                radio = "4px 0 0 4px"
            elif hora == HORAS[-1]:
                radio = "0 4px 4px 0"
        else:
            fondo = t["acento_suave"] if activa else "transparent"
            color = t["acento"] if activa else (t["texto"] if completa else t["tenue"])
            borde = f"1px solid {t['acento'] if activa else 'transparent'}"
            radio = "3px"
        celda_riel = QLabel(hora)
        celda_riel.setFont(mono(9))
        celda_riel.setFixedSize(42, 24)
        celda_riel.setAlignment(Qt.AlignCenter)
        celda_riel.setStyleSheet(
            f"color:{color};background:{fondo};border:{borde};border-radius:{radio};"
        )
        lay.addWidget(celda_riel)
        if not segmentado:
            punto = QLabel("●" if completa else "○")
            punto.setFont(ui(6))
            punto.setStyleSheet(f"color:{t['ok'] if completa else t['borde']};background:transparent;")
            lay.addWidget(punto)
    return w


def barra(padre: QWidget, t: dict, texto: str, variante: str = "riel") -> QWidget:
    """Barra de contexto: estación, día, hora. La misma en Sinóptico y en CLI."""
    w = QWidget(padre)
    w.setStyleSheet(f"background:{t['superficie']};border-bottom:1px solid {t['borde']};")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(14, 7, 14, 7)
    lay.setSpacing(10)
    lay.addWidget(etiqueta(texto, t["texto"], ui(10, 800)))

    est = QLabel("78486 · Central  ▾")
    est.setFont(ui(9))
    est.setStyleSheet(
        f"color:{t['texto']};background:{t['fondo']};border:1px solid {t['borde']};"
        "border-radius:4px;padding:5px 9px;"
    )
    lay.addWidget(est)

    # día: stepper inline (1 tecla) en lugar de un modal de 4 pasos
    dia = QWidget()
    dl = QHBoxLayout(dia)
    dl.setContentsMargins(0, 0, 0, 0)
    dl.setSpacing(0)
    for txt, izq in (("‹", True), ("08/12/2025", False), ("›", True)):
        b = QLabel(txt)
        b.setFont(ui(9) if not izq else mono(11))
        b.setAlignment(Qt.AlignCenter)
        b.setFixedHeight(26)
        b.setFixedWidth(22 if izq else 88)
        b.setStyleSheet(
            f"color:{t['suave'] if izq else t['texto']};background:{t['fondo']};"
            f"border:1px solid {t['borde']};"
            + ("border-top-left-radius:4px;border-bottom-left-radius:4px;" if izq and txt == "‹" else "")
            + ("border-top-right-radius:4px;border-bottom-right-radius:4px;" if izq and txt == "›" else "")
            + ("border-left:none;border-right:none;" if not izq else "")
        )
        dl.addWidget(b)
    lay.addWidget(dia)

    if variante == "riel":
        lay.addWidget(_riel(t))
        lay.addWidget(etiqueta("18/21", t["tenue"], mono(9)))
    elif variante == "segmentado":
        lay.addWidget(_riel(t, segmentado=True))
    elif variante == "solo_hora":
        lay.addWidget(etiqueta("Hora 12Z", t["acento"], mono(11)))
        lay.addWidget(etiqueta("18 de 21 grupos", t["tenue"], ui(8)))

    lay.addStretch(1)
    if variante == "siguiente":
        sig = QLabel("Siguiente pendiente →  15Z")
        sig.setFont(ui(9, 600))
        sig.setStyleSheet(
            f"color:{t['acento']};background:{t['acento_suave']};"
            "border-radius:4px;padding:6px 12px;"
        )
        lay.addWidget(sig)
    lay.addWidget(etiqueta("Observador: A. Pérez", t["suave"], ui(8)))
    return w


def celda(
    texto: str, t: dict, *, ancho: int = 0, fuerte: bool = False, vacio: bool = False,
    fondo: str | None = None, alinear_derecha: bool = True,
) -> QLabel:
    lab = QLabel("—" if vacio else texto)
    lab.setFont(mono(11))
    color = t["tenue"] if vacio else (t["texto"] if fuerte else t["suave"])
    lab.setStyleSheet(
        f"color:{color};background:{fondo or 'transparent'};"
        f"border-bottom:1px solid {t['borde']};padding:5px 8px;"
    )
    lab.setAlignment((Qt.AlignRight if alinear_derecha else Qt.AlignLeft) | Qt.AlignVCenter)
    if ancho:
        lab.setFixedWidth(ancho)
    return lab


def cabecera_libro(t: dict) -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background:{t['superficie']};")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(8, 6, 8, 6)
    lay.setSpacing(0)
    lab_hora = etiqueta("HORA", t["suave"], ui(8, 600))
    lab_hora.setFixedWidth(56)
    lab_hora.setStyleSheet(f"color:{t['suave']};background:transparent;")
    lay.addWidget(lab_hora)
    for nombre, unidad in COLS:
        celda_txt = nombre + (f" {unidad}" if unidad else "")
        lab = QLabel(celda_txt)
        lab.setFont(ui(8, 600))
        lab.setStyleSheet(
            f"color:{t['suave']};background:transparent;border-bottom:1px solid {t['borde']};"
            "padding:4px 8px;"
        )
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lab.setFixedWidth(ANCHO_COL)
        lay.addWidget(lab)
    return w


ANCHO_COL = 84
ANCHO_HORA = 56


def libro(t: dict, *, editable: bool = False, con_errores: bool = True) -> QWidget:
    """La grilla del módulo Synop: 8 filas de hora x columnas de grupo."""
    w = QWidget()
    w.setStyleSheet(f"background:{t['superficie']};")
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    outer.addWidget(cabecera_libro(t))

    for hora in HORAS:
        activa = hora == HORA_ACTIVA
        fondo = t["hora_activa"] if activa else "transparent"
        fila = QWidget()
        fila.setStyleSheet(f"background:{fondo};")
        lay = QHBoxLayout(fila)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(0)

        etq = QLabel(hora)
        etq.setFont(mono(11))
        etq.setFixedWidth(ANCHO_HORA)
        etq.setStyleSheet(
            f"color:{t['acento'] if activa else t['texto']};background:transparent;"
            f"font-weight:{600 if activa else 400};padding:2px 0;"
            "border-bottom:1px solid " + t["borde"] + ";"
        )
        lay.addWidget(etq)

        valores = DATOS[hora]
        for idx, (nombre, _u) in enumerate(COLS):
            valor = valores[idx]
            vacio = valor == ""
            hay_error = con_errores and hora == "15Z" and nombre == "P3"
            texto = valor if not hay_error else valor or "10,2"
            lab = celda(
                texto, t,
                ancho=ANCHO_COL,
                fuerte=activa,
                vacio=vacio and not hay_error,
                fondo=t["error_suave"] if hay_error else None,
            )
            if editable:
                lab.setStyleSheet(lab.styleSheet() + "border:1px solid " + t["borde"] + ";")
            lay.addWidget(lab)

        # medidor de completitud al pie de la fila (2 px)
        lay.addSpacing(8)
        medidor = QProgressBar()
        medidor.setFixedHeight(2)
        medidor.setMaximumWidth(120)
        medidor.setRange(0, TOTAL_HORA)
        medidor.setValue(COMPLETO[hora])
        medidor.setTextVisible(False)
        medidor.setStyleSheet(
            f"QProgressBar{{background:{t['borde']};border:none;}}"
            f"QProgressBar::chunk{{background:{t['ok'] if COMPLETO[hora] == TOTAL_HORA else t['acento']};}}"
        )
        lay.addWidget(medidor, 0, Qt.AlignVCenter)
        pct = etiqueta(f"{COMPLETO[hora]}/{TOTAL_HORA}", t["tenue"], mono(9))
        pct.setFixedWidth(40)
        lay.addWidget(pct)
        lay.addStretch(1)
        outer.addWidget(fila)
    outer.addStretch(1)
    return w


FAMILIAS = (
    ("Temperatura", (("Ts", "Ts (°C)"), ("Th", "Th (°C)"), ("T máx", "T máx"), ("T mín", "T mín"))),
    ("Presión y tendencia", (("Pres. estación", "Pres. estación (hPa)"), ("P3", "P3 (hPa)"), ("P24", "P24 (hPa)"))),
    ("Viento y visibilidad", (("Dir", "Viento dir (°)"), ("Vel", "Viento vel"), ("Vis", "Visibilidad"))),
    ("Cielo y nubosidad", (("Nddff", "N dd ff"), ("0CS", "0CS DL DM DH"), ("8Ns", "8NsChs"))),
    ("Tiempo presente", (("YYGG", "YYGG Iw"), ("Ir iX H VV", "Ir iX H VV"), ("7ww", "7 ww W1W2"))),
    ("Lluvia y fenómenos", (("LL", "LL (mm)"), ("5 EEE", "5 EEEjE"), ("6RRR", "6RRRtr"))),
)


def campo(t: dict, nombre: str, valor: str, *, error: str | None = None, derivado: str | None = None) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    lab = etiqueta(nombre, t["suave"], ui(8, 600))
    lay.addWidget(lab)
    fila = QHBoxLayout()
    fila.setContentsMargins(0, 0, 0, 0)
    fila.setSpacing(6)
    caja = QLabel(valor or "—")
    caja.setFont(mono(12))
    caja.setFixedHeight(32)
    borde = t["error"] if error else t["borde"]
    caja.setStyleSheet(
        f"background:{t['superficie']};color:{t['texto'] if valor else t['tenue']};"
        f"border:1px solid {borde};border-radius:4px;padding:0 8px;"
    )
    caja.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    fila.addWidget(caja, 1)
    if derivado:
        fant = etiqueta(derivado, t["fantasma"], mono(8))
        fant.setMinimumWidth(58)
        fila.addWidget(fant)
    lay.addLayout(fila)
    if error:
        lay.addWidget(etiqueta(error, t["error"], ui(8)))
    return w


def editor(t: dict, hora: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background:{t['fondo']};")
    outer = QVBoxLayout(w)
    outer.setContentsMargins(14, 10, 14, 10)
    outer.setSpacing(8)

    cab = QHBoxLayout()
    cab.addWidget(etiqueta(f"Hora {hora}", t["texto"], ui(12, 800)))
    pct = int(COMPLETO[hora] / TOTAL_HORA * 100)
    cab.addWidget(etiqueta(f"{COMPLETO[hora]} de {TOTAL_HORA} grupos · {pct}%", t["suave"], ui(9)))
    cab.addStretch(1)
    cab.addWidget(etiqueta("Ts 29.8  ·  Pres 1011.4  ·  HR 74.2", t["fantasma"], mono(9)))
    outer.addLayout(cab)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
    interno = QWidget()
    interno.setStyleSheet("background:transparent;")
    grid = QGridLayout(interno)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(6)

    derivados = {
        "Ts": "HR 74.2",
        "Th": "rocío 24.9",
        "Pres. estación": "NMM 1011.4",
    }
    fila_grid = 0
    for titulo, campos in FAMILIAS:
        enc = QLabel(titulo.upper())
        enc.setFont(ui(8, 600))
        enc.setStyleSheet(
            f"color:{t['acento']};background:transparent;letter-spacing:1px;"
            f"border-bottom:1px solid {t['borde']};padding-bottom:3px;"
        )
        grid.addWidget(enc, fila_grid, 0, 1, 2)
        fila_grid += 1
        for i, (clave, etq) in enumerate(campos):
            valor = ""
            if clave == "Ts":
                valor = "29.8"
            elif clave == "Th":
                valor = "22.1"
            elif clave == "Pres. estación":
                valor = "1011.4"
            elif clave == "P3":
                valor = "10,2"
            elif clave == "Nddff":
                valor = "82618"
            error = "P3: 4 de 5 dígitos" if clave == "P3" else None
            grid.addWidget(
                campo(t, etq, valor, error=error, derivado=derivados.get(clave)),
                fila_grid + i // 2,
                i % 2,
            )
        fila_grid += (len(campos) + 1) // 2

    scroll.setWidget(interno)
    outer.addWidget(scroll, 1)
    return w


def barra_guardado(t: dict, *, mensaje: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background:{t['superficie']};border-top:1px solid {t['borde']};")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(16, 8, 16, 8)
    lay.setSpacing(12)
    lay.addWidget(etiqueta(mensaje, t["suave"], ui(9)))
    lay.addStretch(1)
    cancelar = QPushButton("Descartar")
    cancelar.setFont(ui(9))
    cancelar.setStyleSheet(
        f"background:transparent;color:{t['suave']};border:1px solid {t['borde']};"
        "border-radius:4px;padding:6px 14px;"
    )
    lay.addWidget(cancelar)
    guardar = QPushButton("Guardar día  ·  Ctrl+S")
    guardar.setFont(ui(9, 600))
    guardar.setStyleSheet(
        f"background:{t['acento']};color:{'#04222b' if t is TEMAS['oscuro'] else '#ffffff'};"
        "border:none;border-radius:4px;padding:7px 18px;"
    )
    lay.addWidget(guardar)
    return w


def raiz(t: dict, titulo: str, cuerpo: QWidget, *, mensaje: str, variante: str = "riel") -> QWidget:
    w = QWidget()
    w.setStyleSheet(f"background:{t['fondo']};")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addWidget(barra(w, t, titulo, variante))
    lay.addWidget(cuerpo, 1)
    lay.addWidget(barra_guardado(t, mensaje=mensaje))
    return w


# ---------------------------------------------------------------- variantes


def d1_matriz_inspector(t: dict) -> QWidget:
    cuerpo = QWidget()
    lay = QHBoxLayout(cuerpo)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    izq = QWidget()
    l1 = QVBoxLayout(izq)
    l1.setContentsMargins(0, 0, 0, 0)
    l1.addWidget(etiqueta("  Libro del día — edición en celda", t["suave"], ui(8, 600)))
    l1.addWidget(libro(t, editable=True))
    lay.addWidget(izq, 72)

    der = QWidget()
    der.setStyleSheet(f"background:{t['superficie']};border-left:1px solid {t['borde']};")
    l2 = QVBoxLayout(der)
    l2.setContentsMargins(16, 12, 16, 12)
    l2.setSpacing(10)
    l2.addWidget(etiqueta("INSPECTOR · P3 (hPa)", t["acento"], ui(8, 600)))
    l2.addWidget(etiqueta("15Z · Presión a 3 horas", t["texto"], ui(11, 600)))
    for k, v in (
        ("Valor", "10,2"),
        ("Estructura", "4 de 5 dígitos"),
        ("Derivado", "NMM 1012.6"),
        ("Regla", "si < 1000 → +1000"),
        ("Estado", "error de longitud"),
    ):
        fila = QHBoxLayout()
        fila.addWidget(etiqueta(k, t["suave"], ui(9)))
        fila.addStretch(1)
        color = t["error"] if k == "Estado" else t["texto"]
        fila.addWidget(etiqueta(v, color, mono(10)))
        l2.addLayout(fila)
    l2.addStretch(1)
    l2.addWidget(etiqueta("Tab: aceptar y bajar · Esc: volver al libro", t["tenue"], ui(8)))
    lay.addWidget(der, 28)
    return raiz(t, "Sinóptico", cuerpo, mensaje="15Z tiene 1 problema · no se puede guardar")


def d2_libro_hoja(t: dict, variante: str = "riel") -> QWidget:
    cuerpo = QWidget()
    lay = QHBoxLayout(cuerpo)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    izq = QWidget()
    l1 = QVBoxLayout(izq)
    l1.setContentsMargins(0, 0, 0, 0)
    l1.addWidget(etiqueta("  Libro del día — clic en la fila para editar", t["suave"], ui(8, 600)))
    l1.addWidget(libro(t))
    lay.addWidget(izq, 62)
    der = QWidget()
    der.setStyleSheet(f"border-left:1px solid {t['borde']};")
    l2 = QVBoxLayout(der)
    l2.setContentsMargins(0, 0, 0, 0)
    l2.addWidget(editor(t, HORA_ACTIVA))
    lay.addWidget(der, 38)
    return raiz(t, "Sinóptico", cuerpo, mensaje="12Z · 18 de 21 grupos · sin errores", variante=variante)


def d3_turno(t: dict) -> QWidget:
    cuerpo = QWidget()
    lay = QHBoxLayout(cuerpo)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    tira = QWidget()
    tira.setStyleSheet(f"background:{t['superficie']};")
    tira.setFixedWidth(132)
    l1 = QVBoxLayout(tira)
    l1.setContentsMargins(8, 12, 8, 12)
    l1.setSpacing(6)
    for hora in HORAS:
        fila = QWidget()
        activa = hora == HORA_ACTIVA
        fila.setStyleSheet(
            f"background:{t['acento_suave'] if activa else 'transparent'};border-radius:4px;"
        )
        fl = QVBoxLayout(fila)
        fl.setContentsMargins(8, 6, 8, 6)
        fl.setSpacing(4)
        fl.addWidget(
            etiqueta(hora, t["acento"] if activa else t["texto"], mono(12))
        )
        med = QProgressBar()
        med.setFixedHeight(3)
        med.setRange(0, TOTAL_HORA)
        med.setValue(COMPLETO[hora])
        med.setTextVisible(False)
        med.setStyleSheet(
            f"QProgressBar{{background:{t['borde']};border:none;border-radius:1px;}}"
            f"QProgressBar::chunk{{background:{t['ok'] if COMPLETO[hora] == TOTAL_HORA else t['acento']};}}"
        )
        fl.addWidget(med)
        l1.addWidget(fila)
    l1.addStretch(1)
    lay.addWidget(tira)

    der = QWidget()
    l2 = QVBoxLayout(der)
    l2.setContentsMargins(0, 0, 0, 0)
    l2.addWidget(editor(t, HORA_ACTIVA))
    lay.addWidget(der, 1)
    return raiz(t, "Sinóptico · turno", cuerpo, mensaje="12Z · 18 de 21 · Tab para el siguiente grupo")


def d4_revision(t: dict) -> QWidget:
    cuerpo = QWidget()
    lay = QHBoxLayout(cuerpo)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    izq = QWidget()
    izq.setStyleSheet(f"background:{t['superficie']};")
    l1 = QVBoxLayout(izq)
    l1.setContentsMargins(0, 0, 0, 0)
    l1.setSpacing(0)
    cab = QWidget()
    cl = QHBoxLayout(cab)
    cl.setContentsMargins(16, 8, 16, 8)
    cl.addWidget(etiqueta("HORA", t["suave"], ui(8, 600)))
    for nombre, ancho in (("CAMPO", 0), ("PROBLEMA", 0), ("VALOR", 80)):
        lab = etiqueta(nombre, t["suave"], ui(8, 600))
        if ancho:
            lab.setFixedWidth(ancho)
        cl.addWidget(lab, 1 if not ancho else 0)
    l1.addWidget(cab)
    problemas = (
        ("15Z", "P3 (hPa)", "4 de 5 dígitos · falta la decena", "10,2"),
        ("15Z", "P24 (hPa)", "vacío y es obligatorio en 15Z", "—"),
        ("21Z", "N dd ff", "dd=50 no es múltiplo de 10", "82506"),
        ("00Z", "7wwW1W2", "grupo incompleto para la hora", "80151"),
        ("12Z", "0CS DL DM DH", "DL no corresponde con 8Ns", "82618"),
    )
    for hora, campo_, problema, valor in problemas:
        fila = QWidget()
        fila.setStyleSheet(f"background:{t['error_suave']};")
        fl = QHBoxLayout(fila)
        fl.setContentsMargins(16, 8, 16, 8)
        fl.addWidget(etiqueta(hora, t["error"], mono(10)))
        lab = etiqueta(campo_, t["texto"], ui(9, 600))
        fl.addWidget(lab, 1)
        lab2 = etiqueta(problema, t["suave"], ui(9))
        fl.addWidget(lab2, 1)
        lab3 = etiqueta(valor, t["texto"], mono(10))
        lab3.setFixedWidth(80)
        lab3.setAlignment(Qt.AlignRight)
        fl.addWidget(lab3)
        l1.addWidget(fila)
    l1.addStretch(1)
    lay.addWidget(izq, 58)

    der = QWidget()
    der.setStyleSheet(f"border-left:1px solid {t['borde']};")
    l2 = QVBoxLayout(der)
    l2.setContentsMargins(0, 0, 0, 0)
    l2.addWidget(editor(t, "15Z"))
    lay.addWidget(der, 42)
    return raiz(t, "Sinóptico · revisar antes de guardar", cuerpo, mensaje="5 problemas en el día")


def cli_3074(t: dict) -> QWidget:
    """Los CLI conservan su grilla única: 24 horas x columnas + inspector."""
    cuerpo = QWidget()
    lay = QHBoxLayout(cuerpo)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    izq = QWidget()
    izq.setStyleSheet(f"background:{t['superficie']};")
    l1 = QVBoxLayout(izq)
    l1.setContentsMargins(0, 0, 0, 0)
    l1.setSpacing(0)
    cab = QWidget()
    cl = QHBoxLayout(cab)
    cl.setContentsMargins(12, 6, 12, 6)
    cl.setSpacing(0)
    h = etiqueta("H", t["suave"], ui(8, 600))
    h.setFixedWidth(40)
    cl.addWidget(h)
    for nombre in ("Ts", "Th", "Pres", "P3", "P24", "Dir", "Vel", "Vis", "LL", "N", "ww", "W1", "W2"):
        lab = QLabel(nombre)
        lab.setFont(ui(8, 600))
        lab.setStyleSheet(f"color:{t['suave']};background:transparent;")
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lab.setFixedWidth(72)
        cl.addWidget(lab)
    l1.addWidget(cab)
    for i in range(1, 25):
        hora = f"{i:02d}"
        activa = i == 13
        fila = QWidget()
        fila.setStyleSheet(f"background:{t['hora_activa'] if activa else 'transparent'};")
        fl = QHBoxLayout(fila)
        fl.setContentsMargins(12, 0, 12, 0)
        fl.setSpacing(0)
        e = QLabel(hora)
        e.setFont(mono(10))
        e.setFixedWidth(40)
        e.setStyleSheet(
            f"color:{t['acento'] if activa else t['suave']};background:transparent;"
            f"border-bottom:1px solid {t['borde']};"
        )
        fl.addWidget(e)
        for c in range(13):
            texto = "—" if (i > 18 or c in (3, 12)) and not activa else Texto_fake(i, c)
            lab = celda(texto, t, ancho=72, fuerte=activa, vacio=texto == "—")
            fl.addWidget(lab)
        l1.addWidget(fila)
    l1.addStretch(1)
    lay.addWidget(izq, 74)

    der = QWidget()
    der.setStyleSheet(f"background:{t['fondo']};border-left:1px solid {t['borde']};")
    l2 = QVBoxLayout(der)
    l2.setContentsMargins(16, 14, 16, 14)
    l2.setSpacing(10)
    l2.addWidget(etiqueta("GRUPO DECODIFICADO", t["acento"], ui(8, 600)))
    l2.addWidget(etiqueta("13 · 12Z", t["texto"], ui(12, 800)))
    for grupo, valor, lectura in (
        ("N dd ff", "82618", "N=4/8 · dd=260° · ff=18"),
        ("7 ww W1W2", "80352", "ww=03 · W1=5 · W2=2"),
        ("Ir iX H VV", "82412", "Ir=8 · H=2 · VV=12"),
    ):
        l2.addWidget(etiqueta(grupo, t["suave"], ui(8, 600)))
        fila = QHBoxLayout()
        fila.addWidget(etiqueta(valor, t["texto"], mono(12)))
        fila.addStretch(1)
        fila.addWidget(etiqueta(lectura, t["fantasma"], mono(8)))
        l2.addLayout(fila)
    l2.addWidget(etiqueta("10 carriles de fenómenos", t["suave"], ui(8, 600)))
    chips = QHBoxLayout()
    for nombre in ("lluvia", "niebla", "tormenta", "granizo"):
        chip = etiqueta(nombre, t["acento"], ui(8))
        chip.setStyleSheet(
            f"color:{t['acento']};background:{t['acento_suave']};"
            "border-radius:9px;padding:3px 8px;"
        )
        chips.addWidget(chip)
    chips.addStretch(1)
    l2.addLayout(chips)
    l2.addStretch(1)
    lay.addWidget(der, 26)
    return raiz(t, "CLI 3074", cuerpo, mensaje="24 horas · 13 columnas · autoguardado 700 ms")


def Texto_fake(fila: int, col: int) -> str:  # noqa: N802 - nombre de tabla de prueba
    base = [
        ["23.4", "19.8", "1013.2", "0.4", "-0.6", "090", "12", "18", "0.0", "4", "05", "5", "2"],
        ["26.1", "20.4", "1012.6", "0.8", "0.2", "110", "16", "20", "0.0", "4", "02", "5", "2"],
        ["29.8", "22.1", "1011.4", "1.2", "1.0", "120", "20", "22", "0.0", "6", "03", "5", "2"],
    ]
    return base[fila % 3][col]


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="Migración/evidencias/DISENO_NUEVO")
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    variantes = (
        ("D1", d1_matriz_inspector),
        ("D2", d2_libro_hoja),
        ("D3", d3_turno),
        ("D4", d4_revision),
    )
    hechos = []
    for nombre_tema, t in TEMAS.items():
        for clave, constructor in variantes:
            w = constructor(t)
            w.resize(ANCHO, ALTO)
            w.show()
            app.processEvents()
            destino = salida / f"{clave.lower()}-{nombre_tema}.png"
            w.grab().save(str(destino))
            hechos.append(destino)
            w.close()
        # los CLI conservan la grilla única: se muestran en D2 (pantalla real)
        for nav in ("riel", "segmentado", "solo_hora", "siguiente"):
            w = d2_libro_hoja(t, variante=nav)
            w.resize(ANCHO, ALTO)
            w.show()
            app.processEvents()
            destino = salida / f"nav-{nav}-{nombre_tema}.png"
            w.grab().save(str(destino))
            hechos.append(destino)
            w.close()
        w = cli_3074(t)
        w.resize(ANCHO, ALTO)
        w.show()
        app.processEvents()
        destino = salida / f"cli3074-{nombre_tema}.png"
        w.grab().save(str(destino))
        hechos.append(destino)
        w.close()

    for p in hechos:
        print(f"{p}  ({p.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
