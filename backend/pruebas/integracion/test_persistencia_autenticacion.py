from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.persistencia.modelos import (
    ContextoCsrf,
    EventoAutenticacion,
    LimiteAutenticacion,
    Sesion,
    TokenCsrf,
    Usuario,
)


def digest(valor: str) -> bytes:
    return sha256(valor.encode("utf-8")).digest()


def crear_usuario(sesion) -> Usuario:
    usuario = Usuario(
        nombre="Agente de autenticación",
        correo=f"auth-{uuid4()}@example.invalid",
        hash_contrasena="hash_ficticio_no_utilizable_para_autenticacion",
    )
    sesion.add(usuario)
    sesion.flush()
    return usuario


def crear_sesion(sesion, usuario: Usuario, *, sufijo: str = "principal") -> Sesion:
    ahora = datetime.now(UTC).replace(microsecond=0)
    registro = Sesion(
        usuario_id=usuario.id,
        digest_credencial=digest(f"session-{sufijo}-{uuid4()}"),
        creado_en=ahora,
        ultima_actividad=ahora,
        expira_en=ahora + timedelta(hours=8),
    )
    sesion.add(registro)
    sesion.flush()
    return registro


def test_persistir_sesion_contextos_tokens_y_relaciones(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    sesion = crear_sesion(sesion_bd_test, usuario)
    ahora = sesion.creado_en

    contexto_anonimo = ContextoCsrf(
        tipo="anonymous",
        digest_secreto=digest("anonymous-context"),
        creado_en=ahora,
        expira_en=ahora + timedelta(minutes=15),
    )
    contexto_autenticado = ContextoCsrf(
        tipo="authenticated",
        sesion=sesion,
        creado_en=ahora,
        expira_en=ahora + timedelta(minutes=15),
    )
    token_actual = TokenCsrf(
        contexto=contexto_autenticado,
        digest_token=digest("csrf-current"),
        emitido_en=ahora,
        expira_en=ahora + timedelta(minutes=10),
    )
    token_renovado = TokenCsrf(
        contexto=contexto_autenticado,
        digest_token=digest("csrf-renewed"),
        emitido_en=ahora + timedelta(minutes=1),
        expira_en=ahora + timedelta(minutes=10),
    )
    sesion_bd_test.add_all([contexto_anonimo, contexto_autenticado, token_actual, token_renovado])
    sesion_bd_test.flush()
    sesion_bd_test.expire_all()

    recuperada = sesion_bd_test.get(Sesion, sesion.id)
    assert recuperada.usuario.id == usuario.id
    assert len(recuperada.digest_credencial) == 32
    assert recuperada.expira_en > recuperada.ultima_actividad
    assert recuperada.revocada_en is None

    contexto_recuperado = sesion_bd_test.get(ContextoCsrf, contexto_autenticado.id)
    assert contexto_recuperado.sesion.id == sesion.id
    assert len(contexto_recuperado.tokens) == 2
    assert sesion_bd_test.get(ContextoCsrf, contexto_anonimo.id).sesion is None
    assert sesion_bd_test.get(TokenCsrf, token_actual.id).contexto.id == contexto_autenticado.id


def test_digests_unicos_y_no_se_persisten_secretos(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    raw_session = "session-secret-never-stored"
    digest_session = digest(raw_session)
    ahora = datetime.now(UTC).replace(microsecond=0)
    primera = Sesion(
        usuario_id=usuario.id,
        digest_credencial=digest_session,
        creado_en=ahora,
        ultima_actividad=ahora,
        expira_en=ahora + timedelta(hours=8),
    )
    sesion_bd_test.add(primera)
    sesion_bd_test.flush()

    assert primera.digest_credencial == digest_session
    assert raw_session.encode() not in primera.digest_credencial

    duplicada = Sesion(
        usuario_id=usuario.id,
        digest_credencial=digest_session,
        creado_en=ahora,
        ultima_actividad=ahora,
        expira_en=ahora + timedelta(hours=8),
    )
    sesion_bd_test.add(duplicada)
    with pytest.raises(IntegrityError):
        sesion_bd_test.flush()


def test_revocacion_y_caducidad_se_representan_sin_borrar_sesion(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    sesion = crear_sesion(sesion_bd_test, usuario)
    sesion.revocada_en = sesion.creado_en + timedelta(minutes=2)
    sesion.motivo_revocacion = "logout"
    sesion_bd_test.flush()
    sesion_bd_test.refresh(sesion)

    assert sesion.revocada_en is not None
    assert sesion.motivo_revocacion == "logout"
    assert sesion_bd_test.scalar(select(Sesion.id).where(Sesion.id == sesion.id)) == sesion.id


def test_contexto_rechaza_vinculacion_ambigua(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    sesion = crear_sesion(sesion_bd_test, usuario)
    ahora = datetime.now(UTC).replace(microsecond=0)
    contexto_invalido = ContextoCsrf(
        tipo="anonymous",
        digest_secreto=digest("anonymous"),
        sesion_id=sesion.id,
        creado_en=ahora,
        expira_en=ahora + timedelta(minutes=15),
    )
    sesion_bd_test.add(contexto_invalido)
    with pytest.raises(IntegrityError):
        sesion_bd_test.flush()


def test_token_rechaza_digest_invalido(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    sesion = crear_sesion(sesion_bd_test, usuario, sufijo="token-integrity")
    ahora = datetime.now(UTC).replace(microsecond=0)
    contexto = ContextoCsrf(
        tipo="authenticated",
        sesion=sesion,
        creado_en=ahora,
        expira_en=ahora + timedelta(minutes=15),
    )
    sesion_bd_test.add(contexto)
    sesion_bd_test.flush()
    token = TokenCsrf(
        contexto_id=contexto.id,
        digest_token=b"digest-too-short",
        emitido_en=ahora,
        expira_en=ahora + timedelta(minutes=10),
    )
    sesion_bd_test.add(token)
    with pytest.raises(IntegrityError):
        sesion_bd_test.flush()


def test_limite_persistente_con_contadores_y_clave_de_ventana_unica(sesion_bd_test) -> None:
    ahora = datetime.now(UTC).replace(microsecond=0)
    limite = LimiteAutenticacion(
        tipo_clave="account",
        clave_digest=digest("account@example.invalid"),
        ventana_inicia_en=ahora,
        ventana_termina_en=ahora + timedelta(minutes=5),
        intentos=2,
        reservas=1,
        bloqueado_hasta=ahora + timedelta(minutes=1),
    )
    sesion_bd_test.add(limite)
    sesion_bd_test.flush()
    limite.intentos += 1
    limite.reservas -= 1
    sesion_bd_test.flush()
    sesion_bd_test.refresh(limite)

    assert limite.intentos == 3
    assert limite.reservas == 0
    assert limite.bloqueado_hasta is not None
    assert limite.version == 2

    duplicado = LimiteAutenticacion(
        tipo_clave=limite.tipo_clave,
        clave_digest=limite.clave_digest,
        ventana_inicia_en=limite.ventana_inicia_en,
        ventana_termina_en=limite.ventana_termina_en,
    )
    sesion_bd_test.add(duplicado)
    with pytest.raises(IntegrityError):
        sesion_bd_test.flush()


def test_evento_de_auditoria_minimo_con_referencias_opcionales(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    sesion = crear_sesion(sesion_bd_test, usuario)
    evento = EventoAutenticacion(
        tipo_evento="login",
        resultado="success",
        usuario_id=usuario.id,
        sesion_id=sesion.id,
        request_id="request-ficticio-1",
        motivo="credentials_validated",
        ip_verificada_digest=digest("192.0.2.10"),
    )
    sesion_bd_test.add(evento)
    sesion_bd_test.flush()
    sesion_bd_test.expire_all()
    recuperado = sesion_bd_test.get(EventoAutenticacion, evento.id)

    assert recuperado.usuario.id == usuario.id
    assert recuperado.sesion.id == sesion.id
    assert recuperado.resultado == "success"
    assert recuperado.request_id == "request-ficticio-1"
    assert recuperado.ip_verificada_digest == digest("192.0.2.10")


def test_rollback_no_deja_sesion_persistida(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    identificador = None
    with pytest.raises(RuntimeError, match="rollback solicitado"):
        with sesion_bd_test.begin_nested():
            registro = crear_sesion(sesion_bd_test, usuario, sufijo="rollback")
            identificador = registro.id
            raise RuntimeError("rollback solicitado")

    assert identificador is not None
    assert sesion_bd_test.get(Sesion, identificador) is None
