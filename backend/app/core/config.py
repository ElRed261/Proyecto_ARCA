import os

class Settings:
    PROJECT_NAME: str = "Proyecto ARCA"
    PROJECT_VERSION: str = "1.0.0"
    
    # Base de Datos
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "admin_arca")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "123456")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "arca_db")
    DATABASE_URL: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}/{POSTGRES_DB}"

    # Seguridad
    SECRET_KEY: str = "ESTA_ES_LA_LLAVE_MAESTRA_CAMBIALA_EN_PRODUCCION_POR_FAVOR"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 horas

settings = Settings()
