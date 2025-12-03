from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base

# 1. IMPORTAMOS MODELOS PARA CREAR TABLAS
from app.modules.auth import models as auth_models
from app.modules.hrm import models as hrm_models
from app.modules.scm import models as scm_models
from app.modules.crm import models as crm_models
from app.modules.accounting import models as accounting_models

# 2. IMPORTAMOS RUTAS
from app.modules.auth import router as auth_router
from app.modules.auth import admin_router
from app.modules.accounting import router as accounting_router

# 3. CREAMOS TABLAS
Base.metadata.create_all(bind=engine)

# 4. INICIAMOS APP
app = FastAPI(title="Proyecto ARCA")

origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. ACTIVAMOS RUTAS
app.include_router(auth_router.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["Administración"])
app.include_router(accounting_router.router, prefix="/api/accounting", tags=["Contabilidad"])

@app.get("/")
def read_root():
    return {"sistema": "ARCA", "estado": "online"}