from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.modules.audit import models, schemas
from app.core.dependencies import get_current_active_user

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    responses={404: {"description": "Not found"}},
)

@router.get("/logs", response_model=List[schemas.AuditLogResponse])
def read_audit_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs

@router.post("/corrections", response_model=schemas.CorrectionRequestResponse)
def create_correction_request(request: schemas.CorrectionRequestCreate, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    db_request = models.CorrectionRequest(**request.dict(), requester_id=current_user.id)
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

@router.get("/corrections", response_model=List[schemas.CorrectionRequestResponse])
def read_correction_requests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    requests = db.query(models.CorrectionRequest).order_by(models.CorrectionRequest.created_at.desc()).offset(skip).limit(limit).all()
    return requests
