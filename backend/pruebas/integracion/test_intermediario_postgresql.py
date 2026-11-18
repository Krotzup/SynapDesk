"""Integración interna: la evidencia IP pertenece al fixture, nunca al cliente.

Las rutas de ensayo solo se registran aquí. No acreditan Next.js ni Render.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.aplicacion import crear_aplicacion
from app.api.dependencias_auth import IntermediarioHttp
from app.persistencia.conexion import construir_url_bd
from app.persistencia.modelos import ContextoCsrf, CuotaBootstrapCsrf, LimiteAutenticacion, TokenCsrf
from app.seguridad.bootstrap_csrf import CuotaBootstrapAgotada, ServicioBootstrapCsrf
from app.seguridad.csrf import ServicioCsrf
from app.seguridad.intermediario import ServicioIntermediario
from app.seguridad.transacciones import ErrorSeguridad
from pruebas.intermediario_auxiliar import ORIGEN, cabeceras, credencial, politica
# Reutiliza el fixture de commits reales que exige base temporal exclusiva en 5433.
from pruebas.integracion.test_bootstrap_csrf import entorno_bootstrap, cantidad, filas, servicio


def preparar(e):
    token = credencial()
    config = e["config"].model_copy(deep=True)
    from app.seguridad.intermediario import PoliticaIntermediario
    config.auth_intermediario = PoliticaIntermediario(**politica([token]))
    config.auth_origenes_permitidos = [ORIGEN]
    return token, config


def estado(e):
    return tuple(cantidad(e, modelo) for modelo in (
        CuotaBootstrapCsrf, ContextoCsrf, TokenCsrf, LimiteAutenticacion))


@pytest.mark.parametrize("caso", ["ausente", "incorrecta", "duplicada", "http"])
def test_rechazo_de_servicio_no_llega_a_cuotas_ni_a_emision(entorno_bootstrap, caso):
    e = entorno_bootstrap
    token, config = preparar(e)
    app = crear_aplicacion(config)

    @app.get("/ensayo-interno")
    def ensayo(identidad: IntermediarioHttp):
        servicio(e).emitir(ip=e["ip"])
        return {}

    headers = list(cabeceras(token).items())
    if caso == "ausente":
        headers = []
    elif caso == "incorrecta":
        headers = list(cabeceras(credencial()).items())
    elif caso == "duplicada":
        headers.append(("Authorization", cabeceras(token)["Authorization"]))
    with TestClient(app, base_url="http://testserver" if caso == "http" else "https://testserver") as cliente:
        assert cliente.get("/ensayo-interno", headers=headers).status_code == 503
    assert estado(e) == (0, 0, 0, 0)


def test_servicio_valido_sin_ip_acreditada_no_toca_postgresql(entorno_bootstrap):
    e = entorno_bootstrap
    token, config = preparar(e)
    with TestClient(crear_aplicacion(config), base_url="https://testserver") as cliente:
        for headers in (cabeceras(token), cabeceras(token) | {"X-SynapDesk-Client-IP": "198.51.100.99"}):
            assert cliente.get("/api/v1/auth/csrf", headers=headers).status_code == 503
    assert estado(e) == (0, 0, 0, 0)


def test_servicio_e_ip_controlada_reutilizan_cuotas_y_csrf_sin_endpoint_real(entorno_bootstrap):
    e = entorno_bootstrap
    token, config = preparar(e)
    app = crear_aplicacion(config)
    resultados = []

    @app.get("/ensayo-interno")
    def ensayo(identidad: IntermediarioHttp):
        resultados.append(servicio(e).emitir(ip=e["ip"]))
        return {"confirmado": True}

    with TestClient(app, base_url="https://testserver") as cliente:
        assert cliente.get("/ensayo-interno", headers=cabeceras(token)).status_code == 200
        assert cliente.get("/api/v1/auth/csrf", headers=cabeceras(token)).status_code == 503
    assert estado(e) == (5, 1, 1, 0)
    resultado = resultados[0]
    with Session(e["motor"]) as db, db.begin():
        ServicioCsrf(db, e["config"], e["reloj"]).validar_token(
            resultado.token.token, anonimo=resultado.contexto_nuevo.secreto)


def test_concurrencia_autenticada_no_cambia_atomicidad_de_bootstrap(entorno_bootstrap):
    e = entorno_bootstrap
    token, config = preparar(e)
    verificador = ServicioIntermediario(config)
    bootstrap = servicio(e, intentos_global=dict(cantidad=3, segundos=60))

    def intentar(n):
        try:
            verificador.verificar([cabeceras(token if n < 8 else credencial())["Authorization"]],
                                  esquema="https", cabeceras_reenviadas=False)
            bootstrap.emitir(ip=e["ip"])
            return "emitido"
        except CuotaBootstrapAgotada:
            return "cuota"
        except ErrorSeguridad:
            return "servicio"

    with ThreadPoolExecutor(max_workers=8) as grupo:
        resultados = list(grupo.map(intentar, range(10)))
    assert resultados.count("emitido") == 3
    assert resultados.count("cuota") == 5 and resultados.count("servicio") == 2
    assert filas(e, "intentos_global")[0].usados == 3
    assert cantidad(e, TokenCsrf) == 3 and cantidad(e, LimiteAutenticacion) == 0


def test_servicio_valido_no_oculta_un_fallo_real_postgresql(entorno_bootstrap, configuracion_bd_test):
    e = entorno_bootstrap
    token, config = preparar(e)
    # Base inexistente exclusiva de ensayo, en el mismo servidor 5433 verificado.
    url = construir_url_bd(configuracion_bd_test).set(database=configuracion_bd_test.postgres_db + "_ausente")
    motor = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 2})
    app = crear_aplicacion(config)

    @app.get("/ensayo-interno")
    def ensayo(identidad: IntermediarioHttp):
        ServicioBootstrapCsrf(motor, config, e["reloj"]).emitir(ip=e["ip"])
        return {}

    try:
        with TestClient(app, base_url="https://testserver") as cliente:
            respuesta = cliente.get("/ensayo-interno", headers=cabeceras(token))
        assert respuesta.status_code == 503
        assert respuesta.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "_ausente" not in respuesta.text and token.get_secret_value() not in respuesta.text
        assert estado(e) == (0, 0, 0, 0)
    finally:
        motor.dispose()
