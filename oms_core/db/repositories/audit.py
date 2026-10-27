"""error_marks + corrections repositories.

Port of ``OLD frontend/src-tauri/src/adapters/sqlite_audit_repository.rs``:
same queries, same semantics. The real duplicate barrier is the UNIQUE index
``uq_error_marks_slot`` created by M003; a conflicting mark is translated to
:class:`MarkConflictError` exactly as the Rust code maps it to
``AppError::Validation("Este campo ya está marcado como error")``.

``fecha`` is ISO ``YYYY-MM-DD`` (the month filters use ``LIKE 'YYYY-MM-%'``).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


class MarkConflictError(Exception):
    """Raised when marking a slot that is already marked (unique barrier)."""


# --------------------------------------------------------------------------
# dataclasses (mirror of the Rust domain models used by the queries)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorMark:
    id: int | None
    station_id: str
    fecha: str
    hora: str
    campo: str
    tipo_error: str
    nota: str | None
    marcado_por: str
    created_at: str | None


@dataclass(frozen=True)
class Correction:
    id: int | None
    station_id: str
    fecha: str
    hora: str
    campo: str
    valor_original: str
    valor_corregido: str
    justificacion: str
    corregido_por: str
    aprobado_por: str | None
    estado: str
    created_at: str | None


@dataclass(frozen=True)
class ErrorReportRow:
    error_id: int
    station_id: str
    fecha: str
    hora: str
    campo: str
    tipo_error: str
    nota: str | None
    marcado_por: str
    valor_original: str | None
    valor_corregido: str | None
    justificacion: str | None
    corregido_por: str | None
    estado: str | None
    created_at: str | None


@dataclass(frozen=True)
class PersonSummaryRow:
    persona: str
    errores_marcados: int
    correcciones_propuestas: int
    correcciones_aprobadas: int


# --------------------------------------------------------------------------
# error_marks
# --------------------------------------------------------------------------


def mark_error(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    fecha: str,
    hora: str,
    campo: str,
    tipo_error: str,
    marcado_por: str,
    nota: str | None = None,
) -> int:
    """Mark a slot. ON CONFLICT DO NOTHING + pending check replaces the old
    check-then-insert race (see Rust mark_error comment)."""
    cur = conn.execute(
        "INSERT INTO error_marks (station_id, fecha, hora, campo, tipo_error, nota, marcado_por)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(station_id, fecha, hora, campo) DO NOTHING",
        (station_id, fecha, hora, campo, tipo_error, nota, marcado_por),
    )
    if cur.rowcount == 0:
        # The INSERT opened an implicit transaction even when it inserted
        # nothing; leaving it open makes the caller's next BEGIN IMMEDIATE
        # fail with "cannot start a transaction within a transaction"
        # (Judgment Day SEG-02).
        conn.rollback()
        raise MarkConflictError("Este campo ya está marcado como error")
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_error_marks(conn: sqlite3.Connection, station_id: str, fecha: str) -> list[ErrorMark]:
    rows = conn.execute(
        "SELECT id, station_id, fecha, hora, campo, tipo_error, nota, marcado_por, created_at"
        " FROM error_marks WHERE station_id = ? AND fecha = ?",
        (station_id, fecha),
    ).fetchall()
    return [
        ErrorMark(
            id=int(r["id"]),
            station_id=r["station_id"],
            fecha=r["fecha"],
            hora=r["hora"],
            campo=r["campo"],
            tipo_error=r["tipo_error"],
            nota=r["nota"],
            marcado_por=r["marcado_por"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def get_mark_details(conn: sqlite3.Connection, mark_id: int) -> tuple[str, str, str, str] | None:
    row = conn.execute(
        "SELECT station_id, fecha, hora, campo FROM error_marks WHERE id = ?", (mark_id,)
    ).fetchone()
    if row is None:
        return None
    return (row["station_id"], row["fecha"], row["hora"], row["campo"])


def unmark_error(conn: sqlite3.Connection, mark_id: int) -> None:
    conn.execute("DELETE FROM error_marks WHERE id = ?", (mark_id,))
    conn.commit()


def update_mark_note(conn: sqlite3.Connection, mark_id: int, note: str | None) -> None:
    conn.execute("UPDATE error_marks SET nota = ? WHERE id = ?", (note, mark_id))
    conn.commit()


# --------------------------------------------------------------------------
# corrections
# --------------------------------------------------------------------------


_CORRECTION_COLS = (
    "station_id",
    "fecha",
    "hora",
    "campo",
    "valor_original",
    "valor_corregido",
    "justificacion",
    "corregido_por",
    "aprobado_por",
    "estado",
)


def _correction_from_row(row: sqlite3.Row) -> Correction:
    return Correction(
        id=int(row["id"]),
        station_id=row["station_id"],
        fecha=row["fecha"],
        hora=row["hora"],
        campo=row["campo"],
        valor_original=row["valor_original"],
        valor_corregido=row["valor_corregido"],
        justificacion=row["justificacion"],
        corregido_por=row["corregido_por"],
        aprobado_por=row["aprobado_por"],
        estado=row["estado"],
        created_at=row["created_at"],
    )


def propose_correction(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    fecha: str,
    hora: str,
    campo: str,
    valor_original: str,
    valor_corregido: str,
    justificacion: str,
    corregido_por: str,
    aprobado_por: str | None = None,
    estado: str = "pendiente",
) -> int:
    """Propose a correction for a slot: previous corrections for the same slot
    are deleted first, exactly like the Rust propose_correction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "DELETE FROM corrections WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
            (station_id, fecha, hora, campo),
        )
        cur = conn.execute(
            f"INSERT INTO corrections ({', '.join(_CORRECTION_COLS)})"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                station_id,
                fecha,
                hora,
                campo,
                valor_original,
                valor_corregido,
                justificacion,
                corregido_por,
                aprobado_por,
                estado,
            ),
        )
        new_id = int(cur.lastrowid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return new_id


def get_corrections(conn: sqlite3.Connection, station_id: str, fecha: str) -> list[Correction]:
    rows = conn.execute(
        "SELECT id, station_id, fecha, hora, campo, valor_original, valor_corregido,"
        " justificacion, corregido_por, aprobado_por, estado, created_at"
        " FROM corrections WHERE station_id = ? AND fecha = ?",
        (station_id, fecha),
    ).fetchall()
    return [_correction_from_row(row) for row in rows]


def delete_corrections_by_mark(
    conn: sqlite3.Connection, station_id: str, fecha: str, hora: str, campo: str
) -> None:
    conn.execute(
        "DELETE FROM corrections WHERE station_id = ? AND fecha = ? AND hora = ? AND campo = ?",
        (station_id, fecha, hora, campo),
    )
    conn.commit()


def get_approved_corrections_for_date(
    conn: sqlite3.Connection, station_id: str, fecha: str
) -> list[tuple[str, str, str]]:
    rows = conn.execute(
        "SELECT hora, campo, valor_corregido FROM corrections"
        " WHERE station_id = ? AND fecha = ? AND estado = 'aprobado'",
        (station_id, fecha),
    ).fetchall()
    return [(row["hora"], row["campo"], row["valor_corregido"]) for row in rows]


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------


def _month_like_args(year: str, month: str) -> str | None:
    """Build the fecha LIKE fragment exactly like the Rust report queries."""
    y = year or ""
    m = month or ""
    if y and m:
        return f"{y}-{m}-%"
    if y:
        return f"{y}-%"
    if m:
        return f"%-{m}-%"
    return None


def get_error_report(
    conn: sqlite3.Connection,
    *,
    station_id: str | None = None,
    year: str = "",
    month: str = "",
) -> list[ErrorReportRow]:
    sql = (
        "SELECT e.id, e.station_id, e.fecha, e.hora, e.campo, e.tipo_error, e.nota, e.marcado_por,"
        " c.valor_original, c.valor_corregido, c.justificacion, c.corregido_por, c.estado, e.created_at"
        " FROM error_marks e"
        " LEFT JOIN corrections c ON e.station_id = c.station_id AND e.fecha = c.fecha"
        " AND e.hora = c.hora AND e.campo = c.campo"
        " WHERE 1=1"
    )
    args: list[str] = []
    if station_id:
        sql += " AND e.station_id = ?"
        args.append(station_id)
    like = _month_like_args(year, month)
    if like is not None:
        sql += " AND e.fecha LIKE ?"
        args.append(like)
    sql += " ORDER BY e.fecha DESC, e.hora ASC"
    return [
        ErrorReportRow(
            error_id=int(row["id"]),
            station_id=row["station_id"],
            fecha=row["fecha"],
            hora=row["hora"],
            campo=row["campo"],
            tipo_error=row["tipo_error"],
            nota=row["nota"],
            marcado_por=row["marcado_por"],
            valor_original=row["valor_original"],
            valor_corregido=row["valor_corregido"],
            justificacion=row["justificacion"],
            corregido_por=row["corregido_por"],
            estado=row["estado"],
            created_at=row["created_at"],
        )
        for row in conn.execute(sql, args)
    ]


def get_daily_error_counts(
    conn: sqlite3.Connection, station_id: str, month_prefix: str
) -> dict[str, int]:
    rows = conn.execute(
        "SELECT fecha, COUNT(*) FROM error_marks WHERE station_id = ? AND fecha LIKE ?"
        " GROUP BY fecha",
        (station_id, month_prefix),
    ).fetchall()
    return {row["fecha"]: int(row[1]) for row in rows}


def get_daily_correction_counts(
    conn: sqlite3.Connection, station_id: str, month_prefix: str
) -> dict[str, int]:
    rows = conn.execute(
        "SELECT fecha, COUNT(*) FROM corrections WHERE station_id = ? AND fecha LIKE ?"
        " GROUP BY fecha",
        (station_id, month_prefix),
    ).fetchall()
    return {row["fecha"]: int(row[1]) for row in rows}


def get_person_summary(
    conn: sqlite3.Connection,
    *,
    station_id: str | None = None,
    year: str = "",
    month: str = "",
) -> list[PersonSummaryRow]:
    """Counts per person over both tables (Rust get_person_summary)."""
    summary: dict[str, PersonSummaryRow] = {}

    err_sql = "SELECT marcado_por, COUNT(*) FROM error_marks WHERE 1=1"
    err_args: list[str] = []
    if station_id:
        err_sql += " AND station_id = ?"
        err_args.append(station_id)
    err_like = _month_like_args(year, month)
    if err_like is not None:
        err_sql += " AND fecha LIKE ?"
        err_args.append(err_like)
    err_sql += " GROUP BY marcado_por"
    for row in conn.execute(err_sql, err_args):
        summary[row["marcado_por"]] = PersonSummaryRow(
            persona=row["marcado_por"],
            errores_marcados=int(row[1]),
            correcciones_propuestas=0,
            correcciones_aprobadas=0,
        )

    corr_sql = (
        "SELECT corregido_por, COUNT(*),"
        " SUM(CASE WHEN estado = 'aprobado' THEN 1 ELSE 0 END)"
        " FROM corrections WHERE 1=1"
    )
    corr_args: list[str] = []
    if station_id:
        corr_sql += " AND station_id = ?"
        corr_args.append(station_id)
    corr_like = _month_like_args(year, month)
    if corr_like is not None:
        corr_sql += " AND fecha LIKE ?"
        corr_args.append(corr_like)
    corr_sql += " GROUP BY corregido_por"
    for row in conn.execute(corr_sql, corr_args):
        persona = row["corregido_por"]
        total = int(row[1])
        aprobadas = int(row[2] or 0)
        if persona in summary:
            summary[persona] = PersonSummaryRow(
                persona=summary[persona].persona,
                errores_marcados=summary[persona].errores_marcados,
                correcciones_propuestas=total,
                correcciones_aprobadas=aprobadas,
            )
        else:
            summary[persona] = PersonSummaryRow(
                persona=persona,
                errores_marcados=0,
                correcciones_propuestas=total,
                correcciones_aprobadas=aprobadas,
            )

    return sorted(summary.values(), key=lambda r: r.errores_marcados, reverse=True)


# ---------------------------------------------------------------------------
# audit_days — a day an auditor finished reviewing (M007)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditDay:
    station_id: str
    fecha: str
    auditado_por: str
    auditado_en: str
    nota: str | None = None


def upsert_audit_day(
    conn: sqlite3.Connection,
    *,
    station_id: str,
    fecha: str,
    auditado_por: str,
    auditado_en: str,
    nota: str | None = None,
) -> None:
    """Record (or refresh) that this station-day was audited."""
    conn.execute(
        "INSERT INTO audit_days (station_id, fecha, auditado_por, auditado_en, nota)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(station_id, fecha) DO UPDATE SET"
        " auditado_por = excluded.auditado_por,"
        " auditado_en = excluded.auditado_en,"
        " nota = excluded.nota",
        (station_id, fecha, auditado_por, auditado_en, nota),
    )
    conn.commit()


def delete_audit_day(
    conn: sqlite3.Connection, *, station_id: str, fecha: str
) -> bool:
    cursor = conn.execute(
        "DELETE FROM audit_days WHERE station_id = ? AND fecha = ?",
        (station_id, fecha),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_audit_day(
    conn: sqlite3.Connection, *, station_id: str, fecha: str
) -> AuditDay | None:
    row = conn.execute(
        "SELECT station_id, fecha, auditado_por, auditado_en, nota"
        " FROM audit_days WHERE station_id = ? AND fecha = ?",
        (station_id, fecha),
    ).fetchone()
    return None if row is None else AuditDay(*tuple(row))


def list_audit_days(
    conn: sqlite3.Connection,
    *,
    station_id: str | None = None,
    year: str = "",
    month: str = "",
) -> list[AuditDay]:
    """Audited days of the period, oldest first."""
    sql = "SELECT station_id, fecha, auditado_por, auditado_en, nota FROM audit_days WHERE 1=1"
    args: list[str] = []
    if station_id:
        sql += " AND station_id = ?"
        args.append(station_id)
    like = _month_like_args(year, month)
    if like is not None:
        sql += " AND fecha LIKE ?"
        args.append(like)
    sql += " ORDER BY fecha ASC"
    return [AuditDay(*tuple(row)) for row in conn.execute(sql, args).fetchall()]


def marks_for_period(
    conn: sqlite3.Connection,
    *,
    station_id: str | None = None,
    year: str = "",
    month: str = "",
) -> list[dict[str, Any]]:
    """Every mark of the period, as plain dicts (report aggregation input)."""
    sql = (
        "SELECT station_id, fecha, hora, campo, tipo_error, marcado_por"
        " FROM error_marks WHERE 1=1"
    )
    args: list[str] = []
    if station_id:
        sql += " AND station_id = ?"
        args.append(station_id)
    like = _month_like_args(year, month)
    if like is not None:
        sql += " AND fecha LIKE ?"
        args.append(like)
    sql += " ORDER BY fecha ASC, hora ASC"
    return [dict(row) for row in conn.execute(sql, args).fetchall()]
