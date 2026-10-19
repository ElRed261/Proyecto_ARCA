"""Audit service — PRD F6: quality control, error marks and overlays.

Qt-free port (ADR-03) of the read-only oracle
``OLD/frontend/src-tauri/src/audit/{service,commands}.rs`` on top of the F1
``oms_core.db.repositories.audit`` queries (same SQL, same semantics):

- ``month_name_to_num`` (spanish + english, lowercase match, ``None`` unknown);
- ``map_datos_field`` / ``map_calculado_field`` (the two frontend routing maps);
- ``months`` listing (two-digit dirs + legacy spanish names shown by number —
  pure read, never renames; the one-shot rename is ``migrate_legacy_month_dirs``);
- ``migrate_legacy_month_dirs`` VERBATIM rename-or-merge semantics: rename when
  the numeric dir is absent, otherwise move only non-colliding files (never
  overwrite), remove the legacy dir only when left empty. Idempotent;
- ``load_observation_with_audit``: the diario document comes from the F1
  ``summary_logs`` repo (``kind='diario'``), flattened per hour like the oracle
  ``get_observation_core`` view, with approved corrections overlaid and the
  verbatim auto-mark rule (data without observer -> "Falta nombre de
  observador" by "Sistema de Calidad");
- mark / unmark (also drops the slot corrections, like the oracle) / note /
  propose / approve (approve flips ``estado`` + ``aprobado_por``);
- error report + person summary (thin wrappers over the F1 queries);
- ``export_corrected_json``: doc copy + approved corrections applied into a new
  ``correcciones/<station><DDMMYYYY>_cor.json`` file, never overwriting the
  original (atomic write).

Deliberate, documented deviations from the oracle (see Migración/evidencias/F6):

- propose creates ``estado='pendiente'``; a separate ``approve_correction``
  flips it to ``'aprobado'`` (the oracle auto-approved inside propose, so the
  approve gate was untestable there);
- role checks take a plain ``role`` string via :mod:`oms_core.services.access`
  (the enforced App.jsx RoleRoute boundary: admin + control_calidad only).
  Every mutating entry accepts ``role=None`` for already-gated internal
  callers; when a role IS given it is enforced with the exact oracle message.

No Qt is imported here (ADR-03); the pages live in ``oms_ui.pages.audit*``.
"""

from __future__ import annotations

import calendar
import copy
import datetime as _dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import oms_calc
from oms_core import paths as paths_mod
from oms_core.db.repositories import audit as audit_repo
from oms_core.db.repositories import stations as stations_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services import access
from oms_core.services.synoptic import _recalc_derived

#: Canonical synoptic hours inspected by the auto-mark rule (oracle order).
HOURS = ("00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z")

#: Roles allowed to audit (enforced App.jsx RoleRoute boundary, NOT the wider
#: Sidebar list — see F6 NOTA for the discrepancy and the user's final call).
AUDIT_ROLES = ("admin", "control_calidad")

#: Month number -> Spanish label for the wizard and the report filters.
MONTH_NAMES = {
    "01": "Enero",
    "02": "Febrero",
    "03": "Marzo",
    "04": "Abril",
    "05": "Mayo",
    "06": "Junio",
    "07": "Julio",
    "08": "Agosto",
    "09": "Septiembre",
    "10": "Octubre",
    "11": "Noviembre",
    "12": "Diciembre",
}

#: Frontend key -> diario-document ``datos`` key (oracle map verbatim).
_DATOS_MAP = {
    "ts": "ts",
    "th": "th",
    "pres_est": "pres_est",
    "p3": "p3",
    "p24": "p24",
    "viento_dir": "viento_dir",
    "viento_vel": "viento_vel",
    "visibilidad": "visibilidad",
    "t_max": "Tmax",
    "t_min": "Tmin",
    "ll": "LL",
    "t_max_24h": "Tmax_24h",
    "t_min_24h": "Tmin_24h",
    "ll_24h": "LL_24h",
    "correc_alt": "correc_alt",
}

#: Frontend key -> diario-document ``calculado`` key (oracle map verbatim).
_CALCULADO_MAP = {
    "pres_nmm": "pres_nmm",
    "punto_rocio": "pr",
    "tension_vapor": "tv",
    "humedad_relativa": "hr",
    "diferencia": "dif",
}

#: ``calculado`` doc key -> flattened frontend key (get_observation_core view).
_CALCULADO_TO_FRONTEND = {
    "pr": "punto_rocio",
    "tv": "tension_vapor",
    "hr": "humedad_relativa",
    "dif": "diferencia",
}

#: Hour keys that never count as "has data" for the auto-mark rule (oracle).
_NON_DATA_KEYS = frozenset({"observador", "station_id", "fecha", "nombre_observador"})

_MONTH_ES_EN = {
    "enero": "01",
    "january": "01",
    "febrero": "02",
    "february": "02",
    "marzo": "03",
    "march": "03",
    "abril": "04",
    "april": "04",
    "mayo": "05",
    "may": "05",
    "junio": "06",
    "june": "06",
    "julio": "07",
    "july": "07",
    "agosto": "08",
    "august": "08",
    "septiembre": "09",
    "september": "09",
    "octubre": "10",
    "october": "10",
    "noviembre": "11",
    "november": "11",
    "diciembre": "12",
    "december": "12",
}


class AuditError(Exception):
    """Structured audit failure (validation, missing day, missing correction)."""


# ---------------------------------------------------------------------------
# pure mappers (oracle verbatim)
# ---------------------------------------------------------------------------


def month_name_to_num(name: str) -> str | None:
    """Spanish/english month dirname -> 'MM' (lowercase match, else None)."""
    if not isinstance(name, str):
        return None
    return _MONTH_ES_EN.get(name.lower())


def map_datos_field(campo: str) -> str | None:
    """Frontend key -> diario ``datos`` key (None when it routes elsewhere)."""
    return _DATOS_MAP.get(campo)


def map_calculado_field(campo: str) -> str | None:
    """Frontend key -> diario ``calculado`` key (None when it routes elsewhere)."""
    return _CALCULADO_MAP.get(campo)


def normalize_station_code(code: str) -> str:
    """Filesystem station key: trimmed lowercase (oracle P1.5)."""
    return code.strip().lower()


def default_base_dir() -> Path:
    """Base synop dir: ``ARCA_BASE_DIR`` env, else the platform default root.

    Single source of truth: the layout lives in ``oms_core.paths``, never in
    a second hardcoded literal here.
    """
    env = os.environ.get(paths_mod.ENV_BASE_DIR, "").strip()
    if env:
        return paths_mod.section_dir(env, paths_mod.SECTION_SYNOP)
    return paths_mod.section_dir(
        paths_mod.default_documents_root(), paths_mod.SECTION_SYNOP)


def resolve_base_dir(conn: sqlite3.Connection) -> Path:
    """The synop base dir the administrator actually configured.

    Follows the same env > profile > default chain as the rest of the app, so
    setting the root in Maintenance moves the audit browser with it.
    """
    try:
        root = paths_mod.offline_base_dir(conn, modulo="")
    except paths_mod.PathConfigError:
        return default_base_dir()
    if str(root) in ("", "."):
        return default_base_dir()
    return root / paths_mod.SECTION_SYNOP


# ---------------------------------------------------------------------------
# role gates (enforced boundary)
# ---------------------------------------------------------------------------


def require_audit_role(role: str) -> None:
    """Admin / control_calidad only, with the exact oracle message."""
    if not access.can_access(role, "audit"):
        raise PermissionError("No autorizado: privilegios insuficientes")


def _check_audit_role(role: str | None) -> None:
    if role is not None:
        require_audit_role(role)


def _check_admin_role(role: str | None) -> None:
    if role is not None:
        from oms_core.services.auth import normalize_role

        if normalize_role(role) != "admin":
            raise PermissionError("No autorizado: privilegios insuficientes")


# ---------------------------------------------------------------------------
# validation (oracle messages)
# ---------------------------------------------------------------------------


def _validate_station(station: object) -> str:
    if not isinstance(station, str) or station == "" or len(station) > 10:
        raise AuditError("Código de estación inválido")
    if not all(c.isascii() and (c.isalnum() or c == "_") for c in station):
        raise AuditError("Código de estación contiene caracteres no permitidos")
    return station


def _validate_fecha(fecha: object) -> tuple[int, int, int]:
    text = fecha if isinstance(fecha, str) else ""
    parts = text.split("-")
    if len(parts) != 3:
        raise AuditError("Formato de fecha inválido. Debe ser YYYY-MM-DD")
    yyyy, mm, dd = parts
    if len(yyyy) != 4 or len(mm) != 2 or len(dd) != 2:
        raise AuditError("Formato de fecha inválido. Debe ser YYYY-MM-DD")
    if not (yyyy.isdigit() and mm.isdigit() and dd.isdigit()):
        raise AuditError("La fecha debe contener solo dígitos")
    year, month, day = int(yyyy), int(mm), int(dd)
    if not (1 <= month <= 12 and 1 <= day <= calendar.monthrange(year, month)[1]):
        raise AuditError("La fecha no es una fecha de calendario real")
    return year, month, day


def _now_local() -> str:
    return _dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _station_ch(conn: sqlite3.Connection, station: str) -> str:
    row = stations_repo.get_station(conn, station)
    return "" if row is None else str(row.ch)


# ---------------------------------------------------------------------------
# browse (filesystem + DB counts; base dir is always a parameter)
# ---------------------------------------------------------------------------


def browse_stations(
    base_dir: str | Path,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, str]]:
    """Digit-only station subdirs, names resolved via the stations repo."""
    base = Path(base_dir)
    stations: list[dict[str, str]] = []
    if base.exists():
        for entry in sorted(base.iterdir(), key=lambda p: p.name):
            if not entry.is_dir() or not entry.name.isascii() or not entry.name.isdigit():
                continue
            name = "Estación Desconocida"
            if conn is not None:
                row = stations_repo.get_station(conn, entry.name)
                if row is not None:
                    name = row.name
            stations.append({"code": entry.name, "name": name})
    stations.sort(key=lambda s: s["code"])
    return stations


def browse_years(base_dir: str | Path, station: str) -> list[str]:
    """Four-digit year dirs, newest first (oracle order)."""
    station_dir = Path(base_dir) / normalize_station_code(station)
    years: list[str] = []
    if station_dir.exists():
        for entry in station_dir.iterdir():
            if entry.is_dir() and len(entry.name) == 4 and entry.name.isdigit():
                years.append(entry.name)
    years.sort(reverse=True)
    return years


def browse_months(base_dir: str | Path, station: str, year: str) -> list[str]:
    """Two-digit months + legacy spanish names shown by number (pure read)."""
    year_dir = Path(base_dir) / normalize_station_code(station) / year
    months: list[str] = []
    if year_dir.exists():
        for entry in year_dir.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            if len(name) == 2 and name.isdigit():
                months.append(name)
            elif (num := month_name_to_num(name)) is not None:
                months.append(num)
    months.sort()
    return list(dict.fromkeys(months))


def browse_days(
    base_dir: str | Path, conn: sqlite3.Connection, station: str, year: str, month: str
) -> list[dict[str, Any]]:
    """One row per ``*.json`` file with DB error/correction counts."""
    month_dir = Path(base_dir) / normalize_station_code(station) / year / month
    days: list[dict[str, Any]] = []
    if not month_dir.exists():
        return days
    month_prefix = f"{year}-{month}-%"
    error_counts = audit_repo.get_daily_error_counts(conn, station, month_prefix)
    correction_counts = audit_repo.get_daily_correction_counts(conn, station, month_prefix)
    for entry in sorted(month_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_file() or entry.suffix != ".json":
            continue
        stem = entry.stem
        if len(stem) >= 8 and stem[-8:].isdigit():
            part = stem[-8:]
            date = f"{part[4:8]}-{part[2:4]}-{part[0:2]}"
        else:
            date = f"{year}-{month}-01"
        observador = "Desconocido"
        horas_registradas = 0
        try:
            doc = json.loads(entry.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = None
        if isinstance(doc, dict):
            meta = doc.get("meta")
            if isinstance(meta, dict):
                obs = meta.get("observador")
                if isinstance(obs, str) and obs.strip():
                    observador = obs
            horas = doc.get("horas")
            if isinstance(horas, dict):
                for hora_val in horas.values():
                    if not isinstance(hora_val, dict):
                        continue
                    has_data = False
                    datos = hora_val.get("datos")
                    if isinstance(datos, dict):
                        for key, value in datos.items():
                            if key == "correc_alt" or value is None:
                                continue
                            if isinstance(value, str):
                                if value.strip():
                                    has_data = True
                                    break
                            else:
                                has_data = True
                                break
                    if not has_data:
                        synop = hora_val.get("synop")
                        if isinstance(synop, dict):
                            for value in synop.values():
                                if value is None:
                                    continue
                                if isinstance(value, str):
                                    if value.strip():
                                        has_data = True
                                        break
                                else:
                                    has_data = True
                                    break
                    if has_data:
                        horas_registradas += 1
        days.append(
            {
                "filename": entry.name,
                "date": date,
                "observador": observador,
                "horas_registradas": horas_registradas,
                "error_count": error_counts.get(date, 0),
                "correction_count": correction_counts.get(date, 0),
            }
        )
    days.sort(key=lambda d: d["date"])
    return days


# ---------------------------------------------------------------------------
# load (diario doc from F1 + overlay + auto-mark)
# ---------------------------------------------------------------------------


def _flatten_hora(hora_entry: dict, meta_observador: str, station: str) -> dict[str, Any]:
    """F4 doc hour -> oracle flat view (datos + frontend synop + calculado)."""
    flat: dict[str, Any] = {}
    datos = hora_entry.get("datos")
    if isinstance(datos, dict):
        flat.update(datos)
    synop = hora_entry.get("synop")
    if isinstance(synop, dict):
        for key, value in synop.items():
            flat[oms_calc.to_frontend_name(key)] = value
    calculado = hora_entry.get("calculado")
    if isinstance(calculado, dict):
        for key, value in calculado.items():
            flat[_CALCULADO_TO_FRONTEND.get(key, key)] = value
    observer = hora_entry.get("observador")
    if not (isinstance(observer, str) and observer.strip()) and meta_observador:
        observer = meta_observador
    if isinstance(observer, str) and observer:
        flat["observador"] = observer
    flat["station_id"] = station
    return flat


def _recalc_flat(
    conn: sqlite3.Connection, station: str, flat: dict[str, Any], prev_nddff: str
) -> None:
    """Oracle policy: psycho derived always rewritten, synoptic ones when set."""
    derived = _recalc_derived(
        {k: v for k, v in flat.items()},
        station,
        prev_nddff,
        _station_ch(conn, station) or None,
    )
    flat["tension_vapor"] = derived.get("tension_vapor", "")
    flat["humedad_relativa"] = derived.get("humedad_relativa", "")
    flat["punto_rocio"] = derived.get("punto_rocio", "")
    flat["diferencia"] = derived.get("diferencia", "")
    flat["pres_nmm"] = derived.get("pres_nmm", "")
    for key in ("visibilidad", "tend_dif", "tend_car", "tiempo_presente"):
        if derived.get(key):
            flat[key] = derived[key]


def load_observation_with_audit(
    conn: sqlite3.Connection, station: str, fecha: str
) -> dict[str, Any]:
    """Flattened diario view + marks + corrections (oracle semantics)."""
    _validate_station(station)
    year, month, day = _validate_fecha(fecha)
    text = summaries_repo.get_summary_doc(conn, station, year, month, "diario", day=day)
    if text is None:
        raise AuditError(f"Observacion no encontrada: {station} {fecha}")
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise AuditError(f"Documento diario corrupto: {station} {fecha}") from exc
    if not isinstance(doc, dict):
        raise AuditError(f"Documento diario corrupto: {station} {fecha}")

    meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
    meta_observador = meta.get("observador")
    meta_observador = meta_observador if isinstance(meta_observador, str) else ""
    observation: dict[str, Any] = {
        "station_id": station,
        "fecha": fecha,
        "observador": meta_observador,
    }
    horas = doc.get("horas") if isinstance(doc.get("horas"), dict) else {}
    for hora_key, hora_val in horas.items():
        if isinstance(hora_val, dict):
            observation[hora_key] = _flatten_hora(hora_val, meta_observador, station)

    corrections = audit_repo.get_corrections(conn, station, fecha)
    error_marks = audit_repo.get_error_marks(conn, station, fecha)

    # verbatim auto-mark rule: hours with data but missing observer
    nuevas: list[audit_repo.ErrorMark] = []
    for hora in HOURS:
        hora_val = observation.get(hora)
        if not isinstance(hora_val, dict):
            continue
        tiene_datos = False
        for key, value in hora_val.items():
            if key in _NON_DATA_KEYS or value is None:
                continue
            if isinstance(value, str):
                if value.strip():
                    tiene_datos = True
                    break
            else:
                tiene_datos = True
                break
        if not tiene_datos:
            continue
        obs_name = hora_val.get("observador")
        obs_name = obs_name.strip() if isinstance(obs_name, str) else ""
        if obs_name and obs_name != "Desconocido":
            continue
        if any(m.hora == hora and m.campo == "observador" for m in error_marks):
            continue
        mark = audit_repo.ErrorMark(
            id=None,
            station_id=station,
            fecha=fecha,
            hora=hora,
            campo="observador",
            tipo_error="Falta nombre de observador",
            nota="Generado automáticamente: observador no especificado en el turno.",
            marcado_por="Sistema de Calidad",
            created_at=_now_local(),
        )
        try:
            new_id = audit_repo.mark_error(
                conn,
                station_id=mark.station_id,
                fecha=mark.fecha,
                hora=mark.hora,
                campo=mark.campo,
                tipo_error=mark.tipo_error,
                marcado_por=mark.marcado_por,
                nota=mark.nota,
            )
        except audit_repo.MarkConflictError:
            continue
        nuevas.append(
            audit_repo.ErrorMark(
                id=new_id,
                station_id=mark.station_id,
                fecha=mark.fecha,
                hora=mark.hora,
                campo=mark.campo,
                tipo_error=mark.tipo_error,
                nota=mark.nota,
                marcado_por=mark.marcado_por,
                created_at=mark.created_at,
            )
        )
    error_marks = list(error_marks) + nuevas

    # approved-corrections overlay (pending corrections are ignored)
    for corr in corrections:
        if corr.estado == "aprobado" and corr.hora in observation:
            hora_val = observation[corr.hora]
            if isinstance(hora_val, dict):
                hora_val[corr.campo] = corr.valor_corregido

    # derived recalculation over the overlaid view (oracle policy)
    for hora in HOURS:
        hora_val = observation.get(hora)
        if not isinstance(hora_val, dict):
            continue
        prev = oms_calc.get_prev_hour(hora)
        prev_val = observation.get(prev)
        prev_nddff = ""
        if isinstance(prev_val, dict):
            raw = prev_val.get("meteo_4_1")
            if isinstance(raw, str):
                prev_nddff = raw
        _recalc_flat(conn, station, hora_val, prev_nddff)

    return {
        "observation": observation,
        "error_marks": [m.__dict__ for m in error_marks],
        "corrections": [c.__dict__ for c in corrections],
    }


# ---------------------------------------------------------------------------
# mark / unmark / note / propose / approve
# ---------------------------------------------------------------------------


def mark_error(
    conn: sqlite3.Connection,
    *,
    role: str | None,
    station_id: str,
    fecha: str,
    hora: str,
    campo: str,
    tipo_error: str,
    marcado_por: str,
    nota: str | None = None,
) -> dict[str, Any]:
    """Mark a slot (unique barrier speaks the oracle message)."""
    _check_audit_role(role)
    new_id = audit_repo.mark_error(
        conn,
        station_id=station_id,
        fecha=fecha,
        hora=hora,
        campo=campo,
        tipo_error=tipo_error,
        marcado_por=marcado_por,
        nota=nota,
    )
    return {
        "id": new_id,
        "station_id": station_id,
        "fecha": fecha,
        "hora": hora,
        "campo": campo,
        "tipo_error": tipo_error,
        "nota": nota,
        "marcado_por": marcado_por,
    }


def unmark_error(conn: sqlite3.Connection, *, role: str | None, mark_id: int) -> bool:
    """Drop a mark AND its slot corrections (oracle cascade)."""
    _check_audit_role(role)
    details = audit_repo.get_mark_details(conn, mark_id)
    if details is not None:
        station_id, fecha, hora, campo = details
        audit_repo.delete_corrections_by_mark(conn, station_id, fecha, hora, campo)
    audit_repo.unmark_error(conn, mark_id)
    return True


def update_mark_note(
    conn: sqlite3.Connection, *, role: str | None, mark_id: int, nota: str | None
) -> bool:
    """Edit a mark note (the report page inline edit)."""
    _check_audit_role(role)
    audit_repo.update_mark_note(conn, mark_id, nota)
    return True


def propose_correction(
    conn: sqlite3.Connection,
    *,
    role: str | None,
    station_id: str,
    fecha: str,
    hora: str,
    campo: str,
    valor_original: str,
    valor_corregido: str,
    justificacion: str,
    corregido_por: str,
) -> dict[str, Any]:
    """Propose a correction: starts ``pendiente`` until explicitly approved."""
    _check_audit_role(role)
    new_id = audit_repo.propose_correction(
        conn,
        station_id=station_id,
        fecha=fecha,
        hora=hora,
        campo=campo,
        valor_original=valor_original,
        valor_corregido=valor_corregido,
        justificacion=justificacion,
        corregido_por=corregido_por,
        aprobado_por=None,
        estado="pendiente",
    )
    return {
        "id": new_id,
        "station_id": station_id,
        "fecha": fecha,
        "hora": hora,
        "campo": campo,
        "valor_original": valor_original,
        "valor_corregido": valor_corregido,
        "justificacion": justificacion,
        "corregido_por": corregido_por,
        "aprobado_por": None,
        "estado": "pendiente",
    }


def approve_correction(
    conn: sqlite3.Connection, *, role: str | None, correction_id: int, aprobado_por: str
) -> dict[str, Any]:
    """Approve a proposed correction (sets estado + aprobado_por)."""
    _check_audit_role(role)
    row = conn.execute(
        "SELECT id, station_id, fecha, hora, campo, valor_original, valor_corregido,"
        " justificacion, corregido_por, aprobado_por, estado, created_at"
        " FROM corrections WHERE id = ?",
        (correction_id,),
    ).fetchone()
    if row is None:
        raise AuditError(f"Corrección no encontrada: {correction_id}")
    conn.execute(
        "UPDATE corrections SET estado = 'aprobado', aprobado_por = ? WHERE id = ?",
        (aprobado_por, correction_id),
    )
    conn.commit()
    return {
        "id": int(row["id"]),
        "station_id": row["station_id"],
        "fecha": row["fecha"],
        "hora": row["hora"],
        "campo": row["campo"],
        "valor_original": row["valor_original"],
        "valor_corregido": row["valor_corregido"],
        "justificacion": row["justificacion"],
        "corregido_por": row["corregido_por"],
        "aprobado_por": aprobado_por,
        "estado": "aprobado",
    }


# ---------------------------------------------------------------------------
# reports (F1 queries, dict surface for the UI)
# ---------------------------------------------------------------------------


def get_error_report(
    conn: sqlite3.Connection, *, station_id: str | None = None, year: str = "", month: str = ""
) -> list[dict[str, Any]]:
    """Detailed report rows (fecha DESC, hora ASC — oracle order)."""
    return [
        r.__dict__
        for r in audit_repo.get_error_report(
            conn, station_id=station_id, year=year or "", month=month or ""
        )
    ]


def get_person_summary(
    conn: sqlite3.Connection, *, station_id: str | None = None, year: str = "", month: str = ""
) -> list[dict[str, Any]]:
    """Per-person counts (errors desc — oracle order)."""
    return [
        r.__dict__
        for r in audit_repo.get_person_summary(
            conn, station_id=station_id, year=year or "", month=month or ""
        )
    ]


# ---------------------------------------------------------------------------
# export (copy + approved corrections -> new file, original never touched)
# ---------------------------------------------------------------------------


def export_corrected_json(
    conn: sqlite3.Connection,
    base_dir: str | Path,
    station_id: str,
    fecha: str,
    role: str | None = None,
) -> str:
    """Apply approved corrections to a COPY of the original day file."""
    _check_audit_role(role)
    _validate_station(station_id)
    parts = fecha.split("-") if isinstance(fecha, str) else []
    if len(parts) != 3:
        raise AuditError("Formato de fecha inválido. Debe ser YYYY-MM-DD")
    year, month, day = parts
    filename_date = f"{day}{month}{year}"
    station_fs = normalize_station_code(station_id)
    dir_path = Path(base_dir) / station_fs / year / month
    original = dir_path / f"{station_fs}{filename_date}.json"
    if not original.exists():
        raise AuditError(f"No existe la observación original en {original}")
    try:
        root = json.loads(original.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise AuditError(f"Observación original corrupta en {original}") from exc
    if not isinstance(root, dict):
        raise AuditError(f"Observación original corrupta en {original}")

    corrections = audit_repo.get_approved_corrections_for_date(conn, station_id, fecha)
    horas = root.get("horas")
    if isinstance(horas, dict):
        for hora, campo, valor_corregido in corrections:
            hora_val = horas.get(hora)
            if not isinstance(hora_val, dict):
                continue
            if campo in ("nombre_observador", "observador"):
                hora_val["observador"] = valor_corregido
            elif (datos_field := map_datos_field(campo)) is not None:
                datos_val = hora_val.get("datos")
                if isinstance(datos_val, dict):
                    datos_val[datos_field] = valor_corregido
                else:
                    hora_val["datos"] = {datos_field: valor_corregido}
            elif (calc_field := map_calculado_field(campo)) is not None:
                calc_val = hora_val.get("calculado")
                if isinstance(calc_val, dict):
                    calc_val[calc_field] = valor_corregido
                else:
                    hora_val["calculado"] = {calc_field: valor_corregido}
            else:
                synop_field = oms_calc.to_synop_name(campo)
                synop_val = hora_val.get("synop")
                if isinstance(synop_val, dict):
                    synop_val[synop_field] = valor_corregido
                else:
                    hora_val["synop"] = {synop_field: valor_corregido}

        # psycho recalculation over the corrected datos (oracle policy)
        for hora_val in horas.values():
            if not isinstance(hora_val, dict):
                continue
            datos = hora_val.get("datos")
            if not isinstance(datos, dict):
                continue
            derived = _recalc_derived(
                dict(datos), station_id, "", _station_ch(conn, station_id) or None
            )
            renamed = {
                "pres_nmm": "pres_nmm",
                "punto_rocio": "pr",
                "tension_vapor": "tv",
                "humedad_relativa": "hr",
                "diferencia": "dif",
            }
            calculado: dict[str, str] = {}
            for front, doc_key in renamed.items():
                if derived.get(front):
                    calculado[doc_key] = derived[front]
            if calculado:
                hora_val["calculado"] = calculado

    meta = root.get("meta")
    if isinstance(meta, dict):
        meta["ultima_actualizacion"] = _now_local()

    corr_dir = dir_path / "correcciones"
    corr_dir.mkdir(parents=True, exist_ok=True)
    corr_path = corr_dir / f"{station_id}{filename_date}_cor.json"
    payload = json.dumps(root, ensure_ascii=False, indent=2)
    tmp_path = corr_path.with_suffix(".json.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, corr_path)
    return str(corr_path)


# ---------------------------------------------------------------------------
# legacy month migration (oracle VERBATIM: rename-or-merge, never overwrite)
# ---------------------------------------------------------------------------


def migrate_legacy_month_dirs(base_dir: str | Path, role: str | None = None) -> dict[str, int]:
    """One-shot spanish month dirs -> numeric (idempotent, non-destructive)."""
    _check_admin_role(role)
    base = Path(base_dir)
    renamed = 0
    moved = 0
    if not base.exists():
        return {"renamed_dirs": 0, "moved_files": 0}
    for station_entry in sorted(base.iterdir(), key=lambda p: p.name):
        if not station_entry.is_dir():
            continue
        for year_entry in sorted(station_entry.iterdir(), key=lambda p: p.name):
            if not year_entry.is_dir():
                continue
            for month_entry in sorted(year_entry.iterdir(), key=lambda p: p.name):
                if not month_entry.is_dir():
                    continue
                num = month_name_to_num(month_entry.name)
                if num is None:
                    continue
                old_path = month_entry
                new_path = year_entry / num
                if not new_path.exists():
                    os.rename(old_path, new_path)
                    renamed += 1
                else:
                    for item in sorted(old_path.iterdir(), key=lambda p: p.name):
                        if not item.is_file():
                            continue
                        target = new_path / item.name
                        if target.exists():
                            continue  # never overwrite newer content
                        os.rename(item, target)
                        moved += 1
                    try:
                        if not any(old_path.iterdir()):
                            old_path.rmdir()
                    except OSError:
                        pass  # not empty (or raced): keep it, never force
    return {"renamed_dirs": renamed, "moved_files": moved}


def seed_report_fixture(conn: sqlite3.Connection) -> dict[str, int]:
    """Seed helper used by the F6 oracle script (not by the app)."""
    counts = {"marks": 0, "corrections": 0}
    for slot in (
        ("78451", "2025-06-10", "06Z", "ts", "auditor@x"),
        ("78451", "2025-06-10", "12Z", "th", "auditor@x"),
        ("78451", "2025-06-11", "06Z", "ts", "otro@y"),
    ):
        audit_repo.mark_error(
            conn,
            station_id=slot[0],
            fecha=slot[1],
            hora=slot[2],
            campo=slot[3],
            tipo_error="Sintaxis",
            marcado_por=slot[4],
        )
        counts["marks"] += 1
    for corr in (
        ("78451", "2025-06-10", "06Z", "ts", "20.0", "20.5", "auditor@x", "aprobado", "auditor@x"),
        ("78451", "2025-06-11", "06Z", "ts", "21.0", "21.5", "otro@y", "pendiente", None),
    ):
        audit_repo.propose_correction(
            conn,
            station_id=corr[0],
            fecha=corr[1],
            hora=corr[2],
            campo=corr[3],
            valor_original=corr[4],
            valor_corregido=corr[5],
            justificacion="j",
            corregido_por=corr[6],
            estado=corr[7],
            aprobado_por=corr[8],
        )
        counts["corrections"] += 1
    return counts


def export_state_snapshot(
    conn: sqlite3.Connection, *, station_id: str, year: str, month: str
) -> dict[str, Any]:
    """Hand-checkable oracle snapshot: deep copies of both report surfaces."""
    return {
        "error_report": copy.deepcopy(
            get_error_report(conn, station_id=station_id, year=year, month=month)
        ),
        "person_summary": copy.deepcopy(
            get_person_summary(conn, station_id=station_id, year=year, month=month)
        ),
    }
