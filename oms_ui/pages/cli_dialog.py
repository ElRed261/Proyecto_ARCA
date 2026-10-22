"""Generic CLI module dialog (OBS MÓDULOS CLI card).

One dialog parameterized by module: numeric inputs from the service's exact
per-module field lists, prefilled from the stored cli document, saved back
through ``save_cli`` by the caller. Presentation-only; validation lives in
``oms_core.services.cli``.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from oms_core.services import cli as cli_service

MODULE_TITLES = {
    "cli3074": "CLI 3074",
    "cli4074": "CLI 4074",
    "cli5074": "CLI 5074",
}


def module_fields(module_key: str) -> list[str]:
    """Exact numeric field list for the module (decimals + ceil ints)."""
    decimals = {
        "cli3074": cli_service.DECIMAL_FIELDS_3074,
        "cli4074": cli_service.DECIMAL_FIELDS_4074,
        "cli5074": cli_service.DECIMAL_FIELDS_5074,
    }[module_key]
    ceils = list(
        getattr(cli_service, f"CEIL_FIELDS_{module_key[3:]}", []) or []
    )
    ordered = list(dict.fromkeys(list(decimals) + ceils))
    return ordered


class CliModuleDialog(QDialog):
    """Numeric sheet for one CLI module with load prefill + collect."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        station: str,
        fecha: str,
        module_key: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if module_key not in cli_service.CLI_KEYS:
            raise ValueError(f"cli_key inválida: '{module_key}'")
        self._conn = conn
        self._station = station
        self._fecha = fecha
        self._module_key = module_key
        self._fields = module_fields(module_key)
        self.inputs: dict[str, QLineEdit] = {}

        self.setWindowTitle(MODULE_TITLES[module_key])
        layout = QVBoxLayout(self)
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        stored = cli_service.load_cli(conn, station, fecha, module_key) or {}
        if not isinstance(stored, dict):
            stored = {}
        for row, field in enumerate(self._fields):
            grid.addWidget(QLabel(field), row, 0)
            edit = QLineEdit()
            value = stored.get(field)
            if value is not None:
                edit.setText(str(value))
            grid.addWidget(edit, row, 1)
            self.inputs[field] = edit
        layout.addWidget(grid_host)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def collect(self) -> dict[str, str]:
        """Current sheet values (raw strings; the service validates)."""
        return {field: edit.text() for field, edit in self.inputs.items()}

    def save(self) -> None:
        """Persist through the transactional service path."""
        cli_service.save_cli(
            self._conn, self._station, self._fecha, self._module_key, self.collect()
        )
