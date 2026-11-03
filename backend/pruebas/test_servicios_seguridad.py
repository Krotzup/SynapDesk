import base64
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.persistencia.modelos import Sesion, Usuario
from app.seguridad.secretos import digest_secreto, generar_secreto
from app.seguridad.sesiones import ServicioSesiones
from app.seguridad.transacciones import (
    CodigoSeguridad as C, ErrorSeguridad, instante, transaccion_seguridad,
)


def test_secretos_unicos_opacos_sin_filtracion(caplog):
    uno, dos = generar_secreto(), generar_secreto()
    assert uno != dos
    bruto = base64.urlsafe_b64decode(uno.get_secret_value() + "=")
    assert len(bruto) == 32
    assert len(digest_secreto(uno, C.TOKEN_INVALIDO)) == 32
    assert digest_secreto(uno, C.TOKEN_INVALIDO) != digest_secreto(dos, C.TOKEN_INVALIDO)
    assert uno.get_secret_value() not in repr(uno)
    assert not caplog.records


@pytest.mark.parametrize("entrada", [None, 42, "", "secreto", "\ud800", "a b", "a" * 43 + "=", "+" * 43])
def test_secretos_malformados_se_rechazan_sin_exponer_entrada(entrada):
    with pytest.raises(ErrorSeguridad) as error:
        digest_secreto(entrada, C.TOKEN_INVALIDO)
    assert error.value.codigo == C.TOKEN_INVALIDO
    assert str(error.value) == "Operación de seguridad rechazada: TOKEN_INVALIDO."


@pytest.mark.parametrize("segundos,vence", [(1799, False), (1800, True), (1801, True)])
def test_limite_unitario_inactividad(segundos, vence):
    inicio = datetime(2026, 11, 3, tzinfo=UTC)
    registro = Sesion(creado_en=inicio, ultima_actividad=inicio, expira_en=inicio + timedelta(hours=8))
    usuario = Usuario(activo=True, rol="agent")
    if vence:
        with pytest.raises(ErrorSeguridad) as error:
            ServicioSesiones._validar(registro, usuario, inicio + timedelta(seconds=segundos))
        assert error.value.codigo == C.SESION_VENCIDA
    else:
        ServicioSesiones._validar(registro, usuario, inicio + timedelta(seconds=segundos))


@pytest.mark.parametrize("campo,valor", [
    ("auth_csrf_token_bytes", 31), ("auth_csrf_token_segundos", 0),
    ("auth_csrf_contexto_segundos", -1), ("auth_csrf_max_tokens", 0),
    ("auth_csrf_max_tokens", True),
])
def test_configuracion_csrf_invalida(campo, valor):
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None, **{campo: valor})


def test_configuracion_csrf_provisional_ajustable():
    configuracion = Configuracion(_env_file=None)
    assert (configuracion.auth_csrf_token_bytes, configuracion.auth_csrf_token_segundos,
            configuracion.auth_csrf_contexto_segundos, configuracion.auth_csrf_max_tokens) == (32, 600, 900, 8)
    otra = Configuracion(_env_file=None, auth_csrf_token_bytes=64, auth_csrf_token_segundos=30,
                        auth_csrf_contexto_segundos=60, auth_csrf_max_tokens=2)
    assert otra.auth_csrf_max_tokens == 2


def test_reloj_sin_zona_no_se_acepta():
    with Session() as db, pytest.raises(ErrorSeguridad) as error:
        instante(db, lambda _: datetime(2026, 11, 3))
    assert error.value.codigo == C.INFRAESTRUCTURA


@pytest.mark.parametrize("tipo,codigo", [(OperationalError, C.INFRAESTRUCTURA), (IntegrityError, C.TRANSACCION)])
def test_excepciones_sql_saneadas_y_rollback(tipo, codigo, caplog):
    with Session() as db:
        with pytest.raises(ErrorSeguridad) as error:
            with transaccion_seguridad(db):
                raise tipo("SQL secreto", {"secreto": "credencial privada"}, Exception("driver privado"))
        assert not db.in_transaction()
    assert error.value.codigo == codigo
    assert "privad" not in str(error.value)
    assert "SQL secreto" not in str(error.value)
    assert not caplog.records


def test_operaciones_exigen_transaccion_y_no_anidan_autobegin():
    with Session() as db:
        with pytest.raises(ErrorSeguridad) as error:
            ServicioSesiones(db).consultar(generar_secreto())
        assert error.value.codigo == C.TRANSACCION
        with db.begin():
            with pytest.raises(ErrorSeguridad) as error:
                with transaccion_seguridad(db):
                    pass
            assert error.value.codigo == C.TRANSACCION
