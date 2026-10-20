from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AuditLogBase(BaseModel):
    action: str
    entity: str
    entity_id: str
    details: str

class AuditLogCreate(AuditLogBase):
    user_id: int

class AuditLogResponse(AuditLogBase):
    id: int
    timestamp: datetime
    user_id: int

    class Config:
        from_attributes = True

class CorrectionRequestBase(BaseModel):
    description: str

class CorrectionRequestCreate(CorrectionRequestBase):
    pass

class CorrectionRequestResponse(CorrectionRequestBase):
    id: int
    created_at: datetime
    requester_id: int
    status: str

    class Config:
        from_attributes = True
