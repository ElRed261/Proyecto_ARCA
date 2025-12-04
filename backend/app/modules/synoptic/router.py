from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.modules.synoptic import models, schemas
from app.core.dependencies import get_current_active_user

router = APIRouter(
    prefix="/synoptic",
    tags=["synoptic"],
    responses={404: {"description": "Not found"}},
)

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
