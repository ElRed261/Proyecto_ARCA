"""Migrate the legacy (schema 1) day documents into schema 2 inside SQLite.

The 2,554 files the old build produced carry derived blocks and, worse, the
last nine-lane slots polluted with the ``555`` marker, the ``29uuu`` group and
old UI labels (see ``docs/ARQUITECTURA_DATOS.md`` section 6). This module
rewrites each file into a clean schema-2 document and upserts it, dropping
what must not be stored (rule R2) and keeping every observed value (rule R1).

It is a dry run by default: nothing is written until ``dry_run=False``.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import cli as cli_service
from oms_core.services import document_map as dm
from oms_core.services import synoptic as synoptic_service
from oms_core.services import versions as versions_service


@dataclass
class MigrationReport:
    seen: int = 0
    migrated: int = 0
    already_v2: int = 0
    rejected: list[tuple[str, str]] = field(default_factory=list)
    lanes_dropped: int = 0
    cli_blocks: int = 0
    dry_run: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "seen": self.seen,
            "migrated": self.migrated,
            "already_v2": self.already_v2,
            "rejected": len(self.rejected),
            "lanes_dropped": self.lanes_dropped,
            "cli_blocks": self.cli_blocks,
            "dry_run": self.dry_run,
        }


def _iso_fecha(raw: str) -> str:
    """DDMMYYYY (legacy) -> YYYY-MM-DD."""
    text = str(raw or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[4:8]}-{text[2:4]}-{text[0:2]}"
    return text


def _iso_actualizado(raw: object) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    iso = text.replace(" ", "T")
    if "+" in iso or iso.endswith("Z"):
        return iso
    return f"{iso}-04:00"


def build_v2_document(legacy: dict[str, Any], *, station: str, fecha: str) -> tuple[dict, int]:
    """Legacy document -> schema 2. Returns (document, dropped_lane_count)."""
    horas = legacy.get("horas") if isinstance(legacy.get("horas"), dict) else {}
    dropped = 0
    synop: dict[str, dict[str, Any]] = {}
    for hora in synoptic_service.HOURS:
        entry = horas.get(hora) if isinstance(horas.get(hora), dict) else {}
        datos_doc = entry.get("datos") if isinstance(entry.get("datos"), dict) else {}
        grupos_doc = entry.get("synop") if isinstance(entry.get("synop"), dict) else {}
        datos = dm.datos_to_document(dm.document_to_datos(datos_doc))
        grupos = dm.groups_to_document(dm.document_to_groups(grupos_doc, legacy=True))
        dropped += sum(
            1 for name in grupos_doc
            if name in dm.POLLUTED_9SP_LANES and str(grupos_doc[name]).strip()
        )
        synop[hora] = {
            "observador": str(entry.get("observador") or ""),
            "datos": datos,
            "grupos": grupos,
        }

    cli: dict[str, Any] = {}
    for key in cli_service.CLI_KEYS:
        block = legacy.get(key)
        if isinstance(block, dict) and block:
            cli[key.replace("cli", "")] = block

    document = {
        "schema": 2,
        "meta": {
            "estacion": station,
            "fecha": fecha,
            "actualizado": _iso_actualizado((legacy.get("meta") or {}).get("ultima_actualizacion")),
        },
        "synop": synop,
        "cli": cli,
    }
    return document, dropped


def migrate_file(conn: sqlite3.Connection, path: Path, *, dry_run: bool = True,
                 actor: str = "migracion-v1") -> tuple[bool, int, int]:
    """Migrate one file. Returns (migrated, lanes_dropped, cli_blocks)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("el documento no es un objeto JSON")
    if int(raw.get("schema") or 1) >= 2:
        return False, 0, 0
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    station = str(meta.get("estacion") or "").strip()
    fecha = _iso_fecha(meta.get("fecha") or "")
    if not station or not fecha:
        raise ValueError("meta.estacion o meta.fecha faltan")
    document, dropped = build_v2_document(raw, station=station, fecha=fecha)
    cli_count = len(document["cli"])
    if dry_run:
        return True, dropped, cli_count

    year, month, day = synoptic_service.validate_fecha(fecha)
    station = synoptic_service.validate_station(station)
    body = json.dumps(document, ensure_ascii=False)
    sha = synoptic_service._sha256_text(body)
    conn.execute("SAVEPOINT legacy_migration")
    try:
        tx = synoptic_service._NoCommitConnection(conn)
        summaries_repo.upsert_summary_doc(
            tx, station_id=station, year=year, month=month, kind="diario",
            data=body, sha256=sha, day=day,
        )
        versions_service.record(
            tx, station, year, month, day, actor=actor,
            sha256_before=None, sha256_after=sha, summary="migracion schema 1 -> 2",
        )
        conn.execute("RELEASE legacy_migration")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO legacy_migration")
        conn.execute("RELEASE legacy_migration")
        raise
    return True, dropped, cli_count


def migrate_root(conn: sqlite3.Connection, root: str | Path, *,
                 dry_run: bool = True) -> MigrationReport:
    """Walk every ``*.json`` under ``root`` and migrate the legacy ones."""
    report = MigrationReport(dry_run=dry_run)
    for path in sorted(Path(root).rglob("*.json")):
        report.seen += 1
        try:
            migrated, dropped, cli_blocks = migrate_file(conn, path, dry_run=dry_run)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            report.rejected.append((str(path), str(exc)))
            continue
        report.lanes_dropped += dropped
        report.cli_blocks += cli_blocks
        if migrated:
            report.migrated += 1
        else:
            report.already_v2 += 1
    return report


__all__ = [
    "MigrationReport",
    "build_v2_document",
    "migrate_file",
    "migrate_root",
]
