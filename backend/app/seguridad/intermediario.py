"""Identidad de servicio, independiente de sesiones, IP y cuotas.

El adaptador HTTP debe acreditar TLS directo sin cabeceras de proxy.
Un bearer es reutilizable: este módulo no ofrece protección antirreplay.
"""

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import (
    BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator, model_validator,
)

from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad

if TYPE_CHECKING:
    from app.configuracion import Configuracion

EntornoServicio = Literal["development", "testing", "staging", "production"]


def digest_credencial_servicio(credencial: SecretStr, entorno: EntornoServicio) -> SecretStr:
    """Preparación de configuración; nunca registra ni devuelve el bearer.

    Exigir 32 bytes CSPRNG externos. El formato no demuestra la entropía.
    El dominio/entorno impide reutilizar un digest configurado en otro entorno.
    """
    valor = credencial.get_secret_value()
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", valor, re.ASCII):
        raise ValueError("Formato de credencial de servicio inválido.")
    bruto = base64.urlsafe_b64decode(valor + "=")
    if base64.urlsafe_b64encode(bruto).decode("ascii").rstrip("=") != valor:
        raise ValueError("Formato de credencial de servicio inválido.")
    if entorno not in {"development", "testing", "staging", "production"}:
        raise ValueError("Entorno de servicio inválido.")
    return SecretStr(hashlib.sha256(
        b"synapdesk:intermediario:v1\0" + entorno.encode("ascii") + b"\0" + bruto
    ).hexdigest())


class CredencialServicio(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    identificador: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    digest: SecretStr = Field(repr=False)
    vence_en: datetime

    @field_validator("digest")
    @classmethod
    def validar_digest(cls, valor: SecretStr) -> SecretStr:
        if not re.fullmatch(r"[a-f0-9]{64}", valor.get_secret_value(), re.ASCII):
            raise ValueError("Digest de servicio inválido.")
        return valor

    @field_validator("vence_en")
    @classmethod
    def validar_vencimiento(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("El vencimiento requiere zona horaria.")
        return valor.astimezone(UTC)


class PoliticaIntermediario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    habilitado: StrictBool = False
    entorno: EntornoServicio
    transporte: Literal["tls_directo"]
    politica_ip: Literal["no_acreditada"]
    credenciales: tuple[CredencialServicio, ...] = Field(min_length=1, max_length=2, repr=False)

    @model_validator(mode="after")
    def validar_rotacion(self) -> "PoliticaIntermediario":
        if (len({c.identificador for c in self.credenciales}) != len(self.credenciales)
                or len({c.digest.get_secret_value() for c in self.credenciales}) != len(self.credenciales)):
            raise ValueError("Las credenciales configuradas deben ser distintas.")
        return self


@dataclass(frozen=True)
class IdentidadIntermediario:
    entorno: EntornoServicio
    servicio: Literal["nextjs"] = "nextjs"


class ServicioIntermediario:
    def __init__(self, configuracion: "Configuracion") -> None:
        politica = configuracion.auth_intermediario
        if (politica is None or not politica.habilitado
                or politica.entorno != configuracion.app_env):
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        self._politica = politica

    def verificar(self, valores: list[str], *, esquema: str,
                  cabeceras_reenviadas: bool, ahora: datetime | None = None) -> IdentidadIntermediario:
        """Todas las claves se comparan, incluso vencidas, sin selección del cliente."""
        if esquema != "https" or cabeceras_reenviadas or len(valores) != 1:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        # Una representación estricta; rechaza comas, whitespace, Unicode y listas.
        coincidencia = re.fullmatch(r"Bearer ([A-Za-z0-9_-]{43})", valores[0], re.ASCII)
        if coincidencia is None:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        try:
            recibido = bytes.fromhex(digest_credencial_servicio(
                SecretStr(coincidencia[1]), self._politica.entorno,
            ).get_secret_value())
        except ValueError:
            raise ErrorSeguridad(C.INFRAESTRUCTURA) from None
        observado = ahora if ahora is not None else datetime.now(UTC)
        if observado.tzinfo is None or observado.utcoffset() is None:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        valido = False
        for credencial in self._politica.credenciales:
            coincide = hmac.compare_digest(recibido, bytes.fromhex(credencial.digest.get_secret_value()))
            vigente = observado < credencial.vence_en
            valido |= coincide & vigente
        if not valido:
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        return IdentidadIntermediario(entorno=self._politica.entorno)
