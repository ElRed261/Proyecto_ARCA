"""S4: guardar escribe el documento en el árbol y encola la sincronización.

Judgment Day EFF-01 (`docs/AUDITORIA_JD.md`): `emit_dual_after_save` sólo se
llamaba desde tests, así que el árbol `synop/` no recibía ningún documento
nuevo y `sync_pending` quedaba vacía para siempre mientras el panel mostraba
"Sincronización al día".
"""

from __future__ import annotations

import json

import pytest

from oms_core import paths as paths_mod
from oms_core.services import synoptic as synoptic_service

STATION = "78485"
FECHA = "2025-12-08"
# station + dd + mm + yyyy: el nombre que usa el emisor dual.
NOMBRE = "7848508122025.json"


@pytest.fixture(autouse=True)
def _sin_env_de_arbol(monkeypatch, tmp_path):
    """`ARCA_BASE_DIR` gana sobre el perfil y convierte el emit en no-op.

    Además: sin perfil el árbol cae al Documents del usuario, así que el
    default se apunta a tmp. Un test jamás debe escribir en el archivo real.
    """
    monkeypatch.delenv(paths_mod.ENV_BASE_DIR, raising=False)
    monkeypatch.delenv("ARCA_BASE_DIR", raising=False)
    monkeypatch.setattr(
        paths_mod, "default_documents_root", lambda *_a, **_k: tmp_path / "documentos"
    )


@pytest.fixture
def arbol(fresh_db, tmp_path):
    offline = tmp_path / "offline"
    offline.mkdir()
    paths_mod.set_path_profile(
        fresh_db, paths_mod.PathProfile(offline_root=str(offline))
    )
    return offline


def test_guardar_escribe_el_json_en_el_arbol(fresh_db, arbol):
    synoptic_service.save_day(fresh_db, STATION, FECHA, {}, observer="Ana")

    destino = arbol / paths_mod.SECTION_SYNOP / STATION / "2025" / "12" / NOMBRE

    assert destino.is_file(), f"no se escribió {destino}"
    doc = json.loads(destino.read_text(encoding="utf-8"))
    assert doc["schema"] == 2
    assert doc["meta"]["estacion"] == STATION
    assert set(doc["synop"]) == set(synoptic_service.HOURS)


def test_guardar_una_hora_suelta_tambien_escribe_el_arbol(fresh_db, arbol):
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", {})

    assert (arbol / paths_mod.SECTION_SYNOP / STATION / "2025" / "12" / NOMBRE).is_file()


def test_sin_arbol_online_el_guardado_va_al_arbol_por_defecto(fresh_db, tmp_path):
    synoptic_service.save_day(fresh_db, STATION, FECHA, {}, observer="Ana")

    filas = fresh_db.execute(
        "SELECT COUNT(*) FROM observations WHERE station_id = ?", (STATION,)
    ).fetchone()[0]
    assert filas == 8
    # Sin perfil el árbol es el Documents por defecto (aquí, redirigido a tmp):
    # el documento tiene que llegar igual.
    destino = (
        tmp_path / "documentos" / paths_mod.SECTION_SYNOP / STATION / "2025" / "12" / NOMBRE
    )
    assert destino.is_file()
    # Y sin raíz online el emit es un no-op honesto: nada en cola, nada roto.
    cola = fresh_db.execute("SELECT COUNT(*) FROM sync_pending").fetchone()[0]
    assert cola == 0


def test_copia_online_fallida_deja_la_fila_en_cola(fresh_db, arbol, tmp_path):
    bloqueado = tmp_path / "online-bloqueado"
    bloqueado.write_text("no soy un directorio", encoding="utf-8")
    paths_mod.set_path_profile(
        fresh_db,
        paths_mod.PathProfile(offline_root=str(arbol), online_root=str(bloqueado)),
    )

    synoptic_service.save_day(fresh_db, STATION, FECHA, {}, observer="Ana")

    fila = fresh_db.execute(
        "SELECT relative_path, last_error FROM sync_pending WHERE synced_at IS NULL"
    ).fetchone()
    assert fila is not None, "la copia falló y no se encoló nada"
    assert fila["relative_path"].endswith(NOMBRE)
    assert fila["last_error"]
