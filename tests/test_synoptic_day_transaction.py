"""S2: un día se guarda entero o no se guarda.

Judgment Day EFF-02 (`docs/AUDITORIA_JD.md`): `save_hour` hace `RELEASE` +
`commit()` por hora, así que un fallo en una hora posterior dejaba las
anteriores persistidas, mientras el llamador dice "whole day fails".
"""

from __future__ import annotations

import pytest

from oms_core.services import synoptic as synoptic_service

STATION = "78485"
FECHA = "2025-12-08"


def _rows(conn) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM observations WHERE station_id = ? AND fecha = ?",
            (STATION, FECHA),
        ).fetchone()[0]
    )


def _versions(conn) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM document_versions WHERE station_id = ? AND day = 8",
            (STATION,),
        ).fetchone()[0]
    )


def test_save_day_guarda_las_ocho_horas(fresh_db):
    synoptic_service.save_day(fresh_db, STATION, FECHA, {}, observer="Ana Pérez")

    assert _rows(fresh_db) == 8


def test_save_day_con_una_hora_invalida_no_guarda_ninguna(fresh_db):
    # "no es un dict" falla en la validación de save_hour, en la quinta hora.
    day_data = {hora: {} for hora in synoptic_service.HOURS}
    day_data["18Z"] = "no es un dict"

    with pytest.raises(synoptic_service.SaveError):
        synoptic_service.save_day(fresh_db, STATION, FECHA, day_data, observer="Ana")

    assert _rows(fresh_db) == 0


def test_save_day_fallido_no_deja_filas_de_version(fresh_db):
    before = _versions(fresh_db)
    day_data = {hora: {} for hora in synoptic_service.HOURS}
    day_data["03Z"] = "no es un dict"

    with pytest.raises(synoptic_service.SaveError):
        synoptic_service.save_day(fresh_db, STATION, FECHA, day_data, observer="Ana")

    assert _versions(fresh_db) == before


def test_save_hour_suelto_sigue_confirmando(fresh_db):
    """El comportamiento previo de save_hour no cambia para sus otros llamadores."""
    synoptic_service.save_hour(fresh_db, STATION, FECHA, "06Z", {})

    assert _rows(fresh_db) == 1


def test_save_day_guarda_el_observador_de_la_estacion(fresh_db):
    synoptic_service.save_day(fresh_db, STATION, FECHA, {}, observer="Ana Pérez")

    assert synoptic_service.observer_for(fresh_db, STATION) == "Ana Pérez"
