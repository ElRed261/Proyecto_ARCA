from sqlalchemy import Column, Integer, String, DECIMAL, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    tax_id = Column(String) # RNC/Cedula
    email = Column(String)
    phone = Column(String)
    address = Column(String)

class SaleOrder(Base):
    __tablename__ = "sale_orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    employee_id = Column(Integer, ForeignKey("employees.id"))
    
    status = Column(String) # COTIZACION, FACTURADO
    total_amount = Column(DECIMAL(10, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer")
    details = relationship("SaleOrderDetail", back_populates="order")

class SaleOrderDetail(Base):
    __tablename__ = "sale_order_details"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("sale_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id")) # Asumiendo que products está en 'products' table
    
    quantity = Column(Integer)
    unit_price = Column(DECIMAL(10, 2))

    order = relationship("SaleOrder", back_populates="details")