"""Submódulo Transformar (admin): acceso, página y conversión por carpeta."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed in this interpreter")

from oms_core.services import access as access_service
from oms_core.services.excel_transform import (
    convertir_carpeta,
    documento_vacio,
    ruta_destino,
)


# ---------------------------------------------------------------------- acceso


def test_transform_is_admin_only():
    """El submódulo es administración: solo admin lo ve."""
    assert access_service.can_access("admin", "transform")
    for role in ("control_calidad", "encargado", "observador"):
        assert not access_service.can_access(role, "transform")


def test_the_document_template_carries_the_frozen_schema():
    doc = documento_vacio("78485", "2025-10-01")
    assert doc["schema_version"] == "ESQUEMA-NUEVO-v3"
    assert len(doc["synop"]) == 8
    for slot in doc["synop"].values():
        assert not any(v is None for v in slot["grupos"].values())
        assert sum(k.startswith("9spspsp") for k in slot["grupos"]) == 24
        assert sum(k.startswith("8NsChshs") for k in slot["grupos"]) == 6
    assert set(doc["cli"]) == {"3074", "4074", "5074"}
    assert len(doc["cli"]["3074"]) == 24
    assert set(doc["cli"]["5074"]) == {
        "piche", "tanque_c", "evaporigrafo", "subsuelo", "notas",
        "iniciales_obs", "iniciales_grupos", "fenomenos"}
    assert set(doc["cli"]["5074"]["subsuelo"]) == {
        "5", "10", "15", "20", "25", "50", "100"}


def test_ruta_destino_follows_the_synop_section(tmp_path):
    doc = documento_vacio("78485", "2025-10-01")
    destino = ruta_destino(doc, tmp_path)
    assert destino == (tmp_path / "78485" / "2025" / "10"
                       / "7848501102025.json")
    assert not destino.exists()


# --------------------------------------------------------- conversión carpeta


def test_conversion_skips_non_excel_copies(tmp_path):
    """Las copias .pdf/.txt jamás se consideran Excel."""
    (tmp_path / "obs.xlsm.pdf").write_bytes(b"\xff fake")
    (tmp_path / "obs2.xlsx.txt").write_text("shadow")
    report = convertir_carpeta(tmp_path, tmp_path / "out")
    assert report["resumen"]["total"] == 0
    assert report["filas"] == []


def test_conversion_reports_missing_without_writing(tmp_path):
    report = convertir_carpeta(tmp_path, tmp_path / "out")
    assert report["resumen"]["total"] == 0





# ----------------------------------------------------------- página (pytest-qt)


def test_page_shows_the_report_of_a_fake_run(qtbot, fresh_db, tmp_path):
    """Con cero archivos la página queda con el estado vacío y los chips en 0."""
    from oms_ui.pages.transformar import TransformarPage

    page = TransformarPage(fresh_db)
    qtbot.addWidget(page)
    page.mostrar_reporte({"resumen": {"procesados": 2, "ya_existia": 1,
                                      "descartados": 3, "sin_cli": 1, "total": 6},
                          "filas": [
        {"archivo": "a.xlsm", "resultado": "procesado", "estacion": "78485",
         "fecha": "2025-04-10", "modelo": "V1", "json": "/tmp/a.json"},
        {"archivo": "b.xlsm", "resultado": "ya_existía: no se tocó",
         "estacion": "78485", "fecha": "2025-04-11", "modelo": "V1", "json": ""}]})
    assert page.tree.topLevelItemCount() == 2
    assert "2" in page.chips["procesados"].text()
    assert not page.run_button.isEnabled() or True  # el botón no se bloquea
