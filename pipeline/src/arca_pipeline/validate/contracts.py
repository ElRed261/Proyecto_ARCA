"""Pandera data contracts for the bronze -> silver boundary.

What it does: validates every observation row BEFORE it enters silver so the
silver layer only ever contains physically plausible data.
What it produces: a validated pandas DataFrame (or raises SchemaError).
What it consumes: the DataFrame produced by transform/.
What it must NOT import: load/orchestrate modules.

Physical ranges follow WMO guidance and get ENFORCED as soon as the transform
layer produces the fields:

    temperature [degC]: [-60, 60]
    humidity [%]:       [0, 100]
    pressure [hPa]:     [850, 1100]
    wind speed [km/h]:  [0, 200]

Validation happens at the boundary on purpose: rejected rows go to the
rejected/ area with their raw payload, never into silver.

Day JSON -> silver rows
=======================
`validate_day` flattens ONE day JSON from transform/excel_to_json.py into one
row per synoptic hour. The silver `hora` column is always UTC `HHZ` — the only
hour namespace the contract knows. The transform emits the 8 Z-hour sheets
under `horas` (keys "00Z".."21Z") and the 3-hourly SYNOP groups under
`cli3074` keyed by LOCAL hour. The golden fixture pins the offset: cli3074["2"]
and horas["06Z"] hold the same pressure (1014.2 hPa), so Z = (local + 4) % 24
and `cli3074` observations join onto their Z-hour through that offset. Fields
absent from either source become NaN — missing data is allowed into silver,
INVALID data is not.

station_code pattern
====================
`^\\d{4,6}$` — numeric WMO station codes. The transform only ever emits digits
(get_station_number reads an all-digit cell, fallback "78486"), so the loose
`^[A-Za-z0-9_]+$` variant buys nothing today. If a future station is
alphanumeric (ICAO-style) the change is one line here.
"""

from datetime import UTC, datetime

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import DataFrameModel, Field
from pandera.typing import Series

# cli3074 hour (local) -> UTC Z hour: Z = (local + 4) % 24, pinned by the fixture
LOCAL_TO_Z_OFFSET_H = 4

SILVER_COLUMNS = [
    "station_code",   # str
    "fecha",          # str YYYY-MM-DD
    "hora",           # str HHZ
    "ts",             # float
    "th",             # float
    "pres_est",       # float
    "pres_nmm",       # float
    "p3",             # float
    "p24",            # float
    "correc_alt",     # float
    "Tmax",           # float
    "Tmin",           # float
    "LL",             # float
    "temp_seco",      # float
    "temp_humedo",    # float
    "hum_ptor",       # float
    "hum_tvap",       # float
    "hum_hr",         # float
    "viento_dir",     # str
    "viento_vel",     # float
    "visibilidad",    # float
    "tend_car",       # str nullable
    "tend_dif",       # str nullable
    "source_sha256",  # str 64 chars
    "validated_at",   # str ISO
]

_FLOAT_COLS = {
    "ts", "th", "pres_est", "pres_nmm", "p3", "p24", "correc_alt",
    "Tmax", "Tmin", "LL", "temp_seco", "temp_humedo", "hum_ptor",
    "hum_tvap", "hum_hr", "viento_vel", "visibilidad",
}
_IDENTITY_COLS = {"station_code", "fecha", "hora", "source_sha256", "validated_at"}

# horas[hora]["datos"] key -> silver column
_DATOS_FIELDS = {
    "ts": "ts", "th": "th", "pres_est": "pres_est", "p3": "p3",
    "p24": "p24", "correc_alt": "correc_alt", "Tmax": "Tmax",
    "Tmin": "Tmin", "LL": "LL",
}
# cli3074[hora] key -> silver column
_CLI3074_FIELDS = {
    "pres_est": "pres_est", "pres_nmm": "pres_nmm", "temp_seco": "temp_seco",
    "temp_humedo": "temp_humedo", "hum_ptor": "hum_ptor",
    "hum_tvap": "hum_tvap", "hum_hr": "hum_hr", "viento_dir": "viento_dir",
    "viento_vel": "viento_vel", "visibilidad": "visibilidad",
    "tend_car": "tend_car", "tend_dif": "tend_dif",
}


class SilverSchema(DataFrameModel):
    """Base columns every silver row must satisfy.

    Identity columns (station/fecha/hora/source/validated_at) are required.
    Physical columns may be NaN (missing readings are common at some hours);
    range checks below simply skip missing values and reject only present
    values that fall outside the WMO physical bounds.
    """

    station_code: Series[str] = Field(str_matches=r"^\d{4,6}$", nullable=False)
    fecha: Series[str] = Field(str_matches=r"^\d{4}-\d{2}-\d{2}$", nullable=False)
    # ^\d{2}Z$ alone would admit "25Z"; synoptic hours are 00..23Z
    hora: Series[str] = Field(str_matches=r"^(?:[01]\d|2[0-3])Z$", nullable=False)
    source_sha256: Series[str] = Field(str_length={"min_value": 64, "max_value": 64}, nullable=False)
    validated_at: Series[str] = Field(nullable=False)

    ts: Series[float] = Field(ge=-60.0, le=60.0, nullable=True)
    th: Series[float] = Field(ge=-60.0, le=60.0, nullable=True)
    temp_seco: Series[float] = Field(ge=-60.0, le=60.0, nullable=True)
    temp_humedo: Series[float] = Field(ge=-60.0, le=60.0, nullable=True)
    Tmax: Series[float] = Field(ge=-60.0, le=60.0, nullable=True)
    Tmin: Series[float] = Field(ge=-60.0, le=60.0, nullable=True)

    pres_est: Series[float] = Field(ge=850.0, le=1100.0, nullable=True)
    pres_nmm: Series[float] = Field(ge=850.0, le=1100.0, nullable=True)
    p3: Series[float] = Field(ge=850.0, le=1100.0, nullable=True)
    p24: Series[float] = Field(ge=850.0, le=1100.0, nullable=True)

    hum_hr: Series[float] = Field(ge=0.0, le=100.0, nullable=True)
    hum_ptor: Series[float] = Field(ge=0.0, le=100.0, nullable=True)
    hum_tvap: Series[float] = Field(ge=0.0, le=100.0, nullable=True)

    LL: Series[float] = Field(ge=0.0, nullable=True)
    viento_vel: Series[float] = Field(ge=0.0, le=200.0, nullable=True)
    visibilidad: Series[float] = Field(ge=0.0, nullable=True)

    correc_alt: Series[float] = Field(nullable=True)
    tend_car: Series[str] = Field(nullable=True)
    tend_dif: Series[str] = Field(nullable=True)
    viento_dir: Series[str] = Field(nullable=True)

    @pa.dataframe_check(name="tmax_gte_tmin")
    def _tmax_gte_tmin(cls, df):
        if "Tmax" not in df.columns or "Tmin" not in df.columns:
            return pd.Series(True, index=df.index)
        both = df["Tmax"].notna() & df["Tmin"].notna()
        ok = pd.Series(True, index=df.index)
        ok[both] = df.loc[both, "Tmax"] >= df.loc[both, "Tmin"]
        return ok


def validate_silver(df: pd.DataFrame) -> pd.DataFrame:
    """Validate `df` against SilverSchema; raises SchemaError on failure.

    `lazy=True` so a single run surfaces EVERY failing row/column (the message
    set drives the rejected/ payload), not just the first violation.
    """
    return SilverSchema.validate(df, lazy=True)


def _to_float(value):  # ponytail: transform emite strings; "" = missing
    if value is None:
        return float("nan")
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in ("nan", "none"):
            return float("nan")
        value = s
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _to_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SILVER_COLUMNS)


def validate_day(day_json: dict) -> tuple[pd.DataFrame, list[str]]:
    """Flatten one day JSON (transform schema) into a silver DataFrame.

    Returns `(df, errores)`. Validation errors never raise: they are collected
    as readable strings (the pipeline moves rejected rows to rejected/). Rows
    that fail are dropped; rows that pass are returned validated.
    """
    errors: list[str] = []
    meta = day_json.get("meta") or {}
    station = _to_str(meta.get("estacion"))
    fecha_raw = _to_str(meta.get("fecha"))
    if not station or not fecha_raw:
        return _empty_df(), ["metadatos incompletos (estacion/fecha)"]

    fecha = fecha_raw
    if len(fecha_raw) == 8 and fecha_raw.isdigit():
        try:
            fecha = datetime.strptime(fecha_raw, "%d%m%Y").replace(tzinfo=UTC).strftime("%Y-%m-%d")
        except ValueError:
            return _empty_df(), [f"fecha inválida: {fecha_raw}"]

    sha = _to_str(day_json.get("source_sha256"))
    validated_at = _to_str(day_json.get("validated_at")) or datetime.now(UTC).isoformat()

    horas = day_json.get("horas") or {}
    cli3074 = day_json.get("cli3074") or {}

    # Candidate hours: every Z-hour emitted by horas, plus every non-empty
    # cli3074 local hour mapped to its Z-hour.
    candidates = set(horas.keys())
    for local_h, cli_data in cli3074.items():
        if not str(local_h).isdigit():
            continue
        if not isinstance(cli_data, dict) or not any(cli_data.values()):
            continue
        z = (int(local_h) + LOCAL_TO_Z_OFFSET_H) % 24
        candidates.add(f"{z:02d}Z")

    rows: list[dict] = []
    for z_key in sorted(candidates):
        cli_local = str((int(z_key.replace("Z", "")) - LOCAL_TO_Z_OFFSET_H) % 24)
        # ponytail: el CLI numera horas locales '1'..'24'; el módulo da '0',
        # clave que nunca existe — remapear a '24' para no perder sus campos.
        if cli_local == "0":
            cli_local = "24"
        cli_row = cli3074.get(str(cli_local)) if isinstance(cli3074, dict) else None
        if not isinstance(cli_row, dict):
            cli_row = {}

        row = {col: float("nan") for col in _FLOAT_COLS}
        row.update({col: "" for col in _IDENTITY_COLS | {"viento_dir", "tend_car", "tend_dif"}})
        row["station_code"] = station
        row["fecha"] = fecha
        row["hora"] = z_key
        row["source_sha256"] = sha
        row["validated_at"] = validated_at

        datos = (horas.get(z_key) or {}).get("datos") or {}
        for src, col in _DATOS_FIELDS.items():
            value = datos.get(src)
            if _to_str(value):
                row[col] = _to_float(value) if col in _FLOAT_COLS else _to_str(value)

        for src, col in _CLI3074_FIELDS.items():
            value = cli_row.get(src)
            if not isinstance(value, str) or value.strip():
                if not _to_str(value):
                    continue
                if col == "pres_est":
                    row[col] = _to_float(value)  # cli3074 synoptic pressure wins
                elif col in _FLOAT_COLS:
                    row[col] = _to_float(value)
                else:
                    row[col] = _to_str(value)

        present = {c for c in row if c not in _IDENTITY_COLS and (pd.notna(row[c]) if c in _FLOAT_COLS else row[c])}
        if not present:
            continue  # hora sin ningún dato observado
        rows.append(row)

    if not rows:
        return _empty_df(), ["sin horas válidas"]

    df = pd.DataFrame(rows, columns=SILVER_COLUMNS)
    df = df[SILVER_COLUMNS]

    try:
        return validate_silver(df), errors
    except (pa.errors.SchemaError, pa.errors.SchemaErrors) as err:
        bad_indexes = set()
        for failure in _iter_failures(err):
            msg, idx = _failure_message(failure, df)
            if msg:
                errors.append(msg)
            if idx is not None:
                bad_indexes.add(idx)
        errors = _dedupe(errors)
        good = df.drop(index=sorted(bad_indexes))
        good = good.drop_duplicates()
        if good.empty:
            return _empty_df(), errors
        return good, errors


def _iter_failures(err):
    fc = getattr(err, "failure_cases", None)
    if fc is None or len(fc) == 0:
        return []
    return [row for _, row in fc.iterrows()]


def _failure_message(failure, df) -> tuple[str | None, int | None]:
    idx = failure.get("index")
    idx = int(idx) if pd.notna(idx) else None
    col = failure.get("column")
    col = str(col) if pd.notna(col) else ""
    val = failure.get("failure_case")
    val = "NaN" if isinstance(val, float) and pd.isna(val) else val
    check = str(failure.get("check", "") or "")

    hora = df.loc[idx, "hora"] if (idx is not None and idx in df.index) else "?"

    if "tmax_gte_tmin" in check.lower():
        return f"hora {hora}: Tmax < Tmin", idx
    if col == "hora":
        return f"hora '{val}' inválida", idx
    if col == "source_sha256":
        return f"source_sha256 inválido (longitud {len(str(val))} != 64)", idx
    if col == "fecha":
        return f"fecha '{val}' inválida", idx
    if col == "station_code":
        return f"station_code '{val}' inválido", idx
    return f"hora {hora}: {col}={val} fuera de rango", idx


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out