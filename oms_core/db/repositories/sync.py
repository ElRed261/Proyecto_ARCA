"""sync_pending queue repository.

Table and enqueue semantics are verbatim ports of
``OLD .../sync_queue.rs`` (MIGATION_SQL + enqueue_pending). The retry pass
with backoff is ported in F7; the queue itself becomes durable in F1.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class SyncRow:
    module: str
    station_code: str
    relative_path: str
    source_path: str


@dataclass(frozen=True)
class SyncErrorRow:
    station_code: str
    relative_path: str
    detail: str


@dataclass(frozen=True)
class SyncStatus:
    pending: int
    synced: int
    last_attempt: str | None
    last_errors: list[SyncErrorRow]


def enqueue_pending(
    conn: sqlite3.Connection, row: SyncRow, sha256: str | None
) -> bool:
    """Enqueue a row with the source file sha256 (INSERT OR IGNORE: unique by
    (module, station_code, relative_path), avoids duplicates between saves).
    Returns True when a new row was inserted."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO sync_pending"
        " (module, station_code, relative_path, source_path, sha256)"
        " VALUES (?, ?, ?, ?, ?)",
        (row.module, row.station_code, row.relative_path, row.source_path, sha256),
    )
    conn.commit()
    return cur.rowcount == 1


def record_attempt(conn: sqlite3.Connection, row_id: int, *, error: str | None) -> None:
    """Register one retry pass result (attempts, timestamp, last error)."""
    conn.execute(
        "UPDATE sync_pending SET attempts = attempts + 1, last_error = ?,"
        " last_attempt_at = CURRENT_TIMESTAMP, last_attempt_ms = ? WHERE id = ?",
        (error, int(time.time() * 1000), row_id),
    )
    conn.commit()


def mark_synced(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute(
        "UPDATE sync_pending SET synced_at = CURRENT_TIMESTAMP WHERE id = ?", (row_id,)
    )
    conn.commit()


def get_sync_status(conn: sqlite3.Connection) -> SyncStatus:
    """Aggregated status for the sync panel (P3.4 port)."""
    pending = int(
        conn.execute(
            "SELECT COUNT(*) FROM sync_pending WHERE synced_at IS NULL"
        ).fetchone()[0]
    )
    synced = int(
        conn.execute(
            "SELECT COUNT(*) FROM sync_pending WHERE synced_at IS NOT NULL"
        ).fetchone()[0]
    )
    last_row = conn.execute(
        "SELECT MAX(last_attempt_at) FROM sync_pending WHERE last_attempt_at IS NOT NULL"
    ).fetchone()
    last_attempt = last_row[0] if last_row else None
    error_rows = conn.execute(
        "SELECT station_code, relative_path, IFNULL(last_error,'') FROM sync_pending"
        " WHERE synced_at IS NULL AND last_error IS NOT NULL"
        " ORDER BY last_attempt_at DESC LIMIT 5"
    ).fetchall()
    return SyncStatus(
        pending=pending,
        synced=synced,
        last_attempt=last_attempt,
        last_errors=[
            SyncErrorRow(
                station_code=row["station_code"],
                relative_path=row["relative_path"],
                detail=row[2],
            )
            for row in error_rows
        ],
    )
