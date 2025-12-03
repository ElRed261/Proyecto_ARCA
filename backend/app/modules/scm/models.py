from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

# --- CATEGORÍAS Y ALMACENES ---
class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    products = relationship("Product", back_populates="category")

class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    location = Column(String)

# --- PRODUCTOS ---
class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    sale_price = Column(DECIMAL(10, 2)) 
    cost_price = Column(DECIMAL(10, 2))
    is_service = Column(Boolean, default=False)

    category = relationship("Category", back_populates="products")
    movements = relationship("InventoryMovement", back_populates="product")

# --- MOVIMIENTOS DE INVENTARIO (KARDEX) ---
class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"))
    movement_type = Column(String) # COMPRA, VENTA, AJUSTE
    quantity = Column(Integer)     # + entra, - sale
    reference_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="movements")
    warehouse = relationship("Warehouse")

# --- PROVEEDORES Y COMPRAS ---
class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    rnc = Column(String)
    email = Column(String)
    phone = Column(String)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    # Usamos string en la relación para evitar errores si HRM no carga primero
    employee_id = Column(Integer, ForeignKey("employees.id")) 
    
    date = Column(DateTime(timezone=True), server_default=func.now())
    total_amount = Column(DECIMAL(10, 2))
    status = Column(String) # BORRADOR, RECIBIDO

    supplier = relationship("Supplier")
    details = relationship("PurchaseDetail", back_populates="order")

class PurchaseDetail(Base):
    __tablename__ = "purchase_details"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_cost = Column(DECIMAL(10, 2))

    order = relationship("PurchaseOrder", back_populates="details")
    product = relationship("Product")