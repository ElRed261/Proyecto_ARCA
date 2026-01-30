import os
from pathlib import Path

class Settings:
    PROJECT_NAME: str = "Proyecto ARCA"
    PROJECT_VERSION: str = "2.2.0"
    
    # Base de Datos LOCAL (SQLite)
    # Archivo se crea en backend/arca_local.db
    DB_PATH: Path = Path(__file__).parent.parent.parent / "arca_local.db"
    DATABASE_URL: str = f"sqlite:///{DB_PATH}"
    
    # PostgreSQL (comentado - para uso con servidor central futuro)
    # POSTGRES_USER: str = os.getenv("POSTGRES_USER", "admin_arca")
    # POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "123456")
    # POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    # POSTGRES_DB: str = os.getenv("POSTGRES_DB", "arca_db")
    # DATABASE_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}/{POSTGRES_DB}"

    # Seguridad
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ARCA_LOCAL_SECRET_KEY_2025")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas

settings = Settings()
