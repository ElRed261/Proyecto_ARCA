"""Version trail for a station-day document.

Rule R4 of ``docs/ARQUITECTURA_DATOS.md``: after the day closes at 06Z of the
next day, corrections go through audit — and audit needs to show what changed.
Every write registers the before/after document hash plus who did it, which is
what turns "I fixed a typo" into something reviewable.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def record(
    conn: sqlite3.Connection,
    station_id: str,
    year: int,
    month: int,
    day: int,
    *,
    actor: str,
    sha256_before: str | None,
    sha256_after: str,
    summary: str = "",
) -> None:
    """Append one version row. Never raises on a missing actor."""
    conn.execute(
        "INSERT INTO document_versions"
        " (station_id, year, month, day, at, actor,"
        "  sha256_antes, sha256_despues, resumen_cambio)"
        " VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)",
        (station_id, int(year), int(month), int(day), actor or "",
         sha256_before, sha256_after, summary),
    )


def list_versions(
    conn: sqlite3.Connection, station_id: str, year: int, month: int, day: int
) -> list[dict[str, Any]]:
    """Newest first, as the audit screen shows them."""
    rows = conn.execute(
        "SELECT at, actor, sha256_antes, sha256_despues, resumen_cambio"
        " FROM document_versions"
        " WHERE station_id = ? AND year = ? AND month = ? AND day = ?"
        " ORDER BY id DESC",
        (station_id, int(year), int(month), int(day)),
    ).fetchall()
    return [dict(row) for row in rows]


def count(conn: sqlite3.Connection, station_id: str, year: int, month: int, day: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM document_versions"
        " WHERE station_id = ? AND year = ? AND month = ? AND day = ?",
        (station_id, int(year), int(month), int(day)),
    ).fetchone()
    return int(row[0]) if row else 0


__all__ = ["count", "list_versions", "record"]
