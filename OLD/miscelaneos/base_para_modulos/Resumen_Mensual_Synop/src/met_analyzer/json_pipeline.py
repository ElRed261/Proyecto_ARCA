# Conversión Excel→JSON y análisis desde JSON

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple

import pandas as pd
import numpy as np

from .config import CONFIG
from . import data_parser
from . import calc


def _extract_date_from_name(path: Path) -> datetime | None:
    match = pd.Series([path.stem]).str.extract(r"(\d{8})").iloc[0, 0]
    return datetime.strptime(match, "%d%m%Y") if isinstance(match, str) else None


def _extract_station_from_name(path: Path) -> str:
    # Toma todo antes del bloque de 8 dígitos como nombre de estación
    stem = path.stem
    parts = pd.Series([stem]).str.extract(r"^(.*?)(?:\s*\d{8})").iloc[0, 0]
    station = parts.strip() if isinstance(parts, str) and parts.strip() else stem
    return station.replace("  ", " ")


def _hours_mapping_from_config() -> List[str]:
    # Mapeo de horas en el mismo orden que CONFIG['filas_8_observaciones']
    return CONFIG.get(
        "horas_observacion",
        ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"],
    )


def build_json_from_excel(path: Path) -> Dict[str, Any]:
    """Lee un Excel y construye el JSON con el esquema requerido."""
    all_sheets = data_parser.read_sheets_from_file(path)
    df_3074 = all_sheets[CONFIG['hoja_datos_diarios']]
    df_4074 = all_sheets[CONFIG['hoja_nuvosidad_y_temp']]
    df_lluvia = all_sheets[CONFIG['hoja_resumen_lluvia']]

    filas_obs = [f - 1 for f in CONFIG['filas_8_observaciones']]
    horas = _hours_mapping_from_config()

    def safe_num(val):
        return pd.to_numeric(val, errors='coerce')

    # Extraer precipitación del día (para encadenar al anterior en análisis)
    import re as _re
    pp = None
    try:
        fila_lluvia = int(_re.search(r"\d+", CONFIG['celda_lluvia']).group()) - 1
        col_lluvia_letra = _re.search(r"[A-Z]+", CONFIG['celda_lluvia'].upper()).group()
        col_lluvia_num = sum([(ord(ch) - 64) * (26 ** i) for i, ch in enumerate(reversed(col_lluvia_letra))]) - 1
        if 0 <= fila_lluvia < df_lluvia.shape[0] and 0 <= col_lluvia_num < df_lluvia.shape[1]:
            valor_lluvia = safe_num(df_lluvia.iloc[fila_lluvia, col_lluvia_num])
            pp = float(valor_lluvia) if not pd.isna(valor_lluvia) else None
    except Exception:
        pp = None

    # Horarias
    horarias: List[Dict[str, Any]] = []
    for idx, fila in enumerate(filas_obs):
        registro = {
            "hora": horas[idx] if idx < len(horas) else f"H{idx}",
            "datos": {
                "p_est": safe_num(df_3074.iloc[fila, CONFIG['col_presion_estacion']]),
                "p_nmm": safe_num(df_3074.iloc[fila, CONFIG['col_presion_nmm']]),
                "rocio": safe_num(df_3074.iloc[fila, CONFIG['col_punto_rocio']]),
                "t_vapor": safe_num(df_3074.iloc[fila, CONFIG['col_tension_vapor']]),
                "hr": safe_num(df_3074.iloc[fila, CONFIG['col_humedad_relativa']]),
                "v_dir_deg": safe_num(df_3074.iloc[fila, CONFIG['col_viento_direccion']]),
                "v_vel": safe_num(df_3074.iloc[fila, CONFIG['col_viento_velocidad']]),
            }
        }
        horarias.append(registro)

    # Máximas/mínimas temperatura (4 temperaturas)
    filas_4temps = [f - 1 for f in CONFIG['filas_4_temperaturas']]
    for fila in filas_4temps:
        # Intentamos inferir tmax/tmin si hay columnas configuradas
        if 'col_temp_maxima' in CONFIG:
            val = safe_num(df_4074.iloc[fila, CONFIG['col_temp_maxima']])
            if not pd.isna(val):
                horarias.append({"hora": "TMAX", "datos": {"tmax": float(val)}})
        if 'col_temp_minima' in CONFIG:
            val = safe_num(df_4074.iloc[fila, CONFIG['col_temp_minima']])
            if not pd.isna(val):
                horarias.append({"hora": "TMIN", "datos": {"tmin": float(val)}})

    # Nuvosidad (día y tarde)
    def append_nub_from_rows(rows_key: str):
        if rows_key not in CONFIG: return
        for fila in [f - 1 for f in CONFIG[rows_key]]:
            nub_val = safe_num(df_4074.iloc[fila, CONFIG['col_nuvosidad']])
            if not pd.isna(nub_val):
                horarias.append({"hora": rows_key, "datos": {"nub": float(nub_val)}})

    append_nub_from_rows('filas_nuvosidad_dia')
    append_nub_from_rows('filas_nuvosidad_tarde')

    fecha = _extract_date_from_name(path)
    # Formato solicitado ddmmyyyy
    fecha_str = fecha.strftime('%d%m%Y') if fecha else None

    json_doc: Dict[str, Any] = {
        "meta": {
            "estacion": _extract_station_from_name(path),
            "fecha": fecha_str,
        },
        "horarias": horarias,
        "resumen_dia": {"pp": pp}
    }
    return json_doc


def save_json(doc: Dict[str, Any], out_dir: Path) -> Path:
    # Crear estructura Estacion/Año/Mes a partir de meta.estacion y fecha ddmmyyyy
    meta = doc.get("meta", {})
    estacion = (meta.get("estacion") or "estacion").strip()
    fecha = (meta.get("fecha") or "").strip()  # formato ddmmyyyy
    yyyy = fecha[4:8] if len(fecha) == 8 else ""
    mm = fecha[2:4] if len(fecha) == 8 else ""
    destino = Path(out_dir)
    if estacion:
        destino = destino / estacion
    if yyyy:
        destino = destino / yyyy
    if mm:
        destino = destino / mm
    destino.mkdir(parents=True, exist_ok=True)

    nombre = f"{estacion} {fecha}.json" if fecha else f"{estacion}.json"
    out_path = destino / nombre
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return out_path


def convert_excels_to_json(paths: List[str | Path], out_dir: str | Path) -> List[Path]:
    out_dir = Path(out_dir)
    resultados: List[Path] = []
    for p in paths:
        pth = Path(p)
        doc = build_json_from_excel(pth)
        resultados.append(save_json(doc, out_dir))
    return resultados


def _collect_from_horarias(horarias: List[Dict[str, Any]], key: str) -> List[float]:
    vals: List[float] = []
    for h in horarias:
        d = h.get("datos", {})
        if key in d and pd.notna(d[key]):
            vals.append(float(d[key]))
    return vals


def process_day_data_from_json(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Replica process_day_data pero con datos JSON horarios."""
    horarias = doc.get("horarias", [])

    def rh(vals: List[float], decimals: int = 1):
        return calc.round_half_up(np.mean(vals), decimals=decimals) if vals else np.nan

    p_nmm_vals = _collect_from_horarias(horarias, "p_nmm")
    p_est_vals = _collect_from_horarias(horarias, "p_est")
    hr_vals = _collect_from_horarias(horarias, "hr")
    rocio_vals = _collect_from_horarias(horarias, "rocio")
    tvapor_vals = _collect_from_horarias(horarias, "t_vapor")
    vdir_vals = _collect_from_horarias(horarias, "v_dir_deg")
    vvel_vals_ms = _collect_from_horarias(horarias, "v_vel")

    # Temperaturas máximas/mínimas si vienen dispersas en registros especiales
    tmax_vals = _collect_from_horarias(horarias, "tmax")
    tmin_vals = _collect_from_horarias(horarias, "tmin")

    # Nuvosidad: tomar valores etiquetados si existen; si no, usar promedio simple de nub
    nub_vals = _collect_from_horarias(horarias, "nub")

    t_max_abs = calc.round_half_up(max(tmax_vals), decimals=1) if tmax_vals else np.nan
    t_min_abs = calc.round_half_up(min(tmin_vals), decimals=1) if tmin_vals else np.nan
    t_media = calc.round_half_up((t_max_abs + t_min_abs) / 2, decimals=1) if pd.notna(t_max_abs) and pd.notna(t_min_abs) else np.nan

    p_nmm_max = calc.round_half_up(max(p_nmm_vals), decimals=1) if p_nmm_vals else np.nan
    p_nmm_min = calc.round_half_up(min(p_nmm_vals), decimals=1) if p_nmm_vals else np.nan
    p_nmm_media = calc.round_half_up((p_nmm_max + p_nmm_min) / 2, decimals=1) if pd.notna(p_nmm_max) and pd.notna(p_nmm_min) else np.nan
    p_est_media = calc.round_half_up(np.mean(p_est_vals), decimals=1) if p_est_vals else np.nan

    hr_max = calc.round_half_up(max(hr_vals), decimals=0) if hr_vals else np.nan
    hr_min = calc.round_half_up(min(hr_vals), decimals=0) if hr_vals else np.nan
    hr_media = calc.round_half_up(np.mean(hr_vals), decimals=1) if hr_vals else np.nan

    v_moda = "VRB"
    v_vel_media = np.nan
    v_recorrido = np.nan
    vel_max_y_dir_formato_final = "N/A"
    if vvel_vals_ms:
        v_dirs_cardinal = [calc.degrees_to_cardinal(v) for v in vdir_vals if pd.notna(v)]
        from collections import Counter
        cnt = Counter(d for d in v_dirs_cardinal if d not in ["N/A", "CALMA"])
        v_moda = next((d for d, f in cnt.items() if f >= 3), "VRB")
        if np.mean(vvel_vals_ms) < 0.1:
            v_moda = "CALMA"

        v_vel_media = calc.round_half_up(np.mean(vvel_vals_ms) * 3.6, decimals=1)
        v_recorrido = calc.round_half_up(np.sum(vvel_vals_ms) * 3.6, decimals=1)

        # Máxima velocidad y dirección correspondiente
        idx_max = int(np.argmax(vvel_vals_ms))
        val_max_ms = vvel_vals_ms[idx_max]
        dir_deg = vdir_vals[idx_max] if idx_max < len(vdir_vals) else np.nan
        dir_card = calc.degrees_to_cardinal(dir_deg)
        vel_max_kmh = val_max_ms * 3.6
        vel_max_red = calc.round_half_up(vel_max_kmh, decimals=1)
        vel_max_y_dir_formato_final = f"{dir_card} {str(vel_max_red).replace('.', ',')}"

    # Nuvosidad: promedio simple si hay valores
    nuvo_dia_redondeado = calc.round_half_up(np.mean(nub_vals), decimals=1) if nub_vals else np.nan
    nuvo_tarde_redondeado = np.nan  # no distinguimos sin etiquetas explícitas
    nuvo_media_redondeada = calc.round_half_up(np.mean(nub_vals), decimals=1) if nub_vals else np.nan

    p_rocio_media = calc.round_half_up(np.mean(rocio_vals), decimals=1) if rocio_vals else np.nan
    t_vapor_media = calc.round_half_up(np.mean(tvapor_vals), decimals=1) if tvapor_vals else np.nan

    return {
        'Mayor temperatura máxima': t_max_abs, 'Menor temperatura minima': t_min_abs, 'Media temperatura': t_media,
        'MAxima presión nivel medio del mar': p_nmm_max, 'Minima presión nivel medio del mar': p_nmm_min, 'Media presión nivel medio del mar': p_nmm_media,
        'Media presion en la estación': p_est_media, 'Dirección del viento': v_moda, 'Velocidad media del viento': v_vel_media,
        'Velocidad máxima y direccion': vel_max_y_dir_formato_final, 'Recorrido del viento': v_recorrido,
        'Nuvocidad dia': nuvo_dia_redondeado, 'Nuvocidad noche': nuvo_tarde_redondeado, 'Media de nuvocidad': nuvo_media_redondeada,
        'Humedad maxima': hr_max, 'Humedad minima': hr_min, 'Humedad media': hr_media,
        'Punto de rocio': p_rocio_media, 'Tensión de vapor': t_vapor_media,
    }


def run_analysis_from_json(list_of_json_paths: List[str | Path], update_callback=None) -> Tuple[pd.DataFrame, List[str]]:
    paths = [Path(p) for p in list_of_json_paths]
    # Ordenar por fecha del JSON
    docs_with_dates: List[Tuple[datetime, Dict[str, Any], Path]] = []
    mensajes: List[str] = []
    for p in paths:
        try:
            with p.open('r', encoding='utf-8') as f:
                doc = json.load(f)
            fecha_str = doc.get('meta', {}).get('fecha')
            # Interpretar fecha en formato ddmmyyyy
            fecha = datetime.strptime(fecha_str, '%d%m%Y') if fecha_str else None
            if fecha is None:
                mensajes.append(f"⚠️ Ignorado: No se pudo extraer la fecha de '{p.name}'.")
                continue
            docs_with_dates.append((fecha, doc, p))
        except Exception as e:
            mensajes.append(f"❌ Error al leer '{p.name}': {type(e).__name__} - {e}")

    docs_with_dates.sort(key=lambda t: t[0])
    if not docs_with_dates:
        return (pd.DataFrame(), mensajes)

    resumenes: List[Dict[str, Any]] = []
    lluvia_dia_siguiente = np.nan
    for i, (fecha, doc, p) in enumerate(reversed(docs_with_dates)):
        if update_callback:
            update_callback(f"Procesando {i+1}/{len(docs_with_dates)}: {p.name}...")
        try:
            resumen_dia = process_day_data_from_json(doc)
            resumen_dia['Dias'] = fecha
            resumen_dia['Lluvia'] = lluvia_dia_siguiente
            resumenes.append(resumen_dia)

            # Preparar lluvia para la siguiente iteración
            pp = doc.get('resumen_dia', {}).get('pp')
            lluvia_dia_siguiente = pd.to_numeric(pp, errors='coerce')
        except Exception as e:
            mensajes.append(f"❌ Error al procesar '{p.name}': {type(e).__name__} - {e}")
            lluvia_dia_siguiente = np.nan

    resumenes.reverse()
    if not resumenes:
        return (pd.DataFrame(), mensajes)

    df_reporte = pd.DataFrame(resumenes)
    df_reporte['Dias'] = pd.to_datetime(df_reporte['Dias']).dt.strftime('%Y-%m-%d')
    columnas_finales = ['Dias', 'Mayor temperatura máxima', 'Menor temperatura minima', 'Media temperatura', 'MAxima presión nivel medio del mar', 'Minima presión nivel medio del mar', 'Media presión nivel medio del mar', 'Media presion en la estación', 'Lluvia', 'Dirección del viento', 'Velocidad media del viento', 'Velocidad máxima y direccion', 'Recorrido del viento', 'Nuvocidad dia', 'Nuvocidad noche', 'Media de nuvocidad', 'Humedad maxima', 'Humedad minima', 'Humedad media', 'Punto de rocio', 'Tensión de vapor']
    for col in columnas_finales:
        if col not in df_reporte.columns:
            df_reporte[col] = np.nan
    return (df_reporte[columnas_finales], mensajes)


# --- Persistencia de resúmenes (para historial de gráficas) ---

def save_summary_from_dataframe(df_report: pd.DataFrame, out_dir: str | Path, estacion: str | None = None) -> Path:
    """Guarda el DataFrame del resumen en JSON con metadatos para histórico.

    Estructura:
    {
      "meta": {"estacion": str, "periodo": "mmyyyy", "registros": N},
      "data": { <columnas>: [valores ...] }
    }
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if df_report.empty:
        raise ValueError("El DataFrame de resumen está vacío")

    # Determinar periodo del mes desde la columna 'Dias'
    dias = pd.to_datetime(df_report['Dias'], errors='coerce')
    fechas_validas = dias.dropna()
    if fechas_validas.empty:
        # fallback: usar hoy
        periodo = datetime.now().strftime('%m%Y')
    else:
        # Tomar el primer día válido como referencia
        ref = fechas_validas.iloc[0]
        periodo = ref.strftime('%m%Y')

    # Inferir estación si no se pasa explícita
    est = estacion or "estacion"

    doc = {
        "meta": {
            "estacion": est,
            "periodo": periodo,
            "registros": int(len(df_report))
        },
        "data": df_report.to_dict(orient='list')
    }

    nombre = f"resumen_{est}_{periodo}.json"
    out_path = out_dir / nombre
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return out_path


def load_summary_json(path: str | Path) -> pd.DataFrame:
    """Carga un JSON de resumen guardado y lo devuelve como DataFrame con mismas columnas."""
    with Path(path).open('r', encoding='utf-8') as f:
        doc = json.load(f)
    data = doc.get('data', {})
    df = pd.DataFrame(data)
    return df


