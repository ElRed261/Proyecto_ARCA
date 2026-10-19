"""Observation-file intake: validate the on-disk documents, then organize.

The ARCA documents the application itself writes look like::

    {
      "meta": {"estacion": "78486", "fecha": "14102023", ...},
      "horas": {"00Z": {"datos": {...}, "observador": "...", "synop": "..."}, ...},
      "cli3074": {...}, "cli4074": {...}, "cli5074": {...}
    }

``horas`` is an object keyed by canonical hour (``modules/synoptic/storage.rs``
in the oracle), which is why this module validates against that shape and not
against the monthly pipeline's ``horarias`` list.

The flow is deliberately two-step: ``plan_organization`` only reads and
reports (dry run), and ``apply_plan`` is the only function that moves
anything. Nothing here ever overwrites an existing file: a destination that
already exists becomes a ``collision`` the caller has to look at.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from oms_core import paths as paths_mod
from oms_core.services.audit import HOURS, normalize_station_code

#: The document must carry at least this much to be a usable daily record.
REQUIRED_TOP_LEVEL = ("meta", "horas")


class IngestError(ValueError):
    """A candidate file is not a valid observation document."""


@dataclass(frozen=True)
class Candidate:
    """A validated observation document and where it belongs."""

    path: Path
    station: str
    year: int
    month: int
    day: int
    sha256: str

    @property
    def period(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass
class Rejection:
    path: Path
    reason: str


@dataclass
class Plan:
    """A dry-run result: what would move where, and what will not."""

    destination_root: Path
    moves: list[tuple[Candidate, Path]] = field(default_factory=list)
    in_place: list[Candidate] = field(default_factory=list)
    collisions: list[tuple[Candidate, Path]] = field(default_factory=list)
    rejections: list[Rejection] = field(default_factory=list)

    @property
    def total_seen(self) -> int:
        return (
            len(self.moves) + len(self.in_place)
            + len(self.collisions) + len(self.rejections)
        )


def validate_document(doc: object) -> tuple[str, int, int, int]:
    """Validate one parsed document; return (station, year, month, day).

    Raises :class:`IngestError` naming the offending field, so a report can
    say *why* a file was left alone instead of silently skipping it.
    """
    if not isinstance(doc, dict):
        raise IngestError("el documento no es un objeto JSON")
    for key in REQUIRED_TOP_LEVEL:
        if key not in doc:
            raise IngestError(f"falta el bloque '{key}'")
    meta = doc["meta"]
    if not isinstance(meta, dict):
        raise IngestError("'meta' no es un objeto")
    station = meta.get("estacion")
    if not isinstance(station, str) or not station.strip():
        raise IngestError("meta.estacion falta o está vacío")
    fecha = meta.get("fecha")
    if not isinstance(fecha, str) or not fecha.strip():
        raise IngestError("meta.fecha falta o está vacío")
    # DDMMYYYY, the format the application writes
    digits = fecha.strip()
    if len(digits) != 8 or not digits.isdigit():
        raise IngestError(f"meta.fecha '{fecha}' no tiene formato DDMMYYYY")
    day, month, year = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    if not 1 <= month <= 12:
        raise IngestError(f"meta.fecha '{fecha}' trae un mes inválido")
    if not 1 <= day <= 31:
        raise IngestError(f"meta.fecha '{fecha}' trae un día inválido")
    if not 1990 <= year <= 2250:
        raise IngestError(f"meta.fecha '{fecha}' trae el año fuera de rango: {year}")
    try:
        import datetime as _dt

        _dt.date(year, month, day)
    except ValueError as exc:
        raise IngestError(f"meta.fecha '{fecha}' no es una fecha real: {exc}") from exc

    horas = doc["horas"]
    if not isinstance(horas, dict):
        raise IngestError("'horas' no es un objeto")
    if not horas:
        raise IngestError("'horas' está vacío: el documento no tiene observaciones")
    for hour, entry in horas.items():
        if hour not in HOURS:
            raise IngestError(f"hora desconocida en 'horas': '{hour}'")
        if not isinstance(entry, dict):
            raise IngestError(f"horas['{hour}'] no es un objeto")
        datos = entry.get("datos")
        if datos is not None and not isinstance(datos, dict):
            raise IngestError(f"horas['{hour}'].datos no es un objeto")
    for cli in ("cli3074", "cli4074", "cli5074"):
        if cli in doc and not isinstance(doc[cli], dict):
            raise IngestError(f"'{cli}' no es un objeto")
    return station.strip(), year, month, day


def candidate_from_file(path: Path) -> Candidate:
    """Read and validate one file, or raise :class:`IngestError`."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise IngestError(f"no se pudo leer: {exc}") from exc
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise IngestError(f"JSON inválido: {exc}") from exc
    station, year, month, day = validate_document(doc)
    return Candidate(
        path=path, station=station, year=year, month=month, day=day,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def destination_for(candidate: Candidate, root: str | Path) -> Path:
    """``{root}/synop/<ESTACION>/<AÑO>/<MES>/<nombre original>``."""
    section = paths_mod.section_dir(root, paths_mod.SECTION_SYNOP)
    return (
        section
        / normalize_station_code(candidate.station)
        / f"{candidate.year:04d}"
        / f"{candidate.month:02d}"
        / candidate.path.name
    )


def scan_json_files(root: Path) -> list[Path]:
    """Every ``*.json`` under ``root``, sorted for a reproducible report."""
    return sorted(p for p in Path(root).rglob("*.json") if p.is_file())


def plan_organization(
    sources: list[Path],
    destination_root: str | Path,
    *,
    keep_original_name: bool = True,
) -> Plan:
    """Dry run: validate every source and compute the move it would need."""
    root = Path(destination_root)
    plan = Plan(destination_root=root)
    for path in sources:
        try:
            candidate = candidate_from_file(path)
        except IngestError as exc:
            plan.rejections.append(Rejection(path=path, reason=str(exc)))
            continue
        destination = destination_for(candidate, root)
        if not keep_original_name:
            destination = destination.with_name(
                f"{normalize_station_code(candidate.station)}"
                f"{candidate.day:02d}{candidate.month:02d}{candidate.year:04d}.json"
            )
        if path.resolve() == destination.resolve():
            plan.in_place.append(candidate)
        elif destination.exists():
            plan.collisions.append((candidate, destination))
        else:
            plan.moves.append((candidate, destination))
    return plan


def apply_plan(plan: Plan, *, log: list[str] | None = None) -> dict[str, int]:
    """Execute a plan: create the tree and MOVE each file, never overwriting.

    Returns counters for the caller's report. Files that could not be moved
    are left untouched where they are.
    """
    moved = 0
    failed = 0
    for candidate, destination in plan.moves:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():  # a re-run raced us: never overwrite
                plan.collisions.append((candidate, destination))
                failed += 1
                if log is not None:
                    log.append(f"colisión, no se movió: {destination}")
                continue
            shutil.move(str(candidate.path), str(destination))
            moved += 1
            if log is not None:
                log.append(f"{candidate.path} -> {destination}")
        except OSError as exc:
            failed += 1
            if log is not None:
                log.append(f"error moviendo {candidate.path}: {exc}")
    return {
        "moved": moved,
        "failed": failed,
        "collisions": len(plan.collisions),
        "in_place": len(plan.in_place),
        "rejected": len(plan.rejections),
    }


__all__ = [
    "Candidate",
    "IngestError",
    "Plan",
    "Rejection",
    "apply_plan",
    "candidate_from_file",
    "destination_for",
    "plan_organization",
    "scan_json_files",
    "validate_document",
]
