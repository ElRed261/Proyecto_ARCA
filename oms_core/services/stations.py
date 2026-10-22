"""stations — CRUD service over the stations repository (PRD F3).

Plain-function port of the oracle commands in
``OLD .../modules/synoptic/calculations.rs`` (L623-646), which wrap
``repositories/stations_repo.rs``:

- ``get_stations``      -> :func:`get_stations` (plus an inactive filter the
  admin UI needs; the oracle returned every row);
- ``create_station``    -> :func:`create_station` (plain INSERT, duplicate
  ids fail through the PRIMARY KEY);
- ``update_station``    -> :func:`update_station` (UPDATE of name..is_active
  by id, oracle semantics exactly);
- ``delete_station``    -> :func:`delete_station` (hard DELETE, oracle
  semantics exactly — stations referenced by observations/audit rows are
  protected by the FK barriers of the schema);
- :func:`deactivate_station` is the soft option the F3 admin UI offers
  (``is_active = 0``), so history is never orphaned by a hard delete.
"""

from __future__ import annotations

import sqlite3

import oms_core.db.repositories.stations as stations_repo
from oms_core.db.repositories.stations import Station


def get_stations(
    conn: sqlite3.Connection, *, include_inactive: bool = False
) -> list[Station]:
    return stations_repo.list_stations(conn, include_inactive=include_inactive)


def create_station(
    conn: sqlite3.Connection,
    *,
    id: str,
    name: str,
    provincia: str,
    latitud: float,
    longitud: float,
    elevacion: float,
    ch: float,
    is_active: bool = True,
) -> None:
    stations_repo.add_station(
        conn,
        id=id,
        name=name,
        provincia=provincia,
        latitud=latitud,
        longitud=longitud,
        elevacion=elevacion,
        ch=ch,
        is_active=is_active,
    )


def update_station(
    conn: sqlite3.Connection,
    *,
    id: str,
    name: str,
    provincia: str,
    latitud: float,
    longitud: float,
    elevacion: float,
    ch: float,
    is_active: bool,
) -> None:
    conn.execute(
        "UPDATE stations SET name=?, provincia=?, latitud=?, longitud=?,"
        " elevacion=?, ch=?, is_active=? WHERE id=?",
        (name, provincia, latitud, longitud, elevacion, ch, 1 if is_active else 0, id),
    )
    conn.commit()


def deactivate_station(conn: sqlite3.Connection, station_id: str) -> None:
    """Soft delete (F3 admin UI): keep the row, mark it inactive."""
    conn.execute(
        "UPDATE stations SET is_active = 0 WHERE id = ?", (station_id,)
    )
    conn.commit()


def delete_station(conn: sqlite3.Connection, station_id: str) -> None:
    """Hard delete mirroring the oracle ``delete_station`` command.

    Raises sqlite3.IntegrityError when the station is referenced (FK ON).
    """
    conn.execute("DELETE FROM stations WHERE id=?", (station_id,))
    conn.commit()
