"""stations repository (stations table + 15 seeded rows from db.rs M1)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    provincia: str
    latitud: float
    longitud: float
    elevacion: float
    ch: float
    is_active: bool


_ROW = "SELECT id, name, provincia, latitud, longitud, elevacion, ch, is_active FROM stations"


def _from_row(row: sqlite3.Row) -> Station:
    return Station(
        id=row["id"],
        name=row["name"],
        provincia=row["provincia"],
        latitud=float(row["latitud"]),
        longitud=float(row["longitud"]),
        elevacion=float(row["elevacion"]),
        ch=float(row["ch"]),
        is_active=bool(row["is_active"]),
    )


def get_station(conn: sqlite3.Connection, station_id: str) -> Station | None:
    row = conn.execute(_ROW + " WHERE id = ?", (station_id,)).fetchone()
    return _from_row(row) if row else None


def station_exists(conn: sqlite3.Connection, station_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM stations WHERE id = ?", (station_id,)).fetchone()
    return row is not None


def list_stations(conn: sqlite3.Connection, *, include_inactive: bool = False) -> list[Station]:
    sql = _ROW
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY id"
    return [_from_row(row) for row in conn.execute(sql)]


def add_station(
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
    """Insert a station. Raises sqlite3.IntegrityError on duplicate id."""
    conn.execute(
        "INSERT INTO stations (id, name, provincia, latitud, longitud, elevacion, ch, is_active)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (id, name, provincia, latitud, longitud, elevacion, ch, 1 if is_active else 0),
    )
    conn.commit()
