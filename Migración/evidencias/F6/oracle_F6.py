"""F6 oracle run (§7-F6): seeded-marks report check + legacy migration diff.

- Reports oracle: a seeded marks DB with HAND-COMPUTED expected values for
  both report surfaces (detailed rows + person summary).
- Migration oracle: a fixture tree (built in tmp, NEVER OLD/ or originals) is
  COPIED, migrated, and verified by before/after tree diff (rename case +
  merge-no-overwrite case + idempotent re-run).

Writes Migración/evidencias/F6/oracle_F6.json with the verdict.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from oms_core.db import migrations
from oms_core.db.connection import connect
from oms_core.services import audit as audit_service

OUT = Path(__file__).resolve().parent / "oracle_F6.json"


def _fresh_db(path: Path) -> sqlite3.Connection:
    conn = connect(path)
    migrations.migrate(conn)
    return conn


def reports_oracle() -> dict:
    """Seeded marks DB vs hand-computed expectations."""
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_db(Path(tmp) / "oracle.db")
        seeded = audit_service.seed_report_fixture(conn)
        snapshot = audit_service.export_state_snapshot(
            conn, station_id="78451", year="2025", month="06"
        )
        conn.close()

    expected_report = [
        {
            "fecha": "2025-06-11",
            "hora": "06Z",
            "campo": "ts",
            "valor_original": "21.0",
            "valor_corregido": "21.5",
            "estado": "pendiente",
            "marcado_por": "otro@y",
        },
        {
            "fecha": "2025-06-10",
            "hora": "06Z",
            "campo": "ts",
            "valor_original": "20.0",
            "valor_corregido": "20.5",
            "estado": "aprobado",
            "marcado_por": "auditor@x",
        },
        {
            "fecha": "2025-06-10",
            "hora": "12Z",
            "campo": "th",
            "valor_original": None,
            "valor_corregido": None,
            "estado": None,
            "marcado_por": "auditor@x",
        },
    ]
    actual_report = [{k: row[k] for k in expected_report[0]} for row in snapshot["error_report"]]
    expected_person = [
        {
            "persona": "auditor@x",
            "errores_marcados": 2,
            "correcciones_propuestas": 1,
            "correcciones_aprobadas": 1,
        },
        {
            "persona": "otro@y",
            "errores_marcados": 1,
            "correcciones_propuestas": 1,
            "correcciones_aprobadas": 0,
        },
    ]
    actual_person = [{k: row[k] for k in expected_person[0]} for row in snapshot["person_summary"]]
    report_ok = actual_report == expected_report
    person_ok = actual_person == expected_person
    return {
        "seeded": seeded,
        "expected_report": expected_report,
        "actual_report": actual_report,
        "expected_person": expected_person,
        "actual_person": actual_person,
        "report_ok": report_ok,
        "person_ok": person_ok,
    }


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def migration_oracle() -> dict:
    """Fixture copies (never originals): before/after tree diff + re-run."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture"
        (fixture / "st1" / "2025" / "mayo").mkdir(parents=True)
        (fixture / "st1" / "2025" / "mayo" / "a.json").write_text("{}", encoding="utf-8")
        (fixture / "st2" / "2025" / "05").mkdir(parents=True)
        (fixture / "st2" / "2025" / "05" / "keep.json").write_text("new", encoding="utf-8")
        (fixture / "st2" / "2025" / "mayo").mkdir(parents=True)
        (fixture / "st2" / "2025" / "mayo" / "keep.json").write_text("old", encoding="utf-8")
        (fixture / "st2" / "2025" / "mayo" / "extra.json").write_text("old2", encoding="utf-8")

        work = Path(tmp) / "copy"
        shutil.copytree(fixture, work)
        before = _tree(work)
        stats = audit_service.migrate_legacy_month_dirs(work)
        after = _tree(work)
        kept_new = (work / "st2" / "2025" / "05" / "keep.json").read_text() == "new"
        moved_extra = (work / "st2" / "2025" / "05" / "extra.json").read_text() == "old2"
        stats2 = audit_service.migrate_legacy_month_dirs(work)
        after2 = _tree(work)

    expected_after = sorted(
        [
            "st1/2025/05/a.json",
            "st2/2025/05/extra.json",
            "st2/2025/05/keep.json",
            "st2/2025/mayo/keep.json",
        ]
    )
    ok = (
        stats == {"renamed_dirs": 1, "moved_files": 1}
        and after == expected_after
        and kept_new
        and moved_extra
        and stats2 == {"renamed_dirs": 0, "moved_files": 0}
        and after2 == after
    )
    return {
        "before": before,
        "stats_first_run": stats,
        "after_first_run": after,
        "colliding_file_kept_new_content": kept_new,
        "extra_file_moved": moved_extra,
        "stats_second_run": stats2,
        "after_second_run": after2,
        "migration_ok": ok,
    }


def main() -> int:
    reports = reports_oracle()
    migration = migration_oracle()
    verdict = bool(reports["report_ok"] and reports["person_ok"] and migration["migration_ok"])
    payload = {"reports": reports, "migration": migration, "verdict": "ok" if verdict else "FAIL"}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "out": str(OUT)}, ensure_ascii=False))
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
