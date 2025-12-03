from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.accounting import schemas, services, models

router = APIRouter()

# --- ACCOUNTS ---
@router.post("/accounts", response_model=schemas.AccountResponse)
def create_account(account: schemas.AccountCreate, db: Session = Depends(get_db)):
    try:
        return services.create_account(db, account)
    except Exception as e:
        # Check for integrity error (duplicate code)
        error_str = str(e).lower()
        if "unique" in error_str and "code" in error_str:
            raise HTTPException(status_code=400, detail="El código de cuenta ya existe. Por favor use otro código.")
        
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts", response_model=List[schemas.AccountResponse])
def list_accounts(db: Session = Depends(get_db)):
    return services.get_accounts(db)

@router.get("/accounts/{account_id}/ledger", response_model=List[schemas.LedgerItemResponse])
def get_account_ledger(account_id: int, db: Session = Depends(get_db)):
    return services.get_account_ledger(db, account_id)

# --- JOURNAL ENTRIES ---
@router.post("/entries", response_model=schemas.JournalEntryResponse)
def create_entry(entry: schemas.JournalEntryCreate, db: Session = Depends(get_db)):
    return services.create_journal_entry(db, entry)

@router.post("/entries/{entry_id}/post", response_model=schemas.JournalEntryResponse)
def post_entry(entry_id: int, db: Session = Depends(get_db)):
    return services.post_journal_entry(db, entry_id)

@router.get("/entries", response_model=List[schemas.JournalEntryResponse])
def list_entries(db: Session = Depends(get_db)):
    return db.query(models.JournalEntry).order_by(models.JournalEntry.date.desc()).all()

# --- FISCAL PERIODS ---
@router.post("/periods", response_model=schemas.FiscalPeriodResponse)
def create_period(period: schemas.FiscalPeriodCreate, db: Session = Depends(get_db)):
    return services.create_fiscal_period(db, period)

@router.post("/periods/{period_id}/close", response_model=schemas.FiscalPeriodResponse)
def close_period(period_id: int, db: Session = Depends(get_db)):
    return services.close_fiscal_period(db, period_id)

@router.get("/periods", response_model=List[schemas.FiscalPeriodResponse])
def list_periods(db: Session = Depends(get_db)):
    return services.get_fiscal_periods(db)

# --- REPORTS ---
@router.get("/reports/trial-balance")
def get_trial_balance(db: Session = Depends(get_db)):
    return services.generate_trial_balance(db)

@router.get("/reports/income-statement")
def get_income_statement(db: Session = Depends(get_db)):
    return services.generate_income_statement(db)

@router.get("/reports/balance-sheet")
def get_balance_sheet(db: Session = Depends(get_db)):
    return services.generate_balance_sheet(db)

# --- COST CENTERS ---
@router.post("/cost-centers", response_model=schemas.CostCenterResponse)
def create_cost_center(cost_center: schemas.CostCenterCreate, db: Session = Depends(get_db)):
    return services.create_cost_center(db, cost_center)

@router.get("/cost-centers", response_model=List[schemas.CostCenterResponse])
def list_cost_centers(db: Session = Depends(get_db)):
    return services.get_cost_centers(db)

# --- ADMIN ENDPOINTS ---
def check_admin(user = Depends(get_current_user)):
    # Asumimos que user tiene roles cargados. Si no, habría que cargarlos.
    # En dependencies.py get_current_user devuelve el modelo User.
    # El modelo User tiene relación 'roles'.
    
    # Verificar si tiene rol 'admin'
    is_admin = any(role.name == 'admin' for role in user.roles)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Requiere privilegios de administrador")
    return user

@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), user = Depends(check_admin)):
    return services.delete_account(db, account_id)

@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: Session = Depends(get_db), user = Depends(check_admin)):
    return services.delete_entry(db, entry_id)

@router.delete("/cost-centers/{cc_id}")
def delete_cost_center(cc_id: int, db: Session = Depends(get_db), user = Depends(check_admin)):
    return services.delete_cost_center(db, cc_id)

@router.delete("/periods/{period_id}")
def delete_period(period_id: int, db: Session = Depends(get_db), user = Depends(check_admin)):
    return services.delete_period(db, period_id)

@router.post("/periods/{period_id}/reopen")
def reopen_period(period_id: int, db: Session = Depends(get_db), user = Depends(check_admin)):
    return services.reopen_period(db, period_id)
