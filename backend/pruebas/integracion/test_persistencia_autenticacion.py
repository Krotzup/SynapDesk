from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.persistencia.conexion import crear_motor_bd

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


# Clave pública ficticia: exclusiva de pruebas, nunca utilizable en producción.
CLAVE_HMAC_PRUEBAS = b"synapdesk-only-tests-not-a-production-key"


def identificador_hmac(tipo: str, valor_normalizado: str) -> bytes:
    mensaje = f"{tipo}:{valor_normalizado}".encode("utf-8")
    return hmac.digest(CLAVE_HMAC_PRUEBAS, mensaje, "sha256")


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


def test_sesion_persiste_digest_y_rechaza_duplicados(sesion_bd_test) -> None:
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
        clave_digest=identificador_hmac("account", "account@example.invalid"),
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
    assert limite.clave_digest == identificador_hmac("account", "account@example.invalid")

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
        ip_verificada_digest=identificador_hmac("ip", "192.0.2.10"),
    )
    sesion_bd_test.add(evento)
    sesion_bd_test.flush()
    sesion_bd_test.expire_all()
    recuperado = sesion_bd_test.get(EventoAutenticacion, evento.id)

    assert recuperado.usuario.id == usuario.id
    assert recuperado.sesion.id == sesion.id
    assert recuperado.resultado == "success"
    assert recuperado.request_id == "request-ficticio-1"
    assert recuperado.ip_verificada_digest == identificador_hmac("ip", "192.0.2.10")


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


def comprobar_rechazo(sesion, restriccion: str | tuple[str, ...], sqlstate: str = "23514") -> None:
    with pytest.raises(IntegrityError) as error:
        sesion.flush()
    assert error.value.orig.sqlstate == sqlstate
    admitidas = (restriccion,) if isinstance(restriccion, str) else restriccion
    assert error.value.orig.diag.constraint_name in admitidas


@pytest.mark.parametrize(
    ("campo", "desplazamiento", "restriccion"),
    [
        ("expira_en", timedelta(0), "fechas_vigencia_validas"),
        # Una expiración anterior a creación infringe ambas restricciones.
        ("expira_en", timedelta(seconds=-1), ("fechas_vigencia_validas", "actividad_no_supera_expiracion")),
        ("ultima_actividad", timedelta(seconds=-1), "fechas_vigencia_validas"),
        ("ultima_actividad", timedelta(hours=8, seconds=1), "actividad_no_supera_expiracion"),
        ("revocada_en", timedelta(seconds=-1), "revocacion_no_anterior"),
    ],
)
def test_sesion_rechaza_fechas_incoherentes(
    sesion_bd_test, campo, desplazamiento, restriccion
) -> None:
    registro = crear_sesion(sesion_bd_test, crear_usuario(sesion_bd_test))
    setattr(registro, campo, registro.creado_en + desplazamiento)
    nombres = (restriccion,) if isinstance(restriccion, str) else restriccion
    comprobar_rechazo(sesion_bd_test, tuple(f"ck_sesiones_{nombre}" for nombre in nombres))


def test_sesion_admite_actividad_y_revocacion_en_limites(sesion_bd_test) -> None:
    registro = crear_sesion(sesion_bd_test, crear_usuario(sesion_bd_test))
    registro.ultima_actividad = registro.expira_en
    registro.revocada_en = registro.creado_en
    sesion_bd_test.flush()
    sesion_bd_test.refresh(registro)
    # Representación válida en BD, no autorización de una sesión caducada/revocada.
    assert registro.ultima_actividad == registro.expira_en
    assert registro.revocada_en == registro.creado_en


def crear_contexto(sesion, registro: Sesion | None = None) -> ContextoCsrf:
    ahora = datetime.now(UTC).replace(microsecond=0)
    contexto = ContextoCsrf(
        tipo="authenticated" if registro else "anonymous",
        sesion_id=registro.id if registro else None,
        digest_secreto=None if registro else digest(f"context-{uuid4()}"),
        creado_en=ahora,
        expira_en=ahora + timedelta(minutes=15),
    )
    sesion.add(contexto)
    sesion.flush()
    return contexto


@pytest.mark.parametrize(
    ("campo", "valor", "restriccion"),
    [
        ("tipo", "authenticated", "vinculacion_tipo_consistente"),
        ("tipo", "invalid", "tipo_valido"),
        ("expira_en", timedelta(0), "fechas_vigencia_validas"),
        ("expira_en", timedelta(seconds=-1), "fechas_vigencia_validas"),
        ("revocado_en", timedelta(seconds=-1), "revocacion_no_anterior"),
    ],
)
def test_contexto_rechaza_tipo_vinculacion_y_fechas(
    sesion_bd_test, campo, valor, restriccion
) -> None:
    contexto = crear_contexto(sesion_bd_test)
    if isinstance(valor, timedelta):
        valor = contexto.creado_en + valor
    # El caso autenticado carece tanto de sesión como de secreto anónimo.
    if valor == "authenticated":
        contexto.digest_secreto = None
    setattr(contexto, campo, valor)
    comprobar_rechazo(sesion_bd_test, f"ck_contextos_csrf_{restriccion}")


def test_un_solo_contexto_autenticado_por_sesion(sesion_bd_test) -> None:
    registro = crear_sesion(sesion_bd_test, crear_usuario(sesion_bd_test))
    crear_contexto(sesion_bd_test, registro)
    ahora = registro.creado_en
    sesion_bd_test.add(ContextoCsrf(
        tipo="authenticated", sesion_id=registro.id, creado_en=ahora,
        expira_en=ahora + timedelta(minutes=15),
    ))
    comprobar_rechazo(sesion_bd_test, "uq_contextos_csrf_sesion_id", "23505")


@pytest.mark.parametrize(
    ("campo", "desplazamiento", "restriccion"),
    [
        ("expira_en", timedelta(0), "fechas_vigencia_validas"),
        ("expira_en", timedelta(seconds=-1), "fechas_vigencia_validas"),
        ("invalidado_en", timedelta(seconds=-1), "invalidacion_no_anterior"),
    ],
)
def test_token_rechaza_fechas_incoherentes(
    sesion_bd_test, campo, desplazamiento, restriccion
) -> None:
    contexto = crear_contexto(sesion_bd_test)
    ahora = contexto.creado_en
    token = TokenCsrf(
        contexto_id=contexto.id, digest_token=digest(f"token-{uuid4()}"),
        emitido_en=ahora, expira_en=ahora + timedelta(minutes=10),
    )
    setattr(token, campo, ahora + desplazamiento)
    sesion_bd_test.add(token)
    comprobar_rechazo(sesion_bd_test, f"ck_tokens_csrf_{restriccion}")


@pytest.mark.parametrize("longitud", [0, 31, 33])
def test_token_exige_digest_de_32_bytes(sesion_bd_test, longitud) -> None:
    contexto = crear_contexto(sesion_bd_test)
    sesion_bd_test.add(TokenCsrf(
        contexto_id=contexto.id, digest_token=b"x" * longitud,
        emitido_en=contexto.creado_en, expira_en=contexto.expira_en,
    ))
    comprobar_rechazo(sesion_bd_test, "ck_tokens_csrf_digest_token_longitud")


def test_digest_token_unico_incluso_entre_contextos(sesion_bd_test) -> None:
    primero = crear_contexto(sesion_bd_test)
    segundo = crear_contexto(sesion_bd_test)
    token_digest = digest("random-test-token")
    for contexto in (primero, segundo):
        sesion_bd_test.add(TokenCsrf(
            contexto_id=contexto.id, digest_token=token_digest,
            emitido_en=contexto.creado_en, expira_en=contexto.expira_en,
        ))
        if contexto is primero:
            sesion_bd_test.flush()
    comprobar_rechazo(sesion_bd_test, "uq_tokens_csrf_digest_token", "23505")


def test_token_rechaza_contexto_inexistente(sesion_bd_test) -> None:
    ahora = datetime.now(UTC)
    sesion_bd_test.add(TokenCsrf(
        contexto_id=uuid4(), digest_token=digest("orphan-token"),
        emitido_en=ahora, expira_en=ahora + timedelta(minutes=10),
    ))
    comprobar_rechazo(sesion_bd_test, "fk_tokens_csrf_contexto_id_contextos_csrf", "23503")


def datos_limite() -> dict:
    ahora = datetime.now(UTC).replace(microsecond=0)
    return dict(
        tipo_clave="account",
        clave_digest=identificador_hmac("account", f"{uuid4()}@example.invalid"),
        ventana_inicia_en=ahora, ventana_termina_en=ahora + timedelta(minutes=5),
    )


@pytest.mark.parametrize(
    ("campo", "valor", "restriccion"),
    [
        ("intentos", -1, "intentos_no_negativos"),
        ("reservas", -1, "reservas_no_negativas"),
        ("ventana_termina_en", timedelta(0), "ventana_valida"),
        ("ventana_termina_en", timedelta(seconds=-1), "ventana_valida"),
        ("bloqueado_hasta", timedelta(seconds=-1), "bloqueo_no_anterior"),
    ],
)
def test_limite_rechaza_contadores_y_ventanas_invalidos(
    sesion_bd_test, campo, valor, restriccion
) -> None:
    datos = datos_limite()
    datos[campo] = datos["ventana_inicia_en"] + valor if isinstance(valor, timedelta) else valor
    sesion_bd_test.add(LimiteAutenticacion(**datos))
    comprobar_rechazo(sesion_bd_test, f"ck_limites_autenticacion_{restriccion}")


def test_conflicto_version_entre_conexiones_y_sesiones_independientes(
    configuracion_bd_test,
) -> None:
    """Ambas sesiones leen v1; el segundo commit no puede perder el primero."""
    motor = crear_motor_bd(configuracion_bd_test)
    identificador = None
    try:
        with Session(motor) as inicial:
            limite = LimiteAutenticacion(**datos_limite())
            inicial.add(limite)
            inicial.flush()
            identificador = limite.id
            inicial.commit()
        with Session(motor) as primera, Session(motor) as segunda:
            uno = primera.get(LimiteAutenticacion, identificador)
            dos = segunda.get(LimiteAutenticacion, identificador)
            assert primera.connection() is not segunda.connection()
            assert uno.version == dos.version == 1
            uno.intentos = 1
            primera.commit()
            dos.intentos = 2
            with pytest.raises(StaleDataError):
                segunda.commit()
            segunda.rollback()
        with Session(motor) as verificacion:
            persistido = verificacion.get(LimiteAutenticacion, identificador)
            assert persistido.intentos == 1
            assert persistido.version == 2
    finally:
        if identificador is not None:
            with motor.begin() as conexion:
                conexion.execute(delete(LimiteAutenticacion).where(
                    LimiteAutenticacion.id == identificador
                ))
        motor.dispose()


def test_fk_restrict_usuario_con_sesion(sesion_bd_test) -> None:
    usuario = crear_usuario(sesion_bd_test)
    crear_sesion(sesion_bd_test, usuario)
    # DELETE Core evita que el ORM intente primero desvincular la relación.
    with pytest.raises(IntegrityError) as error:
        sesion_bd_test.execute(delete(Usuario).where(Usuario.id == usuario.id))
    assert error.value.orig.sqlstate == "23503"
    assert error.value.orig.diag.constraint_name == "fk_sesiones_usuario_id_usuarios"


@pytest.mark.parametrize("entidad", ["sesion", "usuario"])
def test_auditoria_sobrevive_borrado_con_set_null(sesion_bd_test, entidad) -> None:
    usuario = crear_usuario(sesion_bd_test)
    registro = crear_sesion(sesion_bd_test, usuario) if entidad == "sesion" else None
    evento = EventoAutenticacion(
        tipo_evento="logout" if registro else "login",
        resultado="success", usuario_id=usuario.id,
        sesion_id=registro.id if registro else None,
    )
    sesion_bd_test.add(evento)
    sesion_bd_test.flush()
    modelo, identificador = (Sesion, registro.id) if registro else (Usuario, usuario.id)
    sesion_bd_test.execute(delete(modelo).where(modelo.id == identificador))
    sesion_bd_test.expire_all()
    recuperado = sesion_bd_test.get(EventoAutenticacion, evento.id)
    assert recuperado is not None
    assert recuperado.resultado == "success"
    assert recuperado.sesion_id is None
    assert recuperado.usuario_id == (usuario.id if registro else None)
