from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


class Configuracion(BaseSettings):
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    backend_cors_origins: list[str] = Field(default_factory=list)
    postgres_host: str = Field(default="127.0.0.1", min_length=1)
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str | None = Field(default=None, min_length=1)
    postgres_user: str | None = Field(default=None, min_length=1)
    postgres_password: SecretStr | None = None
    postgres_sslmode: Literal[
        "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
    ] = "prefer"

    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def tiene_configuracion_bd(self) -> bool:
        return bool(
            self.postgres_db
            and self.postgres_user
            and self.postgres_password
            and self.postgres_password.get_secret_value()
        )
