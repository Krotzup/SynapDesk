from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


class Configuracion(BaseSettings):
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    backend_cors_origins: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
