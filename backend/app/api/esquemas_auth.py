"""DTO HTTP de AUTH-07A; no implementan operaciones de autenticación."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, StrictStr,
    field_serializer, field_validator,
)

from app.seguridad.cuentas import normalizar_cuenta


class EsquemaHttp(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class AuthUser(EsquemaHttp):
    id: UUID
    email: StrictStr = Field(min_length=1)
    role: Literal["admin", "agent"]


class RespuestaUsuario(EsquemaHttp):
    user: AuthUser


class SolicitudLogin(EsquemaHttp):
    email: StrictStr
    password: SecretStr = Field(repr=False)

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        # Sintaxis mínima sin biblioteca ni equivalencias de proveedores nuevas.
        correo = normalizar_cuenta(valor)
        if correo.count("@") != 1 or any(c.isspace() for c in correo):
            raise ValueError("El correo no tiene un formato válido.")
        if not all(correo.split("@")):
            raise ValueError("El correo no tiene un formato válido.")
        return correo

    @field_validator("password", mode="before")
    @classmethod
    def validar_password(cls, valor: object) -> object:
        if not isinstance(valor, str) or not valor:
            raise ValueError("La contraseña debe ser texto no vacío.")
        try:
            valor.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("La contraseña debe ser texto válido.") from None
        return valor


class RespuestaCsrf(EsquemaHttp):
    # Campos propuestos por contrato. Único token destinado a JSON; nunca cookie.
    csrfToken: SecretStr = Field(repr=False)
    expiresAt: AwareDatetime

    @field_validator("csrfToken")
    @classmethod
    def validar_token(cls, valor: SecretStr) -> SecretStr:
        from app.seguridad.secretos import digest_secreto
        from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad
        try:
            digest_secreto(valor, CodigoSeguridad.TOKEN_INVALIDO)
        except ErrorSeguridad:
            raise ValueError("El token CSRF no tiene una representación válida.") from None
        return valor

    @field_validator("expiresAt")
    @classmethod
    def utc(cls, valor: datetime) -> datetime:
        return valor.astimezone(UTC)

    @field_serializer("csrfToken", when_used="json")
    def token_para_respuesta(self, valor: SecretStr) -> str:
        return valor.get_secret_value()


class DetalleValidacion(EsquemaHttp):
    field: str
    message: str


class ApiErrorBody(EsquemaHttp):
    code: str
    message: str
    details: list[DetalleValidacion] | None = None
    requestId: UUID


class RespuestaError(EsquemaHttp):
    error: ApiErrorBody


# Misma envoltura contractual, sin DTO paralelo de errores de autenticación.
ErrorAutenticacion = RespuestaError
