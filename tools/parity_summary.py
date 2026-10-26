#!/usr/bin/env python3
"""Compare the monthly summary against the OLD oracle, column by column.

Usage (from the repository root, with the GIL venv):

    QT_QPA_PLATFORM=offscreen .venv-gil/bin/python tools/parity_summary.py

It reads the live database (``~/.local/share/oms/oms.db``) and the two oracle
documents the OLD app produced for 10/2025 (``../OLD/Resumen_Mensual_Synop``)
and prints, day by day and column by column, every difference that is NOT a
declared deviation.

Declared deviations (never reported as failures):
* ``Lluvia``            — F5 CORREGIR: rain stays on its own day.
* humidity group        — R32 PRECISIÓN: derived from the 1-decimal inputs the
                          document stores, while the oracle read values the old
                          app had already computed at full precision.

Exit code: 0 when only declared deviations remain, 1 otherwise.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

# Runnable straight from the repository root without installing the package.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from oms_core.services import summary as summary_service  # noqa: E402

ORACLE_DIR = pathlib.Path("../OLD/Resumen_Mensual_Synop").resolve()
DEFAULT_DB = pathlib.Path.home() / ".local" / "share" / "oms" / "oms.db"

#: Column -> why it may differ. Signed deviations the owner accepted.
DECLARED = {
    "Lluvia": "F5: lluvia en su día",
    "Humedad maxima": "R32: derivada de ts/th",
    "Humedad minima": "R32: derivada de ts/th",
    "Humedad media": "R32: derivada de ts/th",
    "Punto de rocio": "R32: derivado de ts/th",
    "Tensión de vapor": "R32: derivado de ts/th",
}

#: Columns whose difference has the same cause — the document derives what the
#: old app stored — but which the owner has NOT signed off yet. They are
#: reported apart so a real regression is never hidden behind a label.
PENDING = (
    "Dirección del viento",
    "Nuvocidad dia",
    "Nuvocidad noche",
    "Media de nuvocidad",
    "MAxima presión nivel medio del mar",
    "Minima presión nivel medio del mar",
    "Media presión nivel medio del mar",
    "Media presion en la estación",
    "Mayor temperatura máxima",
    "Menor temperatura minima",
    "Media temperatura",
)


def _same(left: object, right: object) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(left - right) < 1e-9
    return left == right


def compare(conn: sqlite3.Connection, station: str, year: int, month: int) -> int:
    oracle_path = ORACLE_DIR / f"resumen_{station}_{month:02d}{year}.json"
    if not oracle_path.exists():
        print(f"[{station}] sin oráculo en {oracle_path}")
        return 0
    oracle = {
        row["Dias"]: row
        for row in json.loads(oracle_path.read_text(encoding="utf-8"))["datos"]
    }
    generated = summary_service.generate_month(conn, station, year, month, overlay=False)
    headers = [h for h in next(iter(oracle.values())) if h != "Dias"]

    unexpected: dict[str, list[tuple[str, object, object]]] = {}
    pending: dict[str, list[tuple[str, object, object]]] = {}
    declared: dict[str, int] = {}
    days_compared = 0
    for kpis in generated["datos"]:
        expected = oracle.get(kpis.get("Dias"))
        if expected is None:
            continue
        if all(kpis.get(header) in (None, "N/A") for header in headers):
            print(f"[{station}] {kpis['Dias']}: el documento está vacío")
            continue
        days_compared += 1
        for header in headers:
            mine, theirs = kpis.get(header), expected.get(header)
            if _same(mine, theirs):
                continue
            if header in DECLARED:
                declared[header] = declared.get(header, 0) + 1
            elif header in PENDING:
                pending.setdefault(header, []).append((kpis["Dias"], mine, theirs))
            else:
                unexpected.setdefault(header, []).append((kpis["Dias"], mine, theirs))

    print(f"\n[{station}] {days_compared} días comparados contra {oracle_path.name}")
    for header, count in sorted(declared.items()):
        print(f"  desviación declarada  {header}: {count} días ({DECLARED[header]})")
    if pending:
        print("  PENDIENTES DE CLASIFICAR (misma causa: el documento deriva lo que el oráculo guardaba):")
        for header, rows in pending.items():
            day, mine, theirs = rows[0]
            print(f"    {header}: {len(rows)} días · ej {day}: {mine!r} != {theirs!r}")
    if not unexpected:
        print("  sin diferencias de REGLA (las reglas coinciden)")
        return 1 if pending else 0
    print("  DIFERENCIAS INESPERADAS:")
    for header, rows in unexpected.items():
        day, mine, theirs = rows[0]
        print(f"    {header}: {len(rows)} días · ej {day}: {mine!r} != {theirs!r}")
    return 1


def main() -> int:
    database = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not database.exists():
        print(f"no existe la base {database}")
        return 2
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    failures = 0
    for station in ("78485", "78486"):
        failures += compare(conn, station, 2025, 10)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
