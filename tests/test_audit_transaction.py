"""S1: el repositorio no deja la conexión en transacción implícita.

Judgment Day SEG-02 (`docs/AUDITORIA_JD.md`): `mark_error` lanzaba
`MarkConflictError` después de un `INSERT ... ON CONFLICT DO NOTHING`, sin
cerrar la transacción. La conexión quedaba abierta y el siguiente
`BEGIN IMMEDIATE` fallaba con "cannot start a transaction within a
transaction", deshabilitando correcciones y resúmenes hasta reiniciar.
"""

from __future__ import annotations

import pytest

from oms_core.db.repositories import audit as audit_repo

STATION = "78485"
FECHA = "08122025"


def _mark(conn, campo: str = "meteo_2_1") -> int:
    return audit_repo.mark_error(
        conn,
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo=campo,
        tipo_error="dato_erroneo",
        marcado_por="auditora",
    )


def _correction(conn, campo: str = "meteo_2_1") -> int:
    return audit_repo.propose_correction(
        conn,
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo=campo,
        valor_original="15.2",
        valor_corregido="15.4",
        justificacion="lectura del libro de campo",
        corregido_por="auditora",
    )


def test_mark_error_exitoso_no_deja_transaccion_abierta(fresh_db):
    _mark(fresh_db)

    assert fresh_db.in_transaction is False


def test_conflicto_de_marca_no_deja_transaccion_abierta(fresh_db):
    _mark(fresh_db)

    with pytest.raises(audit_repo.MarkConflictError):
        _mark(fresh_db)

    assert fresh_db.in_transaction is False


def test_conflicto_de_marca_conserva_el_mensaje_del_oraculo(fresh_db):
    _mark(fresh_db)

    with pytest.raises(audit_repo.MarkConflictError) as excinfo:
        _mark(fresh_db)

    assert str(excinfo.value) == "Este campo ya está marcado como error"


def test_tras_un_conflicto_se_puede_proponer_correccion(fresh_db):
    _mark(fresh_db)
    with pytest.raises(audit_repo.MarkConflictError):
        _mark(fresh_db)

    # El impacto real: la conexión del llamador debe seguir usable.
    mark_id = _correction(fresh_db)

    assert mark_id > 0
    assert fresh_db.in_transaction is False
