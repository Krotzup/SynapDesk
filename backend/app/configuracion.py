import base64
import binascii
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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

    # PROVISIONAL_CONFIGURATION / PENDING_MEASUREMENT; memoria en KiB.
    auth_argon2_memoria_kib: int = Field(default=65536, ge=8, le=2**32 - 1)
    auth_argon2_iteraciones: int = Field(default=3, ge=1, le=2**32 - 1)
    auth_argon2_paralelismo: int = Field(default=1, ge=1, le=2**24 - 1)
    # Sin secreto por defecto, tampoco en testing. Se exige al crear el servicio.
    auth_hmac_clave: SecretStr | None = Field(default=None, repr=False)
    auth_hmac_id_clave: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{1,32}$"
    )
    # CSRF: parámetros provisionales, sin cambios en el esquema relacional.
    auth_csrf_token_bytes: int = Field(default=32, ge=32)
    auth_csrf_token_segundos: int = Field(default=600, gt=0)
    auth_csrf_contexto_segundos: int = Field(default=900, gt=0)
    auth_csrf_max_tokens: int = Field(default=8, gt=0)
    # Cerrado por defecto. CORS no determina el origen público de autenticación.
    auth_origenes_permitidos: list[str] = Field(default_factory=list)
    auth_proxies_autorizados: list[str] = Field(default_factory=list)
    # Sin cuotas implícitas ni certificación de producción: configurar las seis.
    auth_limite_cuenta_intentos: int | None = Field(default=None, gt=0, le=2**31 - 1)
    auth_limite_cuenta_ventana_segundos: int | None = Field(default=None, gt=0, le=2**31 - 1)
    auth_limite_cuenta_bloqueo_segundos: int | None = Field(default=None, gt=0, le=2**31 - 1)
    auth_limite_ip_intentos: int | None = Field(default=None, gt=0, le=2**31 - 1)
    auth_limite_ip_ventana_segundos: int | None = Field(default=None, gt=0, le=2**31 - 1)
    auth_limite_ip_bloqueo_segundos: int | None = Field(default=None, gt=0, le=2**31 - 1)
    auth_limite_reintentos_version: int = Field(default=2, ge=0, le=5)

    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("auth_hmac_clave")
    @classmethod
    def validar_clave_hmac(cls, valor: SecretStr | None) -> SecretStr | None:
        if valor is not None:
            cls._decodificar_clave_hmac(valor)
        return valor

    @field_validator(
        "auth_argon2_memoria_kib", "auth_argon2_iteraciones", "auth_argon2_paralelismo",
        mode="before",
    )
    @classmethod
    def rechazar_booleanos_argon2(cls, valor: object) -> object:
        if isinstance(valor, bool):
            raise ValueError("Los parámetros Argon2 deben ser enteros positivos.")
        return valor

    @field_validator(
        "auth_csrf_token_bytes", "auth_csrf_token_segundos",
        "auth_csrf_contexto_segundos", "auth_csrf_max_tokens", mode="before",
    )
    @classmethod
    def rechazar_booleanos_csrf(cls, valor: object) -> object:
        if isinstance(valor, bool):
            raise ValueError("Los parámetros CSRF deben ser enteros positivos.")
        return valor

    @field_validator("auth_origenes_permitidos")
    @classmethod
    def validar_origenes_auth(cls, valores: list[str]) -> list[str]:
        from app.seguridad.origenes import validar_origenes_configurados
        return validar_origenes_configurados(valores)

    @field_validator("auth_proxies_autorizados")
    @classmethod
    def validar_proxies_auth(cls, valores: list[str]) -> list[str]:
        from app.seguridad.proxies import redes_autorizadas
        redes_autorizadas(valores)
        return valores

    @field_validator(
        "auth_limite_cuenta_intentos", "auth_limite_cuenta_ventana_segundos",
        "auth_limite_cuenta_bloqueo_segundos", "auth_limite_ip_intentos",
        "auth_limite_ip_ventana_segundos", "auth_limite_ip_bloqueo_segundos",
        "auth_limite_reintentos_version", mode="before",
    )
    @classmethod
    def rechazar_booleanos_limites(cls, valor: object) -> object:
        if isinstance(valor, bool):
            raise ValueError("Los parámetros del limitador deben ser enteros.")
        return valor

    @staticmethod
    def _decodificar_clave_hmac(valor: SecretStr) -> bytes:
        try:
            texto = valor.get_secret_value()
            clave = base64.b64decode(texto, validate=True)
            if (
                len(clave) < 32
                or len(set(clave)) < 2
                or base64.b64encode(clave).decode("ascii") != texto
            ):
                raise ValueError
        except (ValueError, binascii.Error):
            raise ValueError(
                "La clave HMAC debe ser base64 canónico de al menos 32 bytes aleatorios."
            ) from None
        return clave

    @model_validator(mode="after")
    def validar_seguridad(self) -> "Configuracion":
        if self.auth_argon2_memoria_kib < 8 * self.auth_argon2_paralelismo:
            raise ValueError("La memoria Argon2 debe ser al menos ocho veces el paralelismo.")
        if (self.auth_hmac_clave is None) != (self.auth_hmac_id_clave is None):
            raise ValueError("Configura conjuntamente la clave HMAC y su identificador.")
        return self

    def obtener_clave_hmac(self) -> bytes:
        """Falla antes de construir servicios HMAC; salud no necesita este secreto."""
        if self.auth_hmac_clave is None:
            raise ValueError("Falta configurar la clave HMAC del servidor.")
        return self._decodificar_clave_hmac(self.auth_hmac_clave)

    @property
    def tiene_configuracion_bd(self) -> bool:
        return bool(
            self.postgres_db
            and self.postgres_user
            and self.postgres_password
            and self.postgres_password.get_secret_value()
        )
