from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.seguridad.auditoria import MotivoEvento as M
from app.seguridad.login import (
    ContextoLoginValidado, CredencialesLogin, LoginConfirmado, LoginRechazado,
    PruebaAnonimaLogin, ServicioLogin,
)
from app.seguridad.secretos import generar_secreto
from app.seguridad.sesiones import Identidad, SesionEmitida
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad
from pruebas.login_auxiliar import configuracion_login, ip_controlada


@pytest.fixture
def motor():
    # Engine perezoso: estas unitarias nunca conectan ni crean una base.
    engine = create_engine("postgresql+psycopg://localhost:5433/no_conectar")
    yield engine
    engine.dispose()


@pytest.mark.parametrize("cuenta", ["  AGENTE@Example.Invalid  ", "agente@example.invalid"])
def test_entrada_normalizada_sin_exponer_contrasena(cuenta):
    secreto = generar_secreto()
    entrada = CredencialesLogin(cuenta, secreto)
    assert entrada.cuenta == "agente@example.invalid"
    assert secreto.get_secret_value() not in repr(entrada)
    assert entrada.cuenta not in repr(entrada)
    with pytest.raises(FrozenInstanceError):
        entrada.cuenta = "otro@example.invalid"


@pytest.mark.parametrize("cuenta,clave", [(None, SecretStr("x")), ("", SecretStr("x")),
    ("a\x00b", SecretStr("x")), ("a", "texto"), ("a", SecretStr("")), ("a", SecretStr("\ud800"))])
def test_entrada_invalida_no_expone_valores(cuenta, clave):
    with pytest.raises(ValueError):
        CredencialesLogin(cuenta, clave)


@pytest.mark.parametrize("capacidad", [0, -1, True, 1.5])
def test_capacidad_explicita_invalida(motor, capacidad):
    with pytest.raises(ErrorSeguridad) as error:
        ServicioLogin(motor, configuracion_login(), capacidad_argon2=capacidad)
    assert error.value.codigo == C.INFRAESTRUCTURA


def test_configuracion_incompleta_no_degrada_controles(motor):
    for config in (Configuracion(_env_file=None),
                   configuracion_login(auth_limite_ip_intentos=None)):
        with pytest.raises(ErrorSeguridad) as error:
            ServicioLogin(motor, config, capacidad_argon2=1)
        assert error.value.codigo == C.INFRAESTRUCTURA


def test_contexto_booleano_uuid_o_de_otro_coordinador_no_autoriza(motor):
    config = configuracion_login()
    servicio = ServicioLogin(motor, config, capacidad_argon2=1)
    entrada = CredencialesLogin("a@example.invalid", generar_secreto())
    falso = ContextoLoginValidado(PruebaAnonimaLogin(generar_secreto(), generar_secreto()),
                                 ip_controlada(config), None, object())
    for contexto in (True, uuid4(), "cabecera", falso):
        with pytest.raises(ErrorSeguridad) as error:
            servicio.autenticar(entrada, contexto)
        assert error.value.codigo == C.CONTEXTO_INVALIDO


def test_resultado_no_serializa_sesion_en_repr_y_rechazo_es_uniforme():
    secreto = generar_secreto()
    resultado = LoginConfirmado(Identidad(uuid4(), "a@example.invalid", "agent"),
        SesionEmitida(uuid4(), datetime(2026, 11, 12, tzinfo=UTC), secreto))
    assert secreto.get_secret_value() not in repr(resultado)
    assert set(resultado.usuario.__dataclass_fields__) == {"id", "email", "role"}
    assert LoginRechazado(M.CREDENCIALES_INVALIDAS).limite is None


def test_no_hay_endpoint_login_y_csrf_sigue_cerrado_sin_bearer_de_usuario():
    config = Configuracion(_env_file=None, auth_origenes_permitidos=["http://localhost:3000"])
    with TestClient(crear_aplicacion(config)) as cliente:
        assert cliente.post("/api/v1/auth/login", json={}).status_code == 404
        respuesta = cliente.get("/api/v1/auth/csrf", headers={"Origin": "http://localhost:3000"})
        assert respuesta.status_code == 503
        assert respuesta.headers["cache-control"] == "no-store"
        assert "set-cookie" not in respuesta.headers
