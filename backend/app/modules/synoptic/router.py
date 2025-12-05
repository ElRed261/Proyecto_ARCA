from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
from app.core.database import get_db
from app.modules.synoptic import models, schemas
from app.modules.synoptic.calculations import realizar_calculos, get_all_stations, get_station_info
from app.core.dependencies import get_current_active_user

router = APIRouter(
    tags=["synoptic"],
    responses={404: {"description": "Not found"}},
)

# =============================================================================
# ENDPOINTS DE CÁLCULO METEOROLÓGICO
# =============================================================================

@router.post("/calculate", response_model=schemas.CalculationResponse)
def calculate_observations(
    data: schemas.CalculationRequest,
    current_user = Depends(get_current_active_user)
):
    """
    Realiza todos los cálculos meteorológicos y genera códigos SYNOP.
    
    - Cálculos de temperatura: Tv, Hr, Pr, Dif
    - Cálculos de presión: Let., Dif., Pres.NMM
    - Códigos SYNOP: 1snTTT, 2snTdTdTd, 4PPPP, 5aPPP
    - Lookup de estación: IIiii → Correc. Alt.
    """
    result = realizar_calculos(data.model_dump())
    
    # Convertir station_info si existe
    if result.get("station_info"):
        result["station_info"] = schemas.StationInfo(**result["station_info"])
    
    return result


@router.get("/stations", response_model=Dict[str, schemas.StationInfo])
def list_stations(current_user = Depends(get_current_active_user)):
    """Retorna todas las estaciones disponibles con su información."""
    stations = get_all_stations()
    return {
        station_id: schemas.StationInfo(**info) 
        for station_id, info in stations.items()
    }


@router.get("/stations/{station_id}", response_model=schemas.StationInfo)
def get_station(station_id: str, current_user = Depends(get_current_active_user)):
    """Obtiene información de una estación específica por su ID (IIiii)."""
    station = get_station_info(station_id)
    if not station:
        raise HTTPException(status_code=404, detail=f"Estación {station_id} no encontrada")
    return schemas.StationInfo(**station)


# =============================================================================
# ENDPOINTS DE LOGS (existentes)
# =============================================================================

@router.get("/logs", response_model=List[schemas.SystemLogResponse])
def read_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    logs = db.query(models.SystemLog).order_by(models.SystemLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

@router.post("/logs", response_model=schemas.SystemLogResponse)
def create_log(log: schemas.SystemLogCreate, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    db_log = models.SystemLog(**log.dict())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log
