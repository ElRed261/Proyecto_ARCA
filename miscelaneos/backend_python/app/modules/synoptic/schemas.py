from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class SystemLogBase(BaseModel):
    level: str
    module: str
    message: str

class SystemLogCreate(SystemLogBase):
    user_id: Optional[int] = None

class SystemLogResponse(SystemLogBase):
    id: int
    timestamp: datetime
    user_id: Optional[int]

    class Config:
        from_attributes = True


# =============================================================================
# SCHEMAS PARA CÁLCULOS METEOROLÓGICOS
# =============================================================================

class CalculationRequest(BaseModel):
    """Datos de entrada para cálculos meteorológicos."""
    # Temperatura
    ts: Optional[str] = None  # Temperatura seca
    th: Optional[str] = None  # Temperatura húmeda
    
    # Presión
    pres_est: Optional[str] = None  # Presión de la estación
    p3: Optional[str] = None  # Presión hace 3 horas
    p24: Optional[str] = None  # Presión hace 24 horas
    correc_alt: Optional[str] = None  # Corrección por altura
    
    # Estación
    station_id: Optional[str] = None  # IIiii código de estación
    
    # Indicadores
    ir: Optional[str] = None  # Indicador de precipitación
    ix: Optional[str] = None  # Indicador de tiempo


class StationInfo(BaseModel):
    """Información de una estación meteorológica."""
    name: str
    ch: float  # Corrección por altura
    lat: float
    lon: float
    h: float  # Altura de la estación


class CalculationResponse(BaseModel):
    """Resultados de los cálculos meteorológicos."""
    # Cálculos de temperatura
    tension_vapor: str = ""
    humedad_relativa: str = ""
    punto_rocio: str = ""
    diferencia: str = ""
    
    # Códigos SYNOP
    grupo_1sn_ttt: str = ""
    grupo_2sn_td: str = ""
    grupo_4pppp: str = ""
    grupo_5appp: str = ""
    grupo_58_59_p24: str = ""  # 58/59 P24P24P24 (24h pressure)
    grupo_29uuu: str = ""      # 29UUU (humidity)
    
    # Cálculos de presión
    p3_let: str = ""
    p24_let: str = ""
    p3_dif: str = ""
    p24_dif: str = ""
    pres_nmm: str = ""
    correc_alt: str = ""
    
    # Indicadores condicionales
    include_precipitation: bool = True
    include_weather: bool = True
    
    # Información de estación
    station_info: Optional[StationInfo] = None
    
    # Errores
    error_message: str = ""


class StationListResponse(BaseModel):
    """Lista de todas las estaciones disponibles."""
    stations: Dict[str, StationInfo]


# =============================================================================
# SCHEMAS PARA GUARDADO DE OBSERVACIONES
# =============================================================================

class SaveObservationRequest(BaseModel):
    """Datos para guardar una observación completa del día."""
    station_code: str  # Código de estación (ej: "78486")
    fecha: str  # Fecha en formato 'YYYY-MM-DD'
    observations: Dict[str, Any]  # Datos por hora {"06Z": {...}, "12Z": {...}}
    observer_name: Optional[str] = None  # Nombre del observador
