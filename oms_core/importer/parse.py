"""Parsing and validation of the two legacy JSON document shapes.

Shells (measured on the OLD sample corpus):

- daily:  ``{"meta": {"estacion", "fecha": "DDMMYYYY"}, "horarias": [...],
           "resumen_dia": {...}}``
- resumen: ``{"meta": {"estacion", "periodo": "MM/YYYY", "total_dias",
           "generado"}, "datos": [...]}}``

Date validation mirrors ``OLD .../json_handler/utils.rs::parse_date_parts``:
P1.4 hard-fail — a malformed or out-of-range date raises, never a silent
default (year 1990..2250, month 01-12, real calendar day including leap
years).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field


class ParseError(ValueError):
    """A legacy document is malformed; stage and detail travel in the message."""


@dataclass(frozen=True)
class HourlyRow:
    hora: str
    datos: dict
    observador: str


@dataclass(frozen=True)
class DailyDocument:
    station: str
    fecha_iso: str  # YYYY-MM-DD
    horarias: list[HourlyRow]
    resumen_dia: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResumenDocument:
    station: str
    year: int
    month: int
    total_dias: int | None
    generado: str | None
    datos: list


def parse_ddmmyyyy(fecha: str) -> tuple[int, int, int]:
    """Validate a DDMMYYYY date, mirroring json_handler utils (P1.4)."""
    if len(fecha) != 8:
        raise ParseError(
            f"formato de fecha inválido: '{fecha}' no es YYYY-MM-DD ni DDMMYYYY"
        )
    if not fecha.isdigit():
        raise ParseError(f"la fecha '{fecha}' debe contener solo dígitos")
    day, month, year = int(fecha[0:2]), int(fecha[2:4]), int(fecha[4:8])
    if not 1990 <= year <= 2250:
        raise ParseError(f"año '{year}' fuera de rango razonable (1990-2250)")
    if not 1 <= month <= 12:
        raise ParseError(f"mes '{month}' inválido (debe ser 01-12)")
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        raise ParseError(f"día '{day}' inválido para {year}-{month:02d}")
    return year, month, day


def iso_date(fecha: str) -> str:
    year, month, day = parse_ddmmyyyy(fecha)
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_meta(doc: object) -> dict:
    """Shared meta validation. Raises ParseError mentioning the stage."""
    if not isinstance(doc, dict):
        raise ParseError("meta: el documento no es un objeto JSON")
    meta = doc.get("meta")
    if not isinstance(meta, dict):
        raise ParseError("meta: falta el bloque 'meta' o no es un objeto")
    station = meta.get("estacion")
    if not isinstance(station, str) or not station.strip():
        raise ParseError("meta: 'estacion' falta o está vacío")
    return meta


def parse_daily(doc: object) -> DailyDocument:
    """Parse a daily ({meta, horarias, resumen_dia}) document."""
    meta = parse_meta(doc)
    assert isinstance(doc, dict)  # for the type checker; parse_meta guarantees it
    fecha = meta.get("fecha")
    if not isinstance(fecha, str):
        raise ParseError(f"meta: 'fecha' falta o no es un string (recibido {fecha!r})")
    fecha_iso = iso_date(fecha)  # raises ParseError on a bad calendar date

    horarias_raw = doc.get("horarias")
    if not isinstance(horarias_raw, list):
        raise ParseError("horarias: falta 'horarias' o no es una lista")
    horarias: list[HourlyRow] = []
    for index, row in enumerate(horarias_raw):
        if not isinstance(row, dict):
            raise ParseError(f"horarias[{index}]: no es un objeto")
        hora = row.get("hora")
        if not isinstance(hora, str) or not hora.strip():
            raise ParseError(f"horarias[{index}]: 'hora' falta o está vacío")
        datos = row.get("datos", {})
        if not isinstance(datos, dict):
            raise ParseError(f"horarias[{index}]: 'datos' no es un objeto")
        observador = row.get("observador", "")
        if not isinstance(observador, str):
            raise ParseError(f"horarias[{index}]: 'observador' no es un string")
        horarias.append(HourlyRow(hora=hora, datos=datos, observador=observador))

    resumen_dia = doc.get("resumen_dia", {})
    if not isinstance(resumen_dia, dict):
        raise ParseError("resumen_dia: no es un objeto")
    return DailyDocument(
        station=meta["estacion"].strip(),
        fecha_iso=fecha_iso,
        horarias=horarias,
        resumen_dia=resumen_dia,
    )


def parse_resumen(doc: object) -> ResumenDocument:
    """Parse a monthly summary ({meta, datos}) document."""
    meta = parse_meta(doc)
    periodo = meta.get("periodo")
    if not isinstance(periodo, str) or not (match := re.fullmatch(r"(\d{1,2})/(\d{4})", periodo)):
        raise ParseError(f"meta: 'periodo' inválido (se recibió {periodo!r})")
    month, year = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        raise ParseError(f"meta: mes '{month}' inválido (debe ser 01-12)")
    if not 1990 <= year <= 2250:
        raise ParseError(f"meta: año '{year}' fuera de rango razonable (1990-2250)")

    datos = doc.get("datos") if isinstance(doc, dict) else None
    if not isinstance(datos, list):
        raise ParseError("datos: falta 'datos' o no es una lista")

    total_dias = meta.get("total_dias")
    if total_dias is not None and not isinstance(total_dias, int):
        raise ParseError("meta: 'total_dias' no es un entero")
    generado = meta.get("generado")
    if generado is not None and not isinstance(generado, str):
        raise ParseError("meta: 'generado' no es un string")

    return ResumenDocument(
        station=meta["estacion"].strip(),
        year=year,
        month=month,
        total_dias=total_dias,
        generado=generado,
        datos=datos,
    )
