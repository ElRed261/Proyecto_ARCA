"""app_config key/value store (db.rs M1). Also backs the PathProfile used by
oms_core.paths under the 'path_config' key."""

from __future__ import annotations

import sqlite3


def get(conn: sqlite3.Connection, key: str) -> str | None:
    # Index-based access: repositories accept connections with any row factory.
    row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Insert or replace a setting, refreshing updated_at (Rust set_path_config_db)."""
    conn.execute(
        "INSERT OR REPLACE INTO app_config (key, value, updated_at)"
        " VALUES (?, ?, CURRENT_TIMESTAMP)",
        (key, value),
    )
    conn.commit()
