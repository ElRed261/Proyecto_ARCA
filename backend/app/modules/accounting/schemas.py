from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from app.modules.accounting.models import AccountType, JournalEntryState

# --- COST CENTERS ---
class CostCenterBase(BaseModel):
    code: str
    name: str

class CostCenterCreate(CostCenterBase):
    pass

class CostCenterResponse(CostCenterBase):
    id: int
    class Config:
        from_attributes = True

# --- ACCOUNTS ---
class AccountBase(BaseModel):
    code: str
    name: str
    account_type: AccountType
    is_imputable: bool = True
    parent_id: Optional[int] = None

class AccountCreate(AccountBase):
    pass

class AccountResponse(AccountBase):
    id: int
    children: List['AccountResponse'] = [] # For hierarchy
    class Config:
        from_attributes = True

# --- JOURNAL ENTRIES ---
class JournalItemBase(BaseModel):
    account_id: int
    description: Optional[str] = None
    debit: Decimal = Decimal('0.00')
    credit: Decimal = Decimal('0.00')
    cost_center_id: Optional[int] = None

    @validator('debit', 'credit')
    def non_negative(cls, v):
        if v < 0:
            raise ValueError('Must be non-negative')
        return v

class JournalEntryCreate(BaseModel):
    date: date
    description: str
    items: List[JournalItemBase]

    @validator('items')
    def validate_balance(cls, items):
        total_debit = sum(item.debit for item in items)
        total_credit = sum(item.credit for item in items)
        if total_debit != total_credit:
            raise ValueError(f'Entry is not balanced: Debit {total_debit} != Credit {total_credit}')
        if not items:
            raise ValueError('Entry must have at least one item')
        return items

class JournalItemResponse(JournalItemBase):
    id: int
    class Config:
        from_attributes = True

class JournalEntryResponse(BaseModel):
    id: int
    entry_number: Optional[str]
    date: date
    description: str
    state: JournalEntryState
    created_at: datetime
    items: List[JournalItemResponse]
    class Config:
        from_attributes = True

# --- FISCAL PERIODS ---
class FiscalPeriodBase(BaseModel):
    name: str
    start_date: date
    end_date: date

class FiscalPeriodCreate(FiscalPeriodBase):
    pass

class FiscalPeriodResponse(FiscalPeriodBase):
    id: int
    is_closed: bool
    class Config:
        from_attributes = True

# --- LEDGER ---
class LedgerItemResponse(BaseModel):
    date: date
    entry_number: Optional[str]
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
