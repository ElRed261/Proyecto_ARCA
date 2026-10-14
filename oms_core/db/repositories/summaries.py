"""summary_logs repository — verbatim document storage.

The legacy table (db.rs M1) gained three columns in M005 (kind/day/sha256)
and a natural-key uniqueness so re-importing a document overwrites instead of
duplicating:

- kind='resumen': whole-period monthly summary JSON ({meta, datos}), day = 0;
- kind='diario': the full legacy daily JSON ({meta, horarias, resumen_dia}),
  day = the calendar day; this is what preserves the auxiliary horarias rows
  (TMAX/TMIN/filas_nuvosidad) that cannot key the observations table.

``data`` always stores the source file content verbatim (byte-identical after
UTF-8 decode); the SHA-256 of the original bytes travels in ``sha256``.
"""

from __future__ import annotations

import sqlite3

_COLS = "station_id, year, month, day, kind, data, sha256"


def upsert_summary_doc(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    year: int,
    month: int,
    kind: str,
    data: str,
    sha256: str | None,
    day: int = 0,
) -> None:
    """Insert or replace the document for its natural key.

    Natural key: (station_id, year, month, kind, day); day=0 for whole-period
    documents. Backed by the uq_summary_logs_doc unique index (M005).
    """
    conn.execute(
        "INSERT OR REPLACE INTO summary_logs "
        "(station_id, year, month, data, kind, day, sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (station_id, year, month, data, kind, day, sha256),
    )
    conn.commit()


def get_summary_doc(
    conn: sqlite3.Connection,
    station_id: str,
    year: int,
    month: int,
    kind: str,
    *,
    day: int = 0,
) -> str | None:
    row = conn.execute(
        "SELECT data FROM summary_logs WHERE station_id = ? AND year = ? AND month = ?"
        " AND kind = ? AND day = ?",
        (station_id, year, month, kind, day),
    ).fetchone()
    return row["data"] if row else None


def list_docs(
    conn: sqlite3.Connection, *, kind: str | None = None
) -> list[sqlite3.Row]:
    sql = f"SELECT {', '.join(('id', *_COLS.split(', '), 'created_at'))} FROM summary_logs"
    params: tuple = ()
    if kind is not None:
        sql += " WHERE kind = ?"
        params = (kind,)
    sql += " ORDER BY station_id, year, month, day"
    return conn.execute(sql, params).fetchall()


def count_docs(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM summary_logs").fetchone()[0])
