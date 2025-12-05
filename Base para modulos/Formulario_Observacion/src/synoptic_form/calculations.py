# src/synoptic_form/calculations.py
# Este archivo contiene únicamente las funciones de cálculo.

import math

# ... (Pega aquí el contenido completo de tu archivo calc.py original) ...

def calcular_h26(temp_humedo):
    if temp_humedo + 243.5 == 0: return None
    return 6.112 * math.exp((17.67 * temp_humedo) / (temp_humedo + 243.5))

def calcular_h27(temp_humedo):
    return 0.00066 * 1000 * (1 + 0.00115 * temp_humedo)

def calcular_h28_asumido(temp_seco):
    if temp_seco + 243.5 == 0: return None
    return 6.112 * math.exp((17.67 * temp_seco) / (temp_seco + 243.5))

def calcular_punto_rocio(temp_seco, humedad_rel_calculada_porcentaje):
    try:
        factor_humedad = 1 - (0.01 * humedad_rel_calculada_porcentaje)
        termino1 = (14.55 + 0.114 * temp_seco) * factor_humedad
        termino2 = ((2.5 + 0.007 * temp_seco) * factor_humedad) ** 3
        termino3 = (15.9 + 0.117 * temp_seco) * (factor_humedad ** 14)
        return temp_seco - termino1 - termino2 - termino3
    except: return "Error PR"

def calcular_tension_vapor(temp_seco, temp_humedo):
    h26 = calcular_h26(temp_humedo)
    h27 = calcular_h27(temp_humedo)
    if h26 is None or h27 is None: return "Error TV"
    try:
        resultado = h26 - h27 * (temp_seco - temp_humedo)
        return "  " if round(resultado, 1) == 6.1 else resultado
    except: return "Error TV"

def calcular_humedad_relativa(tension_vapor, temp_seco):
    h28_asumido = calcular_h28_asumido(temp_seco)
    if h28_asumido is None or h28_asumido == 0: return "Error HR"
    try: return (tension_vapor / h28_asumido) * 100
    except: return "Error HR"