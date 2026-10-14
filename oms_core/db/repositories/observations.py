"""observations repository (NEW table, Neo Arca M005).

One row per standard synoptic hour of a day, unique by
``(station_id, fecha, hora)`` — the natural key the PRD mandates for
idempotent JSON-to-SQLite migration. ``fecha`` is ISO ``YYYY-MM-DD``
(the OLD audit queries already filter with ``fecha LIKE 'YYYY-MM-%'``).

Auxiliary daily rows (TMAX/TMIN/filas_nuvosidad_*), which repeat within a
single legacy file and therefore have no unique ``hora`` key, are NOT stored
here: the importer keeps them verbatim inside the daily document held by
``summaries`` (kind='diario').
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

_FIELDS = ("p_est", "p_nmm", "rocio", "t_vapor", "hr", "v_dir_deg", "v_vel")

_COLS = ", ".join(("station_id", "fecha", "hora", *_FIELDS, "observador", "source_sha256"))


@dataclass(frozen=True)
class Observation:
    station_id: str
    fecha: str
    hora: str
    p_est: float | None
    p_nmm: float | None
    rocio: float | None
    t_vapor: float | None
    hr: float | None
    v_dir_deg: float | None
    v_vel: float | None
    observador: str
    source_sha256: str


_ROW = f"SELECT {', '.join(('id', 'station_id', 'fecha', 'hora', *_FIELDS, 'observador', 'source_sha256'))} FROM observations"


def _from_row(row: sqlite3.Row) -> Observation:
    return Observation(
        station_id=row["station_id"],
        fecha=row["fecha"],
        hora=row["hora"],
        p_est=row["p_est"],
        p_nmm=row["p_nmm"],
        rocio=row["rocio"],
        t_vapor=row["t_vapor"],
        hr=row["hr"],
        v_dir_deg=row["v_dir_deg"],
        v_vel=row["v_vel"],
        observador=row["observador"],
        source_sha256=row["source_sha256"],
    )


def upsert_observation(conn: sqlite3.Connection, obs: Observation) -> None:
    """Insert or overwrite by natural key (station, fecha, hora).

    The importer re-running against the same source must land on the exact
    same rows: this upsert is the whole idempotency mechanism.
    """
    conn.execute(
        f"INSERT INTO observations ({_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(station_id, fecha, hora) DO UPDATE SET "
        "p_est = excluded.p_est, p_nmm = excluded.p_nmm, rocio = excluded.rocio, "
        "t_vapor = excluded.t_vapor, hr = excluded.hr, v_dir_deg = excluded.v_dir_deg, "
        "v_vel = excluded.v_vel, observador = excluded.observador, "
        "source_sha256 = excluded.source_sha256",
        (
            obs.station_id,
            obs.fecha,
            obs.hora,
            obs.p_est,
            obs.p_nmm,
            obs.rocio,
            obs.t_vapor,
            obs.hr,
            obs.v_dir_deg,
            obs.v_vel,
            obs.observador,
            obs.source_sha256,
        ),
    )
    conn.commit()


def get_day(conn: sqlite3.Connection, station_id: str, fecha: str) -> list[Observation]:
    rows = conn.execute(
        _ROW + " WHERE station_id = ? AND fecha = ? ORDER BY hora",
        (station_id, fecha),
    ).fetchall()
    return [_from_row(row) for row in rows]


def get_month(conn: sqlite3.Connection, station_id: str, year: int, month: int) -> list[Observation]:
    prefix = f"{year:04d}-{month:02d}"
    rows = conn.execute(
        _ROW + " WHERE station_id = ? AND substr(fecha, 1, 7) = ? ORDER BY fecha, hora",
        (station_id, prefix),
    ).fetchall()
    return [_from_row(row) for row in rows]


def count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
