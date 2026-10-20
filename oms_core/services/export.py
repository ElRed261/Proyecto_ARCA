"""Export a stored day back to the Documents tree, and import it again.

Architecture phase A6 (``docs/ARQUITECTURA_DATOS.md`` section 5.5). SQLite is
the source of truth; the JSON tree is the transport/respaldo that Drive
carries between stations. ``export_day`` writes the schema 2 document, so what
lands on disk is exactly what the database holds — no derived blocks, no
polluted lanes, observer on every hour.

``import_day_file`` is the other direction and accepts both shapes, which is
what makes the round trip verifiable: export a day, wipe it, import the file
back and get the same document.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oms_core import paths as paths_mod
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import legacy_migration
from oms_core.services import synoptic as synoptic_service
from oms_core.services import versions as versions_service


@dataclass
class ExportReport:
    written: int = 0
    skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "written": self.written,
            "skipped": self.skipped,
            "errors": len(self.errors),
        }


def day_path(root: str | Path, station: str, year: int, month: int, day: int) -> Path:
    """``{root}/synop/<ESTACION>/<AÑO>/<MES>/<ESTACION><DDMMYYYY>.json``."""
    section = paths_mod.section_dir(root, paths_mod.SECTION_SYNOP)
    return (
        section / synoptic_service.validate_station(station)
        / f"{year:04d}" / f"{month:02d}"
        / f"{station}{day:02d}{month:02d}{year:04d}.json"
    )


def export_day(
    conn: sqlite3.Connection,
    station: str,
    fecha: str,
    root: str | Path,
    *,
    indent: int | None = 2,
) -> Path | None:
    """Write one stored day to the tree; ``None`` when it is not stored."""
    year, month, day = synoptic_service.validate_fecha(fecha)
    station = synoptic_service.validate_station(station)
    text = summaries_repo.get_summary_doc(conn, station, year, month, "diario", day=day)
    if text is None:
        return None
    document = json.loads(text)
    path = day_path(root, station, year, month, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(document, indent=indent, ensure_ascii=False)
    path.write_text(body + "\n", encoding="utf-8")
    return path


def export_all(
    conn: sqlite3.Connection, root: str | Path, *, indent: int | None = 2
) -> ExportReport:
    """Rewrite the whole tree from the database."""
    report = ExportReport()
    rows = conn.execute(
        "SELECT station_id, year, month, day FROM summary_logs"
        " WHERE kind = 'diario' ORDER BY station_id, year, month, day"
    ).fetchall()
    for station, year, month, day in rows:
        fecha = f"{year:04d}-{month:02d}-{day:02d}"
        try:
            written = export_day(conn, station, fecha, root, indent=indent)
        except (OSError, ValueError) as exc:
            report.errors.append((f"{station} {fecha}", str(exc)))
            continue
        if written is None:
            report.skipped += 1
        else:
            report.written += 1
    return report


def import_day_file(
    conn: sqlite3.Connection, path: str | Path, *, dry_run: bool = False,
    actor: str = "import",
) -> bool:
    """Import one day file (schema 1 or 2). True when it was written."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("el documento no es un objeto JSON")
    if int(raw.get("schema") or 1) < 2:
        migrated, _dropped, _cli = legacy_migration.migrate_file(
            conn, Path(path), dry_run=dry_run, actor=actor)
        return migrated
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    station = str(meta.get("estacion") or "").strip()
    fecha = legacy_migration._iso_fecha(meta.get("fecha") or "")
    if not station or not fecha:
        raise ValueError("meta.estacion o meta.fecha faltan")
    year, month, day = synoptic_service.validate_fecha(fecha)
    station = synoptic_service.validate_station(station)
    if dry_run:
        return True
    body = json.dumps(raw, ensure_ascii=False)
    sha = synoptic_service._sha256_text(body)
    conn.execute("SAVEPOINT import_day")
    try:
        tx = synoptic_service._NoCommitConnection(conn)
        summaries_repo.upsert_summary_doc(
            tx, station_id=station, year=year, month=month, kind="diario",
            data=body, sha256=sha, day=day,
        )
        versions_service.record(
            tx, station, year, month, day, actor=actor,
            sha256_before=None, sha256_after=sha, summary="import schema 2",
        )
        conn.execute("RELEASE import_day")
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.execute("ROLLBACK TO import_day")
        conn.execute("RELEASE import_day")
        raise ValueError(
            f"la estación '{station}' no está registrada en la tabla stations: {exc}"
        ) from exc
    except Exception:
        conn.execute("ROLLBACK TO import_day")
        conn.execute("RELEASE import_day")
        raise
    return True


__all__ = [
    "ExportReport",
    "day_path",
    "export_all",
    "export_day",
    "import_day_file",
]
