"""
Excel to JSON - SYNOP data transformation core (pure, UI-free).

This module is the extraction of the pure transformation core from
miscelaneos/scratch/excel_to_json.py (the original Tkinter prototype).

Boundary: every function below is PURE — it operates on a loaded workbook
(`wb`) or a plain value and returns data. There is NO UI (no tkinter, no
dialogs) and NO file I/O beyond `parse_excel`, which is the single entry
point that opens/reads/closes a workbook file.

Supported Excel formats (see detect_format):
  - 'new'     : worksheet '3074' with complete row data
  - 'old'     : no '3074' worksheet, only Z-hour sheets
  - 'horrible': '3074' with digits split into individual cells
  - 'unknown' : unrecognized → parse_excel raises ValueError

Return contract of parse_excel (one JSON-serializable dict per file):
  {
    "cli3074": { <hour "1".."24">: { ... } },
    "horas":   { <"00Z".."21Z">: { "datos", "observador", "synop" } },
    "meta":    { "estacion", "fecha" (DDMMYYYY), "ultima_actualizacion" }
  }

NOTE: function names and JSON keys are kept EXACTLY as in the original
prototype on purpose; any drift against the Rust backend is resolved in
another layer, not here.
"""

import re
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

# ============================================================================
# CONSTANTES Y MAPEOS
# ============================================================================

Z_HOUR_SHEET_NAMES = ['0000Z', '0003Z', '0006Z', '0009Z', '1200Z', '1500Z', '1800Z', '2100Z']
EXCEL_EXTS = ('.xls', '.xlsx', '.xlsm', '.xlsb')

MONTH_NAMES_ES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12',
    'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12',
}

# Z-hour → celdas synop
SYNOP_CELL_MAP = {
    'YYGGiw': {'row': 8, 'col': 'B'},
    'IrIXHVV': {'row': 10, 'col': 'A'},
    'Nddff': {'row': 10, 'col': 'B'},
    '1snTxTxTx': {'row': 10, 'col': 'C'},
    '2snTnTnTn': {'row': 10, 'col': 'D'},
    '7wwW1W2': {'row': 10, 'col': 'G'},
    '8NhCLCMCH': {'row': 12, 'col': 'A'},
    '3Ejjj': {'row': 12, 'col': 'F'},
    '5EEEjE': {'row': 12, 'col': 'G'},
    '56DLDMDH': {'row': 12, 'col': 'K'},
    '6RRRtr': {'row': 14, 'col': 'D'},
    '7R24R24R24R24': {'row': 14, 'col': 'E'},
    '8NsChshs_1': {'row': 14, 'col': 'F'},
    '8NsChshs_2': {'row': 14, 'col': 'G'},
    '0CSDL DM DH': {'row': 12, 'col': 'C'},
    '5nFnFnFn': {'row': 14, 'col': 'A'},
}

SPSP_CELLS = [
    (16, 'C'), (16, 'D'), (16, 'E'), (16, 'F'), (16, 'G'),
    (18, 'A'), (18, 'B'), (18, 'C'), (18, 'D'), (18, 'E'), (18, 'F'), (18, 'G'),
    (20, 'A'), (20, 'B'), (20, 'C'), (20, 'D'), (20, 'E'), (20, 'F'), (20, 'G'),
    (22, 'A'), (22, 'B'), (22, 'C'), (22, 'D'), (22, 'E'),
]
CLOUD_EXTRA_CELLS = {
    '8NsChshs_5': (16, 'A'),
    '8NsChshs_6': (16, 'B'),
}

# Datos para formato normal (hoja Z-hour)
DATOS_CELLS_NEW = {
    'ts': {'row': 29, 'col': 'A'},
    'th': {'row': 33, 'col': 'A'},
    'pres_est': {'row': 31, 'col': 'C', 'add_1000': True},
    'p3': {'row': 29, 'col': 'D', 'add_1000': True},
    'p24': {'row': 29, 'col': 'E', 'add_1000': True},
    'correc_alt': {'row': 33, 'col': 'C'},
    'Tmax': {'row': 29, 'col': 'F'},
    'Tmax_24h': {'row': 29, 'col': 'G'},
    'Tmin': {'row': 33, 'col': 'F'},
    'Tmin_24h': {'row': 33, 'col': 'G'},
    'LL': {'row': 37, 'col': 'F'},
    'LL_24h': {'row': 37, 'col': 'G'},
}
DATOS_CELLS_OLD = {
    'ts': {'row': 27, 'col': 'A'},
    'th': {'row': 31, 'col': 'A'},
    'pres_est': {'row': 29, 'col': 'C', 'add_1000': True},
    'p3': {'row': 27, 'col': 'D', 'add_1000': True},
    'p24': {'row': 27, 'col': 'E', 'add_1000': True},
    'correc_alt': {'row': 31, 'col': 'C'},
    'Tmax': {'row': 27, 'col': 'F'},
    'Tmax_24h': {'row': 27, 'col': 'G'},
    'Tmin': {'row': 31, 'col': 'F'},
    'Tmin_24h': {'row': 31, 'col': 'G'},
    'LL': {'row': 35, 'col': 'F'},
    'LL_24h': {'row': 35, 'col': 'G'},
}

# cli3074 filas de datos (formato normal)
CLI3074_DATA_ROWS = [11, 14, 17, 20, 23, 26, 29, 32]


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def col_letter_to_index(col_letter):
    result = 0
    for char in col_letter.upper():
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result


def get_cell_value(ws, row, col_letter):
    """Lee valor de celda."""
    try:
        cell = ws.cell(row=row, column=col_letter_to_index(col_letter))
        val = cell.value
        if val is None:
            return ""
        if isinstance(val, str):
            return val.strip()
        elif isinstance(val, (int, float)):
            if isinstance(val, float) and val.is_integer():
                return str(int(val))
            return str(val)
        return str(val)
    except Exception:  # noqa: BLE001  # ponytail: celda vacía/formato raro -> "" como el prototipo
        return ""


def format_pressure(val_str):
    """Formatea presión. Si < 1000, suma 1000."""
    if not val_str:
        return ""
    try:
        val = float(val_str)
        if val < 100:
            val += 1000
        return f"{val:.1f}"
    except ValueError:
        return val_str


def bool_from_int(val):
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip() in ('1', 'True', 'true', 'Sí', 'SI', 'si')
    return False


# ============================================================================
# EXTRACCIÓN Y CONVERSIÓN DE FECHAS
# ============================================================================

def _normalize_date(date):
    """Normaliza una fecha inyectada (YYYY-MM-DD o DDMMYYYY) a DDMMYYYY."""
    if not date:
        return None
    d = str(date).strip()
    if len(d) == 8 and d.isdigit():
        return d
    try:
        return datetime.strptime(d.split()[0], "%Y-%m-%d").strftime("%d%m%Y")  # noqa: DTZ007  # ponytail: fecha fija del template WMO
    except ValueError:
        return None


def extract_date_from_filename(filename, date: str | None = None):
    """Extrae DDMMYYYY del nombre. Soporta DDMMYYYY, DDMMYY, y texto."""
    override = _normalize_date(date)
    if override:
        return override

    # 8 dígitos consecutivos
    match = re.search(r'(\d{8})', filename)
    if match:
        date_str = match.group(1)
        day, month = int(date_str[:2]), int(date_str[2:4])
        if 1 <= day <= 31 and 1 <= month <= 12:
            return date_str

    # 6 dígitos consecutivos (DDMMYY) → expandir a siglo 20/21
    match = re.search(r'(\d{6})', filename)
    if match:
        date_str = match.group(1)
        day, month = int(date_str[:2]), int(date_str[2:4])
        if 1 <= day <= 31 and 1 <= month <= 12:
            year_short = int(date_str[4:6])
            year = 2000 + year_short if year_short < 50 else 1900 + year_short
            return f"{date_str[:4]}{year}"

    # Formato texto: "10 OCTUBRE 2023"
    month_pattern = '|'.join(MONTH_NAMES_ES.keys())
    regex2 = r'(\d{1,2})\s*[_\s-]?\s*(' + month_pattern + r')\s*[_\s-]?\s*(\d{4})'
    match = re.search(regex2, filename, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month_num = MONTH_NAMES_ES.get(match.group(2).lower(), '01')
        year = match.group(3)
        return f"{day:02d}{month_num}{year}"

    return None


def extract_date_from_excel(wb, date: str | None = None):
    """Fallback: extrae fecha de celda D8 de primera hoja Z."""
    override = _normalize_date(date)
    if override:
        return override

    for sheet_name in wb.sheetnames:
        if sheet_name in Z_HOUR_SHEET_NAMES:
            ws = wb[sheet_name]
            val = ws.cell(row=8, column=4).value
            if val:
                if isinstance(val, datetime):
                    return val.strftime("%d%m%Y")
                for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
                    try:
                        dt = datetime.strptime(str(val).split()[0], fmt)  # noqa: DTZ007  # ponytail: fecha viva del template
                        return dt.strftime("%d%m%Y")
                    except ValueError:
                        continue
    return None


# ============================================================================
# DETECCIÓN DE FORMATO
# ============================================================================

def detect_format(wb):
    """Detecta formato: 'new', 'old', 'horrible', 'unknown'."""
    if '3074' not in wb.sheetnames:
        # Sin 3074 → viejo
        z_sheets = [s for s in wb.sheetnames if s in Z_HOUR_SHEET_NAMES]
        return 'old' if z_sheets else 'unknown'

    ws = wb['3074']
    # Verificar formato horrible: dígitos separados en fila 11
    val_c = get_cell_value(ws, 11, 'C')
    val_d = get_cell_value(ws, 11, 'D')
    if val_c and len(val_c) == 1 and val_c.isdigit() and val_d and len(val_d) == 1 and val_d.isdigit():  # ponytail: heurística del prototipo
        return 'horrible'

    return 'new'


# ============================================================================
# DECODIFICACIÓN FORMATO HORRIBLE
# ============================================================================

def decode_pressure_h(digits):
    """Decodifica presión de formato horrible. 0120 → 1012.0"""
    if not digits or len(digits) < 4:
        return ""
    try:
        value = int(digits[1:4])
        result = 1000 + value / 10.0
        return f"{result:.1f}"
    except ValueError:
        return ""


def decode_tendency_h(digits):
    """Decodifica tendencia. PQR=010 → '01.0'"""
    if not digits or len(digits) < 3:
        return ""
    try:
        val = int(digits)
        whole = val // 10
        decimal = val % 10
        return f"{whole:02d}.{decimal}"
    except ValueError:
        return ""


def decode_temp_h(digits):
    """Decodifica temperatura. 269 → '26.9'"""
    if not digits or len(digits) < 3:
        return ""
    try:
        val = int(digits)
        whole = val // 10
        decimal = val % 10
        return f"{whole}.{decimal}"
    except ValueError:
        return ""


# ============================================================================
# CONSTRUCCIÓN DE SECCIONES JSON
# ============================================================================

def create_empty_cli3074():
    """Crea estructura cli3074 vacía."""
    result = {}
    for hour in range(1, 25):
        hour_str = str(hour)
        result[hour_str] = {
            "fenomenos": {
                "calima": False, "granizo": False, "neblina": False,
                "niebla": False, "polvo": False, "relampago": False,
                "rocio": False, "tiempo_presente": "", "tornado": False,
                "trueno": False, "ventarron": False
            },
            "hum_hr": "", "hum_ptor": "", "hum_tvap": "",
            "pres_alti": "", "pres_est": "", "pres_nmm": "",
            "temp_humedo": "", "temp_seco": "",
            "tend_car": "", "tend_dif": "",
            "viento_dir": "", "viento_vel": "",
            "visibilidad": ""
        }
    return result


def build_cli3074(wb, fmt):
    """Construye cli3074 según formato."""
    result = create_empty_cli3074()

    if fmt == 'old' or '3074' not in wb.sheetnames:
        return result

    ws = wb['3074']

    if fmt == 'horrible':
        # Formato horrible: dígitos separados
        for row_num in CLI3074_DATA_ROWS:
            hour_val = get_cell_value(ws, row_num, 'B')
            if not hour_val or not hour_val.isdigit():
                continue
            hour_str = hour_val

            # Presión C-F
            pres_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['C', 'D', 'E', 'F']])
            result[hour_str]['pres_est'] = decode_pressure_h(pres_digits)

            # NMM G-J
            nmm_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['G', 'H', 'I', 'J']])
            result[hour_str]['pres_nmm'] = decode_pressure_h(nmm_digits)

            # Altímetro K-N
            alti_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['K', 'L', 'M', 'N']])
            if alti_digits.strip():
                result[hour_str]['pres_alti'] = decode_pressure_h(alti_digits)

            # Tendencia CAR=O, DIF=P-R
            tend_car = get_cell_value(ws, row_num, 'O')
            tend_dif_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['P', 'Q', 'R']])
            result[hour_str]['tend_car'] = tend_car
            result[hour_str]['tend_dif'] = decode_tendency_h(tend_dif_digits)

            # Temperaturas
            ts_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['S', 'T', 'U']])
            th_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['V', 'W', 'X']])
            result[hour_str]['temp_seco'] = decode_temp_h(ts_digits)
            result[hour_str]['temp_humedo'] = decode_temp_h(th_digits)

            # Humedad
            pr_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['Y', 'Z', 'AA']])
            tv_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['AB', 'AC', 'AD']])
            result[hour_str]['hum_ptor'] = decode_temp_h(pr_digits)
            result[hour_str]['hum_tvap'] = decode_temp_h(tv_digits)
            # HR% no está en formato horrible

    else:  # formato new
        cols_map = {
            'C': 'pres_est', 'D': 'pres_nmm', 'E': 'pres_alti',
            'F': 'tend_car', 'G': 'tend_dif', 'H': 'temp_seco',
            'I': 'temp_humedo', 'J': 'hum_ptor', 'K': 'hum_tvap',
            'L': 'hum_hr', 'M': 'viento_dir', 'N': 'viento_vel',
            'O': 'visibilidad',
        }
        fen_map = {
            'P': 'tiempo_presente', 'Q': 'granizo', 'R': 'ventarron',
            'S': 'neblina', 'T': 'trueno', 'U': 'relampago',
            'V': 'rocio', 'W': 'polvo', 'X': 'calima',
            'Y': 'niebla', 'Z': 'tornado',
        }
        for row_num in CLI3074_DATA_ROWS:
            hour_val = get_cell_value(ws, row_num, 'B')
            if not hour_val or not hour_val.isdigit():
                continue
            hour_str = hour_val
            for col_letter, json_key in cols_map.items():
                result[hour_str][json_key] = get_cell_value(ws, row_num, col_letter)
            for col_letter, fen_key in fen_map.items():
                val = get_cell_value(ws, row_num, col_letter)
                if fen_key == 'tiempo_presente':
                    result[hour_str]["fenomenos"][fen_key] = val
                else:
                    result[hour_str]["fenomenos"][fen_key] = bool_from_int(val)

    return result


def build_horas(wb, fmt):
    """Construye la sección horas."""
    datos_cells = DATOS_CELLS_NEW if fmt == 'new' else DATOS_CELLS_OLD

    horas = {}
    for hh in ['00', '03', '06', '09', '12', '15', '18', '21']:
        horas[f"{hh}Z"] = {
            "datos": {
                "LL": "", "LL_24h": "",
                "Tmax": "", "Tmax_24h": "",
                "Tmin": "", "Tmin_24h": "",
                "correc_alt": "",
                "p24": "", "p3": "",
                "pres_est": "",
                "th": "", "ts": ""
            },
            "observador": "",
            "synop": {
                "0CSDL DM DH": "",
                "1snTxTxTx": "", "2snTnTnTn": "",
                "3Ejjj": "", "56DLDMDH": "",
                "5EEEjE": "", "5nFnFnFn": "",
                "6RRRtr": "", "7R24R24R24R24": "",
                "7wwW1W2": "",
                "8NhCLCMCH": "",
                "8NsChshs_1": "", "8NsChshs_2": "",
                "8NsChshs_5": "", "8NsChshs_6": "",
                "IrIXHVV": "", "Nddff": "", "YYGGiw": ""
            }
        }
        for i in range(1, 25):
            horas[f"{hh}Z"]["synop"][f"9spspsp_{i}"] = ""

    for sheet_name in wb.sheetnames:
        if sheet_name not in Z_HOUR_SHEET_NAMES:
            continue

        ws = wb[sheet_name]
        yyggiw = get_cell_value(ws, 8, 'B')
        if len(yyggiw) >= 5:
            hour_str = yyggiw[2:4]
        else:
            hour_str = sheet_name.replace('Z', '').lstrip('0') or '00'
            if len(hour_str) == 1:
                hour_str = '0' + hour_str
        z_key = f"{hour_str}Z"

        if z_key not in horas:
            continue

        # DATOS
        for json_key, cell_info in datos_cells.items():
            val = get_cell_value(ws, cell_info['row'], cell_info['col'])
            if val == "":
                continue
            if cell_info.get('add_1000'):
                val = format_pressure(val)
            horas[z_key]["datos"][json_key] = val

        # OBSERVADOR
        observador = get_cell_value(ws, 6, 'B')
        if observador and observador != "Observador":
            horas[z_key]["observador"] = observador

        # SYNOP
        for json_key, cell_info in SYNOP_CELL_MAP.items():
            val = get_cell_value(ws, cell_info['row'], cell_info['col'])
            if val in ('9', '9 ', ' 9', '0', ''):
                val = ""
            horas[z_key]["synop"][json_key] = val

        for idx, (row, col) in enumerate(SPSP_CELLS, start=1):
            val = get_cell_value(ws, row, col)
            if val in ('9', '9 ', ' 9', '0', ''):
                val = ""
            horas[z_key]["synop"][f"9spspsp_{idx}"] = val

        for json_key, (row, col) in CLOUD_EXTRA_CELLS.items():
            val = get_cell_value(ws, row, col)
            if val in ('9', '9 ', ' 9', '0', '8', ''):
                val = ""
            if val and len(str(val)) >= 4:
                horas[z_key]["synop"][json_key] = val
            else:
                horas[z_key]["synop"][json_key] = ""

    return horas


# ============================================================================
# MERGE DE JSONs CON LA MISMA FECHA
# ============================================================================

def is_placeholder(val):
    """Detecta si un valor es placeholder sin información real."""
    if val is None or val == "":
        return True
    if isinstance(val, str):
        v = val.strip()
        if v in ('9', '9 ', ' 9', '0', '0.0', '555', '555 ', '', 'INAP', 'inap'):
            return True
    return False


def quality_score(obj):
    """Puntuación de calidad: +2 datos reales, +1 genérico, -1 placeholder."""
    if obj is None or obj == "" or obj == []:
        return 0
    if isinstance(obj, dict):
        return sum(quality_score(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(quality_score(v) for v in obj)
    if isinstance(obj, bool):
        return 1 if obj else 0
    # Valor string/number
    if is_placeholder(obj):
        return -1
    return 2


def merge_jsons(json_list):
    """Combina múltiples JSONs del mismo día."""
    if not json_list:
        return None
    if len(json_list) == 1:
        return json_list[0]

    result = {
        "cli3074": create_empty_cli3074(),
        "horas": {},
        "meta": json_list[0]["meta"].copy()
    }

    # Merge cli3074: por cada hora, tomar la versión con más datos
    for hour in range(1, 25):
        hour_str = str(hour)
        best = None
        best_score = -1
        for data in json_list:
            hour_data = data["cli3074"].get(hour_str, {})
            score = quality_score(hour_data)
            if score > best_score:
                best = hour_data
                best_score = score
        result["cli3074"][hour_str] = best

    # Merge horas: combinar TODAS las Z-hours de TODOS los archivos
    all_z_hours = set()
    for data in json_list:
        all_z_hours.update(data["horas"].keys())

    for z_key in all_z_hours:
        # Si la hora existe en múltiples archivos, tomar la versión con más datos
        best = None
        best_score = -1
        for data in json_list:
            if z_key in data["horas"]:
                z_data = data["horas"][z_key]
                score = quality_score(z_data.get("datos", {})) + quality_score(z_data.get("synop", {}))
                if score > best_score:
                    best = z_data
                    best_score = score

        if best:
            result["horas"][z_key] = best

    return result


# ============================================================================
# PROCESAMIENTO PRINCIPAL
# ============================================================================

def get_station_number(wb, station: str | None = None):
    """Extrae número de estación de hoja Z, u override explícito, o fallback."""
    if station:
        return station
    for sheet_name in wb.sheetnames:
        if sheet_name in Z_HOUR_SHEET_NAMES:
            val = get_cell_value(wb[sheet_name], 8, 'C')
            if val and val.isdigit():
                return val
    return "78486"


def parse_excel(path: str | Path, *, station: str | None = None, date: str | None = None) -> dict:
    """Procesa un Excel y retorna el dict JSON (cli3074, horas, meta).

    `station`: override del número de estación (saltea la lectura del libro).
    `date`: override de la fecha de observación (YYYY-MM-DD o DDMMYYYY);
    cuando se inyecta, `ultima_actualizacion` queda vacío (reproducible).
    Lanza excepción (p.ej. FileNotFoundError, o ValueError para formato
    desconocido) — no captura errores, el pipeline decide cómo manejarlos.
    """
    wb = load_workbook(path, data_only=True)
    try:
        fmt = detect_format(wb)
        if fmt == 'unknown':
            raise ValueError(f"formato no reconocido: {Path(path).name}")

        estacion = get_station_number(wb, station)
        filename = Path(path).name
        date_str = extract_date_from_filename(filename, date)
        if not date_str:
            date_str = extract_date_from_excel(wb, date)
        if not date_str:
            date_str = datetime.now().strftime("%d%m%Y")  # noqa: DTZ005  # ponytail: solo fallback sin inyección; el pipeline inyecta fecha

        result = {
            "cli3074": build_cli3074(wb, fmt),
            "horas": build_horas(wb, fmt),
            "meta": {
                "estacion": estacion,
                "fecha": date_str,
                "ultima_actualizacion": ""
                if date
                else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # noqa: DTZ005  # ponytail: timestamp de corrida
            },
        }
    finally:
        wb.close()

    return result