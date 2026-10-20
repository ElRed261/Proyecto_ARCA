#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel a JSON - Transformador de datos SYNOP
Convierte archivos Excel (.xls, .xlsx, .xlsm, .xlsb) de observaciones meteorológicas
a la estructura JSON del sistema ARCA.

Soporta 3 formatos de Excel:
  - Formato NORMAL (con hoja '3074' con datos completos)
  - Formato VIEJO (sin hoja '3074', solo Z-hours)
  - Formato HORRIBLE (dígitos separados en celdas individuales en '3074')

Features:
  - Preserva estructura de carpetas (meses → números)
  - Merge automático de archivos con la misma fecha
  - Combinación de horas de diferentes archivos del mismo día

Uso:
    python3 excel_to_json.py
"""

import os
import sys
import json
import re
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, scrolledtext
from datetime import datetime
from pathlib import Path

try:
    from openpyxl import load_workbook
except ImportError:
    print("ERROR: Se requiere openpyxl. Instalalo con: pip install openpyxl")
    sys.exit(1)


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
    except Exception:
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

def extract_date_from_filename(filename):
    """Extrae DDMMYYYY del nombre. Soporta DDMMYYYY, DDMMYY, y texto."""
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


def extract_date_from_excel(wb):
    """Fallback: extrae fecha de celda D8 de primera hoja Z."""
    for sheet_name in wb.sheetnames:
        if sheet_name in Z_HOUR_SHEET_NAMES:
            ws = wb[sheet_name]
            val = ws.cell(row=8, column=4).value
            if val:
                if isinstance(val, datetime):
                    return val.strftime("%d%m%Y")
                for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"]:
                    try:
                        dt = datetime.strptime(str(val).split()[0], fmt)
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
    if val_c and len(val_c) == 1 and val_c.isdigit():
        if val_d and len(val_d) == 1 and val_d.isdigit():
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
            pres_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['C','D','E','F']])
            result[hour_str]['pres_est'] = decode_pressure_h(pres_digits)
            
            # NMM G-J
            nmm_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['G','H','I','J']])
            result[hour_str]['pres_nmm'] = decode_pressure_h(nmm_digits)
            
            # Altímetro K-N
            alti_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['K','L','M','N']])
            if alti_digits.strip():
                result[hour_str]['pres_alti'] = decode_pressure_h(alti_digits)
            
            # Tendencia CAR=O, DIF=P-R
            tend_car = get_cell_value(ws, row_num, 'O')
            tend_dif_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['P','Q','R']])
            result[hour_str]['tend_car'] = tend_car
            result[hour_str]['tend_dif'] = decode_tendency_h(tend_dif_digits)
            
            # Temperaturas
            ts_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['S','T','U']])
            th_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['V','W','X']])
            result[hour_str]['temp_seco'] = decode_temp_h(ts_digits)
            result[hour_str]['temp_humedo'] = decode_temp_h(th_digits)
            
            # Humedad
            pr_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['Y','Z','AA']])
            tv_digits = ''.join([get_cell_value(ws, row_num, c) for c in ['AB','AC','AD']])
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

def get_station_number(wb):
    for sheet_name in wb.sheetnames:
        if sheet_name in Z_HOUR_SHEET_NAMES:
            val = get_cell_value(wb[sheet_name], 8, 'C')
            if val and val.isdigit():
                return val
    return "78486"


def process_excel_to_json(filepath):
    """Procesa un Excel y retorna (fecha_str, json_data, ok, msg)."""
    try:
        wb = load_workbook(filepath, data_only=True)
        fmt = detect_format(wb)
        
        if fmt == 'unknown':
            wb.close()
            return None, None, False, f"⚠ {os.path.basename(filepath)}: formato no reconocido"
        
        station = get_station_number(wb)
        filename = os.path.basename(filepath)
        date_str = extract_date_from_filename(filename)
        if not date_str:
            date_str = extract_date_from_excel(wb)
        if not date_str:
            date_str = datetime.now().strftime("%d%m%Y")
        
        result = {
            "cli3074": build_cli3074(wb, fmt),
            "horas": build_horas(wb, fmt),
            "meta": {
                "estacion": station,
                "fecha": date_str,
                "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        wb.close()
        return date_str, result, True, f"✓ {filename} ({fmt})"
    
    except Exception as e:
        return None, None, False, f"✗ {os.path.basename(filepath)}: {str(e)}"


# ============================================================================
# RUTAS Y ESTRUCTURA DE CARPETAS
# ============================================================================

def convert_months_in_path(path):
    """Convierte nombres de meses a números en la ruta."""
    parts = path.split(os.sep)
    converted = []
    for part in parts:
        lower_part = part.lower()
        if lower_part in MONTH_NAMES_ES:
            converted.append(MONTH_NAMES_ES[lower_part])
        else:
            converted.append(part)
    return os.sep.join(converted)


def get_common_directory(paths):
    if not paths:
        return ""
    dirs = [os.path.dirname(os.path.abspath(p)) for p in paths]
    split_dirs = [d.split(os.sep) for d in dirs]
    common = []
    for components in zip(*split_dirs):
        if all(c == components[0] for c in components):
            common.append(components[0])
        else:
            break
    return os.sep.join(common) if common else ""


def compute_output_path(input_filepath, input_root, output_root):
    abs_input = os.path.abspath(input_filepath)
    abs_root = os.path.abspath(input_root)
    
    if abs_input.startswith(abs_root):
        rel_path = os.path.relpath(abs_input, abs_root)
    else:
        rel_path = os.path.basename(abs_input)
    
    rel_dir = os.path.dirname(rel_path)
    converted_dir = convert_months_in_path(rel_dir)
    output_dir = os.path.join(output_root, converted_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    return output_dir


# ============================================================================
# INTERFAZ GRÁFICA
# ============================================================================

class ExcelToJsonApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Excel → JSON Transformador SYNOP")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.selected_files = []
        
        self._build_ui()
    
    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title = ttk.Label(main_frame, text="Transformador Excel → JSON", font=('Helvetica', 16, 'bold'))
        title.pack(pady=(0, 10))
        
        desc = ttk.Label(main_frame, text="Selecciona carpeta o archivos. Archivos con la misma fecha se combinan automáticamente.", wraplength=800)
        desc.pack(pady=(0, 15))
        
        # Modo
        mode_frame = ttk.LabelFrame(main_frame, text="Modo de selección", padding="10")
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.mode_var = tk.StringVar(value="folder")
        ttk.Radiobutton(mode_frame, text="📁 Procesar toda una carpeta", variable=self.mode_var, value="folder", command=self._on_mode_change).pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="📄 Seleccionar archivos individuales", variable=self.mode_var, value="files", command=self._on_mode_change).pack(anchor=tk.W)
        
        # Entrada
        self.input_frame = ttk.LabelFrame(main_frame, text="Carpeta de entrada", padding="10")
        self.input_frame.pack(fill=tk.X, pady=(0, 10))
        
        input_row = ttk.Frame(self.input_frame)
        input_row.pack(fill=tk.X)
        
        self.input_entry = ttk.Entry(input_row, textvariable=self.input_dir)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.input_btn = ttk.Button(input_row, text="Seleccionar carpeta...", command=self._select_input)
        self.input_btn.pack(side=tk.RIGHT)
        
        # Lista archivos
        self.files_list_frame = ttk.LabelFrame(main_frame, text="Archivos seleccionados", padding="10")
        
        self.files_listbox = tk.Listbox(self.files_list_frame, selectmode=tk.EXTENDED, font=('Consolas', 10), height=6)
        self.files_listbox.pack(fill=tk.BOTH, expand=True)
        
        files_btn_frame = ttk.Frame(self.files_list_frame)
        files_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(files_btn_frame, text="➕ Agregar archivos...", command=self._add_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(files_btn_frame, text="🗑️ Quitar seleccionados", command=self._remove_selected_files).pack(side=tk.LEFT)
        
        # Salida
        output_frame = ttk.LabelFrame(main_frame, text="Carpeta base de salida (JSON)", padding="10")
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        output_row = ttk.Frame(output_frame)
        output_row.pack(fill=tk.X)
        
        self.output_entry = ttk.Entry(output_row, textvariable=self.output_dir)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(output_row, text="Seleccionar...", command=self._select_output).pack(side=tk.RIGHT)
        
        # Info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 5))
        self.info_label = ttk.Label(info_frame, text="Ej: Central/2023/Octubre → Central/2023/10/", foreground="gray", font=('Consolas', 9))
        self.info_label.pack(anchor=tk.W)
        
        # Transformar
        self.transform_btn = ttk.Button(main_frame, text="🚀 TRANSFORMAR", command=self._transform, style='Accent.TButton')
        self.transform_btn.pack(pady=(0, 10))
        
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 10))
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Registro de actividad", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Helvetica', 12, 'bold'))
    
    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "folder":
            self.input_frame.config(text="Carpeta de entrada")
            self.input_btn.config(text="Seleccionar carpeta...", command=self._select_input)
            self.files_list_frame.pack_forget()
            self.input_dir.set("")
            self.selected_files = []
            self.files_listbox.delete(0, tk.END)
        else:
            self.input_frame.config(text="Archivos seleccionados (raíz calculada automáticamente)")
            self.input_btn.config(text="Agregar archivos...", command=self._add_files)
            self.files_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            self.input_dir.set("")
            self.selected_files = []
            self.files_listbox.delete(0, tk.END)
    
    def _select_input(self):
        directory = filedialog.askdirectory(title="Seleccionar carpeta con Excel")
        if directory:
            self.input_dir.set(directory)
    
    def _select_output(self):
        directory = filedialog.askdirectory(title="Seleccionar carpeta base de salida para JSON")
        if directory:
            self.output_dir.set(directory)
    
    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Seleccionar archivos Excel",
            filetypes=[("Archivos Excel", "*.xls *.xlsx *.xlsm *.xlsb"), ("Todos los archivos", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.selected_files:
                    self.selected_files.append(f)
                    self.files_listbox.insert(tk.END, os.path.basename(f))
            if self.selected_files and not self.input_dir.get():
                common = get_common_directory(self.selected_files)
                self.input_dir.set(common)
    
    def _remove_selected_files(self):
        selection = self.files_listbox.curselection()
        for index in reversed(selection):
            self.files_listbox.delete(index)
            self.selected_files.pop(index)
    
    def _log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def _transform(self):
        output_dir = self.output_dir.get().strip()
        mode = self.mode_var.get()
        
        if not output_dir:
            messagebox.showerror("Error", "Selecciona la carpeta de salida.")
            return
        if not os.path.isdir(output_dir):
            messagebox.showerror("Error", f"La carpeta de salida no existe:\n{output_dir}")
            return
        
        # Determinar archivos
        if mode == "folder":
            input_dir = self.input_dir.get().strip()
            if not input_dir or not os.path.isdir(input_dir):
                messagebox.showerror("Error", "Selecciona una carpeta de entrada válida.")
                return
            # Buscar recursivamente en TODAS las subcarpetas
            xlsm_files = sorted([
                str(p) for p in Path(input_dir).rglob('*')
                if p.is_file() and p.suffix.lower() in EXCEL_EXTS
            ])
            input_root = input_dir
        else:
            xlsm_files = list(self.selected_files)
            if not xlsm_files:
                messagebox.showerror("Error", "No has seleccionado ningún archivo.")
                return
            input_root = self.input_dir.get().strip() or get_common_directory(xlsm_files)
            if not input_root:
                input_root = os.path.dirname(xlsm_files[0])
        
        if not xlsm_files:
            messagebox.showwarning("Sin archivos", "No se encontraron archivos Excel.")
            return
        
        self._log(f"=" * 70)
        self._log(f"INICIANDO TRANSFORMACIÓN")
        self._log(f"Archivos: {len(xlsm_files)}")
        self._log(f"Raíz entrada: {input_root}")
        self._log(f"Salida base: {output_dir}")
        self._log(f"=" * 70)
        
        self.transform_btn.config(state=tk.DISABLED)
        self.progress['maximum'] = len(xlsm_files)
        self.progress['value'] = 0
        
        # PASO 1: Procesar todos los Excels y agrupar por fecha
        results_by_date = {}
        for idx, filepath in enumerate(xlsm_files, 1):
            self.progress['value'] = idx
            date_str, json_data, ok, msg = process_excel_to_json(filepath)
            self._log(msg)
            
            if ok and date_str and json_data:
                if date_str not in results_by_date:
                    results_by_date[date_str] = []
                results_by_date[date_str].append({
                    'json': json_data,
                    'filepath': filepath
                })
        
        # PASO 2: Mergear archivos con la misma fecha y guardar
        self._log(f"\n{'=' * 70}")
        self._log(f"MERGE Y GUARDADO")
        self._log(f"Fechas únicas encontradas: {len(results_by_date)}")
        
        success_count = 0
        for date_str, items in results_by_date.items():
            # Mergear si hay múltiples archivos
            jsons = [item['json'] for item in items]
            merged = merge_jsons(jsons)
            
            # Usar la ruta del primer archivo para determinar estructura de carpetas
            first_filepath = items[0]['filepath']
            out_path = compute_output_path(first_filepath, input_root, output_dir)
            
            station = merged['meta']['estacion']
            output_filename = f"{station}{date_str}.json"
            output_file = os.path.join(out_path, output_filename)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            
            if len(items) > 1:
                self._log(f"  🔄 Merge {len(items)} archivos → {output_filename} ({os.path.relpath(out_path, output_dir)})")
            else:
                self._log(f"  ✓ Guardado → {output_filename} ({os.path.relpath(out_path, output_dir)})")
            success_count += 1
        
        self.progress['value'] = len(xlsm_files)
        self.transform_btn.config(state=tk.NORMAL)
        
        self._log(f"\n{'=' * 70}")
        self._log(f"COMPLETADO: {success_count} JSON generados")
        self._log(f"{'=' * 70}")
        
        messagebox.showinfo("Completado", f"Transformación finalizada.\n\nJSON generados: {success_count}\n\nGuardados en:\n{output_dir}")


def main():
    root = tk.Tk()
    app = ExcelToJsonApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
