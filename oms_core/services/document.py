"""The observation day as ONE object: synoptic hours plus the three CLIs.

Architecture phase A2 (``docs/ARQUITECTURA_DATOS.md``). Loading a day must
bring everything at once — that is the owner's requirement: opening
26/10/2025 hydrates the synoptic grid and the three CLI views from a single
read, with the same values everywhere.

Reads both document shapes:

* schema 1 (legacy): ``{meta, horas{hora:{datos,synop,observador}}}`` + CLI
  keys at the top level.
* schema 2: ``{schema, meta, synop{hora:{observador,datos,grupos}}, cli{…}}``.

Derived values are NOT read from the document: they are recomputed by the
callers (``oms_calc``) from the observed values this module returns.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from oms_core.services import cli as cli_service
from oms_core.services import document_map as dm
from oms_core.services import synoptic as synoptic_service

#: The hours of the synoptic day, in the order the grid shows them.
HOURS = synoptic_service.HOURS

#: CLI keys carried in a day document.
CLI_KEYS = cli_service.CLI_KEYS


@dataclass
class DayDocument:
    """Everything stored for one station-day.

    ``horas`` is form-shaped (``ts``, ``t_max``, ``meteo_4_1``, …) and always
    carries ``nombre_observador`` — even when empty, per the owner's rule.
    """

    station: str
    fecha: str
    horas: dict[str, dict[str, str]] = field(default_factory=dict)
    cli: dict[str, Any] = field(default_factory=dict)
    schema: int = 1

    def hour(self, hora: str) -> dict[str, str]:
        return dict(self.horas.get(hora) or {})

    def observer(self, hora: str) -> str:
        return self.hour(hora).get("nombre_observador", "")

    def observers(self) -> dict[str, str]:
        return {hora: self.observer(hora) for hora in HOURS}


def _document_is_v2(doc: dict[str, Any]) -> bool:
    try:
        return int(doc.get("schema") or 1) >= 2
    except (TypeError, ValueError):
        return False


def _hour_sections(doc: dict[str, Any], hora: str) -> tuple[dict, dict, str]:
    """(datos, grupos, observador) for one hour, whichever shape it is."""
    if _document_is_v2(doc):
        entry = (doc.get("synop") or {}).get(hora)
        if not isinstance(entry, dict):
            return {}, {}, ""
        datos = entry.get("datos") if isinstance(entry.get("datos"), dict) else {}
        grupos = entry.get("grupos") if isinstance(entry.get("grupos"), dict) else {}
        observer = str(entry.get("observador") or "")
        return datos, grupos, observer
    entry = (doc.get("horas") or {}).get(hora)
    if not isinstance(entry, dict):
        return {}, {}, ""
    datos = entry.get("datos") if isinstance(entry.get("datos"), dict) else {}
    grupos = entry.get("synop") if isinstance(entry.get("synop"), dict) else {}
    observer = str(entry.get("observador") or "")
    return datos, grupos, observer


def day_document_from_stored(
    doc: dict[str, Any], station: str, fecha: str, cli_blocks: dict[str, Any] | None = None
) -> DayDocument:
    """Build the full day object from a stored document (no database access)."""
    legacy = not _document_is_v2(doc)
    horas: dict[str, dict[str, str]] = {}
    for hora in HOURS:
        datos, grupos, observer = _hour_sections(doc, hora)
        hour_data: dict[str, str] = {}
        hour_data.update(dm.document_to_datos(datos))
        hour_data.update(dm.document_to_groups(grupos, legacy=legacy))
        # the observer is always present, empty string included (owner rule)
        hour_data["nombre_observador"] = observer
        horas[hora] = hour_data
    return DayDocument(
        station=station,
        fecha=fecha,
        horas=horas,
        cli=dict(cli_blocks or {}),
        schema=1 if legacy else 2,
    )


def empty_day_document(station: str, fecha: str) -> DayDocument:
    """A blank day: eight hours with the observer slot and three empty CLIs."""
    horas = {hora: {"nombre_observador": ""} for hora in HOURS}
    return DayDocument(
        station=station,
        fecha=fecha,
        horas=horas,
        cli={key: {} for key in CLI_KEYS},
        schema=2,
    )


def load_day_document(
    conn: sqlite3.Connection, station: str, fecha: str
) -> DayDocument | None:
    """Read the whole station-day, or ``None`` when nothing is stored yet."""
    station = synoptic_service.validate_station(station)
    year, month, day = synoptic_service.validate_fecha(fecha)
    doc = synoptic_service._diario_doc(conn, station, year, month, day)
    if not isinstance(doc, dict) or not doc:
        return None
    cli_blocks: dict[str, Any] = {}
    if _document_is_v2(doc):
        stored = doc.get("cli") if isinstance(doc.get("cli"), dict) else {}
        for key in CLI_KEYS:
            block = stored.get(key.replace("cli", "")) or stored.get(key)
            if block:
                cli_blocks[key] = block
    if not cli_blocks:  # schema 1 keeps them at the top level
        for key in CLI_KEYS:
            block = cli_service.load_cli(conn, station, fecha, key)
            if block:
                cli_blocks[key] = block
    return day_document_from_stored(doc, station, fecha, cli_blocks)


__all__ = [
    "CLI_KEYS",
    "HOURS",
    "DayDocument",
    "day_document_from_stored",
    "empty_day_document",
    "load_day_document",
]
