from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SystemLogBase(BaseModel):
    level: str
    module: str
    message: str

class SystemLogCreate(SystemLogBase):
    user_id: Optional[int] = None

class SystemLogResponse(SystemLogBase):
    id: int
    timestamp: datetime
    user_id: Optional[int]

    class Config:
        from_attributes = True
