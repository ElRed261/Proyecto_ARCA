"""S9: Transformar convierte fuera del hilo de UI y sin literales de color."""

from __future__ import annotations

import re
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from oms_ui.pages import transformar as modulo

_SRC = Path(__file__).resolve().parents[1] / "oms_ui" / "pages" / "transformar.py"


def test_transformar_no_tiene_colores_literales():
    fuente = _SRC.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{6}\b", fuente)


def test_la_conversion_no_bloquea_el_hilo_de_ui(qtbot, fresh_db, tmp_path, monkeypatch):
    """`_on_transform` vuelve enseguida: el trabajo lo hace el QThread."""
    carpeta = tmp_path / "excels"
    carpeta.mkdir()
    (carpeta / "uno.xlsx").write_bytes(b"placeholder")

    llamadas = {}

    def convertir_lento(carpeta_arg, destino, sobrescribir, estaciones):
        llamadas["hilo"] = True
        time.sleep(0.4)  # si corriera en el hilo de UI, esto congelaría la app
        return {"filas": [], "resumen": {"total": 0}}

    monkeypatch.setattr(modulo.excel_transform, "convertir_carpeta", convertir_lento)

    pagina = modulo.TransformarPage(fresh_db)
    qtbot.addWidget(pagina)
    pagina.folder_edit.setText(str(carpeta))

    inicio = time.monotonic()
    pagina._on_transform()
    transcurrido = time.monotonic() - inicio
    assert transcurrido < 0.2, f"bloqueó {transcurrido:.2f}s: sigue en el hilo de UI"
    assert pagina.run_button.isEnabled() is False

    limite = time.monotonic() + 5
    while pagina.run_button.isEnabled() is False and time.monotonic() < limite:
        QApplication.processEvents()
        time.sleep(0.01)
    assert llamadas.get("hilo") is True
    assert pagina.run_button.isEnabled() is True
    assert "Total de archivos evaluados" in pagina.estado.text()


def test_la_carpeta_invalida_no_arranca_ningun_hilo(qtbot, fresh_db):
    pagina = modulo.TransformarPage(fresh_db)
    qtbot.addWidget(pagina)
    pagina.folder_edit.setText("/no/existe/esta/carpeta")
    pagina._on_transform()
    assert "carpeta válida" in pagina.estado.text()
    assert not hasattr(pagina, "_hilo")
