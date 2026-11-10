"""Perfiles explícitos PROPOSED. Sin nombres ni tiempos por defecto."""

from dataclasses import dataclass
from datetime import datetime
from math import floor
import re
from typing import Literal

from fastapi import Request, Response
from pydantic import SecretStr

from app.configuracion import Configuracion
from app.seguridad.origenes import ErrorConfiguracionSeguridad, ServicioOrigen, origen_canonico
from app.seguridad.secretos import digest_secreto
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad


@dataclass(frozen=True)
class PerfilCookies:
    entorno: str
    origen_publico: str
    nombre_sesion: str
    nombre_contexto: str

    def __post_init__(self) -> None:
        try:
            esquema, host, _ = origen_canonico(self.origen_publico)
        except ValueError:
            raise ErrorConfiguracionSeguridad("El perfil de cookies no es válido.") from None
        if self.entorno not in {"development", "testing", "staging", "production"}:
            raise ErrorConfiguracionSeguridad("El entorno de cookies no es válido.")
        if esquema != "https" and (self.entorno not in {"development", "testing"}
                                    or host not in {"localhost", "127.0.0.1", "::1"}):
            raise ErrorConfiguracionSeguridad("Las cookies requieren HTTPS fuera del perfil local.")
        if self.nombre_sesion == self.nombre_contexto:
            raise ErrorConfiguracionSeguridad("Los nombres de cookies deben ser distintos.")
        for nombre in (self.nombre_sesion, self.nombre_contexto):
            if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,127}", nombre)
                    or (nombre.startswith(("__Host-", "__Secure-")) and esquema != "https")):
                raise ErrorConfiguracionSeguridad("El nombre de cookie no es válido para el perfil.")

    @property
    def secure(self) -> bool:
        return origen_canonico(self.origen_publico)[0] == "https"


def preparar_perfil(configuracion: Configuracion, *, origen_publico: str,
                    nombre_sesion: str, nombre_contexto: str) -> PerfilCookies:
    try:
        ServicioOrigen(configuracion).validar([origen_publico])
    except ErrorSeguridad:
        raise ErrorConfiguracionSeguridad("El perfil requiere un origen público permitido.") from None
    return PerfilCookies(configuracion.app_env, origen_publico, nombre_sesion, nombre_contexto)


def _nombre(perfil: PerfilCookies, tipo: Literal["sesion", "contexto"]) -> str:
    if tipo not in {"sesion", "contexto"}:
        raise ErrorConfiguracionSeguridad("El tipo de cookie no es válido.")
    return perfil.nombre_sesion if tipo == "sesion" else perfil.nombre_contexto


def _sin_cookie_previa(response: Response, nombre: str) -> None:
    for valor in response.headers.getlist("set-cookie"):
        if valor.split("=", 1)[0].strip() == nombre:
            raise ErrorConfiguracionSeguridad("La respuesta ya contiene esa cookie.")


def emitir_cookie(response: Response, perfil: PerfilCookies, tipo: Literal["sesion", "contexto"],
                  secreto: SecretStr, *, ahora: datetime, vence_en: datetime) -> None:
    """Invocar solo después del commit. La vigencia procede del resultado confirmado."""
    nombre = _nombre(perfil, tipo)
    _sin_cookie_previa(response, nombre)
    if (ahora.tzinfo is None or ahora.utcoffset() is None or vence_en.tzinfo is None
            or vence_en.utcoffset() is None or vence_en <= ahora):
        raise ErrorConfiguracionSeguridad("La vigencia de cookie no es válida.")
    segundos = floor((vence_en - ahora).total_seconds())
    if segundos <= 0 or not isinstance(secreto, SecretStr):
        raise ErrorConfiguracionSeguridad("La credencial de cookie no es válida.")
    try:
        digest_secreto(secreto, CodigoSeguridad.SESION_INEXISTENTE)
    except ErrorSeguridad:
        raise ErrorConfiguracionSeguridad("La credencial de cookie no es válida.") from None
    response.set_cookie(nombre, secreto.get_secret_value(), max_age=segundos,
                        path="/", secure=perfil.secure, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"


def eliminar_cookie(response: Response, perfil: PerfilCookies,
                    tipo: Literal["sesion", "contexto"]) -> None:
    nombre = _nombre(perfil, tipo)
    _sin_cookie_previa(response, nombre)
    response.delete_cookie(nombre, path="/", secure=perfil.secure, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"


class CookieAmbigua(ValueError):
    """Rechazo de representación; su catálogo HTTP queda pendiente de AUTH-07B."""


def leer_cookie(request: Request, perfil: PerfilCookies,
                tipo: Literal["sesion", "contexto"]) -> SecretStr | None:
    nombre = _nombre(perfil, tipo)
    encontrados = []
    # Request.cookies elige silenciosamente entre duplicados: leer originales.
    for cabecera in request.headers.getlist("cookie"):
        for parte in cabecera.split(";"):
            clave, separador, valor = parte.strip().partition("=")
            if clave.strip() == nombre:
                if clave != nombre or not separador or not re.fullmatch(r"[A-Za-z0-9_-]+", valor):
                    raise CookieAmbigua("La cookie de autenticación no es inequívoca.")
                encontrados.append(valor)
    if len(encontrados) > 1:
        raise CookieAmbigua("La cookie de autenticación no es inequívoca.")
    return SecretStr(encontrados[0]) if encontrados else None
