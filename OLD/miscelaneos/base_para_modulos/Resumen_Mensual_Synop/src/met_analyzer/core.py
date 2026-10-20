# Nucleo del proceso de análisis.

import pandas as pd
import numpy as np
import re
from datetime import datetime
from pathlib import Path

from .config import CONFIG
from . import data_parser
from . import calc

def _extract_date_from_name(path):
    """Extrae la fecha del nombre de un archivo."""
    match = re.search(r'(\d{8})', path.stem)
    return datetime.strptime(match.group(1), '%d%m%Y') if match else None

def run_analysis(list_of_paths, update_callback=None):
    """Función principal que gestiona la lectura, procesamiento y compilación."""
    paths_with_dates = []
    mensajes = []
    for p in list_of_paths:
        fecha = _extract_date_from_name(Path(p))
        if fecha:
            paths_with_dates.append((fecha, Path(p)))
        else:
            mensajes.append(f"⚠️ Ignorado: No se pudo extraer la fecha de '{Path(p).name}'.")
    paths_with_dates.sort()
    sorted_paths = [p for fecha, p in paths_with_dates]
    
    if not sorted_paths:
        return (pd.DataFrame(), mensajes)

    resumenes = []
    lluvia_dia_siguiente = np.nan
    
    for i, path in enumerate(reversed(sorted_paths)):
        if update_callback:
            update_callback(f"Procesando {i+1}/{len(sorted_paths)}: {path.name}...")
        
        try:
            # Leer datos del archivo
            all_sheets = data_parser.read_sheets_from_file(path)
            
            # Realizar los cálculos
            resumen_dia = calc.process_day_data(all_sheets, CONFIG)
            
            # Añadir fecha y lluvia
            resumen_dia['Dias'] = _extract_date_from_name(path)
            resumen_dia['Lluvia'] = lluvia_dia_siguiente
            resumenes.append(resumen_dia)
            
            # Preparar lluvia para la siguiente iteración
            df_lluvia = all_sheets[CONFIG['hoja_resumen_lluvia']]
            fila_lluvia = int(re.search(r'\d+', CONFIG['celda_lluvia']).group()) - 1
            col_lluvia_letra = re.search(r'[A-Z]+', CONFIG['celda_lluvia'].upper()).group()
            col_lluvia_num = sum([(ord(char) - 64) * (26 ** i) for i, char in enumerate(reversed(col_lluvia_letra))]) -1
            valor_lluvia = df_lluvia.iloc[fila_lluvia, col_lluvia_num]
            lluvia_dia_siguiente = pd.to_numeric(valor_lluvia, errors='coerce')

        except Exception as e:
            mensajes.append(f"❌ Error al procesar '{path.name}': {type(e).__name__} - {e}")
            lluvia_dia_siguiente = np.nan

    resumenes.reverse()

    if not resumenes: return (pd.DataFrame(), mensajes)

    df_reporte = pd.DataFrame(resumenes)
    df_reporte['Dias'] = pd.to_datetime(df_reporte['Dias']).dt.strftime('%Y-%m-%d')
    columnas_finales = ['Dias', 'Mayor temperatura máxima', 'Menor temperatura minima', 'Media temperatura', 'MAxima presión nivel medio del mar', 'Minima presión nivel medio del mar', 'Media presión nivel medio del mar', 'Media presion en la estación', 'Lluvia', 'Dirección del viento', 'Velocidad media del viento', 'Velocidad máxima y direccion', 'Recorrido del viento', 'Nuvocidad dia', 'Nuvocidad noche', 'Media de nuvocidad', 'Humedad maxima', 'Humedad minima', 'Humedad media', 'Punto de rocio', 'Tensión de vapor']
    
    for col in columnas_finales:
        if col not in df_reporte.columns:
            df_reporte[col] = np.nan
    
    return (df_reporte[columnas_finales], mensajes)