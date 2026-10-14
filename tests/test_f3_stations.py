"""F3 — stations service tests, mirroring OLD .../repositories/stations_repo.rs
(get_all / insert / update / delete) plus the F3 soft deactivate used by the
admin UI. assigned_station app_config KV is also covered here (app_config.rs)."""

import sqlite3

import pytest

from oms_core.db.connection import connect
from oms_core.db.migrations import migrate
from oms_core.db.repositories import app_config
from oms_core.db.repositories import stations as stations_repo
from oms_core.services import stations

FIELDS = {
    "name": "Estación Nueva",
    "provincia": "Santo Domingo",
    "latitud": 18.5,
    "longitud": -69.9,
    "elevacion": 10.0,
    "ch": 1.5,
    "is_active": True,
}


def make_db(tmp_path):
    conn = connect(tmp_path / "stations.db")
    migrate(conn)
    return conn


def test_get_stations_incluye_las_15_seed(tmp_path):
    conn = make_db(tmp_path)
    rows = stations.get_stations(conn)
    assert len(rows) == 15
    assert all(s.is_active for s in rows)


def test_get_stations_filtro_incluye_inactivas(tmp_path):
    conn = make_db(tmp_path)
    stations.deactivate_station(conn, "78451")

    assert stations_repo.get_station(conn, "78451").id not in [
        s.id for s in stations.get_stations(conn)
    ]
    ids = [s.id for s in stations.get_stations(conn, include_inactive=True)]
    assert "78451" in ids


def test_create_station_roundtrip(tmp_path):
    conn = make_db(tmp_path)
    stations.create_station(conn, id="TEST01", **FIELDS)

    row = stations_repo.get_station(conn, "TEST01")
    assert row is not None
    assert row.name == "Estación Nueva"
    assert row.ch == 1.5
    assert row.is_active is True


def test_create_station_duplicado_falla(tmp_path):
    conn = make_db(tmp_path)
    stations.create_station(conn, id="TEST01", **FIELDS)
    with pytest.raises(sqlite3.IntegrityError):
        stations.create_station(conn, id="TEST01", **FIELDS)


def test_update_station_sobrescribe_todos_los_campos_incluido_is_active(tmp_path):
    """Oracle update_station updates name..is_active for the given id."""
    conn = make_db(tmp_path)
    stations.create_station(conn, id="TEST01", **FIELDS)

    stations.update_station(
        conn,
        id="TEST01",
        name="Renombrada",
        provincia="La Altagracia",
        latitud=18.6,
        longitud=-68.9,
        elevacion=12.0,
        ch=2.0,
        is_active=False,
    )
    row = stations_repo.get_station(conn, "TEST01")
    assert (row.name, row.provincia, row.ch, row.is_active) == (
        "Renombrada",
        "La Altagracia",
        2.0,
        False,
    )


def test_deactivate_station_no_borra_la_fila(tmp_path):
    conn = make_db(tmp_path)
    stations.create_station(conn, id="TEST01", **FIELDS)

    stations.deactivate_station(conn, "TEST01")
    row = stations_repo.get_station(conn, "TEST01")
    assert row is not None and row.is_active is False


def test_delete_station_borra_estacion_sin_referencias_como_el_oraculo(tmp_path):
    """Oracle delete_station is a hard DELETE (calculations.rs L643)."""
    conn = make_db(tmp_path)
    stations.create_station(conn, id="TEST01", **FIELDS)

    stations.delete_station(conn, "TEST01")
    assert stations_repo.get_station(conn, "TEST01") is None


def test_delete_station_con_observaciones_falla_por_fk(tmp_path):
    """FK barriers from stations(id) protect referenced stations (same schema
    and PRAGMA foreign_keys=ON as the oracle)."""
    conn = make_db(tmp_path)
    conn.execute(
        "INSERT INTO observations (station_id, fecha, hora, observador, source_sha256)"
        " VALUES ('78451', '2025-05-01', '06Z', 'test', 'abc')"
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        stations.delete_station(conn, "78451")
    assert stations_repo.get_station(conn, "78451") is not None


# ---------------------------------------------------------------- assigned_station


def test_assigned_station_kv_roundtrip(tmp_path):
    conn = make_db(tmp_path)
    assert app_config.get(conn, "assigned_station") is None

    app_config.set(conn, "assigned_station", "78451")
    assert app_config.get(conn, "assigned_station") == "78451"
    app_config.set(conn, "assigned_station", "78485")
    assert app_config.get(conn, "assigned_station") == "78485"
