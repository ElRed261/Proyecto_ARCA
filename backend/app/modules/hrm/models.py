from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    
    cedula = Column(String, unique=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String)
    address = Column(String)
    hiring_date = Column(DateTime)
    termination_date = Column(DateTime, nullable=True)

    # Relación backref con User (definida como string para evitar imports circulares)
    user = relationship("app.modules.auth.models.User", backref="employee_profile")