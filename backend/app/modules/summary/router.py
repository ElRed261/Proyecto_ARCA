from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.modules.summary import models, schemas
from app.core.dependencies import get_current_active_user

router = APIRouter(
    prefix="/summary",
    tags=["summary"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[schemas.MonthlySummaryResponse])
def read_summaries(skip: int = 0, limit: int = 12, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    summaries = db.query(models.MonthlySummary).order_by(models.MonthlySummary.year.desc(), models.MonthlySummary.month.desc()).offset(skip).limit(limit).all()
    return summaries

@router.post("/", response_model=schemas.MonthlySummaryResponse)
def create_summary(summary: schemas.MonthlySummaryCreate, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    db_summary = models.MonthlySummary(**summary.dict())
    db.add(db_summary)
    db.commit()
    db.refresh(db_summary)
    return db_summary
