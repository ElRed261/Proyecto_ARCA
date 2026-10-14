from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base

# 1. IMPORTAMOS MODELOS PARA CREAR TABLAS
from app.modules.auth import models as auth_models
from app.modules.synoptic import models as synoptic_models
from app.modules.summary import models as summary_models
from app.modules.audit import models as audit_models

# 2. IMPORTAMOS RUTAS
from app.modules.auth import router as auth_router
from app.modules.auth import admin_router
from app.modules.synoptic import router as synoptic_router
from app.modules.summary import router as summary_router
from app.modules.audit import router as audit_router

# 3. CREAMOS TABLAS
Base.metadata.create_all(bind=engine)

# 4. INICIAMOS APP
app = FastAPI(title="Proyecto ARCA")

origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]
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
app.include_router(synoptic_router.router, prefix="/api/synoptic", tags=["Observación Sinóptica"])
app.include_router(summary_router.router, prefix="/api/summary", tags=["Resumen Mensual"])
app.include_router(audit_router.router, prefix="/api/audit", tags=["Correcciones y Auditoría"])

@app.get("/")
def read_root():
    return {"sistema": "ARCA", "estado": "online", "version": "2.0.0"}