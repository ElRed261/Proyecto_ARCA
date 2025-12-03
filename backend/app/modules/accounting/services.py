from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from fastapi import HTTPException, status
from datetime import datetime
from app.modules.accounting import models, schemas
from decimal import Decimal

def create_account(db: Session, account: schemas.AccountCreate):
    db_account = models.Account(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

def get_accounts(db: Session):
    return db.query(models.Account).all()

def create_journal_entry(db: Session, entry: schemas.JournalEntryCreate):
    # 1. Validar balance (ya lo hace Pydantic, pero doble check no sobra)
    total_debit = sum(item.debit for item in entry.items)
    total_credit = sum(item.credit for item in entry.items)
    if total_debit != total_credit:
        raise HTTPException(status_code=400, detail="El asiento no está balanceado")

    # 2. Validar periodo fiscal abierto
    period = db.query(models.FiscalPeriod).filter(
        models.FiscalPeriod.start_date <= entry.date,
        models.FiscalPeriod.end_date >= entry.date
    ).first()
    
    if period and period.is_closed:
        raise HTTPException(status_code=400, detail="El periodo fiscal está cerrado")

    # 3. Crear cabecera
    db_entry = models.JournalEntry(
        date=entry.date,
        description=entry.description,
        state=models.JournalEntryState.DRAFT
    )
    db.add(db_entry)
    db.flush() # Para obtener ID

    # 4. Crear líneas
    for item in entry.items:
        # Validar que la cuenta sea imputable
        account = db.query(models.Account).get(item.account_id)
        if not account:
            raise HTTPException(status_code=404, detail=f"Cuenta {item.account_id} no encontrada")
        if not account.is_imputable:
            raise HTTPException(status_code=400, detail=f"La cuenta {account.code} no es imputable")

        db_item = models.JournalItem(
            entry_id=db_entry.id,
            account_id=item.account_id,
            description=item.description or entry.description,
            debit=item.debit,
            credit=item.credit,
            cost_center_id=item.cost_center_id
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_entry)
    return db_entry

def post_journal_entry(db: Session, entry_id: int):
    entry = db.query(models.JournalEntry).get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    
    if entry.state == models.JournalEntryState.POSTED:
        raise HTTPException(status_code=400, detail="El asiento ya está posteado")

    # Validar periodo nuevamente
    period = db.query(models.FiscalPeriod).filter(
        models.FiscalPeriod.start_date <= entry.date,
        models.FiscalPeriod.end_date >= entry.date
    ).first()
    
    if period and period.is_closed:
        raise HTTPException(status_code=400, detail="El periodo fiscal está cerrado")

    # Generar número de secuencia (Simulado por ahora con Timestamp, idealmente una secuencia DB)
    entry.entry_number = datetime.now().strftime("%Y%m%d%H%M%S")
    entry.state = models.JournalEntryState.POSTED
    
    db.commit()
    db.refresh(entry)
    return entry

def get_account_ledger(db: Session, account_id: int):
    account = db.query(models.Account).get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    # Obtener todos los items de diario POSTEADOS para esta cuenta, ordenados por fecha
    items = db.query(models.JournalItem).join(models.JournalEntry).filter(
        models.JournalItem.account_id == account_id,
        models.JournalEntry.state == models.JournalEntryState.POSTED
    ).order_by(models.JournalEntry.date.asc(), models.JournalEntry.created_at.asc()).all()

    ledger = []
    balance = Decimal('0.00')

    # Determinar naturaleza de la cuenta para el cálculo del saldo
    # Activo/Gasto: Saldo = Débito - Crédito
    # Pasivo/Patrimonio/Ingreso: Saldo = Crédito - Débito
    is_debit_nature = account.account_type in [models.AccountType.ASSET, models.AccountType.EXPENSE]

    for item in items:
        debit = Decimal(item.debit)
        credit = Decimal(item.credit)
        
        if is_debit_nature:
            balance += debit - credit
        else:
            balance += credit - debit

        ledger.append({
            "date": item.entry.date,
            "entry_number": item.entry.entry_number,
            "description": item.description,
            "debit": debit,
            "credit": credit,
            "balance": balance
        })

    return ledger
    return ledger

# --- FISCAL PERIODS ---
def create_fiscal_period(db: Session, period: schemas.FiscalPeriodCreate):
    # Validar solapamiento
    overlap = db.query(models.FiscalPeriod).filter(
        models.FiscalPeriod.start_date <= period.end_date,
        models.FiscalPeriod.end_date >= period.start_date
    ).first()
    
    if overlap:
        raise HTTPException(status_code=400, detail="El periodo se solapa con uno existente")

    db_period = models.FiscalPeriod(**period.dict())
    db.add(db_period)
    db.commit()
    db.refresh(db_period)
    return db_period

def close_fiscal_period(db: Session, period_id: int):
    period = db.query(models.FiscalPeriod).get(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")
    
    period.is_closed = True
    db.commit()
    db.refresh(period)
    return period

def get_fiscal_periods(db: Session):
    return db.query(models.FiscalPeriod).order_by(models.FiscalPeriod.start_date.desc()).all()

# --- REPORTS ---
def generate_trial_balance(db: Session):
    # Agrupar por cuenta y sumar débitos y créditos
    # Solo cuentas imputables
    accounts = db.query(models.Account).filter(models.Account.is_imputable == True).all()
    
    report = []
    
    for account in accounts:
        # Sumar items posteados
        result = db.query(
            func.sum(models.JournalItem.debit).label("total_debit"),
            func.sum(models.JournalItem.credit).label("total_credit")
        ).join(models.JournalEntry).filter(
            models.JournalItem.account_id == account.id,
            models.JournalEntry.state == models.JournalEntryState.POSTED
        ).first()

        debit = Decimal(result.total_debit or 0)
        credit = Decimal(result.total_credit or 0)
        
        # Si no tiene movimientos y saldo 0, se puede omitir o mostrar
        if debit == 0 and credit == 0:
            continue

        balance = debit - credit # Saldo deudor por defecto para visualización simple
        
        report.append({
            "account_code": account.code,
            "account_name": account.name,
            "debit": debit,
            "credit": credit,
            "balance": balance
        })
    
    report.sort(key=lambda x: x["account_code"])
    return report

def generate_income_statement(db: Session):
    # Ingresos (REVENUE) - Gastos (EXPENSE)
    revenue_accounts = db.query(models.Account).filter(models.Account.account_type == models.AccountType.REVENUE).all()
    expense_accounts = db.query(models.Account).filter(models.Account.account_type == models.AccountType.EXPENSE).all()

    revenues = []
    total_revenue = Decimal(0)
    for acc in revenue_accounts:
        balance = _get_account_balance(db, acc.id)
        # Ingresos son de naturaleza acreedora (Crédito - Débito)
        # Si el balance es positivo, es un ingreso.
        if balance != 0:
            # Para visualización, queremos ver ingresos positivos
            # Balance = Credit - Debit
            revenues.append({"code": acc.code, "name": acc.name, "amount": balance})
            total_revenue += balance

    expenses = []
    total_expenses = Decimal(0)
    for acc in expense_accounts:
        balance = _get_account_balance(db, acc.id)
        # Gastos son de naturaleza deudora (Débito - Crédito)
        if balance != 0:
            expenses.append({"code": acc.code, "name": acc.name, "amount": balance})
            total_expenses += balance

    net_income = total_revenue - total_expenses

    return {
        "revenues": revenues,
        "total_revenue": total_revenue,
        "expenses": expenses,
        "total_expenses": total_expenses,
        "net_income": net_income
    }

def generate_balance_sheet(db: Session):
    # Activos = Pasivos + Patrimonio (incluyendo utilidad del ejercicio)
    
    # 1. Calcular Utilidad del Ejercicio (Net Income)
    income_statement = generate_income_statement(db)
    net_income = income_statement["net_income"]

    # 2. Activos
    assets = []
    total_assets = Decimal(0)
    asset_accounts = db.query(models.Account).filter(models.Account.account_type == models.AccountType.ASSET).all()
    for acc in asset_accounts:
        balance = _get_account_balance(db, acc.id) # Debit - Credit
        if balance != 0:
            assets.append({"code": acc.code, "name": acc.name, "amount": balance})
            total_assets += balance

    # 3. Pasivos
    liabilities = []
    total_liabilities = Decimal(0)
    liability_accounts = db.query(models.Account).filter(models.Account.account_type == models.AccountType.LIABILITY).all()
    for acc in liability_accounts:
        balance = _get_account_balance(db, acc.id) # Credit - Debit
        if balance != 0:
            liabilities.append({"code": acc.code, "name": acc.name, "amount": balance})
            total_liabilities += balance

    # 4. Patrimonio
    equity = []
    total_equity = Decimal(0)
    equity_accounts = db.query(models.Account).filter(models.Account.account_type == models.AccountType.EQUITY).all()
    for acc in equity_accounts:
        balance = _get_account_balance(db, acc.id) # Credit - Debit
        if balance != 0:
            equity.append({"code": acc.code, "name": acc.name, "amount": balance})
            total_equity += balance

    # Agregar Resultado del Ejercicio al Patrimonio
    if net_income != 0:
        equity.append({"code": "RESULT", "name": "Resultado del Ejercicio", "amount": net_income})
        total_equity += net_income

    return {
        "assets": assets,
        "total_assets": total_assets,
        "liabilities": liabilities,
        "total_liabilities": total_liabilities,
        "equity": equity,
        "total_equity": total_equity,
        "total_liabilities_equity": total_liabilities + total_equity
    }

def _get_account_balance(db: Session, account_id: int):
    # Helper para calcular saldo de una cuenta (incluyendo hijos si fuera jerárquico real, 
    # pero aquí asumimos que solo imputables tienen movimientos o sumamos todo)
    # Aquí sumamos movimientos directos de la cuenta.
    # Si es cuenta padre, debería sumar hijos. 
    # Simplificación: Asumimos que el reporte itera sobre todas las cuentas y las muestra.
    # O mejor: Iteramos sobre cuentas imputables y las agrupamos.
    # Para este MVP, calculamos saldo directo de la cuenta.
    
    account = db.query(models.Account).get(account_id)
    
    result = db.query(
        func.sum(models.JournalItem.debit).label("total_debit"),
        func.sum(models.JournalItem.credit).label("total_credit")
    ).join(models.JournalEntry).filter(
        models.JournalItem.account_id == account_id,
        models.JournalEntry.state == models.JournalEntryState.POSTED
    ).first()

    debit = Decimal(result.total_debit or 0)
    credit = Decimal(result.total_credit or 0)

    if account.account_type in [models.AccountType.ASSET, models.AccountType.EXPENSE]:
        return debit - credit
    else:
        return credit - debit

# --- COST CENTERS ---
def create_cost_center(db: Session, cost_center: schemas.CostCenterCreate):
    db_cc = models.CostCenter(**cost_center.dict())
    db.add(db_cc)
    db.commit()
    db.refresh(db_cc)
    return db_cc

def get_cost_centers(db: Session):
    return db.query(models.CostCenter).all()

# --- ADMIN ACTIONS ---
def delete_account(db: Session, account_id: int):
    account = db.query(models.Account).get(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    
    # Verificar si tiene movimientos
    if db.query(models.JournalItem).filter(models.JournalItem.account_id == account_id).count() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar una cuenta con movimientos")
    
    # Verificar si tiene hijos
    if db.query(models.Account).filter(models.Account.parent_id == account_id).count() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar una cuenta con subcuentas")

    db.delete(account)
    db.commit()
    return {"message": "Cuenta eliminada"}

def delete_entry(db: Session, entry_id: int):
    entry = db.query(models.JournalEntry).get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    
    # Si está posteado, se permite eliminar SOLO porque es admin, pero idealmente debería ser reverso.
    # El requerimiento dice "eliminar y/o modificar todos los elementos".
    
    db.delete(entry)
    db.commit()
    return {"message": "Asiento eliminado"}

def delete_cost_center(db: Session, cc_id: int):
    cc = db.query(models.CostCenter).get(cc_id)
    if not cc:
        raise HTTPException(status_code=404, detail="Centro de costos no encontrado")
    
    # Verificar uso
    if db.query(models.JournalItem).filter(models.JournalItem.cost_center_id == cc_id).count() > 0:
        raise HTTPException(status_code=400, detail="Centro de costos en uso")

    db.delete(cc)
    db.commit()
    return {"message": "Centro de costos eliminado"}

def delete_period(db: Session, period_id: int):
    period = db.query(models.FiscalPeriod).get(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")
    
    db.delete(period)
    db.commit()
    return {"message": "Periodo eliminado"}

def reopen_period(db: Session, period_id: int):
    period = db.query(models.FiscalPeriod).get(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Periodo no encontrado")
    
    period.is_closed = False
    db.commit()
    db.refresh(period)
    return period
