"""S5: el auditor ve los días guardados por la aplicación.

Judgment Day ESC-01 (`docs/AUDITORIA_JD.md`): `browse_days` enumeraba sólo el
árbol en disco mientras las observaciones nuevas se escriben en SQLite, así que
ningún día posterior a la migración aparecía en la auditoría.
"""

from __future__ import annotations

import json

from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import audit as audit_service

STATION = "78485"
DOC = {
    "schema": 2,
    "meta": {"estacion": STATION, "fecha": "2025-12-08"},
    "synop": {
        "06Z": {"datos": {"ts": "24.0"}, "observador": "Ana Pérez"},
        "09Z": {"datos": {"ts": ""}},
    },
}


def _guardar_en_db(conn, day: int = 8, year: int = 2025, month: int = 12) -> None:
    summaries_repo.upsert_summary_doc(
        conn,
        station_id=STATION,
        year=year,
        month=month,
        kind="diario",
        data=json.dumps(DOC, ensure_ascii=False),
        sha256="x",
        day=day,
    )


def _archivo_legado(base, day: str = "07", month: str = "11", year: str = "2025"):
    carpeta = base / STATION / year / month
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{STATION}{day}{month}{year}.json"
    destino.write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
    return destino


def test_un_dia_solo_en_sqlite_aparece_en_la_auditoria(fresh_db, tmp_path):
    _guardar_en_db(fresh_db)

    dias = audit_service.browse_days(tmp_path, fresh_db, STATION, "2025", "12")

    assert [d["date"] for d in dias] == ["2025-12-08"]


def test_la_fila_trae_las_mismas_claves_que_el_disco(fresh_db, tmp_path):
    _guardar_en_db(fresh_db)

    (dia,) = audit_service.browse_days(tmp_path, fresh_db, STATION, "2025", "12")

    assert set(dia) == {
        "filename",
        "date",
        "observador",
        "horas_registradas",
        "error_count",
        "correction_count",
    }
    assert dia["observador"] == "Ana Pérez"
    assert dia["horas_registradas"] == 1
    assert dia["filename"] == "7848508122025.json"


def test_un_mes_solo_en_disco_sigue_apareciendo(fresh_db, tmp_path):
    _archivo_legado(tmp_path)

    dias = audit_service.browse_days(tmp_path, fresh_db, STATION, "2025", "11")

    assert [d["date"] for d in dias] == ["2025-11-07"]


def test_un_dia_en_ambas_fuentes_aparece_una_vez(fresh_db, tmp_path):
    _guardar_en_db(fresh_db)
    _archivo_legado(tmp_path, day="08", month="12")

    dias = audit_service.browse_days(tmp_path, fresh_db, STATION, "2025", "12")

    assert len(dias) == 1
    assert dias[0]["date"] == "2025-12-08"


def test_browse_stations_incluye_estaciones_solo_en_sqlite(fresh_db, tmp_path):
    _guardar_en_db(fresh_db)
    tmp_path.mkdir(exist_ok=True)

    estaciones = audit_service.browse_stations(tmp_path, fresh_db)

    assert STATION in [e["code"] for e in estaciones]
    nombre = next(e["name"] for e in estaciones if e["code"] == STATION)
    assert nombre != "Estación Desconocida"


def test_browse_stations_sigue_listando_el_disco(fresh_db, tmp_path):
    (tmp_path / "78486" / "2025" / "11").mkdir(parents=True)

    estaciones = audit_service.browse_stations(tmp_path, fresh_db)

    assert "78486" in [e["code"] for e in estaciones]
