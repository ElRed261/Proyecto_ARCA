from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    level = Column(String, default="INFO") # INFO, WARNING, ERROR
    module = Column(String)
    message = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User")
