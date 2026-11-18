from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.seguridad.operaciones_sesion import (
    ReferenciaSesion, ServicioConsultaSesion, ServicioLogout,
)
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad


@pytest.fixture
def motor():
    # Perezoso y sin conexión: tipos inválidos no deben alcanzar PostgreSQL.
    motor = create_engine("postgresql+psycopg://localhost:5433/no_conectar")
    yield motor
    motor.dispose()


@pytest.mark.parametrize("entrada", [None, True, uuid4(), "cookie", SecretStr(""),
    SecretStr("malformada"), SecretStr("a" * 42 + "="), SecretStr("\ud800")])
def test_referencia_rechaza_identidades_y_representaciones_ambiguas(entrada):
    with pytest.raises(ErrorSeguridad) as error:
        ReferenciaSesion(entrada)
    assert error.value.codigo == C.SESION_INEXISTENTE
    assert str(error.value) == "Operación de seguridad rechazada: SESION_INEXISTENTE."


def test_referencia_es_opaca_inmutable_y_no_es_autorizacion():
    secreto = generar_secreto()
    referencia = ReferenciaSesion(secreto)
    assert secreto.get_secret_value() not in repr(referencia)
    with pytest.raises(FrozenInstanceError):
        referencia.credencial = generar_secreto()


@pytest.mark.parametrize("entrada", [None, True, uuid4(), "cookie", generar_secreto()])
def test_consulta_exige_referencia_interna(motor, entrada):
    with pytest.raises(ErrorSeguridad) as error:
        ServicioConsultaSesion(motor).consultar(entrada)
    assert error.value.codigo == C.SESION_INEXISTENTE


@pytest.mark.parametrize("entrada", [True, uuid4(), "cookie", generar_secreto()])
def test_logout_no_acepta_identidad_cliente(motor, entrada):
    with pytest.raises(ErrorSeguridad):
        ServicioLogout(motor, Configuracion(_env_file=None)).cerrar(entrada)


def test_logout_sin_cookie_no_necesita_bd_ni_csrf(motor):
    assert ServicioLogout(motor, Configuracion(_env_file=None)).cerrar(None).revocada is False


@pytest.mark.parametrize("servicio", [ServicioConsultaSesion, ServicioLogout])
def test_no_degrada_a_persistencia_alternativa(servicio):
    with create_engine("sqlite://").connect() as conexion:
        with pytest.raises(ErrorSeguridad) as error:
            if servicio is ServicioLogout:
                servicio(conexion.engine, Configuracion(_env_file=None))
            else:
                servicio(conexion.engine)
    assert error.value.codigo == C.INFRAESTRUCTURA


def test_rutas_siguen_sin_registrar_y_csrf_cerrado():
    config = Configuracion(_env_file=None, auth_origenes_permitidos=["http://localhost:3000"])
    with TestClient(crear_aplicacion(config)) as cliente:
        for metodo, ruta in (("GET", "me"), ("POST", "logout"), ("POST", "login")):
            assert cliente.request(metodo, "/api/v1/auth/" + ruta).status_code == 404
        respuesta = cliente.get("/api/v1/auth/csrf", headers={"Origin": "http://localhost:3000"})
        assert respuesta.status_code == 503
        assert respuesta.headers["cache-control"] == "no-store"
        assert "set-cookie" not in respuesta.headers
