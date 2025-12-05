"""
Módulo de Cálculos Meteorológicos
Basado en el Manual de Claves OMM N°306 (FM-12 SYNOP)
"""

import math
from typing import Dict, Optional, Any

# =============================================================================
# DATOS DE ESTACIONES (IIiii → Corrección de Altura)
# =============================================================================

STATIONS = {
    "78451": {"name": "Monte Cristi", "ch": 0.5, "lat": 19.8499, "lon": -71.6535, "h": 8},
    "MDCY": {"name": "Catey", "ch": 0.8, "lat": 19.267, "lon": -69.7337, "h": 4},
    "78457": {"name": "Puerto Plata", "ch": 1.0, "lat": 19.7542, "lon": -70.5632, "h": 16},
    "78482": {"name": "Barahona", "ch": 1.2, "lat": 18.24861, "lon": -71.12288, "h": 19.5},
    "78467": {"name": "Sabana de la mar", "ch": 1.2, "lat": 19.0527, "lon": -69.3888, "h": 11},
    "78464": {"name": "Cabrera", "ch": 1.5, "lat": 19.6444, "lon": -69.9063, "h": 18},
    "78486": {"name": "Central", "ch": 1.6, "lat": 18.4734, "lon": -69.8705, "h": 14},
    "78485": {"name": "Las américas", "ch": 2.0, "lat": 18.4331, "lon": -69.6796, "h": 7},
    "78479": {"name": "Punta Cana", "ch": 2.0, "lat": 18.546, "lon": -68.3594, "h": 7},
    "78484": {"name": "El Higüero", "ch": 3.5, "lat": 18.57696, "lon": -69.98158, "h": 27},
    "78466": {"name": "Arroyo Barril", "ch": 3.5, "lat": 19.2005, "lon": -69.43144, "h": 49.4},
    "78480": {"name": "Jimaní", "ch": 4.8, "lat": 18.4928, "lon": -71.853, "h": 45},
    "78473": {"name": "Bayaguana", "ch": 6.0, "lat": 18.7422, "lon": -69.6308, "h": 53},
    "78488": {"name": "La Romana", "ch": 8.5, "lat": 18.4485, "lon": -68.9093, "h": 62},
    "78460": {"name": "Santiago", "ch": 19.8, "lat": 19.4031, "lon": -70.5978, "h": 170},
}


def get_station_info(station_id: str) -> Optional[Dict]:
    """Obtiene información de una estación por su ID (IIiii)."""
    # Buscar por ID exacto o por los últimos 5 dígitos
    station_id = station_id.strip().upper()
    if station_id in STATIONS:
        return STATIONS[station_id]
    # Buscar solo por número (sin prefijo)
    for key, value in STATIONS.items():
        if key.endswith(station_id) or station_id.endswith(key):
            return value
    return None


# =============================================================================
# CÁLCULOS METEOROLÓGICOS
# =============================================================================

def calcular_h26(temp_humedo: float) -> Optional[float]:
    """
    Calcula H26 - Presión de vapor de saturación a temperatura húmeda.
    Fórmula Magnus-Tetens.
    """
    if temp_humedo + 243.5 == 0:
        return None
    return 6.112 * math.exp((17.67 * temp_humedo) / (temp_humedo + 243.5))


def calcular_h27(temp_humedo: float) -> float:
    """Calcula H27 - Constante psicrométrica."""
    return 0.00066 * 1000 * (1 + 0.00115 * temp_humedo)


def calcular_h28_asumido(temp_seco: float) -> Optional[float]:
    """Calcula H28 - Presión de vapor de saturación a temperatura seca."""
    if temp_seco + 243.5 == 0:
        return None
    return 6.112 * math.exp((17.67 * temp_seco) / (temp_seco + 243.5))


def calcular_tension_vapor(temp_seco: float, temp_humedo: float) -> Optional[float]:
    """
    Calcula la tensión de vapor usando la fórmula psicrométrica.
    TV = H26 - H27 * (Ts - Th)
    """
    h26 = calcular_h26(temp_humedo)
    h27 = calcular_h27(temp_humedo)
    if h26 is None:
        return None
    return h26 - h27 * (temp_seco - temp_humedo)


def calcular_humedad_relativa(tension_vapor: float, temp_seco: float) -> Optional[float]:
    """
    Calcula la humedad relativa.
    HR = (TV / H28_asumido) * 100
    """
    h28_asumido = calcular_h28_asumido(temp_seco)
    if h28_asumido is None or h28_asumido == 0:
        return None
    return (tension_vapor / h28_asumido) * 100


def calcular_punto_rocio(temp_seco: float, humedad_relativa_porc: float) -> Optional[float]:
    """Calcula el punto de rocío usando fórmula polinomial."""
    try:
        factor_humedad = 1 - (0.01 * humedad_relativa_porc)
        termino1 = (14.55 + 0.114 * temp_seco) * factor_humedad
        termino2 = ((2.5 + 0.007 * temp_seco) * factor_humedad) ** 3
        termino3 = (15.9 + 0.117 * temp_seco) * (factor_humedad ** 14)
        return temp_seco - termino1 - termino2 - termino3
    except Exception:
        return None


# =============================================================================
# CODIFICACIÓN SYNOP (WMO FM-12)
# =============================================================================

def format_temperature_group(temp: float) -> str:
    """
    Formatea grupo de temperatura 1snTTT.
    sn = 0 para temp >= 0, sn = 1 para temp < 0
    TTT = temperatura × 10 (sin signo)
    Ejemplo: 23.3°C → "10233", -23.3°C → "11233"
    """
    if temp is None or math.isnan(temp):
        return ""
    sign = "0" if temp >= 0 else "1"
    abs_temp = abs(temp)
    ttt = str(round(abs_temp * 10)).zfill(3)
    return f"1{sign}{ttt}"


def format_dew_point_group(dew_point: float) -> str:
    """
    Formatea grupo de punto de rocío 2snTdTdTd.
    sn = 0 para temp >= 0, sn = 1 para temp < 0
    Ejemplo: 21.5°C → "20215", -21.5°C → "21215"
    """
    if dew_point is None or math.isnan(dew_point):
        return ""
    sign = "0" if dew_point >= 0 else "1"
    abs_dew_point = abs(dew_point)
    ttt = str(round(abs_dew_point * 10)).zfill(3)
    return f"2{sign}{ttt}"


def format_pressure_group(pressure: float) -> str:
    """
    Formatea grupo de presión a nivel del mar 4PPPP.
    PPPP = presión × 10 mod 10000 (últimos 4 dígitos)
    Ejemplo: 1017.3 hPa → "40173", 998.5 hPa → "49985"
    """
    if pressure is None or math.isnan(pressure):
        return ""
    pppp = str(round(pressure * 10) % 10000).zfill(4)
    return f"4{pppp}"


def calcular_tendencia_a(diferencia_p3: float) -> str:
    """
    Calcula el código 'a' para el grupo 5aPPP según la tendencia de presión.
    
    Tendencia positiva (presión subiendo):
        0: +0.1 a +0.5 hPa
        1: +0.6 a +1.4 hPa
        2: +1.5 a +1.9 hPa
        3: +2.0 hPa o más
    
    Sin cambio:
        4: 0 hPa
    
    Tendencia negativa (presión bajando):
        5: -0.1 a -0.5 hPa
        6: -0.6 a -1.4 hPa
        7: -1.5 a -1.9 hPa
        8: -2.0 hPa o menos
    """
    if diferencia_p3 is None or math.isnan(diferencia_p3):
        return ""
    
    # Redondear a 1 decimal
    dif = round(diferencia_p3, 1)
    
    # Sin cambio
    if dif == 0:
        return "4"
    
    abs_dif = abs(dif)
    
    # Tendencia positiva (subiendo)
    if dif > 0:
        if 0.1 <= abs_dif <= 0.5:
            return "0"
        elif 0.6 <= abs_dif <= 1.4:
            return "1"
        elif 1.5 <= abs_dif <= 1.9:
            return "2"
        elif abs_dif >= 2.0:
            return "3"
    
    # Tendencia negativa (bajando)
    if dif < 0:
        if 0.1 <= abs_dif <= 0.5:
            return "5"
        elif 0.6 <= abs_dif <= 1.4:
            return "6"
        elif 1.5 <= abs_dif <= 1.9:
            return "7"
        elif abs_dif >= 2.0:
            return "8"
    
    return "4"  # Por defecto, sin cambio


def format_pressure_tendency_group(diferencia_p3: float) -> str:
    """
    Formatea el grupo 5aPPP (tendencia de presión en 3 horas).
    a = código de tendencia (0-8)
    PPP = magnitud del cambio × 10
    """
    if diferencia_p3 is None or math.isnan(diferencia_p3):
        return ""
    
    a = calcular_tendencia_a(diferencia_p3)
    ppp = str(round(abs(diferencia_p3) * 10)).zfill(3)
    return f"5{a}{ppp}"


def should_include_precipitation(ir: str) -> bool:
    """
    Determina si el grupo 6RRR debe incluirse según Ir.
    Ir = 0, 1, 2: incluir; Ir = 3, 4: omitir
    """
    try:
        ir_num = int(ir)
        return 0 <= ir_num <= 2
    except (ValueError, TypeError):
        return True  # Por defecto incluir


def should_include_weather(ix: str) -> bool:
    """
    Determina si el grupo 7ww debe incluirse según Ix.
    Ix = 1, 4: incluir; Ix = 2, 3, 5, 6, 7: omitir
    """
    try:
        ix_num = int(ix)
        return ix_num in (1, 4)
    except (ValueError, TypeError):
        return True  # Por defecto incluir


def format_pressure_24h_group(diferencia_p24: float) -> str:
    """
    Formatea el grupo 58/59 P24P24P24 (cambio de presión en 24 horas).
    58 = presión subió (diferencia positiva)
    59 = presión bajó (diferencia negativa)
    P24P24P24 = magnitud del cambio × 10
    
    Ejemplo: +3.5 hPa → "58035", -2.1 hPa → "59021"
    """
    if diferencia_p24 is None or math.isnan(diferencia_p24):
        return ""
    
    # Redondear a 1 decimal
    dif = round(diferencia_p24, 1)
    
    # Determinar prefijo según si subió o bajó
    if dif >= 0:
        prefix = "58"
    else:
        prefix = "59"
    
    # PPP = magnitud × 10
    ppp = str(round(abs(dif) * 10)).zfill(3)
    return f"{prefix}{ppp}"


def format_humidity_group(humedad_relativa: float) -> str:
    """
    Formatea el grupo 29UUU (humedad relativa).
    UUU = humedad relativa (3 dígitos)
    
    Ejemplo: 71% → "29071", 100% → "29100"
    """
    if humedad_relativa is None or math.isnan(humedad_relativa):
        return ""
    
    # Redondear y asegurar 3 dígitos
    hr = round(min(100, max(0, humedad_relativa)))
    uuu = str(hr).zfill(3)
    return f"29{uuu}"


# =============================================================================
# FUNCIÓN PRINCIPAL DE CÁLCULO
# =============================================================================

def realizar_calculos(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Realiza todos los cálculos meteorológicos y genera códigos SYNOP.
    
    Args:
        data: Diccionario con los datos del formulario
        
    Returns:
        Diccionario con todos los resultados calculados
    """
    results = {
        # Cálculos de temperatura
        "tension_vapor": "",
        "humedad_relativa": "",
        "punto_rocio": "",
        "diferencia": "",
        
        # Códigos SYNOP
        "grupo_1sn_ttt": "",
        "grupo_2sn_td": "",
        "grupo_4pppp": "",
        "grupo_5appp": "",
        "grupo_58_59_p24": "",  # 58/59 P24P24P24 (24h pressure change)
        "grupo_29uuu": "",      # 29UUU (humidity)
        
        # Cálculos de presión
        "p3_let": "",
        "p24_let": "",
        "p3_dif": "",
        "p24_dif": "",
        "pres_nmm": "",
        "correc_alt": "",
        
        # Indicadores condicionales
        "include_precipitation": True,
        "include_weather": True,
        
        # Información de estación
        "station_info": None,
        
        # Errores
        "error_message": ""
    }
    
    # =========================================================================
    # LOOKUP DE ESTACIÓN (IIiii → Correc. Alt.)
    # =========================================================================
    station_id = data.get("station_id", "").strip()
    if station_id:
        station_info = get_station_info(station_id)
        if station_info:
            results["station_info"] = station_info
            results["correc_alt"] = str(station_info["ch"])
    
    # Si no hay station_id pero hay correc_alt manual, usarlo
    if not results["correc_alt"]:
        results["correc_alt"] = data.get("correc_alt", "")
    
    # =========================================================================
    # CÁLCULOS DE TEMPERATURA
    # =========================================================================
    ts_str = data.get("ts", "")
    th_str = data.get("th", "")
    
    temp_seco = None
    punto_rocio = None
    
    if ts_str:
        try:
            temp_seco = float(ts_str)
            # Generar grupo 1snTTT
            results["grupo_1sn_ttt"] = format_temperature_group(temp_seco)
        except ValueError:
            pass
    
    if ts_str and th_str:
        try:
            temp_seco = float(ts_str)
            temp_humedo = float(th_str)
            
            # Validación: Th no puede ser mayor que Ts
            if temp_humedo > temp_seco:
                results["error_message"] = "Error: Th no puede ser mayor que Ts."
            else:
                # Calcular tensión de vapor
                tension_vapor = calcular_tension_vapor(temp_seco, temp_humedo)
                
                if tension_vapor is not None:
                    results["tension_vapor"] = f"{tension_vapor:.1f}"
                    
                    # Calcular humedad relativa
                    humedad_relativa = calcular_humedad_relativa(tension_vapor, temp_seco)
                    
                    if humedad_relativa is not None:
                        results["humedad_relativa"] = f"{min(100, humedad_relativa):.0f}"
                        
                        # Calcular punto de rocío
                        punto_rocio = calcular_punto_rocio(temp_seco, humedad_relativa)
                        
                        if punto_rocio is not None:
                            results["punto_rocio"] = f"{punto_rocio:.1f}"
                            # Generar grupo 2snTdTdTd
                            results["grupo_2sn_td"] = format_dew_point_group(punto_rocio)
                        
                        # Generar grupo 29UUU (humedad)
                        results["grupo_29uuu"] = format_humidity_group(humedad_relativa)
                
                # Calcular diferencia
                diferencia = temp_seco - temp_humedo
                results["diferencia"] = f"{diferencia:.1f}"
                
                # Actualizar grupo 1snTTT
                results["grupo_1sn_ttt"] = format_temperature_group(temp_seco)
                
        except ValueError:
            pass
    
    # =========================================================================
    # CÁLCULOS DE PRESIÓN
    # =========================================================================
    pres_est_str = data.get("pres_est", "")
    p3_str = data.get("p3", "")
    p24_str = data.get("p24", "")
    correc_alt_str = results["correc_alt"] or data.get("correc_alt", "")
    
    if pres_est_str:
        try:
            pres_est = float(pres_est_str)
            
            # Let. = Pres. Est. (auto-llenado)
            results["p3_let"] = f"{pres_est:.1f}"
            results["p24_let"] = f"{pres_est:.1f}"
            
            # P3 Dif. = Pres. Est. - P3
            if p3_str:
                try:
                    p3 = float(p3_str)
                    p3_dif = pres_est - p3
                    results["p3_dif"] = f"{p3_dif:.1f}"
                    
                    # Generar grupo 5aPPP (tendencia de presión)
                    results["grupo_5appp"] = format_pressure_tendency_group(p3_dif)
                except ValueError:
                    pass
            
            # P24 Dif. = Pres. Est. - P24
            if p24_str:
                try:
                    p24 = float(p24_str)
                    p24_dif = pres_est - p24
                    results["p24_dif"] = f"{p24_dif:.1f}"
                    
                    # Generar grupo 58/59 P24P24P24 (cambio 24h)
                    results["grupo_58_59_p24"] = format_pressure_24h_group(p24_dif)
                except ValueError:
                    pass
            
            # Pres. NMM = Pres. Est. + Correc. Alt.
            if correc_alt_str:
                try:
                    correc_alt = float(correc_alt_str)
                    pres_nmm = pres_est + correc_alt
                    results["pres_nmm"] = f"{pres_nmm:.1f}"
                    # Generar grupo 4PPPP
                    results["grupo_4pppp"] = format_pressure_group(pres_nmm)
                except ValueError:
                    pass
                    
        except ValueError:
            pass
    
    # =========================================================================
    # INDICADORES Ir/Ix
    # =========================================================================
    ir = data.get("ir", "")
    ix = data.get("ix", "")
    
    results["include_precipitation"] = should_include_precipitation(ir)
    results["include_weather"] = should_include_weather(ix)
    
    return results


def get_all_stations() -> Dict[str, Dict]:
    """Retorna todas las estaciones disponibles."""
    return STATIONS
