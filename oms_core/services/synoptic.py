"""synoptic service — the observational core of PRD F4 (the queen screen).

Plain-Python port of the OLD oracle (read-only):

- ``OLD/frontend/src/features/synoptic/utils/synopticUtils.js`` — hour lists,
  base/even key models, ``hourCompletion``, ``parseFieldError``,
  ``sanitizeSynopGroup``;
- ``OLD/frontend/src/features/synoptic/utils/synopticDraft.js`` — draft bound
  to (station, fecha) with a validity check (P4.4);
- ``OLD/frontend/src-tauri/src/modules/synoptic/storage.rs`` —
  ``validar_grupos_synop`` (max 5 chars, digits/'/', exact error messages,
  nothing written on failure), ``build_horas_map`` (daily document shape),
  ``get_observation_core`` (frontend flattening on load);
- ``OLD .../app_config.rs`` + localStorage ``arca_observador_{station}`` —
  observer name remembered per station.

Neo Arca adaptation (ADR-02, ADR-03): the daily VERBATIM document lives in
``summary_logs`` (F1 repos, kind='diario'), the typed hourly row lives in
``observations``, and derived values cross the ``oms_calc`` boundary
(``recalculate_derived_fields_json``) with ``correc_alt`` resolved through the
stations repository (F2 D1). Every save is ONE transaction per hour: the row
and the document land together or not at all — the F1 write_guard is replaced
by SQLite transactions (documented equivalence, PRD §F1).

No Qt is imported here (ADR-03): this module is testable headless.
"""

from __future__ import annotations

import calendar
import json
import math
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import oms_calc
from oms_core.db.repositories import app_config
from oms_core.db.repositories import observations as observations_repo
from oms_core.db.repositories import stations as stations_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.db.repositories.observations import Observation

# ---------------------------------------------------------------------------
# Oracle constants (verbatim; do not "fix" the display order of HOURS, the
# hour-selector keyboard shortcuts Alt+1..8 and the UI grids depend on it).
# ---------------------------------------------------------------------------

#: Synoptic observation hours in the order the OLD UI shows them.
HOURS = ("06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z")

#: Even (synoptic main) hours — they carry Tmax/Tmin groups.
EVEN_HOURS = ("00Z", "06Z", "12Z", "18Z")

#: Odd hours — no Tmax/Tmin.
ODD_HOURS = ("03Z", "09Z", "15Z", "21Z")

#: Data keys every hour expects (the honest denominator of hourCompletion).
BASE_DATA_KEYS = (
    "ts", "th", "pres_est", "p3", "p24", "viento_dir", "viento_vel",
    "visibilidad", "ll",
    "meteo_2_1", "meteo_4_irixhvv", "meteo_4_1", "meteo_4_6",
    "meteo_6_2", "meteo_8_1", "extra_8ns_1", "extra_8ns_2",
)

#: Extra data keys only even hours expect (Tmax/Tmin and their 24h cousins).
EVEN_EXTRA_KEYS = ("t_max", "t_min", "t_max_24h", "t_min_24h")

#: Per-hour keys that are NOT data (never counted for completion).
HOUR_META = ("station_id", "fecha", "correc_alt", "nombre_observador")

#: Frontend key prefixes of SYNOP groups (sanitizeSynopGroup contract).
GROUP_PREFIXES = ("meteo_", "extra_")

#: Max group length (FM 12: every group is 5 characters, server-enforced).
GROUP_MAX_LEN = 5

#: dossier filename of the single draft slot (P4.4 binding contract).
DRAFT_FILE = "synoptic_draft.json"

#: app_config key prefix for the observer name remembered per station.
OBSERVER_KEY_PREFIX = "arca_observador_"

#: Exact oracle tail of validar_grupos_synop's over-long group message
#: (Rust string literals keep the trailing newline + indent bytes).
_GROUP_TOO_LONG = (
    "el grupo '{}' en hora {} excede 5 caracteres ({}). "
    "Ejemplos válidos: 32466, 120//, /////\n                     "
)
_GROUP_BAD_CHAR = (
    "el grupo '{}' en hora {} contiene un carácter inválido en la "
    "posición {} (solo dígitos y '/')"
)

_FIELD_ERROR_RE = re.compile(r"el grupo '([A-Za-z0-9_]+)' en hora ([0-9]{2}Z)")

_ERRO_CODIGO_INVALIDO = "Código de estación inválido"
_ERRO_CODIGO_CHARS = "Código de estación contiene caracteres no permitidos"
_ERRO_FECHA_FORMATO = "Formato de fecha inválido. Se espera YYYY-MM-DD"
_ERRO_FECHA_DIGITOS = "La fecha debe contener solo dígitos"
_ERRO_FECHA_RANGO = "La fecha no es una fecha de calendario real"


class SaveError(Exception):
    """Structured save failure ({stage, path, detail} + {field, hour}).

    Mirrors the oracle chain: storage.rs wraps failures in ``SaveErr`` and the
    frontend's ``parseFieldError`` extracts the guilty field/hour from the
    message. Here the caller gets both: parsed attributes AND the exact
    oracle message inside ``detail``/``str()``.
    """

    def __init__(
        self,
        detail: str,
        *,
        field: str | None = None,
        hour: str | None = None,
        stage: str = "validate",
        path: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.field = field
        self.hour = hour
        self.stage = stage
        self.path = path

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "path": self.path, "detail": self.detail}


# ---------------------------------------------------------------------------
# hour model helpers (synopticUtils.js ports)
# ---------------------------------------------------------------------------


def expected_keys(hora: str) -> tuple[str, ...]:
    """Data keys a given hour expects (same order as the oracle iteration)."""
    if hora in EVEN_HOURS:
        return BASE_DATA_KEYS + EVEN_EXTRA_KEYS
    return BASE_DATA_KEYS


def hour_completion(hour_data: object, hora: str) -> dict[str, float | int]:
    """Orientation heuristic port (NOT validation): non-empty expected keys."""
    expected = expected_keys(hora)
    done = 0
    data = hour_data if isinstance(hour_data, dict) else {}
    for key in expected:
        value = data.get(key)
        if value is not None and str(value).strip() != "":
            done += 1
    return {"done": done, "total": len(expected), "ratio": done / len(expected) if expected else 0}


def parse_field_error(message: object) -> dict[str, str] | None:
    """'el grupo X en hora YYZ...' -> {field, hour}, None when unattributable."""
    if not isinstance(message, str) or not message:
        return None
    match = _FIELD_ERROR_RE.search(message)
    if not match:
        return None
    return {"field": match.group(1), "hour": match.group(2)}


# ---------------------------------------------------------------------------
# input validation (json_handler validate_inputs port + real calendar)
# ---------------------------------------------------------------------------


def validate_station(station_code: object) -> str:
    """Oracle validate_inputs: 1..10 chars, ASCII alphanumeric + '_'."""
    if (
        not isinstance(station_code, str)
        or station_code == ""
        or len(station_code) > 10
    ):
        raise SaveError(_ERRO_CODIGO_INVALIDO)
    if not all(c.isascii() and (c.isalnum() or c == "_") for c in station_code):
        raise SaveError(_ERRO_CODIGO_CHARS)
    return station_code


def validate_fecha(fecha: object) -> tuple[int, int, int]:
    """Oracle validate_inputs (shape) + real-calendar day check (rule 9.2).

    Returns (year, month, day); leap years included (2024-02-29 valid).
    """
    text = fecha if isinstance(fecha, str) else ""
    parts = text.split("-")
    if len(parts) == 3:
        yyyy, mm, dd = parts
        if len(yyyy) != 4 or len(mm) != 2 or len(dd) != 2:
            raise SaveError(_ERRO_FECHA_FORMATO)
        if not (yyyy.isdigit() and mm.isdigit() and dd.isdigit()):
            raise SaveError(_ERRO_FECHA_DIGITOS)
    else:
        raise SaveError(_ERRO_FECHA_FORMATO)
    year, month, day = int(yyyy), int(mm), int(dd)
    if not (1990 <= year <= 2250 and 1 <= month <= 12 and 1 <= day <= calendar.monthrange(year, month)[1]):
        raise SaveError(_ERRO_FECHA_RANGO)
    return year, month, day


def format_date_display(fecha: str) -> str:
    """'2025-12-08' -> '08122025' (meta.fecha/filename convention)."""
    yyyy, mm, dd = fecha.split("-")
    return f"{dd}{mm}{yyyy}"


# ---------------------------------------------------------------------------
# group validation (validar_grupos_synop port, per single hour)
# ---------------------------------------------------------------------------


def sanitize_synop_group(value: object) -> str:
    """sanitizeSynopGroup port: drop everything but digits and '/', cap 5."""
    if value is None:
        return ""
    cleaned = "".join(c for c in str(value) if c.isdigit() or c == "/")
    return cleaned[:GROUP_MAX_LEN]


def _validate_groups(hour_data: dict, hora: str) -> None:
    """Server-side guarantee: the HTML maxLength is a suggestion, this is law."""
    for campo, valor in hour_data.items():
        if not campo.startswith(GROUP_PREFIXES):
            continue
        if not isinstance(valor, str):
            continue  # null/other types: the merge tolerates them (oracle)
        if len(valor) > GROUP_MAX_LEN:
            raise SaveError(_GROUP_TOO_LONG.format(campo, hora, valor), field=campo, hour=hora)
        bad_pos = next(
            (i for i, c in enumerate(valor) if not (c.isdigit() and c.isascii() or c == "/")),
            None,
        )
        if bad_pos is not None:
            raise SaveError(
                _GROUP_BAD_CHAR.format(campo, hora, bad_pos + 1), field=campo, hour=hora
            )


# ---------------------------------------------------------------------------
# daily document (build_horas_map port, per hour; verbatim doc in summary_logs)
# ---------------------------------------------------------------------------

#: frontend key -> daily-document 'datos' key (storage.rs build_horas_map).
_DATOS_KEY_MAP = {
    "ts": "ts", "th": "th", "pres_est": "pres_est", "p3": "p3", "p24": "p24",
    "viento_dir": "viento_dir", "viento_vel": "viento_vel",
    "visibilidad": "visibilidad", "t_max": "Tmax", "t_min": "Tmin",
    "ll": "LL", "t_max_24h": "Tmax_24h", "t_min_24h": "Tmin_24h",
    "ll_24h": "LL_24h", "correc_alt": "correc_alt",
}

#: derived frontend key -> daily-document 'calculado' key.
_CALCULADO_KEY_MAP = {
    "pres_nmm": "pres_nmm",
    "punto_rocio": "pr",
    "tension_vapor": "tv",
    "humedad_relativa": "hr",
    "diferencia": "dif",
}


def _build_hora_entry(hour_data: dict, derived: dict, observer: str | None) -> dict:
    """One hour's document structure: {observador, datos, synop, calculado}."""
    entry: dict[str, Any] = {}
    hora_observer = str(hour_data.get("nombre_observador") or "") or observer
    if hora_observer:
        entry["observador"] = hora_observer

    datos: dict[str, Any] = {}
    for data_key, doc_key in _DATOS_KEY_MAP.items():
        if data_key in hour_data:
            datos[doc_key] = hour_data[data_key]
    synop = {
        oms_calc.to_synop_name(key): value
        for key, value in hour_data.items()
        if key.startswith(("meteo_", "extra_"))
    }
    calculado = {
        doc_key: derived[data_key]
        for data_key, doc_key in _CALCULADO_KEY_MAP.items()
        if derived.get(data_key)
    }

    if synop:
        entry["synop"] = synop
    if datos:
        entry["datos"] = datos
    if calculado:
        entry["calculado"] = calculado
    return entry


def _diario_doc(conn: sqlite3.Connection, station: str, year: int, month: int, day: int) -> dict:
    """Load the stored diario document ({} when the day has none yet)."""
    text = summaries_repo.get_summary_doc(conn, station, year, month, "diario", day=day)
    if text is None:
        return {}
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise SaveError(
            f"el documento diario de {station} {fecha_label(year, month, day)} no es JSON válido: {exc}",
            stage="load",
            path=str(Path(station) / f"{year:04d}" / f"{month:02d}"),
        ) from exc
    if not isinstance(doc, dict):
        raise SaveError("el documento de guardado debe ser un objeto", stage="load")
    return doc


#: every hour_data key the UI can hold whose day-document synop name is
#: invertible (verified: to_synop_name is 1:1 over this whole universe).
_SYNOP_FIELD_KEYS: tuple[str, ...] = (
    "meteo_2_1", "meteo_4_irixhvv", "meteo_4_1", "meteo_4_6",
    "meteo_6_0", "meteo_6_2", "meteo_6_3", "meteo_6_4",
    "meteo_6_5", "meteo_6_6",
    "meteo_8_0", "meteo_8_1", "meteo_8_3", "meteo_8_4",
    "meteo_8_5", "meteo_8_6",
    *(f"meteo_{row}_{col}" for row in (10, 12) for col in range(7)),
    *(f"meteo_16_{i}" for i in range(5)),
    "extra_8ns_1", "extra_8ns_2",
)


def load_day(conn: sqlite3.Connection, station: str, fecha: str) -> dict[str, dict] | None:
    """Stored day as flat lowercase hour data (oracle get_observation path).

    Rebuilds hour_data maps from the diario document by inverting the
    ``_DATOS_KEY_MAP`` and the ``to_synop_name`` synop names. Returns None
    when the day has no stored document (the UI decides: blocks backwards
    nav, creates a fresh day forwards — verbatim oracle navigateToDay).
    """
    station = validate_station(station)
    year, month, day = validate_fecha(fecha)
    doc = _diario_doc(conn, station, year, month, day)
    horas_doc = doc.get("horas") if isinstance(doc, dict) else None
    if not isinstance(horas_doc, dict):
        return None
    reverse_datos = {doc_key: key for key, doc_key in _DATOS_KEY_MAP.items()}
    import oms_calc

    reverse_synop = {oms_calc.to_synop_name(key): key for key in _SYNOP_FIELD_KEYS}
    day: dict[str, dict] = {}
    for hora in HOURS:
        entry = horas_doc.get(hora)
        if not isinstance(entry, dict):
            day[hora] = {}
            continue
        hour_data: dict[str, Any] = {}
        datos = entry.get("datos")
        if isinstance(datos, dict):
            for doc_key, value in datos.items():
                key = reverse_datos.get(doc_key)
                if key is not None:
                    hour_data[key] = "" if value is None else str(value)
        synop = entry.get("synop")
        if isinstance(synop, dict):
            for synop_name, value in synop.items():
                key = reverse_synop.get(synop_name)
                if key is not None:
                    hour_data[key] = "" if value is None else str(value)
        observer = str(entry.get("observador") or "")
        if observer:
            hour_data["nombre_observador"] = observer
        day[hora] = hour_data
    return day


def fecha_label(year: int, month: int, day: int) -> str:
    return f"{day:02d}/{month:02d}/{year:04d}"


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _NoCommitConnection:
    """Repo-facing proxy whose commit() defers to the outer transaction.

    F1 repositories call ``conn.commit()`` after each upsert; inside an F4
    save the whole (row + document) pair must be one transaction, so the
    service drives a SQLite SAVEPOINT and gives the repositories this proxy
    whose commit is a no-op. Only the service releases (commits) the
    savepoint — the pair lands together or not at all.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, *args: Any, **kwargs: Any):
        return self._conn.execute(*args, **kwargs)

    def commit(self) -> None:  # deferred to the service's savepoint release
        return None


# ---------------------------------------------------------------------------
# save_hour — ONE transaction per hour
# ---------------------------------------------------------------------------


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def save_hour(
    conn: sqlite3.Connection,
    station: str,
    fecha: str,
    hora: str,
    data: dict,
    observer: str | None = None,
) -> None:
    """Validate, recalc derived, upsert the row and revise the daily doc.

    ONE transaction (SQLite SAVEPOINT): the observations row and the diario
    document land together or the failure leaves NOTHING written — the
    ``nothing is written on failure`` guarantee of validar_grupos_synop.
    """
    validate_station(station)
    year, month, day = validate_fecha(fecha)
    if hora not in HOURS:
        raise SaveError(f"'{hora}' no es una hora sinóptica", hour=hora)
    if not isinstance(data, dict):
        raise SaveError("los datos de la hora deben ser un objeto", hour=hora)
    _validate_groups(data, hora)

    # resolve station fallback ch (oracle correctness for presión NMM)
    station_row = stations_repo.get_station(conn, station)
    station_ch = "" if station_row is None else str(station_row.ch)

    # previous synoptic hour's Nddff for the tendencia group (same-document
    # lookup, like the oracle's get_observation_core)
    existing_doc = _diario_doc(conn, station, year, month, day)
    prev_hora = oms_calc.get_prev_hour(hora)
    prev_nddff = ""
    horas_existing = existing_doc.get("horas")
    if isinstance(horas_existing, dict):
        prev_entry = horas_existing.get(prev_hora)
        if isinstance(prev_entry, dict):
            prev_synop = prev_entry.get("synop")
            if isinstance(prev_synop, dict):
                value = prev_synop.get("Nddff")
                if isinstance(value, str):
                    prev_nddff = value

    derived = _recalc_derived(data, station, prev_nddff, station_ch)

    entry = _build_hora_entry(data, derived, observer)
    horas = dict(horas_existing) if isinstance(horas_existing, dict) else {}
    horas[hora] = entry

    meta = dict(existing_doc.get("meta")) if isinstance(existing_doc.get("meta"), dict) else {}
    meta["estacion"] = station
    meta["fecha"] = format_date_display(fecha)
    if observer:
        meta["observador"] = observer
    meta["ultima_actualizacion"] = _now_local()
    doc = dict(existing_doc)
    doc["meta"] = meta
    doc["horas"] = horas

    # observations row: typed REAL columns from base data + derived values
    obs = Observation(
        station_id=station,
        fecha=fecha,
        hora=hora,
        p_est=_to_float(data.get("pres_est")),
        p_nmm=_to_float(derived.get("pres_nmm")),
        rocio=_to_float(derived.get("punto_rocio")),
        t_vapor=_to_float(derived.get("tension_vapor")),
        hr=_to_float(derived.get("humedad_relativa")),
        v_dir_deg=_to_float(data.get("viento_dir")),
        v_vel=_to_float(data.get("viento_vel")),
        observador=(str(observer) if observer else "")
        or (str(data.get("nombre_observador")) if data.get("nombre_observador") else ""),
        source_sha256="",  # filled by the transaction below with the doc sha
    )

    conn.execute("SAVEPOINT f4_save_hour")
    try:
        tx = _NoCommitConnection(conn)
        text = json.dumps(doc, ensure_ascii=False)
        sha = _sha256_text(text)
        obs = Observation(**{**obs.__dict__, "source_sha256": sha})
        observations_repo.upsert_observation(tx, obs)
        summaries_repo.upsert_summary_doc(
            tx,
            station_id=station,
            year=year,
            month=month,
            kind="diario",
            data=text,
            sha256=sha,
            day=day,
        )
        conn.execute("RELEASE f4_save_hour")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO f4_save_hour")
        conn.execute("RELEASE f4_save_hour")
        raise


def _now_local() -> str:
    """chrono Local::now '%Y-%m-%d %H:%M:%S' equivalent."""
    import datetime as dt

    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _recalc_derived(
    hour_data: dict, station: str, prev_nddff: str, station_ch: str
) -> dict[str, str]:
    json_text = oms_calc.recalculate_derived_fields_json(
        None,  # station_id is pool-legacy, unused (F2 D3/D5)
        _str_or_none(hour_data.get("ts")),
        _str_or_none(hour_data.get("th")),
        _str_or_none(hour_data.get("pres_est")),
        _str_or_none(hour_data.get("p3")),
        _str_or_none(hour_data.get("p24")),
        _str_or_none(hour_data.get("correc_alt")),
        _str_or_none(hour_data.get("meteo_4_irixhvv")),
        _str_or_none(hour_data.get("meteo_4_6")),
        _str_or_none(hour_data.get("meteo_4_1")),
        _str_or_none(prev_nddff),
        station_ch or None,  # correc_alt_resuelta (F2 D1: Python resolves it)
    )
    return json.loads(json_text)


# ---------------------------------------------------------------------------
# pre-save review (SaveConfirmModal port)
# ---------------------------------------------------------------------------


def pre_save_review(day_data: dict) -> dict:
    """{partial: [{hora, done, total}], empty_count} — honest save preview."""
    partial: list[dict[str, int | str]] = []
    empty_count = 0
    for hora in HOURS:
        completion = hour_completion(day_data.get(hora) or {}, hora)
        if completion["done"] == 0:
            empty_count += 1
        elif completion["done"] < completion["total"]:
            partial.append({
                "hora": hora,
                "done": completion["done"],
                "total": completion["total"],
            })
    return {"partial": partial, "empty_count": empty_count}


# ---------------------------------------------------------------------------
# draft bound to (station, fecha) — P4.4 (synopticDraft.js port)
# ---------------------------------------------------------------------------


def config_dir(base: str | Path | None = None) -> Path:
    """Resolved config dir for UI-state files (drafts live here, NOT in the DB).

    ``ARCA_CONFIG_DIR`` env override (tests/advanced installs), else the
    platform keyboard ``~/.config/neearca`` (Home fallback, as F1 paths do).
    """
    env_base = os.environ.get("ARCA_CONFIG_DIR")
    if base is not None:
        return Path(base)
    if env_base:
        return Path(env_base)
    home = os.environ.get("HOME") or str(Path.home())
    return Path(home) / ".config" / "neearca"


def bind_draft(
    observations: object, active_hour: object, results_per_hour: object,
    station: str | None, fecha: str | None,
) -> dict:
    """Attach station/fecha to the payload (oracle bindDraft)."""
    return {
        "observations": observations,
        "active_hour": active_hour,
        "results_per_hour": results_per_hour,
        "station": station,
        "fecha": fecha,
    }


def is_draft_valid_for(draft: object, station: object, fecha: object) -> bool:
    """The draft is usable only for THIS station + THIS date (oracle)."""
    if not isinstance(draft, dict):
        return False
    if not draft.get("station") or not draft.get("fecha"):
        return False
    return draft.get("station") == station and draft.get("fecha") == fecha


def save_draft(base: str | Path | None, draft: dict) -> bool:
    """Persist the single draft slot; refuses unbound payloads."""
    if not (isinstance(draft, dict) and draft.get("station") and draft.get("fecha")):
        raise ValueError("el draft debe estar ligado a estación y fecha (bind_draft)")
    path = config_dir(base) / DRAFT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    return True


def load_draft(base: str | Path | None, station: str | None, fecha: str | None) -> dict | None:
    """Load the draft only when bound to THIS station+fecha (validity check).

    Missing, corrupt, or foreign drafts all return None (oracle: corrupt
    drafts are ignored, foreign drafts never resurrect data).
    """
    path = config_dir(base) / DRAFT_FILE
    if not path.exists():
        return None
    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if not is_draft_valid_for(draft, station, fecha):
        return None
    return draft


def clear_draft(base: str | Path | None) -> None:
    """Remove the draft slot silently (no-op when absent)."""
    path = config_dir(base) / DRAFT_FILE
    path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# observer remembered per station (localStorage arca_observador_* port, KV)
# ---------------------------------------------------------------------------


def remember_observer(conn: sqlite3.Connection, station: str, name: str) -> None:
    """Store the (trimmed, non-empty) observer name for the station."""
    trimmed = (name or "").strip()
    if not trimmed:
        return
    app_config.set(conn, OBSERVER_KEY_PREFIX + station, trimmed)


def observer_for(conn: sqlite3.Connection, station: str) -> str:
    """The observer last saved for this station ('' when never stored)."""
    return app_config.get(conn, OBSERVER_KEY_PREFIX + station) or ""
