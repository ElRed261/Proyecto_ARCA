"""
JSON Handler para guardar observaciones sinópticas.
Solo guarda datos ingresados manualmente (NO calculados automáticamente).

Campos AUTO-CALCULADOS (NO se guardan):
- 1snTTT (de Ts)
- 2snTdTdTd (de punto de rocío)
- 4PPPP (presión NMM)
- 5aPPP (tendencia presión)
- 58/59 P24 (cambio presión 24h)
- 29UUU (humedad relativa)

Estructura de carpetas: data/{station_code}/{year}/{month}/{filename}.json
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Directorio base
DATA_DIR = Path(__file__).parent / "data"

# Horas pares (tienen T_max y T_min)
HORAS_PARES = ["00Z", "06Z", "12Z", "18Z"]
# Horas impares (NO tienen T_max y T_min)
HORAS_IMPARES = ["03Z", "09Z", "15Z", "21Z"]


def ensure_data_dir(station_code: str, year: str, month: str) -> Path:
    """Crea estructura: data/{station_code}/{year}/{month}/"""
    dir_path = DATA_DIR / station_code / year / month
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def format_date_for_filename(fecha: str) -> str:
    """Convierte 'YYYY-MM-DD' a 'DDMMYYYY'."""
    try:
        dt = datetime.strptime(fecha, "%Y-%m-%d")
        return dt.strftime("%d%m%Y")
    except ValueError:
        return fecha.replace("-", "")


def parse_date_parts(fecha: str) -> tuple:
    """Extrae (year, month) de 'YYYY-MM-DD'."""
    try:
        dt = datetime.strptime(fecha, "%Y-%m-%d")
        return dt.strftime("%Y"), dt.strftime("%m")
    except ValueError:
        if len(fecha) == 8:
            return fecha[4:8], fecha[2:4]
        return "2025", "12"


def safe_str(value) -> str:
    """Convierte a string, '' si None/NaN."""
    if value is None or value == "" or value == "null":
        return ""
    try:
        if isinstance(value, float) and (value != value):
            return ""
        return str(value).strip()
    except:
        return ""


def build_observation_json(
    station_code: str,
    fecha: str,
    observations: Dict[str, Dict],
) -> Dict[str, Any]:
    """
    Construye JSON con TODOS los campos (manuales y calculados).
    
    Al CARGAR, el frontend solo debe usar los campos manuales.
    Al GUARDAR, se almacenan todos para referencia histórica.
    
    Campos por hora:
    - nombre_observador (por hora)
    - meteo_2_1 (YYGGIw)
    - Datos manuales: ts, th, pres_est, p3, p24, ll, correc_alt
    - Datos calculados: tv, hr, pr, dif, pres_nmm
    - T_max/T_min solo en horas pares
    - Grupos SYNOP manuales y calculados
    """
    fecha_formatted = format_date_for_filename(fecha)
    
    horas = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"]
    
    horarias = []
    for hora in horas:
        h = observations.get(hora, {})
        es_hora_par = hora in HORAS_PARES
        
        # =============================================
        # DATOS MANUALES
        # =============================================
        datos = {
            # Temperaturas manuales
            "ts": safe_str(h.get("ts")),
            "th": safe_str(h.get("th")),
            # Presiones manuales
            "pres_est": safe_str(h.get("pres_est")),
            "p3": safe_str(h.get("p3")),
            "p24": safe_str(h.get("p24")),
            "let_barom": safe_str(h.get("let_barom")),
            "correc_alt": safe_str(h.get("correc_alt")),
            # Precipitación
            "ll": safe_str(h.get("ll")),
            "ll_24h": safe_str(h.get("ll_24h")),
        }
        
        # T_max y T_min solo en horas pares
        if es_hora_par:
            datos["t_max"] = safe_str(h.get("t_max"))
            datos["t_min"] = safe_str(h.get("t_min"))
            datos["t_max_24h"] = safe_str(h.get("t_max_24h"))
            datos["t_min_24h"] = safe_str(h.get("t_min_24h"))
        
        # =============================================
        # DATOS CALCULADOS (para referencia histórica)
        # =============================================
        calculados = {
            "tv": safe_str(h.get("tv")),           # Tensión de vapor
            "hr": safe_str(h.get("hr")),           # Humedad relativa
            "pr": safe_str(h.get("pr")),           # Punto de rocío
            "dif": safe_str(h.get("dif")),         # Diferencia Ts-Th
            "pres_nmm": safe_str(h.get("pres_nmm")),  # Presión NMM
            "dif_p3": safe_str(h.get("dif_p3")),   # Diferencia P3
            "dif_p24": safe_str(h.get("dif_p24")), # Diferencia P24
        }
        
        # =============================================
        # GRUPOS SYNOP MANUALES
        # =============================================
        synop_manual = {
            # Fila 4: Campos manuales
            "irixhvv": safe_str(h.get("meteo_4_irixhvv")),  # IriXHVV
            "n_dd_ff": safe_str(h.get("meteo_4_1")),        # N dd ff
            "7ww_w1w2": safe_str(h.get("meteo_4_6")),       # 7wwW1W2
            
            # Fila 6: Nubes y sección 333
            "8nh_cl_cm_ch": safe_str(h.get("meteo_6_0")),   # 8NhCLCMCH
            "0cs_dl_dm_dh": safe_str(h.get("meteo_6_2")),   # 0CSDLDMDH
            "3e_jjj": safe_str(h.get("meteo_6_5")),         # 3Ejjj
            "5eee_je": safe_str(h.get("meteo_6_6")),        # 5EEEjE
            
            # Fila 8
            "5n_fn": safe_str(h.get("meteo_8_0")),          # 5nFnFnFn
            "56dl_dm_dh": safe_str(h.get("meteo_8_1")),     # 56DLDMDH
            "6rrr_tr": safe_str(h.get("meteo_8_3")),        # 6RRRtr
            "7r24": safe_str(h.get("meteo_8_4")),           # 7R24R24R24R24
            
            # 4 grupos 8NsChshs
            "8ns_1": safe_str(h.get("meteo_8_5")),
            "8ns_2": safe_str(h.get("meteo_8_6")),
            "8ns_3": safe_str(h.get("meteo_10_0")),
            "8ns_4": safe_str(h.get("meteo_10_1")),
            
            # Grupos 9sp - Fila 10
            "9sp_10_2": safe_str(h.get("meteo_10_2")),
            "9sp_10_3": safe_str(h.get("meteo_10_3")),
            "9sp_10_4": safe_str(h.get("meteo_10_4")),
            "9sp_10_5": safe_str(h.get("meteo_10_5")),
            "9sp_10_6": safe_str(h.get("meteo_10_6")),
            
            # Grupos 9sp - Fila 12
            "9sp_12_0": safe_str(h.get("meteo_12_0")),
            "9sp_12_1": safe_str(h.get("meteo_12_1")),
            "9sp_12_2": safe_str(h.get("meteo_12_2")),
            "9sp_12_3": safe_str(h.get("meteo_12_3")),
            "9sp_12_4": safe_str(h.get("meteo_12_4")),
            "9sp_12_5": safe_str(h.get("meteo_12_5")),
            "9sp_12_6": safe_str(h.get("meteo_12_6")),
            
            # Grupos 9sp - Fila 14
            "9sp_14_0": safe_str(h.get("meteo_14_0")),
            "9sp_14_1": safe_str(h.get("meteo_14_1")),
            "9sp_14_2": safe_str(h.get("meteo_14_2")),
            "9sp_14_3": safe_str(h.get("meteo_14_3")),
            "9sp_14_4": safe_str(h.get("meteo_14_4")),
            "9sp_14_5": safe_str(h.get("meteo_14_5")),
            "9sp_14_6": safe_str(h.get("meteo_14_6")),
            
            # Grupos 9sp - Fila 16
            "9sp_16_0": safe_str(h.get("meteo_16_0")),
            "9sp_16_1": safe_str(h.get("meteo_16_1")),
            "9sp_16_2": safe_str(h.get("meteo_16_2")),
            "9sp_16_3": safe_str(h.get("meteo_16_3")),
            "9sp_16_4": safe_str(h.get("meteo_16_4")),
            
            # 2 grupos 8NsChshs extra
            "extra_8ns_1": safe_str(h.get("extra_8ns_1")),
            "extra_8ns_2": safe_str(h.get("extra_8ns_2")),
        }
        
        # 1snTx y 2snTn manuales solo en horas pares
        if es_hora_par:
            synop_manual["1sn_tx_manual"] = safe_str(h.get("meteo_6_3"))
            synop_manual["2sn_tn_manual"] = safe_str(h.get("meteo_6_4"))
        
        # =============================================
        # GRUPOS SYNOP CALCULADOS (para referencia)
        # =============================================
        synop_calculado = {
            "1sn_ttt": safe_str(h.get("synop_1snTTT")),      # Temperatura seca
            "2sn_tdtdtd": safe_str(h.get("synop_2snTdTdTd")), # Punto de rocío
            "4pppp": safe_str(h.get("synop_4PPPP")),         # Presión NMM
            "5appp": safe_str(h.get("synop_5aPPP")),         # Tendencia 3h
            "58_59_p24": safe_str(h.get("synop_58_59_P24")), # Cambio 24h
            "29uuu": safe_str(h.get("synop_29UUU")),         # Humedad
        }
        
        hora_entry = {
            "hora": hora,
            "nombre_observador": safe_str(h.get("nombre_observador")),
            "yygg_iw": safe_str(h.get("meteo_2_1")),
            "datos": datos,
            "calculados": calculados,
            "synop_manual": synop_manual,
            "synop_calculado": synop_calculado
        }
        
        horarias.append(hora_entry)
    
    # Resumen del día
    pp_24h = safe_str(observations.get("12Z", {}).get("ll_24h"))
    
    return {
        "meta": {
            "estacion": station_code,
            "fecha": fecha_formatted
        },
        "horarias": horarias,
        "resumen_dia": {
            "pp_24h": pp_24h
        }
    }


# Directorio de backups
BACKUP_DIR = Path(__file__).parent / "data" / ".backups"


def ensure_backup_dir(station_code: str) -> Path:
    """Crea directorio de backups: data/.backups/{station_code}/"""
    backup_path = BACKUP_DIR / station_code
    backup_path.mkdir(parents=True, exist_ok=True)
    return backup_path


def create_backup(filepath: Path, station_code: str) -> Optional[str]:
    """
    Crea backup del archivo si existe.
    Mantiene los últimos 10 backups por archivo.
    Nombre: {filename}.{timestamp}.bak
    """
    if not filepath.exists():
        return None
    
    backup_dir = ensure_backup_dir(station_code)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{filepath.stem}.{timestamp}.bak"
    backup_path = backup_dir / backup_name
    
    # Copiar archivo actual al backup
    import shutil
    shutil.copy2(filepath, backup_path)
    
    # Limpiar backups antiguos (mantener solo los últimos 10)
    pattern = f"{filepath.stem}.*.bak"
    backups = sorted(backup_dir.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
    for old_backup in backups[10:]:
        old_backup.unlink()
    
    return str(backup_path)


def save_observation_json(
    station_code: str,
    fecha: str,
    observations: Dict[str, Dict],
    observer_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Guarda en: data/{station}/{year}/{month}/{station}{DDMMYYYY}.json
    
    Retorna dict con:
    - filepath: ruta del archivo guardado
    - backup_path: ruta del backup (si se creó)
    - last_modified: timestamp de la última modificación
    """
    year, month = parse_date_parts(fecha)
    dir_path = ensure_data_dir(station_code, year, month)
    
    fecha_formatted = format_date_for_filename(fecha)
    filename = f"{station_code}{fecha_formatted}.json"
    filepath = dir_path / filename
    
    # Crear backup si el archivo ya existe
    backup_path = create_backup(filepath, station_code)
    
    # Construir y guardar JSON
    json_data = build_observation_json(station_code, fecha, observations)
    
    # Añadir timestamp de última modificación
    json_data["meta"]["last_modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    return {
        "filepath": str(filepath),
        "filename": filename,
        "backup_path": backup_path,
        "last_modified": json_data["meta"]["last_modified"]
    }


def load_observation_json(station_code: str, fecha: str) -> Optional[Dict]:
    """Carga desde: data/{station}/{year}/{month}/{station}{DDMMYYYY}.json"""
    year, month = parse_date_parts(fecha)
    
    if "-" in fecha:
        fecha_formatted = format_date_for_filename(fecha)
    else:
        fecha_formatted = fecha
    
    filename = f"{station_code}{fecha_formatted}.json"
    filepath = DATA_DIR / station_code / year / month / filename
    
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    return None


def list_observations(station_code: Optional[str] = None) -> List[str]:
    """Lista archivos de observación disponibles."""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return []
    
    results = []
    
    if station_code:
        station_dir = DATA_DIR / station_code
        if station_dir.exists():
            for json_file in station_dir.rglob("*.json"):
                results.append(str(json_file.relative_to(DATA_DIR)))
    else:
        for json_file in DATA_DIR.rglob("*.json"):
            results.append(str(json_file.relative_to(DATA_DIR)))
    
    return sorted(results)


def get_oldest_date(station_code: str) -> Optional[str]:
    """Obtiene la fecha más antigua de observaciones para una estación.
    
    Retorna la fecha en formato 'YYYY-MM-DD' o None si no hay observaciones.
    """
    station_dir = DATA_DIR / station_code
    if not station_dir.exists():
        return None
    
    dates = []
    for json_file in station_dir.rglob("*.json"):
        filename = json_file.stem  # e.g., "7848406122025"
        # Extraer DDMMYYYY del final del nombre
        if len(filename) >= 8:
            date_str = filename[-8:]  # DDMMYYYY
            try:
                dd = date_str[0:2]
                mm = date_str[2:4]
                yyyy = date_str[4:8]
                dates.append(f"{yyyy}-{mm}-{dd}")
            except:
                continue
    
    if not dates:
        return None
    
    # Ordenar y retornar la más antigua
    dates.sort()
    return dates[0]


def get_newest_date(station_code: str) -> Optional[str]:
    """Obtiene la fecha más reciente de observaciones para una estación.
    
    Retorna la fecha en formato 'YYYY-MM-DD' o None si no hay observaciones.
    """
    station_dir = DATA_DIR / station_code
    if not station_dir.exists():
        return None
    
    dates = []
    for json_file in station_dir.rglob("*.json"):
        filename = json_file.stem
        if len(filename) >= 8:
            date_str = filename[-8:]
            try:
                dd = date_str[0:2]
                mm = date_str[2:4]
                yyyy = date_str[4:8]
                dates.append(f"{yyyy}-{mm}-{dd}")
            except:
                continue
    
    if not dates:
        return None
    
    dates.sort(reverse=True)
    return dates[0]
