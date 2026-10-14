"""F1 migrations: numbered chain mirroring OLD db.rs order.

Covers: fresh DB to latest, station seed, PRAGMAs, index set, re-run
idempotency, and the legacy upgrade path (pre-migration audit tables dropped,
duplicate error_marks collapsed before the unique barrier).
"""

import sqlite3

import pytest

from oms_core.db import migrations
from oms_core.db.connection import connect

EXPECTED_TABLES = {
    "users",
    "stations",
    "summary_logs",
    "error_marks",
    "corrections",
    "app_config",
    "sync_pending",
    "observations",
}

EXPECTED_INDEXES = {
    "idx_error_marks_station_fecha",
    "idx_corrections_station_fecha",
    "idx_summary_logs_station_period",
    "uq_error_marks_slot",
    "idx_sync_pending_unsent",
    "uq_summary_logs_doc",
    "idx_observations_station_fecha",
}


def test_fresh_db_reaches_latest_version(tmp_path):
    conn = connect(tmp_path / "fresh.db")
    migrations.migrate(conn)
    assert migrations.LATEST_VERSION == 5
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrations.LATEST_VERSION
    conn.close()


def test_fresh_db_has_all_tables_and_indexes(tmp_path):
    conn = connect(tmp_path / "fresh.db")
    migrations.migrate(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert tables == EXPECTED_TABLES
    assert EXPECTED_INDEXES <= indexes
    conn.close()


def test_fresh_db_seed_stations(tmp_path):
    """The 15 seed stations from db.rs must be present after migration."""
    conn = connect(tmp_path / "fresh.db")
    migrations.migrate(conn)
    count = conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    assert count == 15
    row = conn.execute(
        "SELECT name, provincia, latitud, longitud, elevacion, ch, is_active "
        "FROM stations WHERE id = '78451'"
    ).fetchone()
    assert tuple(row) == ("Monte Cristi", "Monte Cristi", 19.8499, -71.6535, 8.0, 0.5, 1)
    row = conn.execute("SELECT ch FROM stations WHERE id = '78460'").fetchone()
    assert tuple(row) == (19.8,)
    conn.close()


def test_connection_pragmas(tmp_path):
    """WAL + foreign_keys + busy_timeout must be set by connect() (per-connection)."""
    db_path = tmp_path / "pragma.db"
    conn = connect(db_path)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "fresh.db")
    migrations.migrate(conn)
    migrations.migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrations.LATEST_VERSION
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 15
    conn.close()


def test_legacy_upgrade_drops_audit_tables(tmp_path):
    """Simulate a legacy DB: pre-migration audit tables must be dropped by M002."""
    conn = connect(tmp_path / "legacy.db")
    migrations.migrate(conn, target=1)
    conn.execute("CREATE TABLE audit_logs (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE correction_requests (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO audit_logs (id) VALUES (1)")
    conn.commit()

    migrations.migrate(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert "audit_logs" not in tables
    assert "correction_requests" not in tables
    conn.close()


def test_legacy_upgrade_collapses_duplicate_error_marks(tmp_path):
    """R6: dedupe BEFORE the unique index so legacy DBs with races still upgrade."""
    conn = connect(tmp_path / "legacy.db")
    migrations.migrate(conn, target=2)
    conn.execute(
        "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, marcado_por) "
        "VALUES ('78451', '2024-03-15', '08', 't_max', 'lectura', 'tester')"
    )
    conn.execute(
        "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, marcado_por) "
        "VALUES ('78451', '2024-03-15', '08', 't_max', 'lectura', 'tester')"
    )
    conn.execute(
        "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, marcado_por) "
        "VALUES ('78451', '2024-03-15', '09', 't_max', 'lectura', 'tester')"
    )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM error_marks").fetchone()[0] == 3

    migrations.migrate(conn)

    rows = conn.execute(
        "SELECT hora, COUNT(*) FROM error_marks GROUP BY hora ORDER BY hora"
    ).fetchall()
    assert [tuple(r) for r in rows] == [("08", 1), ("09", 1)]
    kept = conn.execute(
        "SELECT MIN(id) FROM error_marks WHERE hora = '08'"
    ).fetchone()[0]
    assert conn.execute("SELECT id FROM error_marks WHERE hora = '08'").fetchone()[0] == kept

    # The unique barrier is now active: a duplicate slot is rejected.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, marcado_por) "
            "VALUES ('78451', '2024-03-15', '08', 't_max', 'lectura', 'tester')"
        )
    conn.close()


def test_legacy_upgrade_summary_logs_gains_doc_columns(tmp_path):
    """M005 extends the legacy summary_logs table with the doc columns in place."""
    conn = connect(tmp_path / "legacy.db")
    migrations.migrate(conn, target=4)
    conn.execute(
        "INSERT INTO summary_logs (station_id, year, month, data) "
        "VALUES ('78451', 2025, 5, '{}')"
    )
    conn.commit()

    migrations.migrate(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(summary_logs)")}
    assert {"kind", "day", "sha256"} <= columns
    row = conn.execute(
        "SELECT kind, day FROM summary_logs WHERE station_id = '78451'"
    ).fetchone()
    assert tuple(row) == ("mensual", 0)
    conn.close()
