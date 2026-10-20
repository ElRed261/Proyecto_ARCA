# cálculos meteorológicos.

import pandas as pd
import numpy as np
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

#Funciones de utilidad para los cálculos

def degrees_to_cardinal(degrees):
    """Grado a punto cardinal."""
    if not isinstance(degrees, (int, float, np.number)) or not (0 <= degrees <= 360):
        return "N/A"
    if degrees == 0: return "CALMA"
    
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = round(degrees / (360. / len(dirs)))
    return dirs[ix % len(dirs)]

def round_half_up(n, decimals=1):
    """Redondeo preciso (sube desde .5)."""
    if pd.isna(n) or n is None: return np.nan
    formato = '0' if decimals == 0 else '0.' + '0' * decimals
    return float(Decimal(str(n)).quantize(Decimal(formato), rounding=ROUND_HALF_UP))

#Lógica de cálculo para un día ---

def process_day_data(dfs, config):
    """
    Toma los DataFrames extraídos y la configuración, y devuelve
    un diccionario con todos los cálculos meteorológicos para un día.
    """
    df_3074 = dfs[config['hoja_datos_diarios']]
    df_4074 = dfs[config['hoja_nuvosidad_y_temp']]

    def get_numeric_values(df, rows_key, col_key):
        filas = config[rows_key]
        columna = config[col_key]
        indices = [f - 1 for f in filas]
        return pd.to_numeric(df.iloc[indices, columna], errors='coerce').dropna()

    t_max_vals = get_numeric_values(df_4074, 'filas_4_temperaturas', 'col_temp_maxima')
    t_min_vals = get_numeric_values(df_4074, 'filas_4_temperaturas', 'col_temp_minima')
    p_nmm_vals = get_numeric_values(df_3074, 'filas_8_observaciones', 'col_presion_nmm')
    p_est_vals = get_numeric_values(df_3074, 'filas_8_observaciones', 'col_presion_estacion')
    hr_vals = get_numeric_values(df_3074, 'filas_8_observaciones', 'col_humedad_relativa')
    p_rocio_vals = get_numeric_values(df_3074, 'filas_8_observaciones', 'col_punto_rocio')
    t_vapor_vals = get_numeric_values(df_3074, 'filas_8_observaciones', 'col_tension_vapor')
    n_dia_vals = get_numeric_values(df_4074, 'filas_nuvosidad_dia', 'col_nuvosidad')
    n_tarde_vals = get_numeric_values(df_4074, 'filas_nuvosidad_tarde', 'col_nuvosidad')
    
    t_max_abs = round_half_up(t_max_vals.max(), decimals=1) if not t_max_vals.empty else np.nan
    t_min_abs = round_half_up(t_min_vals.min(), decimals=1) if not t_min_vals.empty else np.nan
    t_media = round_half_up((t_max_abs + t_min_abs) / 2, decimals=1) if pd.notna(t_max_abs) and pd.notna(t_min_abs) else np.nan
    p_nmm_max = round_half_up(p_nmm_vals.max(), decimals=1) if not p_nmm_vals.empty else np.nan
    p_nmm_min = round_half_up(p_nmm_vals.min(), decimals=1) if not p_nmm_vals.empty else np.nan
    p_nmm_media = round_half_up((p_nmm_max + p_nmm_min) / 2, decimals=1) if pd.notna(p_nmm_max) and pd.notna(p_nmm_min) else np.nan
    p_est_media = round_half_up(p_est_vals.mean(), decimals=1) if not p_est_vals.empty else np.nan
    hr_max = round_half_up(hr_vals.max(), decimals=0) if not hr_vals.empty else np.nan
    hr_min = round_half_up(hr_vals.min(), decimals=0) if not hr_vals.empty else np.nan
    hr_media = round_half_up(hr_vals.mean(), decimals=1) if not hr_vals.empty else np.nan

    filas_obs_ajustadas = [f - 1 for f in config['filas_8_observaciones']]
    v_vels_raw = pd.to_numeric(df_3074.iloc[filas_obs_ajustadas, config['col_viento_velocidad']], errors='coerce')
    v_dirs_raw = pd.to_numeric(df_3074.iloc[filas_obs_ajustadas, config['col_viento_direccion']], errors='coerce')
    v_moda = "VRB"
    v_vel_media = np.nan
    v_recorrido = np.nan
    vel_max_y_dir_formato_final = "N/A"
    
    if not v_vels_raw.dropna().empty:
        v_dirs_validas_moda = v_dirs_raw.dropna()
        v_dirs_cardinal = v_dirs_validas_moda.apply(degrees_to_cardinal)
        cnt_viento = Counter(d for d in v_dirs_cardinal if d not in ["N/A", "CALMA"])
        v_moda = next((d for d, f in cnt_viento.items() if f >= 3), "VRB")
        if v_vels_raw.mean() < 0.1: v_moda = "CALMA"
        
        v_vel_media = round_half_up(v_vels_raw.mean() * 3.6, decimals=1)
        v_recorrido = round_half_up(v_vels_raw.sum() * 3.6, decimals=1)
        
        v_vels_validas = v_vels_raw.dropna()
        idx_max_vel = v_vels_validas.idxmax()
        val_max_vel_ms = v_vels_validas.loc[idx_max_vel]
        grados_correspondientes = v_dirs_raw.loc[idx_max_vel]
        dir_max_cardinal = degrees_to_cardinal(grados_correspondientes)
        vel_max_kmh = val_max_vel_ms * 3.6
        vel_max_redondeada = round_half_up(vel_max_kmh, decimals=1)
        vel_max_y_dir_formato_final = f"{dir_max_cardinal} {str(vel_max_redondeada).replace('.', ',')}"

    media_nuvo_dia = n_dia_vals.sum() / len(config['filas_nuvosidad_dia']) if not n_dia_vals.empty else np.nan
    media_nuvo_tarde = n_tarde_vals.sum() / len(config['filas_nuvosidad_tarde']) if not n_tarde_vals.empty else np.nan
    nuvo_dia_redondeado = round_half_up(media_nuvo_dia, decimals=1)
    nuvo_tarde_redondeado = round_half_up(media_nuvo_tarde, decimals=1)
    nuvo_media_redondeada = round_half_up((media_nuvo_dia + media_nuvo_tarde) / 2, decimals=1) if pd.notna(media_nuvo_dia) and pd.notna(media_nuvo_tarde) else np.nan
    p_rocio_media = round_half_up(p_rocio_vals.mean(), decimals=1) if not p_rocio_vals.empty else np.nan
    t_vapor_media = round_half_up(t_vapor_vals.mean(), decimals=1) if not t_vapor_vals.empty else np.nan

    return {
        'Mayor temperatura máxima': t_max_abs, 'Menor temperatura minima': t_min_abs, 'Media temperatura': t_media,
        'MAxima presión nivel medio del mar': p_nmm_max, 'Minima presión nivel medio del mar': p_nmm_min, 'Media presión nivel medio del mar': p_nmm_media,
        'Media presion en la estación': p_est_media, 'Dirección del viento': v_moda, 'Velocidad media del viento': v_vel_media,
        'Velocidad máxima y direccion': vel_max_y_dir_formato_final, 'Recorrido del viento': v_recorrido,
        'Nuvocidad dia': nuvo_dia_redondeado, 'Nuvocidad noche': nuvo_tarde_redondeado, 'Media de nuvocidad': nuvo_media_redondeada,
        'Humedad maxima': hr_max, 'Humedad minima': hr_min, 'Humedad media': hr_media,
        'Punto de rocio': p_rocio_media, 'Tensión de vapor': t_vapor_media,
    }