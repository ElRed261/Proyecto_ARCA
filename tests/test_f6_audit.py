"""F6 — audit service tests (test-first, RED before implementation).

Oracle: OLD/frontend/src-tauri/src/audit/{service,commands}.rs +
sqlite_audit_repository.rs (read-only). The daily document comes from the F1
``summary_logs`` repo (kind='diario'); the filesystem base dir is always an
explicit parameter and TESTS ONLY touch tmp copies, never OLD/ or originals.
"""

import json
from pathlib import Path

import pytest

from oms_core.db.repositories import audit as audit_repo
from oms_core.db.repositories import summaries as summaries_repo

STATION = "78485"
FECHA = "2025-12-08"  # YYYY-MM-DD
FILENAME = "7848508122025.json"

DAY_DOC = {
    "meta": {"estacion": STATION, "fecha": "08122025", "observador": ""},
    "horas": {
        "06Z": {
            "observador": "Juan Perez",
            "datos": {"ts": "23.2", "th": "22.3", "pres_est": "1025.3", "correc_alt": "1.6"},
            "synop": {"Nddff": "81005"},
            "calculado": {},
        },
        "12Z": {
            "observador": "",
            "datos": {"ts": "25.0", "th": "23.0", "pres_est": "1024.0", "correc_alt": "1.6"},
            "synop": {},
            "calculado": {},
        },
    },
}


def _seed_diario(conn, doc=None):
    doc = doc if doc is not None else DAY_DOC
    text = json.dumps(doc, ensure_ascii=False)
    summaries_repo.upsert_summary_doc(
        conn,
        station_id=STATION,
        year=2025,
        month=12,
        kind="diario",
        data=text,
        sha256="seed",
        day=8,
    )


def _make_base(tmp_path: Path) -> Path:
    base = tmp_path / "synop"
    month_dir = base / STATION.lower() / "2025" / "12"
    month_dir.mkdir(parents=True)
    doc = {
        "meta": {"estacion": STATION, "fecha": "08122025", "observador": "Juan Perez"},
        "horas": {
            "06Z": {
                "observador": "Juan Perez",
                "datos": {
                    "ts": "23.2",
                    "th": "22.3",
                    "pres_est": "1025.3",
                    "p3": "1022.3",
                    "p24": "1024.1",
                    "correc_alt": "1.6",
                },
                "synop": {"Nddff": "81005"},
                "calculado": {},
            }
        },
    }
    (month_dir / FILENAME).write_text(json.dumps(doc), encoding="utf-8")
    return base


# ---------------------------------------------------------------- mappers


def test_month_name_to_num_spanish_and_english():
    from oms_core.services import audit

    assert audit.month_name_to_num("enero") == "01"
    assert audit.month_name_to_num("Mayo") == "05"
    assert audit.month_name_to_num("SEPTIEMBRE") == "09"
    assert audit.month_name_to_num("diciembre") == "12"
    assert audit.month_name_to_num("january") == "01"
    assert audit.month_name_to_num("December") == "12"
    assert audit.month_name_to_num("foo") is None
    assert audit.month_name_to_num("05") is None


def test_frontend_field_mappers_match_oracle():
    from oms_core.services import audit

    assert audit.map_datos_field("ts") == "ts"
    assert audit.map_datos_field("t_max") == "Tmax"
    assert audit.map_datos_field("ll") == "LL"
    assert audit.map_datos_field("correc_alt") == "correc_alt"
    assert audit.map_datos_field("nope") is None
    assert audit.map_calculado_field("pres_nmm") == "pres_nmm"
    assert audit.map_calculado_field("punto_rocio") == "pr"
    assert audit.map_calculado_field("tension_vapor") == "tv"
    assert audit.map_calculado_field("humedad_relativa") == "hr"
    assert audit.map_calculado_field("diferencia") == "dif"
    assert audit.map_calculado_field("ts") is None


# ---------------------------------------------------------------- browse


def test_browse_stations_years_months_days(fresh_db, tmp_path):
    from oms_core.services import audit

    base = _make_base(tmp_path)
    stations = audit.browse_stations(base, fresh_db)
    assert stations == [{"code": STATION, "name": "Las américas"}]

    assert audit.browse_years(base, STATION) == ["2025"]

    # legacy spanish month dir is listed by its number, pure read (no rename)
    legacy = base / STATION.lower() / "2025" / "mayo"
    legacy.mkdir(parents=True)
    (legacy / "x.json").write_text("{}", encoding="utf-8")
    months = audit.browse_months(base, STATION, "2025")
    assert months == ["05", "12"]
    assert legacy.exists()  # browse never migrates

    days = audit.browse_days(base, fresh_db, STATION, "2025", "12")
    assert len(days) == 1
    day = days[0]
    assert day["filename"] == FILENAME
    assert day["date"] == FECHA
    assert day["observador"] == "Juan Perez"
    assert day["horas_registradas"] == 1
    assert day["error_count"] == 0
    assert day["correction_count"] == 0


def test_browse_days_counts_come_from_db(fresh_db, tmp_path):
    from oms_core.services import audit

    base = _make_base(tmp_path)
    audit_repo.mark_error(
        fresh_db,
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@arca",
    )
    audit_repo.propose_correction(
        fresh_db,
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        valor_original="23.2",
        valor_corregido="23.5",
        justificacion="typo",
        corregido_por="auditor@arca",
        estado="aprobado",
        aprobado_por="auditor@arca",
    )
    (day,) = audit.browse_days(base, fresh_db, STATION, "2025", "12")
    assert day["error_count"] == 1
    assert day["correction_count"] == 1


# ---------------------------------------------------------------- load + auto-mark


def test_load_observation_flattens_diario_and_applies_approved_overlay(fresh_db):
    from oms_core.services import audit

    _seed_diario(fresh_db)
    audit_repo.propose_correction(
        fresh_db,
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        valor_original="23.2",
        valor_corregido="99.9",
        justificacion="oracle check",
        corregido_por="auditor@arca",
        estado="aprobado",
        aprobado_por="auditor@arca",
    )
    audit_repo.propose_correction(
        fresh_db,
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="th",
        valor_original="22.3",
        valor_corregido="11.1",
        justificacion="pending",
        corregido_por="auditor@arca",
        estado="pendiente",
    )
    data = audit.load_observation_with_audit(fresh_db, STATION, FECHA)
    assert data["observation"]["06Z"]["ts"] == "99.9"  # approved overlay wins
    assert data["observation"]["06Z"]["th"] == "22.3"  # pending ignored
    assert data["observation"]["06Z"]["observador"] == "Juan Perez"
    assert len(data["corrections"]) == 2


def test_load_observation_auto_marks_observer_less_hour(fresh_db):
    from oms_core.services import audit

    _seed_diario(fresh_db)
    data = audit.load_observation_with_audit(fresh_db, STATION, FECHA)
    auto = [m for m in data["error_marks"] if m["hora"] == "12Z" and m["campo"] == "observador"]
    assert len(auto) == 1
    assert auto[0]["tipo_error"] == "Falta nombre de observador"
    assert auto[0]["marcado_por"] == "Sistema de Calidad"
    # persisted: a second load does not duplicate the auto mark
    again = audit.load_observation_with_audit(fresh_db, STATION, FECHA)
    assert (
        len([m for m in again["error_marks"] if m["hora"] == "12Z" and m["campo"] == "observador"])
        == 1
    )
    # no auto mark on the hour that has an observer
    assert not [
        m for m in again["error_marks"] if m["hora"] == "06Z" and m["campo"] == "observador"
    ]


def test_load_observation_missing_day_raises(fresh_db):
    from oms_core.services import audit

    with pytest.raises(audit.AuditError):
        audit.load_observation_with_audit(fresh_db, STATION, "2025-01-01")


# ---------------------------------------------------------------- mark/unmark/note/propose/approve


def test_mark_duplicate_keeps_oracle_message(fresh_db):
    from oms_core.services import audit

    mark = audit.mark_error(
        fresh_db,
        role="admin",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@arca",
    )
    assert mark["id"] is not None
    with pytest.raises(audit_repo.MarkConflictError, match="Este campo ya está marcado como error"):
        audit.mark_error(
            fresh_db,
            role="control_calidad",
            station_id=STATION,
            fecha=FECHA,
            hora="06Z",
            campo="ts",
            tipo_error="Sintaxis",
            marcado_por="otro@arca",
        )


def test_unmark_removes_mark_and_slot_corrections(fresh_db):
    from oms_core.services import audit

    mark = audit.mark_error(
        fresh_db,
        role="admin",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@arca",
    )
    audit.propose_correction(
        fresh_db,
        role="admin",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        valor_original="23.2",
        valor_corregido="23.5",
        justificacion="j",
        corregido_por="auditor@arca",
    )
    assert audit.unmark_error(fresh_db, role="admin", mark_id=mark["id"]) is True
    assert audit_repo.get_error_marks(fresh_db, STATION, FECHA) == []
    assert audit_repo.get_corrections(fresh_db, STATION, FECHA) == []


def test_note_update_roundtrip(fresh_db):
    from oms_core.services import audit

    mark = audit.mark_error(
        fresh_db,
        role="admin",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@arca",
    )
    assert (
        audit.update_mark_note(fresh_db, role="admin", mark_id=mark["id"], nota="revisado") is True
    )
    (stored,) = audit_repo.get_error_marks(fresh_db, STATION, FECHA)
    assert stored.nota == "revisado"


def test_propose_starts_pending_and_approve_flips_estado(fresh_db):
    from oms_core.services import audit

    corr = audit.propose_correction(
        fresh_db,
        role="control_calidad",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        valor_original="23.2",
        valor_corregido="23.5",
        justificacion="typo",
        corregido_por="auditor@arca",
    )
    assert corr["estado"] == "pendiente"
    assert corr["aprobado_por"] is None
    approved = audit.approve_correction(
        fresh_db,
        role="admin",
        correction_id=corr["id"],
        aprobado_por="jefe@arca",
    )
    assert approved["estado"] == "aprobado"
    assert approved["aprobado_por"] == "jefe@arca"


# ---------------------------------------------------------------- round trip


def test_mark_propose_approve_export_roundtrip(fresh_db, tmp_path):
    from oms_core.services import audit

    base = _make_base(tmp_path)
    original_bytes = (base / STATION.lower() / "2025" / "12" / FILENAME).read_bytes()

    audit.mark_error(
        fresh_db,
        role="admin",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@arca",
    )
    corr = audit.propose_correction(
        fresh_db,
        role="admin",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        valor_original="23.2",
        valor_corregido="23.5",
        justificacion="typo",
        corregido_por="auditor@arca",
    )
    audit.approve_correction(
        fresh_db,
        role="admin",
        correction_id=corr["id"],
        aprobado_por="jefe@arca",
    )
    out = audit.export_corrected_json(fresh_db, base, STATION, FECHA)
    exported = json.loads(Path(out).read_text(encoding="utf-8"))
    assert exported["horas"]["06Z"]["datos"]["ts"] == "23.5"
    # original file untouched on disk
    assert (base / STATION.lower() / "2025" / "12" / FILENAME).read_bytes() == original_bytes
    # round 30 (owner option B): the corrected copy lives in its own tree,
    # correcciones/<year>/<month>/, never inside the synoptic archive
    assert Path(out).name == f"{STATION}08122025_cor.json"
    assert Path(out).parent.parent.parent.name == "correcciones"
    assert Path(out).parent.name == "12"


# ---------------------------------------------------------------- reports (hand-computed oracle)


def _seed_report_db(conn):
    audit_repo.mark_error(
        conn,
        station_id="78451",
        fecha="2025-06-10",
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="auditor@x",
    )
    audit_repo.mark_error(
        conn,
        station_id="78451",
        fecha="2025-06-10",
        hora="12Z",
        campo="th",
        tipo_error="Calculo",
        marcado_por="auditor@x",
    )
    audit_repo.mark_error(
        conn,
        station_id="78451",
        fecha="2025-06-11",
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="otro@y",
    )
    audit_repo.propose_correction(
        conn,
        station_id="78451",
        fecha="2025-06-10",
        hora="06Z",
        campo="ts",
        valor_original="20.0",
        valor_corregido="20.5",
        justificacion="j",
        corregido_por="auditor@x",
        estado="aprobado",
        aprobado_por="auditor@x",
    )
    audit_repo.propose_correction(
        conn,
        station_id="78451",
        fecha="2025-06-11",
        hora="06Z",
        campo="ts",
        valor_original="21.0",
        valor_corregido="21.5",
        justificacion="j",
        corregido_por="otro@y",
        estado="pendiente",
    )


def test_error_report_hand_computed_values(fresh_db):
    from oms_core.services import audit

    _seed_report_db(fresh_db)
    rows = audit.get_error_report(fresh_db, station_id="78451", year="2025", month="06")
    assert [(r["fecha"], r["hora"]) for r in rows] == [
        ("2025-06-11", "06Z"),
        ("2025-06-10", "06Z"),
        ("2025-06-10", "12Z"),
    ]
    by_slot = {(r["fecha"], r["hora"]): r for r in rows}
    assert by_slot[("2025-06-10", "06Z")]["valor_corregido"] == "20.5"
    assert by_slot[("2025-06-10", "06Z")]["estado"] == "aprobado"
    assert by_slot[("2025-06-10", "12Z")]["valor_corregido"] is None
    assert by_slot[("2025-06-11", "06Z")]["estado"] == "pendiente"


def test_person_summary_hand_computed_values(fresh_db):
    from oms_core.services import audit

    _seed_report_db(fresh_db)
    rows = audit.get_person_summary(fresh_db, station_id="78451", year="2025", month="06")
    by_person = {r["persona"]: r for r in rows}
    assert by_person["auditor@x"]["errores_marcados"] == 2
    assert by_person["auditor@x"]["correcciones_propuestas"] == 1
    assert by_person["auditor@x"]["correcciones_aprobadas"] == 1
    assert by_person["otro@y"]["errores_marcados"] == 1
    assert by_person["otro@y"]["correcciones_propuestas"] == 1
    assert by_person["otro@y"]["correcciones_aprobadas"] == 0
    assert rows[0]["persona"] == "auditor@x"  # sorted by errors desc


# ---------------------------------------------------------------- migration (tmp copies only)


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _make_legacy_tree(root: Path) -> None:
    (root / "st1" / "2025" / "mayo").mkdir(parents=True)
    (root / "st1" / "2025" / "mayo" / "a.json").write_text("{}", encoding="utf-8")
    (root / "st1" / "2025" / "enero").mkdir(parents=True)
    (root / "st1" / "2025" / "enero" / "b.json").write_text("{}", encoding="utf-8")
    # merge case: numeric dir already exists with a colliding file
    (root / "st2" / "2025" / "05").mkdir(parents=True)
    (root / "st2" / "2025" / "05" / "keep.json").write_text("new", encoding="utf-8")
    (root / "st2" / "2025" / "mayo").mkdir(parents=True)
    (root / "st2" / "2025" / "mayo" / "keep.json").write_text("old", encoding="utf-8")
    (root / "st2" / "2025" / "mayo" / "extra.json").write_text("old2", encoding="utf-8")
    # non-month dirs are ignored
    (root / "st2" / "2025" / "notas").mkdir(parents=True)
    (root / "st2" / "2025" / "notas" / "n.txt").write_text("x", encoding="utf-8")


def test_migrate_rename_and_merge_no_overwrite(tmp_path):
    from oms_core.services import audit

    root = tmp_path / "copy"
    _make_legacy_tree(root)
    stats = audit.migrate_legacy_month_dirs(root)
    assert stats == {"renamed_dirs": 2, "moved_files": 1}
    # rename case
    assert (root / "st1" / "2025" / "05" / "a.json").exists()
    assert not (root / "st1" / "2025" / "mayo").exists()
    assert (root / "st1" / "2025" / "01" / "b.json").exists()
    # merge case: colliding file NOT overwritten, extra moved, legacy kept (not empty)
    assert (root / "st2" / "2025" / "05" / "keep.json").read_text() == "new"
    assert (root / "st2" / "2025" / "05" / "extra.json").read_text() == "old2"
    assert (root / "st2" / "2025" / "mayo" / "keep.json").read_text() == "old"
    # ignored dir untouched
    assert (root / "st2" / "2025" / "notas" / "n.txt").exists()


def test_migrate_is_idempotent(tmp_path):
    from oms_core.services import audit

    root = tmp_path / "copy"
    _make_legacy_tree(root)
    audit.migrate_legacy_month_dirs(root)
    before = _tree(root)
    stats = audit.migrate_legacy_month_dirs(root)
    assert stats == {"renamed_dirs": 0, "moved_files": 0}
    assert _tree(root) == before


# ---------------------------------------------------------------- role gating (enforced boundary)


def test_encargado_is_denied_the_audit_service(fresh_db, tmp_path):
    from oms_core.services import audit

    base = _make_base(tmp_path)
    with pytest.raises(PermissionError, match="privilegios insuficientes"):
        audit.mark_error(
            fresh_db,
            role="encargado",
            station_id=STATION,
            fecha=FECHA,
            hora="06Z",
            campo="ts",
            tipo_error="Sintaxis",
            marcado_por="enc@arca",
        )
    with pytest.raises(PermissionError, match="privilegios insuficientes"):
        audit.export_corrected_json(fresh_db, base, STATION, FECHA, role="encargado")
    with pytest.raises(PermissionError, match="privilegios insuficientes"):
        audit.migrate_legacy_month_dirs(base, role="encargado")
    # admin and control_calidad pass the gate
    audit.mark_error(
        fresh_db,
        role="control_calidad",
        station_id=STATION,
        fecha=FECHA,
        hora="06Z",
        campo="ts",
        tipo_error="Sintaxis",
        marcado_por="cc@arca",
    )
