"""Centralized configuration loaded from environment / .env.

What it does: single source of truth for all pipeline settings.
What it produces: one `settings` instance consumed across layers.
What it consumes: environment variables (see .env.template).
What it must NOT import: any ingest/transform/validate/load module (layer dependency rules).
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PIPELINE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings. Values come from the environment or a root `.env` file."""

    model_config = SettingsConfigDict(env_file=str(_PIPELINE_ROOT / ".env"), env_file_encoding="utf-8")

    google_credentials_path: str = ""
    drive_folder_id: str = ""
    source_dir: str = ""
    database_url: str = "postgresql+psycopg2://arca:arca@localhost:5432/arca"
    run_interval_hours: int = 6


settings = Settings()