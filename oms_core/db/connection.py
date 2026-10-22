"""Connection factory with the per-connection PRAGMAs from the OLD oracle.

Mirrors ``OLD frontend/src-tauri/src/db.rs::init_db``: every connection of the
pool got WAL and foreign_keys via ``with_init``; here every connection opened
through :func:`connect` gets the same treatment. The path is always a plain
parameter — no Tauri app handle, no global state (ADR-03).
"""

import sqlite3
from pathlib import Path

BUSY_TIMEOUT_MS = 5000


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open an SQLite connection with the Neo Arca contract enforced."""
    conn = sqlite3.connect(str(db_path), timeout=BUSY_TIMEOUT_MS / 1000.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn
