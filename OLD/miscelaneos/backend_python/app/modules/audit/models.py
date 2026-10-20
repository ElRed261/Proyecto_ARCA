from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String) # CREATE, UPDATE, DELETE, CORRECTION
    entity = Column(String) # Table/Resource name
    entity_id = Column(String)
    details = Column(Text) # JSON or text description of change

    user = relationship("User")

class CorrectionRequest(Base):
    __tablename__ = "correction_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    requester_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED
    description = Column(Text)
    
    requester = relationship("User")
