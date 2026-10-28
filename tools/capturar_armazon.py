"""Captura el armazón real (riel + dashboard) para la evidencia del rediseño.

`capturar_pantallas.py` sólo sabe de Sinóptico y de los CLI; el armazón necesita
una sesión. Aquí se arma con una base temporal migrada y un rol dado: nunca toca
la base del usuario.

Uso::

    .venv-gil/bin/python tools/capturar_armazon.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from PySide6.QtWidgets import QApplication  # noqa: E402

from oms_core.db import migrations  # noqa: E402
from oms_core.db.connection import connect  # noqa: E402
from oms_ui import theme  # noqa: E402
from oms_ui.main_window import MainWindow  # noqa: E402

SALIDA = RAIZ / "Migración" / "evidencias" / "DISENO_NUEVO" / "shell"

#: Pantallas del armazón: (nombre, colapsado, tema)
TOMAS = (
    ("armazon-claro", False, "claro"),
    ("armazon-colapsado-claro", True, "claro"),
    ("armazon-oscuro", False, "oscuro"),
    ("armazon-colapsado-oscuro", True, "oscuro"),
)


def _ventana(conn, colapsado: bool, tema: str) -> MainWindow:
    theme.apply_theme(QApplication.instance(), tema)
    ventana = MainWindow(role="observador", db_path=conn, email="observador@arca.rd")
    ventana.resize(1366, 768)
    if colapsado != ventana.rail_collapsed:
        ventana.toggle_rail()
    ventana.show()
    QApplication.processEvents()
    return ventana


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    theme.apply_theme(app, "claro")
    SALIDA.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        conn = connect(Path(tmp) / "armazon.db")
        migrations.migrate(conn)
        for nombre, colapsado, tema in TOMAS:
            ventana = _ventana(conn, colapsado, tema)
            QApplication.processEvents()
            destino = SALIDA / f"{nombre}.png"
            ventana.grab().save(str(destino))
            print(f"  {destino.name}  ({destino.stat().st_size // 1024} KB)")
            ventana.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
