"""Credenciales efímeras y evidencia controlada, exclusivamente para pruebas."""

import secrets
from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from app.configuracion import Configuracion
from app.seguridad.intermediario import digest_credencial_servicio

ORIGEN = "http://localhost:3000"


def credencial():
    return SecretStr(secrets.token_urlsafe(32))


def politica(tokens, *, entorno="testing", ahora=None):
    ahora = ahora or datetime.now(UTC)
    return dict(
        habilitado=True, entorno=entorno, transporte="tls_directo", politica_ip="no_acreditada",
        credenciales=[dict(identificador=f"clave_{i}", digest=digest_credencial_servicio(token, entorno),
                           vence_en=ahora + timedelta(hours=1)) for i, token in enumerate(tokens)],
    )


def configuracion(tokens, **cambios):
    return Configuracion(_env_file=None, **(dict(
        app_env="testing", auth_intermediario=politica(tokens),
        auth_origenes_permitidos=[ORIGEN],
    ) | cambios))


def cabeceras(token):
    return {"Authorization": "Bearer " + token.get_secret_value(), "Origin": ORIGEN}
