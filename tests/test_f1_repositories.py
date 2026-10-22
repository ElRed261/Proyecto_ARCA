"""F1 repositories: CRUD, unique rejections and audit queries mirroring the OLD
Rust repositories (db.rs schema + sqlite_audit_repository.rs queries).

Every observable rule here mirrors a query or constraint in the OLD sources.
"""

import sqlite3

import pytest

from oms_core.db.repositories import (
    app_config,
    audit,
    observations,
    stations,
    summaries,
    sync,
    users,
)
from oms_core.db.repositories.audit import MarkConflictError
from oms_core.db.repositories.observations import Observation

# --------------------------------------------------------------------------
# users
# --------------------------------------------------------------------------


def test_user_roundtrip(fresh_db):
    uid = users.add_user(fresh_db, "admin@arca.rd", "hash1", "admin")
    got = users.get_user_by_email(fresh_db, "admin@arca.rd")
    assert got is not None
    assert got.id == uid
    assert got.email == "admin@arca.rd"
    assert got.password_hash == "hash1"
    assert got.role == "admin"
    assert got.is_active is True


def test_user_duplicate_email_rejected(fresh_db):
    users.add_user(fresh_db, "admin@arca.rd", "hash1", "admin")
    with pytest.raises(sqlite3.IntegrityError):
        users.add_user(fresh_db, "admin@arca.rd", "hash2", "observador")


def test_user_set_active_and_password(fresh_db):
    uid = users.add_user(fresh_db, "obs@arca.rd", "hash1", "observador")
    users.set_user_active(fresh_db, uid, False)
    assert users.get_user_by_email(fresh_db, "obs@arca.rd").is_active is False
    users.update_user_password(fresh_db, uid, "hash2")
    assert users.get_user_by_email(fresh_db, "obs@arca.rd").password_hash == "hash2"


def test_user_get_missing_returns_none(fresh_db):
    assert users.get_user_by_email(fresh_db, "no@arca.rd") is None
    assert users.get_user(fresh_db, 999) is None


def test_user_list_excludes_inactive_by_default(fresh_db):
    uid = users.add_user(fresh_db, "a@arca.rd", "h", "admin")
    users.add_user(fresh_db, "b@arca.rd", "h", "observador")
    users.set_user_active(fresh_db, uid, False)
    assert [u.email for u in users.list_users(fresh_db)] == ["b@arca.rd"]
    assert len(users.list_users(fresh_db, include_inactive=True)) == 2


# --------------------------------------------------------------------------
# stations
# --------------------------------------------------------------------------


def test_station_seed_present(fresh_db):
    assert len(stations.list_stations(fresh_db)) == 15
    st = stations.get_station(fresh_db, "MDCY")
    assert st is not None
    assert st.name == "Catey"
    assert st.ch == 0.8


def test_station_add_and_get_missing(fresh_db):
    assert stations.get_station(fresh_db, "XXXXX") is None
    stations.add_station(
        fresh_db,
        id="MDJB",
        name="Jimaní 2",
        provincia="Independencia",
        latitud=18.5,
        longitud=-71.9,
        elevacion=45.0,
        ch=4.8,
    )
    st = stations.get_station(fresh_db, "MDJB")
    assert st.name == "Jimaní 2"
    with pytest.raises(sqlite3.IntegrityError):
        stations.add_station(
            fresh_db,
            id="MDJB",
            name="dup",
            provincia="x",
            latitud=0,
            longitud=0,
            elevacion=0,
            ch=0,
        )


# --------------------------------------------------------------------------
# observations (NEW table — UNIQUE(station_id, fecha, hora))
# --------------------------------------------------------------------------


def _obs(hora="06Z", **overrides):
    base = {
        "station_id": "78451",
        "fecha": "2025-05-07",
        "hora": hora,
        "p_est": 1012.6,
        "p_nmm": 1014.2,
        "rocio": 22.6,
        "t_vapor": 26.7,
        "hr": 86.8,
        "v_dir_deg": 70.0,
        "v_vel": 1.9,
        "observador": "Juan",
        "source_sha256": "a" * 64,
    }
    base.update(overrides)
    return Observation(**base)


def test_observation_upsert_and_get_day(fresh_db):
    observations.upsert_observation(fresh_db, _obs())
    observations.upsert_observation(fresh_db, _obs(hora="09Z", p_est=1013.0))
    rows = observations.get_day(fresh_db, "78451", "2025-05-07")
    assert [r.hora for r in rows] == ["06Z", "09Z"]
    assert rows[0].p_est == 1012.6
    assert rows[0].observador == "Juan"


def test_observation_unique_rejection(fresh_db):
    observations.upsert_observation(fresh_db, _obs())
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.execute(
            "INSERT INTO observations (station_id, fecha, hora, source_sha256) "
            "VALUES ('78451', '2025-05-07', '06Z', 'b')"
        )


def test_observation_upsert_replaces_values(fresh_db):
    """Re-running the importer must overwrite, not duplicate (idempotency)."""
    observations.upsert_observation(fresh_db, _obs())
    observations.upsert_observation(fresh_db, _obs(p_est=999.0, observador=""))
    rows = observations.get_day(fresh_db, "78451", "2025-05-07")
    assert len(rows) == 1
    assert rows[0].p_est == 999.0
    assert rows[0].observador == ""


def test_observation_null_fields(fresh_db):
    observations.upsert_observation(
        fresh_db,
        _obs(p_est=None, p_nmm=None, rocio=None, t_vapor=None, hr=None, v_dir_deg=None, v_vel=None),
    )
    row = observations.get_day(fresh_db, "78451", "2025-05-07")[0]
    assert row.p_est is None and row.hr is None


def test_observation_get_month_and_count(fresh_db):
    observations.upsert_observation(fresh_db, _obs())
    observations.upsert_observation(fresh_db, _obs(hora="09Z"))
    observations.upsert_observation(fresh_db, _obs(hora="12Z", fecha="2025-06-01"))
    assert len(observations.get_month(fresh_db, "78451", 2025, 5)) == 2
    assert observations.count(fresh_db) == 3


def test_observation_fk_requires_station(fresh_db):
    with pytest.raises(sqlite3.IntegrityError):
        observations.upsert_observation(fresh_db, _obs(station_id="NOPE"))


# --------------------------------------------------------------------------
# summary_logs (verbatim docs)
# --------------------------------------------------------------------------


def test_summary_doc_upsert_idempotent(fresh_db):
    summaries.upsert_summary_doc(
        fresh_db,
        station_id="78485",
        year=2025,
        month=10,
        day=0,
        kind="resumen",
        data='{"meta": {}}',
        sha256="c" * 64,
    )
    summaries.upsert_summary_doc(
        fresh_db,
        station_id="78485",
        year=2025,
        month=10,
        day=0,
        kind="resumen",
        data='{"meta": {}, "nuevo": 1}',
        sha256="d" * 64,
    )
    doc = summaries.get_summary_doc(fresh_db, "78485", 2025, 10, "resumen")
    assert doc == '{"meta": {}, "nuevo": 1}'
    assert summaries.count_docs(fresh_db) == 1


def test_summary_daily_doc_separate_natural_key(fresh_db):
    summaries.upsert_summary_doc(
        fresh_db,
        station_id="78451",  # seeded station: foreign key satisfied
        year=2025,
        month=6,
        day=8,
        kind="diario",
        data="{}",
        sha256="e" * 64,
    )
    assert summaries.get_summary_doc(fresh_db, "78451", 2025, 6, "diario", day=8) == "{}"
    assert summaries.get_summary_doc(fresh_db, "78451", 2025, 6, "resumen") is None
    assert len(summaries.list_docs(fresh_db, kind="diario")) == 1


# --------------------------------------------------------------------------
# error_marks + corrections (mirror sqlite_audit_repository.rs)
# --------------------------------------------------------------------------


def _mark(hora="08", **overrides):
    base = {
        "station_id": "78451",
        "fecha": "2024-03-15",
        "hora": hora,
        "campo": "t_max",
        "tipo_error": "lectura",
        "nota": None,
        "marcado_por": "tester",
    }
    base.update(overrides)
    return base


def test_mark_error_and_get(fresh_db):
    mid = audit.mark_error(fresh_db, **_mark())
    assert mid > 0
    marks = audit.get_error_marks(fresh_db, "78451", "2024-03-15")
    assert len(marks) == 1
    assert marks[0].campo == "t_max"
    assert marks[0].created_at is not None


def test_mark_error_duplicate_barrier(fresh_db):
    """Same check as the OLD Rust test: duplicate slot is a validation error."""
    audit.mark_error(fresh_db, **_mark())
    with pytest.raises(MarkConflictError) as exc:
        audit.mark_error(fresh_db, **_mark())
    assert "ya está marcado" in str(exc.value)
    # A different hora still inserts.
    assert audit.mark_error(fresh_db, **_mark(hora="09")) > 0
    assert len(audit.get_error_marks(fresh_db, "78451", "2024-03-15")) == 2


def test_unmark_and_get_mark_details(fresh_db):
    mid = audit.mark_error(fresh_db, **_mark())
    assert audit.get_mark_details(fresh_db, mid) == (
        "78451",
        "2024-03-15",
        "08",
        "t_max",
    )
    audit.unmark_error(fresh_db, mid)
    assert audit.get_error_marks(fresh_db, "78451", "2024-03-15") == []
    assert audit.get_mark_details(fresh_db, mid) is None


def test_update_mark_note(fresh_db):
    mid = audit.mark_error(fresh_db, **_mark())
    audit.update_mark_note(fresh_db, mid, "revisado por supervisor")
    assert audit.get_error_marks(fresh_db, "78451", "2024-03-15")[0].nota == "revisado por supervisor"
    audit.update_mark_note(fresh_db, mid, None)
    assert audit.get_error_marks(fresh_db, "78451", "2024-03-15")[0].nota is None


def _corr(**overrides):
    base = {
        "station_id": "78451",
        "fecha": "2024-03-15",
        "hora": "08",
        "campo": "t_max",
        "valor_original": "27.0",
        "valor_corregido": "28.0",
        "justificacion": "lectura mal copiada",
        "corregido_por": "qc1",
        "aprobado_por": None,
        "estado": "pendiente",
    }
    base.update(overrides)
    return base


def test_propose_correction_replaces_previous(fresh_db):
    """Rust propose_correction deletes prior corrections for the slot first."""
    first = audit.propose_correction(fresh_db, **_corr())
    assert first > 0
    second = audit.propose_correction(fresh_db, **_corr(valor_corregido="29.0"))
    assert second > 0 and second != first
    rows = audit.get_corrections(fresh_db, "78451", "2024-03-15")
    assert len(rows) == 1
    assert rows[0].valor_corregido == "29.0"


def test_delete_corrections_by_mark(fresh_db):
    audit.mark_error(fresh_db, **_mark())
    audit.propose_correction(fresh_db, **_corr())
    audit.delete_corrections_by_mark(fresh_db, "78451", "2024-03-15", "08", "t_max")
    assert audit.get_corrections(fresh_db, "78451", "2024-03-15") == []


def test_approved_corrections_for_date(fresh_db):
    audit.propose_correction(fresh_db, **_corr(estado="aprobado", aprobado_por="admin"))
    audit.propose_correction(fresh_db, **_corr(hora="09", estado="pendiente"))
    approved = audit.get_approved_corrections_for_date(fresh_db, "78451", "2024-03-15")
    assert approved == [("08", "t_max", "28.0")]


def test_error_report_left_join(fresh_db):
    audit.mark_error(fresh_db, **_mark())
    audit.mark_error(fresh_db, **_mark(hora="09"))
    audit.propose_correction(fresh_db, **_corr(hora="08"))
    report = audit.get_error_report(fresh_db, station_id="78451")
    assert len(report) == 2
    by_hora = {r.hora: r for r in report}
    assert by_hora["08"].valor_corregido == "28.0"
    assert by_hora["09"].valor_corregido is None
    assert by_hora["08"].estado == "pendiente"


def test_error_report_month_filter(fresh_db):
    audit.mark_error(fresh_db, **_mark())
    audit.mark_error(fresh_db, **_mark(hora="09", fecha="2024-04-02"))
    assert len(audit.get_error_report(fresh_db, year="2024", month="03")) == 1
    assert len(audit.get_error_report(fresh_db, year="2024")) == 2
    assert len(audit.get_error_report(fresh_db, month="04")) == 1
    assert len(audit.get_error_report(fresh_db)) == 2


def test_daily_counts(fresh_db):
    audit.mark_error(fresh_db, **_mark())
    audit.mark_error(fresh_db, **_mark(hora="09"))
    audit.mark_error(fresh_db, **_mark(hora="10", fecha="2024-04-02"))
    audit.propose_correction(fresh_db, **_corr())
    errs = audit.get_daily_error_counts(fresh_db, "78451", "2024-03-%")
    assert errs == {"2024-03-15": 2}
    corrs = audit.get_daily_correction_counts(fresh_db, "78451", "2024-03-%")
    assert corrs == {"2024-03-15": 1}


def test_person_summary(fresh_db):
    audit.mark_error(fresh_db, **_mark())
    audit.mark_error(fresh_db, **_mark(hora="09"))
    audit.propose_correction(fresh_db, **_corr())
    audit.propose_correction(
        fresh_db,
        **_corr(hora="09", corregido_por="qc2", estado="aprobado", aprobado_por="admin"),
    )
    rows = audit.get_person_summary(fresh_db, year="2024", month="03")
    by_person = {r.persona: r for r in rows}
    assert by_person["tester"].errores_marcados == 2
    assert by_person["qc1"].correcciones_propuestas == 1
    assert by_person["qc1"].correcciones_aprobadas == 0
    assert by_person["qc2"].correcciones_aprobadas == 1


# --------------------------------------------------------------------------
# app_config KV
# --------------------------------------------------------------------------


def test_config_roundtrip(fresh_db):
    assert app_config.get(fresh_db, "path_config") is None
    app_config.set(fresh_db, "path_config", '{"offline_root": "/data"}')
    assert app_config.get(fresh_db, "path_config") == '{"offline_root": "/data"}'
    app_config.set(fresh_db, "path_config", '{"offline_root": "/other"}')
    assert app_config.get(fresh_db, "path_config") == '{"offline_root": "/other"}'
    row = fresh_db.execute(
        "SELECT updated_at FROM app_config WHERE key = 'path_config'"
    ).fetchone()
    assert row is not None


# --------------------------------------------------------------------------
# sync_pending (mirror sync_queue.rs MIGATION_SQL + enqueue semantics)
# --------------------------------------------------------------------------


def test_sync_enqueue_ignores_duplicates(fresh_db):
    row = sync.SyncRow(
        module="synop",
        station_code="78451",
        relative_path="78451/2025/05/x.json",
        source_path="/tmp/x.json",
    )
    sha = "f" * 64
    assert sync.enqueue_pending(fresh_db, row, sha) is True
    assert sync.enqueue_pending(fresh_db, row, sha) is False
    status = sync.get_sync_status(fresh_db)
    assert status.pending == 1
    assert status.synced == 0
    assert status.last_errors == []


def test_sync_record_attempt_and_mark_synced(fresh_db):
    row = sync.SyncRow(
        module="synop",
        station_code="78451",
        relative_path="78451/2025/05/x.json",
        source_path="/tmp/x.json",
    )
    sync.enqueue_pending(fresh_db, row, "f" * 64)
    sid = fresh_db.execute("SELECT id FROM sync_pending").fetchone()[0]

    sync.record_attempt(fresh_db, sid, error="upload failed")
    status = sync.get_sync_status(fresh_db)
    assert status.pending == 1
    assert len(status.last_errors) == 1
    assert status.last_errors[0].detail == "upload failed"
    assert status.last_attempt is not None

    sync.mark_synced(fresh_db, sid)
    status = sync.get_sync_status(fresh_db)
    assert status.pending == 0
    assert status.synced == 1
