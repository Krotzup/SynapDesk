"""Parámetros de ensayo explícitos; no configuran ningún adaptador HTTP."""

from app.configuracion import Configuracion
from pruebas.bootstrap_auxiliar import configuracion_ensayo, ip_controlada


def configuracion_login(**cambios) -> Configuracion:
    base = configuracion_ensayo().model_dump()
    base.update(
        auth_argon2_memoria_kib=1024, auth_argon2_iteraciones=1, auth_argon2_paralelismo=1,
        auth_limite_cuenta_intentos=20, auth_limite_cuenta_ventana_segundos=120,
        auth_limite_cuenta_bloqueo_segundos=20, auth_limite_ip_intentos=30,
        auth_limite_ip_ventana_segundos=120, auth_limite_ip_bloqueo_segundos=20,
    )
    base.update(cambios)
    return Configuracion(_env_file=None, **base)


__all__ = ["configuracion_login", "ip_controlada"]
