"""StationsAdminPage — station management for the Seguridad page (PRD F3).

Table of stations plus a small form to create/edit and a deactivate button
(soft delete). Wired directly to ``oms_core.services.stations``.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from oms_core.db.repositories import stations as stations_repo
from oms_core.services import stations

_COLUMNS = ("ID", "Nombre", "Provincia", "Latitud", "Longitud", "Elevación", "Ch", "Activa")


class StationsAdminPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, parent=None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._include_inactive = False

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection)

        self.id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.provincia_edit = QLineEdit()
        self.lat_spin = QDoubleSpinBox()
        self.long_spin = QDoubleSpinBox()
        self.elev_spin = QDoubleSpinBox()
        self.ch_spin = QDoubleSpinBox()
        for spin in (self.lat_spin, self.long_spin, self.elev_spin, self.ch_spin):
            spin.setRange(-1000.0, 10000.0)
            spin.setDecimals(4)
        self.active_check = QCheckBox("Activa")
        self.active_check.setChecked(True)

        form = QFormLayout()
        form.addRow("ID:", self.id_edit)
        form.addRow("Nombre:", self.name_edit)
        form.addRow("Provincia:", self.provincia_edit)
        form.addRow("Latitud:", self.lat_spin)
        form.addRow("Longitud:", self.long_spin)
        form.addRow("Elevación:", self.elev_spin)
        form.addRow("Ch:", self.ch_spin)
        form.addRow("", self.active_check)

        self.create_button = QPushButton("Crear")
        self.update_button = QPushButton("Guardar cambios")
        self.deactivate_button = QPushButton("Desactivar")
        self.create_button.clicked.connect(self.create_clicked)
        self.update_button.clicked.connect(self.update_clicked)
        self.deactivate_button.clicked.connect(self.deactivate_clicked)

        buttons = QHBoxLayout()
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.deactivate_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(buttons)

        self.refresh()

    # ------------------------------------------------------------ helpers

    def set_include_inactive(self, include: bool) -> None:
        self._include_inactive = include
        self.refresh()

    def row_count(self) -> int:
        return self.table.rowCount()

    def find_row(self, station_id: str) -> int | None:
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == station_id:
                return row
        return None

    def set_form(
        self,
        station_id: str,
        name: str,
        provincia: str,
        latitud: float,
        longitud: float,
        elevacion: float,
        ch: float,
    ) -> None:
        self.id_edit.setText(station_id)
        self.name_edit.setText(name)
        self.provincia_edit.setText(provincia)
        self.lat_spin.setValue(latitud)
        self.long_spin.setValue(longitud)
        self.elev_spin.setValue(elevacion)
        self.ch_spin.setValue(ch)

    def select_station(self, station_id: str) -> None:
        row = self.find_row(station_id)
        if row is not None:
            self.table.selectRow(row)

    def selected_station_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).text()

    def _on_selection(self) -> None:
        station_id = self.selected_station_id()
        if not station_id:
            return
        station = stations_repo.get_station(self._conn, station_id)
        if station is not None:
            self.set_form(
                station.id,
                station.name,
                station.provincia,
                station.latitud,
                station.longitud,
                station.elevacion,
                station.ch,
            )
            self.active_check.setChecked(station.is_active)

    def _form_fields(self) -> dict:
        return {
            "name": self.name_edit.text(),
            "provincia": self.provincia_edit.text(),
            "latitud": self.lat_spin.value(),
            "longitud": self.long_spin.value(),
            "elevacion": self.elev_spin.value(),
            "ch": self.ch_spin.value(),
            "is_active": self.active_check.isChecked(),
        }

    # ------------------------------------------------------------ actions

    def refresh(self) -> None:
        rows = stations.get_stations(self._conn, include_inactive=self._include_inactive)
        self.table.setRowCount(len(rows))
        for row, station in enumerate(rows):
            values = (
                station.id,
                station.name,
                station.provincia,
                station.latitud,
                station.longitud,
                station.elevacion,
                station.ch,
                "Sí" if station.is_active else "No",
            )
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def create_clicked(self) -> None:
        try:
            stations.create_station(self._conn, id=self.id_edit.text().strip(), **self._form_fields())
        except sqlite3.IntegrityError as exc:
            QMessageBox.warning(self, "Estación", f"No se pudo crear la estación:\n{exc}")
            return
        self.refresh()

    def update_clicked(self) -> None:
        try:
            stations.update_station(self._conn, id=self.id_edit.text().strip(), **self._form_fields())
        except sqlite3.Error as exc:
            QMessageBox.warning(self, "Estación", f"No se pudo actualizar la estación:\n{exc}")
            return
        self.refresh()

    def deactivate_clicked(self) -> None:
        station_id = self.selected_station_id()
        if not station_id:
            QMessageBox.information(self, "Estación", "Seleccione una estación de la tabla.")
            return
        stations.deactivate_station(self._conn, station_id)
        self.refresh()
