"""Excel (.xlsx / .xlsm) -> schema 2 day document.

Port of the owner's original transformer
(``OLD/pipeline/src/arca_pipeline/transform/excel_to_json.py``) to the current
document schema. The cell maps and the decoding helpers are kept VERBATIM from
that file on purpose: they encode the station's own workbook layout, discovered
one cell at a time, and are not derivable from anything else in the project.

Three workbook layouts are supported, exactly as before:

``new``
    A ``3074`` worksheet with one row per hour plus the eight Z-hour sheets.
``old``
    Only the Z-hour sheets (no ``3074`` sheet).
``horrible``
    A ``3074`` sheet with every digit split into its own cell.

The output is a schema 2 document (see ``oms_core.services.document``)::

    {"schema": 2,
     "meta": {"estacion", "fecha" (ISO), "actualizado"},
     "synop": {hour: {"observador", "datos", "grupos"}},
     "cli": {"3074": {"horas": {row: {...}}}}}

Form keys (``meteo_4_1``, ``t_max``, ...) come from
``oms_core.services.document_map`` — the single mapping table of the project —
so this module never keeps a second copy of it.

The module is pure: no database, no UI, no writing.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from oms_core.services import document_map as dm

_LOGGER = logging.getLogger(__name__)

#: The eight Z-hour worksheets of the station workbook.
Z_HOUR_SHEET_NAMES = (
    "0000Z", "0003Z", "0006Z", "0009Z", "1200Z", "1500Z", "1800Z", "2100Z",
)

MONTH_NAMES_ES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12",
}

#: WMO group -> cell of the Z-hour sheet (verbatim from the original).
SYNOP_CELL_MAP = {
    "YYGGiw": {"row": 8, "col": "B"},
    "IrIXHVV": {"row": 10, "col": "A"},
    "Nddff": {"row": 10, "col": "B"},
    "1snTxTxTx": {"row": 10, "col": "C"},
    "2snTnTnTn": {"row": 10, "col": "D"},
    "7wwW1W2": {"row": 10, "col": "G"},
    "8NhCLCMCH": {"row": 12, "col": "A"},
    "3Ejjj": {"row": 12, "col": "F"},
    "5EEEjE": {"row": 12, "col": "G"},
    "56DLDMDH": {"row": 12, "col": "K"},
    "6RRRtr": {"row": 14, "col": "D"},
    "7R24R24R24R24": {"row": 14, "col": "E"},
    "8NsChshs_1": {"row": 14, "col": "F"},
    "8NsChshs_2": {"row": 14, "col": "G"},
    "0CSDL DM DH": {"row": 12, "col": "C"},
    "5nFnFnFn": {"row": 14, "col": "A"},
}

#: The 24 soil-temperature lanes (``9spspsp``), in reading order.
SPSP_CELLS = (
    (16, "C"), (16, "D"), (16, "E"), (16, "F"), (16, "G"),
    (18, "A"), (18, "B"), (18, "C"), (18, "D"), (18, "E"), (18, "F"), (18, "G"),
    (20, "A"), (20, "B"), (20, "C"), (20, "D"), (20, "E"), (20, "F"), (20, "G"),
    (22, "A"), (22, "B"), (22, "C"), (22, "D"), (22, "E"),
)

#: The two extra low-cloud groups the form exposes as separate fields.
CLOUD_EXTRA_CELLS = {"8NsChshs_5": (16, "A"), "8NsChshs_6": (16, "B")}

#: ``datos`` cells of the current workbook layout.
DATOS_CELLS_NEW = {
    "ts": {"row": 29, "col": "A"},
    "th": {"row": 33, "col": "A"},
    "pres_est": {"row": 31, "col": "C", "add_1000": True},
    "p3": {"row": 29, "col": "D", "add_1000": True},
    "p24": {"row": 29, "col": "E", "add_1000": True},
    "correc_alt": {"row": 33, "col": "C"},
    "Tmax": {"row": 29, "col": "F"},
    "Tmax_24h": {"row": 29, "col": "G"},
    "Tmin": {"row": 33, "col": "F"},
    "Tmin_24h": {"row": 33, "col": "G"},
    "LL": {"row": 37, "col": "F"},
    "LL_24h": {"row": 37, "col": "G"},
}

#: ``datos`` cells of the older workbook layout (two rows up).
DATOS_CELLS_OLD = {
    "ts": {"row": 27, "col": "A"},
    "th": {"row": 31, "col": "A"},
    "pres_est": {"row": 29, "col": "C", "add_1000": True},
    "p3": {"row": 27, "col": "D", "add_1000": True},
    "p24": {"row": 27, "col": "E", "add_1000": True},
    "correc_alt": {"row": 31, "col": "C"},
    "Tmax": {"row": 27, "col": "F"},
    "Tmax_24h": {"row": 27, "col": "G"},
    "Tmin": {"row": 31, "col": "F"},
    "Tmin_24h": {"row": 31, "col": "G"},
    "LL": {"row": 35, "col": "F"},
    "LL_24h": {"row": 35, "col": "G"},
}

#: Excel rows of the ``3074`` sheet that carry an hour (new layout).
CLI3074_DATA_ROWS = (11, 14, 17, 20, 23, 26, 29, 32)

#: Empty-string markers the workbook uses for "no data".
_PLACEHOLDERS = ("9", "9 ", " 9", "0", "")

#: Form key for each document ``datos`` key, straight from the mapping table.
_FORM_FOR_DATOS = {doc: form for form, doc in dm.OBSERVED_DATOS}
#: Form key for each WMO group of the mapping table (spaces normalised).
_FORM_FOR_SYNOP = {wmo.replace(" ", ""): form for form, wmo in dm.SYNOP_FIELDS}

_ROW_FOR_HOUR = {hour: 2 + 3 * (hour - 1) for hour in range(1, 9)}


# --------------------------------------------------------------------- cells


def col_letter_to_index(col_letter: str) -> int:
    """``A`` -> 1, ``AA`` -> 27 (openpyxl wants numbers)."""
    result = 0
    for char in col_letter.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


def get_cell_value(ws, row: int, col_letter: str) -> str:
    """Cell as text; empty or unusable cells read as an empty string."""
    try:
        value = ws.cell(row=row, column=col_letter_to_index(col_letter)).value
    except Exception:  # noqa: BLE001 - a broken cell is "no data", not a crash
        return ""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def format_pressure(val_str: str) -> str:
    """Pressures below 100 are stored without their leading 1000."""
    if not val_str:
        return ""
    try:
        value = float(val_str)
    except ValueError:
        return val_str
    if value < 100:
        value += 1000
    return f"{value:.1f}"


def bool_from_int(val) -> bool:
    """Workbook flags: 1/true/sí are checked, everything else is not."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip() in ("1", "True", "true", "Sí", "SI", "si")
    return False


# -------------------------------------------------------------------- dates


def _normalize_date(date: str | None) -> str | None:
    """Override date (``YYYY-MM-DD`` or ``DDMMYYYY``) as ``DDMMYYYY``."""
    if not date:
        return None
    text = str(date).strip()
    if len(text) == 8 and text.isdigit():
        return text
    try:
        return datetime.strptime(text.split()[0], "%Y-%m-%d").strftime("%d%m%Y")
    except ValueError:
        return None


def extract_date_from_filename(filename: str, date: str | None = None) -> str | None:
    """``DDMMYYYY`` from the file name; supports ``DDMMYY`` and ``10 OCTUBRE 2023``."""
    override = _normalize_date(date)
    if override:
        return override

    match = re.search(r"(\d{8})", filename)
    if match:
        candidate = match.group(1)
        day, month = int(candidate[:2]), int(candidate[2:4])
        if 1 <= day <= 31 and 1 <= month <= 12:
            return candidate

    match = re.search(r"(\d{6})", filename)
    if match:
        candidate = match.group(1)
        day, month = int(candidate[:2]), int(candidate[2:4])
        if 1 <= day <= 31 and 1 <= month <= 12:
            short_year = int(candidate[4:6])
            year = 2000 + short_year if short_year < 50 else 1900 + short_year
            return f"{candidate[:4]}{year}"

    month_pattern = "|".join(MONTH_NAMES_ES)
    match = re.search(
        r"(\d{1,2})\s*[_\s-]?\s*(" + month_pattern + r")\s*[_\s-]?\s*(\d{4})",
        filename,
        re.IGNORECASE,
    )
    if match:
        month = MONTH_NAMES_ES.get(match.group(2).lower(), "01")
        return f"{int(match.group(1)):02d}{month}{match.group(3)}"
    return None


def extract_date_from_excel(wb, date: str | None = None) -> str | None:
    """Fallback: the date typed in cell D8 of the first Z-hour sheet."""
    override = _normalize_date(date)
    if override:
        return override
    for sheet_name in wb.sheetnames:
        if sheet_name not in Z_HOUR_SHEET_NAMES:
            continue
        value = wb[sheet_name].cell(row=8, column=4).value
        if not value:
            continue
        if isinstance(value, datetime):
            return value.strftime("%d%m%Y")
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(str(value).split()[0], fmt).strftime("%d%m%Y")
            except ValueError:
                continue
    return None


def to_iso(fecha: str) -> str:
    """``DDMMYYYY`` -> ``YYYY-MM-DD`` (the schema stores ISO)."""
    if len(fecha) == 8 and fecha.isdigit():
        return f"{fecha[4:8]}-{fecha[2:4]}-{fecha[0:2]}"
    return fecha


# ------------------------------------------------------------------- format


def detect_format(wb) -> str:
    """``new`` / ``old`` / ``horrible`` / ``unknown`` — the original heuristic."""
    if "3074" not in wb.sheetnames:
        return "old" if any(s in Z_HOUR_SHEET_NAMES for s in wb.sheetnames) else "unknown"
    ws = wb["3074"]
    # "horrible": row 11 keeps one digit per cell instead of whole values
    val_c = get_cell_value(ws, 11, "C")
    val_d = get_cell_value(ws, 11, "D")
    if val_c.isdigit() and len(val_c) == 1 and val_d.isdigit() and len(val_d) == 1:
        return "horrible"
    return "new"


# ------------------------------------------------------------------- decode


def decode_pressure_h(digits: str) -> str:
    """``0120`` -> ``1012.0`` (the digits carry the last three of the pressure)."""
    if not digits or len(digits) < 4:
        return ""
    try:
        return f"{1000 + int(digits[1:4]) / 10.0:.1f}"
    except ValueError:
        return ""


def decode_tendency_h(digits: str) -> str:
    """``010`` -> ``01.0`` (tendency: two digits plus one decimal)."""
    if not digits or len(digits) < 3:
        return ""
    try:
        value = int(digits)
    except ValueError:
        return ""
    return f"{value // 10:02d}.{value % 10}"


def decode_temp_h(digits: str) -> str:
    """``269`` -> ``26.9`` (temperature: two digits plus one decimal)."""
    if not digits or len(digits) < 3:
        return ""
    try:
        value = int(digits)
    except ValueError:
        return ""
    return f"{value // 10}.{value % 10}"


# ------------------------------------------------------------------- builder


def build_cli3074(wb, fmt: str) -> dict[str, dict]:
    """The ``3074`` sheet as rows keyed by their form row number (2, 5, ...)."""
    rows: dict[str, dict] = {}
    if fmt == "old":
        return rows
    ws = wb["3074"]

    if fmt == "horrible":
        for row_num in CLI3074_DATA_ROWS:
            hour = get_cell_value(ws, row_num, "B")
            if not hour.isdigit():
                continue
            row: dict = {}
            pres = "".join(get_cell_value(ws, row_num, c) for c in ("C", "D", "E", "F"))
            nmm = "".join(get_cell_value(ws, row_num, c) for c in ("G", "H", "I", "J"))
            alti = "".join(get_cell_value(ws, row_num, c) for c in ("K", "L", "M", "N"))
            tend = "".join(get_cell_value(ws, row_num, c) for c in ("P", "Q", "R"))
            ts = "".join(get_cell_value(ws, row_num, c) for c in ("S", "T", "U"))
            th = "".join(get_cell_value(ws, row_num, c) for c in ("V", "W", "X"))
            ptor = "".join(get_cell_value(ws, row_num, c) for c in ("Y", "Z", "AA"))
            tvap = "".join(get_cell_value(ws, row_num, c) for c in ("AB", "AC", "AD"))
            row["pres_est"] = decode_pressure_h(pres)
            row["pres_nmm"] = decode_pressure_h(nmm)
            row["pres_alti"] = decode_pressure_h(alti)
            row["tend_car"] = get_cell_value(ws, row_num, "O")
            row["tend_dif"] = decode_tendency_h(tend)
            row["temp_seco"] = decode_temp_h(ts)
            row["temp_humedo"] = decode_temp_h(th)
            row["hum_ptor"] = decode_temp_h(ptor)
            row["hum_tvap"] = decode_temp_h(tvap)
            rows[str(_ROW_FOR_HOUR.get(int(hour), int(hour)))] = row
        return rows

    cols_map = {
        "C": "pres_est", "D": "pres_nmm", "E": "pres_alti",
        "F": "tend_car", "G": "tend_dif", "H": "temp_seco",
        "I": "temp_humedo", "J": "hum_ptor", "K": "hum_tvap",
        "L": "hum_hr", "M": "viento_dir", "N": "viento_vel",
        "O": "visibilidad",
    }
    fen_map = {
        "P": "tiempo_presente", "Q": "granizo", "R": "ventarron",
        "S": "neblina", "T": "trueno", "U": "relampago",
        "V": "rocio", "W": "polvo", "X": "calima",
        "Y": "niebla", "Z": "tornado",
    }
    for row_num in CLI3074_DATA_ROWS:
        hour = get_cell_value(ws, row_num, "B")
        if not hour.isdigit():
            continue
        row = {}
        fenomenos: dict[str, object] = {}
        for col_letter, key in cols_map.items():
            row[key] = get_cell_value(ws, row_num, col_letter)
        for col_letter, key in fen_map.items():
            value = get_cell_value(ws, row_num, col_letter)
            fenomenos[key] = value if key == "tiempo_presente" else bool_from_int(value)
        row["fenomenos"] = fenomenos
        rows[str(_ROW_FOR_HOUR.get(int(hour), int(hour)))] = row
    return rows


def build_hours(wb, fmt: str) -> dict[str, dict[str, str]]:
    """Each Z-hour sheet as a FORM-keyed hour dict (``meteo_4_1``, ``ts``...)."""
    datos_cells = DATOS_CELLS_NEW if fmt == "new" else DATOS_CELLS_OLD
    hours: dict[str, dict[str, str]] = {}

    for sheet_name in wb.sheetnames:
        if sheet_name not in Z_HOUR_SHEET_NAMES:
            continue
        ws = wb[sheet_name]

        yyggiw = get_cell_value(ws, 8, "B")
        if len(yyggiw) >= 5:
            hour = yyggiw[2:4]
        else:  # the sheet name: 0003Z -> 03Z
            digits = sheet_name.replace("Z", "").lstrip("0") or "00"
            hour = digits if len(digits) == 2 else f"0{digits}"
        z_key = f"{hour}Z"
        if z_key not in ("00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"):
            continue

        entry: dict[str, str] = {}
        for doc_key, cell in datos_cells.items():
            value = get_cell_value(ws, cell["row"], cell["col"])
            if value == "":
                continue
            if cell.get("add_1000"):
                value = format_pressure(value)
            form_key = _FORM_FOR_DATOS.get(doc_key, doc_key)
            entry[form_key] = value

        observer = get_cell_value(ws, 6, "B")
        if observer and observer != "Observador":
            entry["nombre_observador"] = observer

        for wmo, cell in SYNOP_CELL_MAP.items():
            value = get_cell_value(ws, cell["row"], cell["col"])
            if value in _PLACEHOLDERS:
                value = ""
            form_key = _FORM_FOR_SYNOP.get(wmo.replace(" ", ""))
            if form_key and value:
                entry[form_key] = value

        for index, (row, col) in enumerate(SPSP_CELLS, start=1):
            value = get_cell_value(ws, row, col)
            if value in _PLACEHOLDERS:
                value = ""
            form_key = _FORM_FOR_SYNOP.get(f"9spspsp_{index}")
            if form_key and value:
                entry[form_key] = value

        for wmo, (row, col) in CLOUD_EXTRA_CELLS.items():
            value = get_cell_value(ws, row, col)
            form_key = _FORM_FOR_SYNOP.get(wmo)
            # these two lanes only carry a group when it is complete
            if form_key and value and value not in _PLACEHOLDERS and len(str(value)) >= 4:
                entry[form_key] = str(value)

        hours[z_key] = entry
    return hours


# ------------------------------------------------------------------ public


def parse_excel(
    path: str | Path, *, station: str | None = None, date: str | None = None
) -> dict:
    """Read one workbook and return a schema 2 day document.

    ``station`` overrides the station number read from the book; ``date``
    overrides the observation date (``YYYY-MM-DD`` or ``DDMMYYYY``). Without
    them the book and then the file name are used, exactly like the original
    transformer — but a missing station or date RAISES instead of inventing a
    value, because a wrong day or station in the archive is worse than a
    failed import.
    """
    workbook_path = Path(path)
    keep_vba = workbook_path.suffix.lower() == ".xlsm"
    wb = load_workbook(workbook_path, data_only=True, keep_vba=keep_vba)
    try:
        fmt = detect_format(wb)
        if fmt == "unknown":
            raise ValueError(
                f"formato de libro no reconocido: {workbook_path.name}"
            )

        code = _station_code(wb, station)
        fecha = extract_date_from_filename(workbook_path.name, date)
        if not fecha:
            fecha = extract_date_from_excel(wb, date)
        if not fecha:
            raise ValueError(
                f"no se pudo determinar la fecha de {workbook_path.name}: "
                "ponerla en el nombre del archivo (DDMMAAAA) o indicarla"
            )

        hours = build_hours(wb, fmt)
        if not hours:
            raise ValueError(
                f"{workbook_path.name} no tiene ninguna hoja de hora (0000Z..2100Z)"
            )

        cli_rows = build_cli3074(wb, fmt)
        document: dict = {
            "schema": 2,
            "meta": {
                "estacion": code,
                "fecha": to_iso(fecha),
                "actualizado": datetime.now().isoformat(timespec="seconds"),
            },
            "synop": _synop_block(hours),
        }
        if cli_rows:
            cleaned = dm.clean_cli_block("cli3074", {"horas": cli_rows})
            if cleaned:
                document["cli"] = {"3074": cleaned}
        _LOGGER.info(
            "excel %s: formato %s, estación %s, %s, %d horas",
            workbook_path.name, fmt, code, to_iso(fecha), len(hours),
        )
        return document
    finally:
        wb.close()


def _station_code(wb, station: str | None) -> str:
    if station:
        return str(station)
    for sheet_name in wb.sheetnames:
        if sheet_name in Z_HOUR_SHEET_NAMES:
            value = get_cell_value(wb[sheet_name], 8, "C")
            if value:
                return value
    raise ValueError(
        "no se pudo determinar la estación del libro: indicarla explícitamente"
    )


def _synop_block(hours: dict[str, dict[str, str]]) -> dict[str, dict]:
    """Form-keyed hours -> the schema 2 ``synop`` block."""
    block: dict[str, dict] = {}
    for hora, entry in hours.items():
        block[hora] = {
            "observador": str(entry.get("nombre_observador") or ""),
            "datos": dm.datos_to_document(entry),
            "grupos": dm.groups_to_document(entry),
        }
    return block


__all__ = [
    "build_cli3074",
    "build_hours",
    "detect_format",
    "extract_date_from_excel",
    "extract_date_from_filename",
    "format_pressure",
    "get_cell_value",
    "parse_excel",
    "to_iso",
]
