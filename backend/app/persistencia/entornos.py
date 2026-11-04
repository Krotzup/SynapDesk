from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.configuracion import RAIZ_PROYECTO, Configuracion


class EntornoPruebasBD(BaseSettings):
    postgres_test_host: str = Field(default="127.0.0.1", min_length=1)
    postgres_test_port: int = Field(default=5433, ge=1, le=65535)
    postgres_test_db: str = Field(min_length=1)
    postgres_test_user: str = Field(min_length=1)
    postgres_test_password: SecretStr

    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env", extra="ignore", env_file_encoding="utf-8"
    )


def seleccionar_configuracion_bd(base: str = "principal") -> Configuracion:
    """Selecciona la base principal o una configuración de testing separada."""
    if base not in {"principal", "testing"}:
        raise ValueError("Utiliza base=principal o base=testing.")

    principal = Configuracion()
    if base == "principal":
        return principal

    entorno = EntornoPruebasBD()
    if entorno.postgres_test_db == principal.postgres_db:
        raise ValueError("POSTGRES_TEST_DB debe ser distinta de POSTGRES_DB.")

    configuracion = Configuracion(
        _env_file=None,
        app_env="testing",
        backend_cors_origins=[],
        postgres_host=entorno.postgres_test_host,
        postgres_port=entorno.postgres_test_port,
        postgres_db=entorno.postgres_test_db,
        postgres_user=entorno.postgres_test_user,
        postgres_password=entorno.postgres_test_password,
        postgres_sslmode="prefer",
    )
    if not configuracion.tiene_configuracion_bd:
        raise ValueError("Falta completar la configuración de la base de testing.")
    return configuracion
