"""cli service — CLI 3074/4074/5074 forms + fenómenos rules (PRD F4).

Ports the OLD oracle (read-only):

- ``OLD/frontend/src/features/synoptic/cli3074/utils/rowUpdate.js`` —
  ``enforceOneDecimal`` and ``applyCliFieldUpdate`` (booleans never pass the
  numeric formatter; siblings of ``fenomenos`` survive a toggle; input maps
  are never mutated). Echoed verbatim from ``OLD/frontend/src/test/
  cliFenomenos.test.js``;
- the exact per-CLI decimal field lists of the three pages
  (``cli3074/pages/Cli3074Page.jsx``, ``cli4074/pages/Cli4074Page.jsx``,
  ``cli5074/pages/Cli5074Page.jsx``), including the ceil-to-integer humidity
  fields;
- ``OLD/frontend/src-tauri/src/modules/cli/mod.rs`` — ``save_cli_generic`` /
  ``load_cli_generic`` merge semantics (a cli key is written into the SAME
  daily document without touching ``meta``/``horas``, replaces only its own
  key) and the ``load_cli3074_json_core`` derived-field pass on load.

In Neo Arca that daily document is the F1 verbatim ``summary_logs`` doc, so
CLI saves ride the same transactional document path as ``synoptic.save_hour``
(one SQLite SAVEPOINT per save; on failure nothing is written).
"""

from __future__ import annotations

import json
import math
import sqlite3

import oms_calc
from oms_core.db.repositories import stations as stations_repo
from oms_core.db.repositories import summaries as summaries_repo
from oms_core.services.synoptic import SaveError, validate_fecha, validate_station

# ---------------------------------------------------------------------------
# rowUpdate.js port (fenómenos + one-decimal numerics)
# ---------------------------------------------------------------------------

#: Decimal fields of the CLI 3074 sheet (exact oracle list).
DECIMAL_FIELDS_3074 = [
    "pres_est", "pres_nmm", "pres_alti", "tend_dif",
    "temp_seco", "temp_humedo", "hum_ptor", "hum_tvap",
    "viento_vel", "visibilidad",
]
#: Humidity fields rounded UP to integers (oracle hum_hr / hum_max / hum_min).
CEIL_FIELDS_3074 = ["hum_hr"]

#: Decimal fields of the CLI 4074 sheet (exact oracle list).
DECIMAL_FIELDS_4074 = ["lluvia_6h", "temp_max", "temp_min"]
CEIL_FIELDS_4074: list[str] = []

#: Decimal fields of the CLI 5074 sheet (exact oracle list).
DECIMAL_FIELDS_5074 = [
    "temp_max", "temp_min", "rafaga_dir", "rafaga_vel",
    "pres_max", "pres_min", "insolac", "radiac", "lluvia",
    "evap_tanque_a", "punto_rocio", "recorrido_viento",
    "lect_bar", "term_anexo", "correc_temp", "correc_alt", "pres_nmm", "pres_est",
    "d5", "d10", "d15", "d20", "d25", "d50", "d100",
    "piche", "tanque_c", "evaporigrafo",
]
CEIL_FIELDS_5074 = ["hum_max", "hum_min"]

#: The ten fenómenos booleans of the 3074 sheet (WMO 020003 abbrs on the UI).
DEFAULT_FENOMENOS: dict[str, bool] = {
    "granizo": False, "ventarron": False, "neblina": False, "trueno": False,
    "relampago": False, "rocio": False, "polvo": False, "calima": False,
    "niebla": False, "tornado": False,
}

CLI_KEYS = ("cli3074", "cli4074", "cli5074")


def enforce_one_decimal(
    val: object,
    field: str | None,
    *,
    decimal_fields: list[str] | tuple[str, ...] = (),
    ceil_fields: list[str] | tuple[str, ...] = (),
) -> object:
    """rowUpdate.js enforceOneDecimal, parameterised per CLI.

    - None/''/'': passes through unchanged;
    - ceil fields: Math.ceil to an integer string;
    - decimal fields: when the string has MORE than one decimal digit, it is
      rounded half-away (positive up, negative down — Math.ceil/floor) to
      exactly one decimal; otherwise untouched;
    - everything else (booleans, non-numeric strings, plain numbers in other
      fields) returns as received.
    """
    if val is None or val == "":
        return val

    if field in ceil_fields:
        try:
            number = float(val)
        except (TypeError, ValueError):
            return val
        return str(_ceil_int(number))

    if field in decimal_fields:
        text = str(val)
        parts = text.split(".")
        if len(parts) > 1 and len(parts[1]) > 1:
            try:
                number = float(text)
            except ValueError:
                return val
            return f"{_rounded_one_decimal(number):.1f}"
    return val


def default_row(decimal_fields: list[str] | tuple[str, ...] = ()) -> dict:
    """A fresh empty row schema (numerics '', fenómenos defaults when used)."""
    row: dict = {key: "" for key in decimal_fields}
    row["fenomenos"] = dict(DEFAULT_FENOMENOS, tiempo_presente="")
    return row


def apply_cli_field_update(
    rows: dict,
    row_num: object,
    field_path: str,
    value: object,
    *,
    decimal_fields: list[str] | tuple[str, ...] = DECIMAL_FIELDS_3074,
    ceil_fields: list[str] | tuple[str, ...] = CEIL_FIELDS_3074,
) -> dict:
    """Pure, immutable row update (oracle rowUpdate.applyCliFieldUpdate).

    - ``fenomenos.<x>`` boolean values are stored as-is (never formatted);
    - every sibling under ``fenomenos`` is preserved (dict copy semantics);
    - numeric fields go through :func:`enforce_one_decimal`;
    - the input map is never mutated.
    """
    next_rows = dict(rows)
    row = dict(next_rows.get(row_num) or {})
    fenomenos = dict(row.get("fenomenos") or {})

    if field_path.startswith("fenomenos."):
        sub_field = field_path.split(".", 1)[1]
        # booleans: stored as-is, without the numeric formatter (oracle rule)
        fenomenos[sub_field] = value if isinstance(value, bool) else enforce_one_decimal(
            value, sub_field, decimal_fields=decimal_fields, ceil_fields=ceil_fields
        )
    else:
        row[field_path] = enforce_one_decimal(
            value, field_path, decimal_fields=decimal_fields, ceil_fields=ceil_fields
        )

    row["fenomenos"] = fenomenos
    next_rows[row_num] = row
    return next_rows


def _ceil_int(val: float) -> int:
    """Math.ceil port for the humidity integer fields."""
    return math.ceil(val)


def _rounded_one_decimal(val: float) -> float:
    """Oracle rounding: Math.ceil(n*10)/10 up, Math.floor(n*10)/10 down."""
    return math.ceil(val * 10) / 10 if val >= 0 else math.floor(val * 10) / 10


# ---------------------------------------------------------------------------
# save / load through the daily document (modules/cli/mod.rs port)
# ---------------------------------------------------------------------------


def save_cli(
    conn: sqlite3.Connection,
    station: str,
    fecha: str,
    cli_key: str,
    data: object,
) -> None:
    """Write ``cli_key`` into the daily document, touching nothing else.

    One transaction (SAVEPOINT): the merged document replaces its own cli key
    and keeps meta/horas/sibling cli keys — oracle save_cli_generic semantics
    on the F1 verbatim doc. On failure nothing is written.
    """
    if cli_key not in CLI_KEYS:
        raise ValueError(f"cli_key inválida: '{cli_key}' (esperada una de {CLI_KEYS})")
    station = validate_station(station)
    year, month, day = validate_fecha(fecha)
    if not isinstance(data, (dict, list)):
        raise SaveError("el documento cli debe ser un objeto", stage="validate")

    text = summaries_repo.get_summary_doc(conn, station, year, month, "diario", day=day)
    if text is None:
        receiver = {
            "meta": {"estacion": station, "fecha": f"{day:02d}{month:02d}{year:04d}"}
        }
    else:
        try:
            parsed = json.loads(text)
        except ValueError as exc:
            raise SaveError(
                f"el documento diario de {station} no es JSON válido: {exc}", stage="load"
            ) from exc
        if not isinstance(parsed, dict):
            raise SaveError("el documento cli debe ser un objeto", stage="load")
        receiver = dict(parsed)
    receiver[cli_key] = data

    conn.execute("SAVEPOINT f4_save_cli")
    try:
        tx = _NoCommitConnection(conn)
        body = json.dumps(receiver, ensure_ascii=False)
        summaries_repo.upsert_summary_doc(
            tx,
            station_id=station,
            year=year,
            month=month,
            kind="diario",
            data=body,
            sha256=_sha256_text(body),
            day=day,
        )
        conn.execute("RELEASE f4_save_cli")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO f4_save_cli")
        conn.execute("RELEASE f4_save_cli")
        raise


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _NoCommitConnection:
    """Repo-facing proxy deferring commit to the service savepoint (see synoptic)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, *args: object, **kwargs: object):
        return self._conn.execute(*args, **kwargs)  # type: ignore[arg-type]

    def commit(self) -> None:
        return None


def load_cli(conn: sqlite3.Connection, station: str, fecha: str, cli_key: str) -> object | None:
    """The stored cli document, or None when the day has no document/key."""
    if cli_key not in CLI_KEYS:
        raise ValueError(f"cli_key inválida: '{cli_key}' (esperada una de {CLI_KEYS})")
    station = validate_station(station)
    year, month, day = validate_fecha(fecha)
    text = summaries_repo.get_summary_doc(conn, station, year, month, "diario", day=day)
    if text is None:
        return None
    doc = json.loads(text)
    return doc.get(cli_key) if isinstance(doc, dict) else None


# ---------------------------------------------------------------------------
# load-side derived pass for CLI 3074 (load_cli3074_json_core port)
# ---------------------------------------------------------------------------

#: hora-key prev map of the oracle (rows are keys "1".."24").
_PREV_ROW = {str(i): (str(i - 1) if i > 1 else None) for i in range(1, 25)}


#: hora sinóptica -> fila del CLI 3074 (oracle synopRows / monthly adapter).
SYNOP_ROWS: tuple[tuple[str, str], ...] = (
    ("06Z", "2"), ("09Z", "5"), ("12Z", "8"), ("15Z", "11"),
    ("18Z", "14"), ("21Z", "17"), ("00Z", "20"), ("03Z", "23"),
)


def _normalize_cli_block(value: object) -> dict | None:
    """Accept the legacy flat block (``{"2": {...}}``) and the current one.

    The application writes ``{"horas": {"2": {...}}}``; the documents produced
    by the old build kept the rows at the top level, so the loader found no
    ``horas`` key and the view rendered an empty table.
    """
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("horas"), dict):
        return value
    rows = {k: v for k, v in value.items() if str(k).isdigit() and isinstance(v, dict)}
    if not rows:
        return value
    return {**value, "horas": rows}


def _viento_dir_from_nddff(nddff: str) -> str:
    """dd (digits 2-3 of Nddff) x 10 -> degrees, as the oracle did."""
    text = str(nddff or "")
    if len(text) >= 3 and text[1] != "/" and text[2] != "/":
        try:
            return str(int(text[1:3]) * 10)
        except ValueError:
            return ""
    return ""


def _overlay_from_synoptic(row: dict, hour: dict, ch: str) -> dict:
    """Fill the row's derived fields from its synoptic hour (rule R3).

    One call to the calculation boundary returns every derived value, so the
    CLI row can never disagree with the form: the synoptic hour owns them.
    """
    out = dict(row)
    ts = str(hour.get("ts") or "")
    th = str(hour.get("th") or "")
    pres_est = str(hour.get("pres_est") or "")
    nddff = str(hour.get("meteo_4_1") or "")
    raw = oms_calc.recalculate_derived_fields_json(
        None, ts, th, pres_est, str(hour.get("p3") or ""),
        str(hour.get("p24") or ""), "", str(hour.get("meteo_4_irixhvv") or ""),
        str(hour.get("meteo_4_6") or ""), nddff, "", ch,
    )
    derived = json.loads(raw) if isinstance(raw, str) else (raw or {})
    values = {
        "temp_seco": ts,
        "temp_humedo": th,
        "pres_est": pres_est,
        "pres_nmm": derived.get("pres_nmm"),
        "tend_dif": derived.get("tend_dif"),
        "tend_car": derived.get("tend_car"),
        "visibilidad": derived.get("visibilidad"),
        "hum_hr": derived.get("humedad_relativa"),
        "hum_tvap": derived.get("tension_vapor"),
        "hum_ptor": derived.get("punto_rocio"),
    }
    for key, value in values.items():
        if value:
            out[key] = str(value)
    direction = _viento_dir_from_nddff(nddff)
    if direction:
        out["viento_dir"] = direction
    return out


def _synoptic_hours(conn: sqlite3.Connection, station: str, fecha: str) -> dict[str, dict]:
    from oms_core.services import document as document_service

    day = document_service.load_day_document(conn, station, fecha)
    return day.horas if day is not None else {}


def load_cli3074(conn: sqlite3.Connection, station: str, fecha: str) -> dict | None:
    """cli3074 document with the automatic fields recalculated on load.

    Port of ``load_cli3074_json_core``: tendencia dif/car, visibilidad from
    IrIXHVV and tiempo_presente per hora-row, using oms_calc pure functions.
    """
    stored = load_cli(conn, station, fecha, "cli3074")
    if stored is not None and not isinstance(stored, dict):
        return None
    value = _normalize_cli_block(stored) if stored is not None else None
    horas_obj = value.get("horas") if isinstance(value, dict) else None
    if not isinstance(horas_obj, dict):
        horas_obj = {}

    new_horas: dict = {}
    for hora_key, hora_data in horas_obj.items():
        if not isinstance(hora_data, dict):
            new_horas[hora_key] = hora_data
            continue
        new_hora = dict(hora_data)

        pres_est = str(hora_data.get("pres_est") or "")
        p3 = str(hora_data.get("p3") or "")

        existing_dif = str(hora_data.get("tend_dif") or "")
        dif = oms_calc.format_dif(existing_dif) if existing_dif else oms_calc.calc_dif(pres_est, p3)
        if dif:
            new_hora["tend_dif"] = dif

        existing_car = str(hora_data.get("tend_car") or "")
        car = existing_car or oms_calc.calc_car(pres_est, p3)
        if car:
            new_hora["tend_car"] = car

        irixhv = str(hora_data.get("meteo_4_irixhvv") or "")
        visibilidad = oms_calc.get_visibilidad_from_irixhv(irixhv)
        if visibilidad:
            new_hora["visibilidad"] = visibilidad

        seven_ww = str(hora_data.get("meteo_4_6") or "")
        nddff = str(hora_data.get("meteo_4_1") or "")
        prev_hour = _PREV_ROW.get(str(hora_key))
        nddff_prev = ""
        if prev_hour is not None:
            prev_rows = horas_obj.get(prev_hour)
            if isinstance(prev_rows, dict):
                nddff_prev = str(prev_rows.get("meteo_4_1") or "")
        tiempo_presente = oms_calc.calc_tiempo_presente(seven_ww, nddff, nddff_prev)
        if tiempo_presente:
            new_hora["tiempo_presente"] = tiempo_presente

        new_horas[hora_key] = new_hora

    # rule R3: for the eight synoptic hours the synoptic form owns the values,
    # so the CLI row shows what the observer typed there (and what derives from
    # it) instead of a stale copy.
    synoptic = _synoptic_hours(conn, station, fecha)
    if synoptic:
        station_row = stations_repo.get_station(conn, station)
        ch = str(station_row.ch) if station_row is not None else ""
        for hora, row_key in SYNOP_ROWS:
            hour = synoptic.get(hora)
            if not hour:
                continue
            existing = new_horas.get(row_key)
            new_horas[row_key] = _overlay_from_synoptic(
                existing if isinstance(existing, dict) else {}, hour, ch)

    # a day with synoptic data yields rows even when no CLI block was stored:
    # the view is a projection of the form, not a separate record.
    if value is None and not new_horas:
        return None
    result = dict(value or {})
    result["horas"] = new_horas
    return result
