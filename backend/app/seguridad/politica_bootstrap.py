"""Política explícita de bootstrap; no contiene cuotas predeterminadas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CuotaBootstrap(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    cantidad: int = Field(ge=1, le=1_000_000)
    segundos: int = Field(ge=1, le=86400)


class PoliticaBootstrap(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    perfil: Literal["ensayo", "aprobado"]
    contextos_ip: CuotaBootstrap
    contextos_global: CuotaBootstrap
    intentos_ip: CuotaBootstrap
    intentos_global: CuotaBootstrap
    emisiones_contexto: CuotaBootstrap
    token_segundos: int = Field(ge=1, le=86400)
    contexto_segundos: int = Field(ge=1, le=86400)
    max_tokens: int = Field(ge=1, le=1000)
    max_filas_cuota: int = Field(ge=5, le=1_000_000)
    max_contextos: int = Field(ge=1, le=1_000_000)
    max_filas_tokens: int = Field(ge=1, le=8_000_000)
    lote_limpieza: int = Field(ge=1, le=1000)
    lock_timeout_ms: int = Field(ge=1, le=5000)
    statement_timeout_ms: int = Field(ge=1, le=10000)

    @model_validator(mode="after")
    def validar_coherencia(self) -> "PoliticaBootstrap":
        if self.token_segundos > self.contexto_segundos:
            raise ValueError("El token no puede durar más que el contexto.")
        if self.emisiones_contexto.cantidad < self.max_tokens:
            raise ValueError("La cuota por contexto debe cubrir los tokens simultáneos.")
        if self.lock_timeout_ms >= self.statement_timeout_ms:
            raise ValueError("La espera de bloqueo debe ser menor que la de sentencia.")
        if self.max_filas_tokens < self.max_contextos:
            raise ValueError("La capacidad de tokens debe cubrir la de contextos.")
        return self
