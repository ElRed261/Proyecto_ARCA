from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MonthlySummaryBase(BaseModel):
    month: int
    year: int
    total_revenue: float
    total_expenses: float
    net_profit: float

class MonthlySummaryCreate(MonthlySummaryBase):
    pass

class MonthlySummaryResponse(MonthlySummaryBase):
    id: int
    generated_at: datetime

    class Config:
        from_attributes = True
