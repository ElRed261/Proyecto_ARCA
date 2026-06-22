from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class MonthlySummary(Base):
    __tablename__ = "monthly_summaries"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(Integer) # 1-12
    year = Column(Integer)
    total_revenue = Column(Float, default=0.0)
    total_expenses = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Podríamos agregar relaciones a detalles específicos si fuera necesario
