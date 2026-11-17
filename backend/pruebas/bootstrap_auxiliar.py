"""Candidatos explícitos de ensayo; únicamente datos de pruebas."""

import base64
import secrets

from app.configuracion import Configuracion
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.proxies import ServicioIpConfiable


def politica_ensayo(**cambios):
    datos = dict(
        perfil="ensayo",
        contextos_ip=dict(cantidad=60, segundos=900),
        contextos_global=dict(cantidad=1000, segundos=900),
        intentos_ip=dict(cantidad=120, segundos=60),
        intentos_global=dict(cantidad=1500, segundos=60),
        emisiones_contexto=dict(cantidad=12, segundos=60),
        token_segundos=600, contexto_segundos=900, max_tokens=8,
        max_filas_cuota=10000, max_contextos=2000, max_filas_tokens=16000,
        lote_limpieza=100, lock_timeout_ms=1000, statement_timeout_ms=3000,
    )
    datos.update(cambios)
    return datos


def configuracion_ensayo(**cambios):
    return Configuracion(
        _env_file=None, app_env="testing", auth_bootstrap=politica_ensayo(**cambios),
        auth_hmac_clave=base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
        auth_hmac_id_clave="bootstrap-prueba", auth_proxies_autorizados=["192.0.2.8/32"],
    )


def ip_controlada(configuracion, direccion="198.51.100.7"):
    return ServicioIpConfiable(configuracion, ServicioIdentificadores(configuracion)).identificar(
        par_transporte="192.0.2.8", valores_ip_cliente=[direccion])
