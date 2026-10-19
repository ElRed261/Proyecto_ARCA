"""Numbered SQLite migrations mirroring ``OLD frontend/src-tauri/src/db.rs``.

The chain replicates the rusqlite_migration order exactly:

- M001: users, stations (+ the 15 seed rows), summary_logs, error_marks,
  corrections, app_config and the three helper indexes.
- M002: DROP audit_logs / correction_requests (pre-migration leftovers).
- M003: collapse duplicate error_marks BEFORE creating the unique barrier
  ``uq_error_marks_slot`` (R6: the old check-then-insert race produced
  duplicates that would break DBs existing at upgrade time).
- M004: the offline-first sync queue (verbatim from
  ``OLD .../sync_queue.rs::MIGATION_SQL``).
- M005 (Neo Arca, new): the ``observations`` table keyed by
  ``UNIQUE(station_id, fecha, hora)`` and the summary_logs doc columns
  (``kind``/``day``/``sha256``) with dedupe-before-unique, same pattern as
  M003.

Version tracking uses ``PRAGMA user_version`` (a number is all this chain
needs; no external migration framework, per F1 scope).
"""

from __future__ import annotations

import sqlite3

M001_UP = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provincia TEXT NOT NULL,
    latitud REAL NOT NULL,
    longitud REAL NOT NULL,
    elevacion REAL NOT NULL,
    ch REAL NOT NULL,
    is_active INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO stations (id, name, provincia, latitud, longitud, elevacion, ch) VALUES
('78451', 'Monte Cristi', 'Monte Cristi', 19.8499, -71.6535, 8.0, 0.5),
('MDCY', 'Catey', 'Samaná', 19.267, -69.7337, 4.0, 0.8),
('78457', 'Puerto Plata', 'Puerto Plata', 19.7542, -70.5632, 16.0, 1.0),
('78482', 'Barahona', 'Barahona', 18.24861, -71.12288, 19.5, 1.2),
('78467', 'Sabana de la mar', 'Hato Mayor', 19.0527, -69.3888, 11.0, 1.2),
('78464', 'Cabrera', 'María Trinidad Sánchez', 19.6444, -69.9063, 18.0, 1.5),
('78486', 'Central', 'Santo Domingo', 18.4734, -69.8705, 14.0, 1.6),
('78485', 'Las américas', 'Santo Domingo', 18.4331, -69.6796, 7.0, 2.0),
('78479', 'Punta Cana', 'La Altagracia', 18.546, -68.3594, 7.0, 2.0),
('78484', 'El Higüero', 'Santo Domingo', 18.57696, -69.98158, 27.0, 3.5),
('78466', 'Arroyo Barril', 'Samaná', 19.2005, -69.43144, 49.4, 3.5),
('78480', 'Jimaní', 'Independencia', 18.4928, -71.853, 45.0, 4.8),
('78473', 'Bayaguana', 'Monte Plata', 18.7422, -69.6308, 53.0, 6.0),
('78488', 'La Romana', 'La Romana', 18.4485, -68.9093, 62.0, 8.5),
('78460', 'Santiago', 'Santiago', 19.4031, -70.5978, 170.0, 19.8);

CREATE TABLE IF NOT EXISTS summary_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

CREATE TABLE IF NOT EXISTS error_marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    campo TEXT NOT NULL,
    tipo_error TEXT NOT NULL,
    nota TEXT,
    marcado_por TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    campo TEXT NOT NULL,
    valor_original TEXT NOT NULL,
    valor_corregido TEXT NOT NULL,
    justificacion TEXT NOT NULL,
    corregido_por TEXT NOT NULL,
    aprobado_por TEXT,
    estado TEXT DEFAULT 'pendiente',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_error_marks_station_fecha ON error_marks(station_id, fecha);
CREATE INDEX IF NOT EXISTS idx_corrections_station_fecha ON corrections(station_id, fecha);
CREATE INDEX IF NOT EXISTS idx_summary_logs_station_period ON summary_logs(station_id, year, month);
"""

M002_UP = """
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS correction_requests;
"""

# R6: unique barrier against duplicate marks (the check-then-insert race).
# Deduplicate BEFORE creating the index so existing DBs keep upgrading.
M003_UP = """
DELETE FROM error_marks WHERE id NOT IN (
    SELECT MIN(id) FROM error_marks GROUP BY station_id, fecha, hora, campo
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_error_marks_slot
    ON error_marks(station_id, fecha, hora, campo);
"""

# Verbatim from OLD .../sync_queue.rs::MIGATION_SQL (P3: offline-first queue).
M004_UP = """
CREATE TABLE IF NOT EXISTS sync_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module TEXT NOT NULL,
    station_code TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    source_path TEXT NOT NULL,
    sha256 TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    last_attempt_at DATETIME,
    last_attempt_ms INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    synced_at DATETIME,
    UNIQUE(module, station_code, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_sync_pending_unsent ON sync_pending(synced_at, created_at);
"""

# Neo Arca core: hourly observations (one row per standard synoptic hour per
# day) plus summary_logs extended to hold verbatim documents (kind='diario'
# for the full legacy daily JSON, kind='resumen' for the monthly summary).
# day=0 denotes a whole-period (monthly) document.
M005_UP = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL REFERENCES stations(id),
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    p_est REAL,
    p_nmm REAL,
    rocio REAL,
    t_vapor REAL,
    hr REAL,
    v_dir_deg REAL,
    v_vel REAL,
    observador TEXT NOT NULL DEFAULT '',
    source_sha256 TEXT NOT NULL,
    UNIQUE(station_id, fecha, hora)
);
CREATE INDEX IF NOT EXISTS idx_observations_station_fecha
    ON observations(station_id, fecha);

ALTER TABLE summary_logs ADD COLUMN kind TEXT NOT NULL DEFAULT 'mensual';
ALTER TABLE summary_logs ADD COLUMN day INTEGER NOT NULL DEFAULT 0;
ALTER TABLE summary_logs ADD COLUMN sha256 TEXT;

DELETE FROM summary_logs WHERE id NOT IN (
    SELECT MAX(id) FROM summary_logs GROUP BY station_id, year, month, kind, day
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_summary_logs_doc
    ON summary_logs(station_id, year, month, kind, day);
"""

M006_UP = """
CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    sha256_antes TEXT,
    sha256_despues TEXT NOT NULL,
    resumen_cambio TEXT
);
CREATE INDEX IF NOT EXISTS ix_document_versions_day
    ON document_versions(station_id, year, month, day);
"""

MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (1, "initial schema (port of db.rs M1)", M001_UP),
    (2, "drop legacy audit tables (port of db.rs M2)", M002_UP),
    (3, "error_marks dedupe + unique barrier uq_error_marks_slot", M003_UP),
    (4, "sync_pending queue (sync_queue.rs MIGATION_SQL)", M004_UP),
    (5, "observations table + summary_logs doc columns", M005_UP),
    (6, "document_versions trail (rule R4)", M006_UP),
)

LATEST_VERSION = MIGRATIONS[-1][0]


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _statements(sql: str) -> list[str]:
    """Split a migration script into statements.

    sqlite3.executescript() implicitly commits before running, which would
    break per-migration atomicity; our scripts never contain ';' inside a
    literal, so a plain split is exact here.
    """
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def migrate(conn: sqlite3.Connection, target: int | None = None) -> None:
    """Apply pending migrations in order, one transaction per migration."""
    destination = LATEST_VERSION if target is None else target
    if destination > LATEST_VERSION:
        raise ValueError(f"unknown migration version {destination}")

    for version, _name, sql in MIGRATIONS:
        if version <= current_version(conn) or version > destination:
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _statements(sql):
                conn.execute(statement)
            # user_version cannot take a bound parameter; the value is a
            # hardcoded constant from this module, never user input.
            conn.execute(f"PRAGMA user_version={version}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
