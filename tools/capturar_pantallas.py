"""Capturas de las pantallas REALES de OMS, en los dos temas.

No son mockups: construye `SynopticPage` y las tres vistas CLI de verdad contra
una base temporal, así la organización de los controles es idéntica a la del
programa por construcción (regla del dueño: «exactamente el mismo formato»).

    QT_QPA_PLATFORM=offscreen .venv-gil/bin/python tools/capturar_pantallas.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QDate  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from oms_core.db import migrations  # noqa: E402
from oms_core.db.connection import connect  # noqa: E402
from oms_ui import theme  # noqa: E402
from oms_ui.pages.cli3074 import Cli3074View  # noqa: E402
from oms_ui.pages.cli4074 import Cli4074View  # noqa: E402
from oms_ui.pages.cli5074 import Cli5074View  # noqa: E402
from oms_ui.pages.synoptic import SynopticPage  # noqa: E402

ANCHO, ALTO = 1366, 768
ESTACION = "78485"
FECHA = "2025-12-08"
SALIDA = Path("Migración/evidencias/DISENO_NUEVO")

#: Datos de ejemplo por hora, en el orden real de los campos del Sinóptico.
MUESTRA = {
    "06Z": {"ts": "23.4", "th": "19.8", "pres_est": "1013.2", "p3": "0.4",
            "p24": "-0.6", "viento_dir": "090", "viento_vel": "12",
            "visibilidad": "18", "ll": "0.0", "meteo_4_1": "82412",
            "meteo_4_6": "80052"},
    "09Z": {"ts": "26.1", "th": "20.4", "pres_est": "1012.6", "p3": "0.8",
            "p24": "0.2", "viento_dir": "110", "viento_vel": "16",
            "visibilidad": "20", "ll": "0.0", "meteo_4_1": "82515",
            "meteo_4_6": "80252"},
    "12Z": {"ts": "29.8", "th": "22.1", "pres_est": "1011.4", "p3": "1.2",
            "p24": "1.0", "viento_dir": "120", "viento_vel": "20",
            "visibilidad": "22", "ll": "0.0", "meteo_4_1": "82618",
            "meteo_4_6": "80352"},
    "15Z": {"ts": "31.2", "th": "23.5", "pres_est": "1010.2", "viento_dir": "130",
            "viento_vel": "24", "visibilidad": "24", "ll": "0.0",
            "meteo_4_1": "82721", "meteo_4_6": "80652"},
}


def _capturar_estados(app: QApplication, nombre_tema: str) -> None:
    """Panel de estados de los controles (fase 1 del sistema de diseño)."""
    from PySide6.QtGui import QStandardItem, QStandardItemModel
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QTableView,
        QVBoxLayout,
        QWidget,
    )

    w = QWidget()
    w.resize(720, 340)
    lay = QVBoxLayout(w)
    lay.setSpacing(10)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.addWidget(QLabel("Estado de controles — sistema de diseño OMS"))
    fila = QHBoxLayout()
    fila.addWidget(QLineEdit("1013.2"))
    bloqueado = QLineEdit("bloqueado")
    bloqueado.setEnabled(False)
    fila.addWidget(bloqueado)
    fila.addWidget(QPushButton("Guardar día"))
    primario = QPushButton("Primario")
    primario.setProperty("primary", True)
    primario.setFocus()
    fila.addWidget(primario)
    lay.addLayout(fila)
    fila2 = QHBoxLayout()
    combo = QComboBox()
    combo.addItems(["78486 · Central"])
    fila2.addWidget(combo)
    combo_off = QComboBox()
    combo_off.addItems(["deshabilitado"])
    combo_off.setEnabled(False)
    fila2.addWidget(combo_off)
    etiqueta_off = QLabel("Etiqueta deshabilitada")
    etiqueta_off.setEnabled(False)
    fila2.addWidget(etiqueta_off)
    lay.addLayout(fila2)
    tabla = QTableView()
    modelo = QStandardItemModel(2, 3)
    for r, valores in enumerate((("06Z", "23.4", "1013.2"), ("09Z", "26.1", "1012.6"))):
        for c, valor in enumerate(valores):
            modelo.setItem(r, c, QStandardItem(valor))
    tabla.setModel(modelo)
    lay.addWidget(tabla)
    _capturar(w, SALIDA / f"fase1-estados-{nombre_tema}.png", app)


def _db_temporal() -> tuple[object, Path]:
    carpeta = Path(tempfile.mkdtemp(prefix="oms-capturas-"))
    conn = connect(carpeta / "capturas.db")
    migrations.migrate(conn)
    return conn, carpeta


def _capturar(widget, destino: Path, app: QApplication) -> None:
    widget.resize(ANCHO, ALTO)
    widget.show()
    app.processEvents()
    app.processEvents()
    widget.grab().save(str(destino))
    widget.close()
    print(f"  {destino.name}  ({destino.stat().st_size // 1024} KB)")


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    conn, carpeta = _db_temporal()

    for nombre_tema in theme.THEMES:
        theme.apply_theme(app, nombre_tema)
        print(f"[{nombre_tema}]")
        _capturar_estados(app, nombre_tema)

        pagina = SynopticPage(conn, config_dir=str(carpeta), role="admin")
        pagina.set_station(ESTACION)
        if hasattr(pagina, "fecha_edit"):
            pagina.fecha_edit.setDate(QDate(2025, 12, 8))
        # Los valores entran por el modelo de la página, que es lo que la grilla
        # pinta al seleccionar la hora (no se tocan widgets a mano).
        for hora, valores in MUESTRA.items():
            if hora in pagina.observations:
                pagina.observations[hora].update(valores)
        pagina.select_hour("12Z")
        _capturar(pagina, SALIDA / f"pantalla-synop-{nombre_tema}.png", app)

        for clave, vista in (
            ("cli3074", Cli3074View),
            ("cli4074", Cli4074View),
            ("cli5074", Cli5074View),
        ):
            try:
                widget = vista(conn, station=ESTACION, fecha=FECHA)
            except TypeError as error:  # firma distinta: se reporta, no se inventa
                print(f"  {clave}: no se pudo construir ({error})")
                continue
            _capturar(widget, SALIDA / f"pantalla-{clave}-{nombre_tema}.png", app)

    theme.apply_theme(app, "claro")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
