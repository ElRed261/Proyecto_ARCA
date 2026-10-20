# Responsable de interactuar con los archivos Excel y extraer datos.

import pandas as pd
from .config import CONFIG

def read_sheets_from_file(path):
    """Lee las hojas de cálculo necesarias de un archivo Excel."""
    sheets_to_read = [
        CONFIG['hoja_datos_diarios'],
        CONFIG['hoja_nuvosidad_y_temp'],
        CONFIG['hoja_resumen_lluvia']
    ]
    return pd.read_excel(path, sheet_name=sheets_to_read, header=None, engine='openpyxl')