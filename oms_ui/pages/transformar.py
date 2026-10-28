"""Transformar — submódulo admin de conversión Excel → JSON.

Solo para el rol administrador. El destino es la sección ``synop`` del
directorio de datos del OMS (la misma raíz que la app ya usa para las
observaciones). Flujo: elegir carpeta → el árbol de identificación
(``oms_core.services.excel_transform``) procesa cada Excel → reporte por
archivo (resultado, estación, fecha, modelo del 3074 y JSON escrito). Los
días que ya existen no se tocan salvo que se marque ``Sobrescribir``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from oms_core.services import excel_transform

#: prefijo del resultado → color de la fila del reporte
COLOR_RESULTADO = (
    ("procesado", "$ok_fuerte"),
    ("ya_existía", "$ambar"),
    ("descartado", "$tenue"),
)

def _qss(plantilla: str) -> str:
    """Resuelve una plantilla QSS con la paleta del tema aplicado (S1)."""
    from string import Template

    from oms_ui import theme as _theme

    return Template(plantilla).substitute(_theme.palette_actual())

PAGE_QSS = """
QFrame#tCard { background: $superficie; border: 1px solid $borde; border-radius: 10px; }
QLabel#tTitle { font-size: 20px; font-weight: 800; color: $texto_alt; }
QLabel#tSub { color: $suave_alt; }
QLabel#tChip { background: $panel; border-radius: 8px; padding: 4px 10px;
               color: $texto; font-weight: 700; }
QLineEdit { background: $superficie; border: 1px solid $borde;
            border-radius: 6px; padding: 4px 8px; color: $texto_alt; }
QTreeWidget { background: $superficie; color: $texto; font-size: 12px;
              border: 1px solid $borde; border-radius: 6px;
              alternate-background-color: $panel_alt;
              selection-background-color: $texto_alt; selection-color: $superficie; }
QTreeWidget::item { padding: 3px; }
QPushButton#tPrimary { background: $acento; color: $banda_texto; border: none;
                       border-radius: 7px; padding: 9px 20px; font-weight: 700; }
QPushButton#tPrimary:hover { background: $acento_hover; }
QPushButton#tSecondary { background: $superficie; color: $texto_alt;
                         border: 1px solid $borde_input; border-radius: 7px;
                         padding: 8px 16px; font-weight: 600; }
QHeaderView::section { background: $panel_alt; color: $suave; border: none;
                       border-bottom: 1px solid $borde; padding: 6px;
                       font-weight: 700; }
"""

CHIPS = (("procesados", "Procesados"), ("ya_existia", "Ya existía"),
         ("descartados", "Descartados"), ("sin_cli", "Sin CLI (bloques vacíos)"))


def destino_synop(conn: sqlite3.Connection) -> Path:
    """La sección synop del directorio de datos que el OMS ya usa.

    ``resolve_base_dir`` ya devuelve «raíz + synop» (la misma base que el
    navegador de la Auditoría); el conversor escribe ahí directamente."""
    from oms_core.services.audit import resolve_base_dir
    return resolve_base_dir(conn)


class _Conversion(QThread):
    """Convierte la carpeta fuera del hilo de UI.

    Antes `_on_transform` llamaba al servicio en el hilo principal y sostenía la
    ventana con `processEvents()`: con 148 archivos la app se congelaba.
    """

    terminado = Signal(object)
    fallo = Signal(str)

    def __init__(self, carpeta: str, destino: Path, sobrescribir: bool,
                 estaciones, parent=None) -> None:
        super().__init__(parent)
        self._carpeta = carpeta
        self._destino = destino
        self._sobrescribir = sobrescribir
        self._estaciones = estaciones

    def run(self) -> None:  # noqa: D102 - contrato de QThread
        try:
            reporte = excel_transform.convertir_carpeta(
                self._carpeta, self._destino,
                sobrescribir=self._sobrescribir,
                estaciones=self._estaciones,
            )
        except Exception as exc:  # noqa: BLE001 - el fallo viaja a la UI
            self.fallo.emit(str(exc))
            return
        self.terminado.emit(reporte)


class TransformarPage(QWidget):
    """Carpeta completa → documentos v3 en el dato OMS, con reporte en vivo."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn  # destino_synop lo necesita al convertir
        self.setObjectName("transformPage")
        page = QVBoxLayout(self)
        page.setContentsMargins(24, 18, 24, 18)
        page.setSpacing(12)
        self.setStyleSheet(_qss(PAGE_QSS))

        cabecera = QVBoxLayout()
        cabecera.setSpacing(2)
        titulo = QLabel("Transformación de datos")
        titulo.setObjectName("tTitle")
        sub = QLabel(
            "Convierte los Excel de una carpeta en los JSON de observación del OMS")
        sub.setObjectName("tSub")
        cabecera.addWidget(titulo)
        cabecera.addWidget(sub)
        page.addLayout(cabecera)

        card_fila = QHBoxLayout()
        card_fila.setContentsMargins(16, 14, 16, 14)
        card_fila.setSpacing(10)
        tarjeta = QFrame()
        tarjeta.setObjectName("tCard")
        tarjeta.setLayout(card_fila)
        page.addWidget(tarjeta)

        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Ruta de la carpeta de Excel…")
        elegir = QPushButton("Elegir carpeta…")
        elegir.setObjectName("tSecondary")
        elegir.clicked.connect(self._on_elegir)
        card_fila.addWidget(self.folder_edit, 1)
        card_fila.addWidget(elegir)

        acciones = QHBoxLayout()
        acciones.setSpacing(14)
        self.overwrite = QCheckBox("Sobrescribir los días que ya existen")
        self.overwrite.setStyleSheet(_qss("color: $texto; font-weight: 600;"))
        self.run_button = QPushButton("Transformar")
        self.run_button.setObjectName("tPrimary")
        self.run_button.clicked.connect(self._on_transform)
        acciones.addWidget(self.overwrite)
        acciones.addStretch(1)
        acciones.addWidget(self.run_button)
        page.addLayout(acciones)

        self.destino_label = QLabel(f"Destino: {destino_synop(conn)}")
        self.destino_label.setObjectName("tSub")
        page.addWidget(self.destino_label)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chips: dict[str, QLabel] = {}
        for clave, etiqueta in CHIPS:
            chip = QLabel(f"{etiqueta}: 0")
            chip.setObjectName("tChip")
            self.chips[clave] = chip
            chips.addWidget(chip)
        chips.addStretch(1)
        page.addLayout(chips)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["Archivo", "Resultado", "Estación", "Fecha",
                                   "Modelo", "JSON"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for indice in range(1, 6):
            self.tree.header().setSectionResizeMode(
                indice, QHeaderView.ResizeMode.ResizeToContents)
        page.addWidget(self.tree, 1)

        self.estado = QLabel("")
        self.estado.setObjectName("tSub")
        page.addWidget(self.estado)

    # ----------------------------------------------------------- interacción

    def _on_elegir(self) -> None:
        elegida = QFileDialog.getExistingDirectory(
            self, "Elegir la carpeta de Excel",
            self.folder_edit.text() or str(Path.home()))
        if elegida:
            self.folder_edit.setText(elegida)

    def _on_transform(self) -> None:
        carpeta = self.folder_edit.text().strip()
        if not carpeta or not Path(carpeta).is_dir():
            self.estado.setText("Elegí una carpeta válida primero.")
            return
        self.estado.setText("Convirtiendo…")
        self.run_button.setEnabled(False)
        self._hilo = _Conversion(
            carpeta,
            destino_synop(self._conn),
            self.overwrite.isChecked(),
            excel_transform.buscador_estaciones(self._conn),
            parent=self,
        )
        self._hilo.terminado.connect(self._on_convertido)
        self._hilo.fallo.connect(self._on_fallo)
        self._hilo.finished.connect(lambda: self.run_button.setEnabled(True))
        self._hilo.start()

    def _on_convertido(self, reporte: object) -> None:
        self.mostrar_reporte(reporte or {})

    def _on_fallo(self, mensaje: str) -> None:
        self.estado.setText(f"No se pudo convertir: {mensaje}")

    # ------------------------------------------------------------ estructura

    def mostrar_reporte(self, reporte: dict[str, Any]) -> None:
        """Pinta el reporte de ``convertir_carpeta`` (probado por las tests)."""
        self.tree.clear()
        for fila in reporte.get("filas") or []:
            item = QTreeWidgetItem([
                str(fila.get("archivo", "")),
                str(fila.get("resultado", "")),
                str(fila.get("estacion", "")),
                str(fila.get("fecha", "")),
                str(fila.get("modelo") or "—"),
                str(fila.get("json", "")),
            ])
            for prefijo, hexcolor in COLOR_RESULTADO:
                if fila.get("resultado", "").startswith(prefijo):
                    item.setForeground(1, QColor(_qss(hexcolor)))
                    break
            self.tree.addTopLevelItem(item)
        resumen = reporte.get("resumen") or {}
        for clave, chip in self.chips.items():
            etiqueta = dict(CHIPS)[clave]
            chip.setText(f"{etiqueta}: {resumen.get(clave, 0)}")
        self.estado.setText(f"Total de archivos evaluados: {resumen.get('total', 0)}")


__all__ = ["TransformarPage", "destino_synop"]
