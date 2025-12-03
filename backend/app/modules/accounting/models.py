from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Enum, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class AccountType(str, enum.Enum):
    ASSET = "ASSET"         # Activo
    LIABILITY = "LIABILITY" # Pasivo
    EQUITY = "EQUITY"       # Patrimonio
    REVENUE = "REVENUE"     # Ingreso
    EXPENSE = "EXPENSE"     # Gasto

class JournalEntryState(str, enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CANCELLED = "CANCELLED"

class Account(Base):
    __tablename__ = "accounting_accounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False) # Ej: 1.1.01
    name = Column(String, nullable=False)
    account_type = Column(Enum(AccountType), nullable=False)
    is_imputable = Column(Boolean, default=True) # True = Recibe asientos, False = Contenedor
    parent_id = Column(Integer, ForeignKey("accounting_accounts.id"), nullable=True)
    
    parent = relationship("Account", remote_side=[id], backref="children")
    journal_items = relationship("JournalItem", back_populates="account")

class CostCenter(Base):
    __tablename__ = "accounting_cost_centers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    
    journal_items = relationship("JournalItem", back_populates="cost_center")

class FiscalPeriod(Base):
    __tablename__ = "accounting_fiscal_periods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False) # Ej: Enero 2025
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, default=False)

class JournalEntry(Base):
    __tablename__ = "accounting_journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    state = Column(Enum(JournalEntryState), default=JournalEntryState.DRAFT)
    entry_number = Column(String, unique=True, nullable=True) # Se genera al postear
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    items = relationship("JournalItem", back_populates="entry", cascade="all, delete-orphan")

class JournalItem(Base):
    __tablename__ = "accounting_journal_items"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("accounting_journal_entries.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounting_accounts.id"), nullable=False)
    description = Column(String, nullable=True) # Detalle de la línea
    
    debit = Column(Numeric(14, 2), default=0)
    credit = Column(Numeric(14, 2), default=0)
    
    cost_center_id = Column(Integer, ForeignKey("accounting_cost_centers.id"), nullable=True)
    
    entry = relationship("JournalEntry", back_populates="items")
    account = relationship("Account", back_populates="journal_items")
    cost_center = relationship("CostCenter", back_populates="journal_items")
