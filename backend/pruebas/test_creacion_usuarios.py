from dataclasses import FrozenInstanceError
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.aplicacion import crear_aplicacion
from app.configuracion import Configuracion
from app.seguridad.auditoria import TipoEvento
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.creacion_usuarios import (
    CodigoCreacionUsuario as C, DatosNuevoUsuario, ErrorCreacionUsuario,
    ServicioCreacionUsuarios, permite_creacion,
)
from app.seguridad.operaciones_sesion import ReferenciaSesion
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad
from herramientas import bootstrap_admin as cli


def datos(**cambios):
    return DatosNuevoUsuario(**(dict(nombre="Persona de ensayo", correo="  NUEVA@EXAMPLE.INVALID  ",
        rol="agent", contrasena=generar_secreto()) | cambios))


@pytest.fixture
def configuracion():
    return Configuracion(_env_file=None, app_env="testing", postgres_host="localhost",
        postgres_port=5433, postgres_db="synapdesk_auth07_sec01a_" + "a" * 32,
        postgres_user="ensayo", postgres_password=generar_secreto(),
        auth_argon2_memoria_kib=1024, auth_argon2_iteraciones=1, auth_argon2_paralelismo=1)


@pytest.fixture
def servicio(configuracion):
    servicio = ServicioCreacionUsuarios(configuracion)
    yield servicio
    servicio.cerrar()


@pytest.mark.parametrize("actor", [None, "agent", "admin", "root"])
@pytest.mark.parametrize("rol", ["admin", "agent", "root"])
def test_matriz_aprobada(actor, rol):
    assert permite_creacion(actor, rol) is (actor == "admin" and rol in {"admin", "agent"})


@pytest.mark.parametrize("cambios", [dict(correo=None), dict(correo=""), dict(correo="a@@b"),
    dict(correo="a b@c"), dict(correo="a\x00@b"), dict(nombre=""), dict(nombre="\ud800"),
    dict(nombre="\x00"), dict(rol="root"), dict(rol=True), dict(rol=[]),
    dict(contrasena="texto"), dict(contrasena=SecretStr("")), dict(contrasena=SecretStr("\ud800"))])
def test_datos_invalidos_sin_entrada_en_error(cambios):
    with pytest.raises(ErrorCreacionUsuario) as error:
        datos(**cambios)
    assert error.value.codigo == C.ENTRADA
    assert str(error.value) == "Creación administrativa rechazada: ENTRADA."


def test_normaliza_hash_fuera_bd_y_no_expone_secretos(servicio):
    entrada = datos()
    preparado = servicio.preparar(entrada)
    assert preparado.correo == "nueva@example.invalid"
    assert preparado.hash_contrasena.get_secret_value().startswith("$argon2id$")
    assert servicio._contrasenas.verificar(preparado.hash_contrasena.get_secret_value(),
                                          entrada.contrasena.get_secret_value())
    assert servicio._motor.pool.checkedout() == 0
    texto = repr(preparado) + repr(entrada)
    assert preparado.hash_contrasena.get_secret_value() not in texto
    assert entrada.contrasena.get_secret_value() not in texto
    assert entrada.correo not in texto
    with pytest.raises(FrozenInstanceError):
        preparado.rol = "admin"


def test_fallo_hash_saneado_y_sin_conexion(servicio, monkeypatch):
    clave = generar_secreto()
    def fallar(self, contrasena):
        assert servicio._motor.pool.checkedout() == 0
        raise ErrorContrasena(clave.get_secret_value())
    monkeypatch.setattr(ServicioContrasenas, "generar_hash", fallar)
    with pytest.raises(ErrorCreacionUsuario) as error:
        servicio.preparar(datos(contrasena=clave))
    assert error.value.codigo == C.HASH
    assert clave.get_secret_value() not in str(error.value)


@pytest.mark.parametrize("referencia", [None, True, uuid4(), "admin", generar_secreto()])
def test_sesion_no_es_identidad_elegida_por_cliente(servicio, referencia):
    with pytest.raises(ErrorSeguridad) as error:
        servicio.ensayar(referencia, servicio.preparar(datos()))
    assert error.value.codigo == CodigoSeguridad.SESION_INEXISTENTE
    assert servicio._motor.pool.checkedout() == 0


@pytest.mark.parametrize("cambio", [dict(app_env="production"), dict(postgres_port=5432),
    dict(postgres_host="example.invalid"), dict(postgres_db="base_desconocida")])
def test_ensayo_no_puede_tocar_otro_destino(configuracion, cambio, monkeypatch):
    servicio = ServicioCreacionUsuarios(configuracion.model_copy(update=cambio))
    try:
        def prohibido(*args, **kwargs):
            pytest.fail("No debe conectar a otro destino.")
        monkeypatch.setattr(servicio._motor, "connect", prohibido)
        with pytest.raises(ErrorCreacionUsuario) as error:
            servicio.ensayar(ReferenciaSesion(generar_secreto()), servicio.preparar(datos()))
        assert error.value.codigo == C.DESTINO_ENSAYO
    finally:
        servicio.cerrar()


def test_preparado_de_otra_instancia_no_se_acepta(servicio, configuracion):
    otro = ServicioCreacionUsuarios(configuracion)
    try:
        with pytest.raises(ErrorCreacionUsuario) as error:
            servicio.ensayar(ReferenciaSesion(generar_secreto()), otro.preparar(datos()))
        assert error.value.codigo == C.ENTRADA
        assert servicio._motor.pool.checkedout() == 0
    finally:
        otro.cerrar()


def test_catalogo_user_created_aprobado():
    assert TipoEvento.USUARIO_CREADO.value == "user_created"


def test_configuracion_ausente_falla_cerrada():
    with pytest.raises(ErrorSeguridad):
        ServicioCreacionUsuarios(Configuracion(_env_file=None))


def test_sin_rutas_http_nuevas_y_csrf_cerrado():
    config = Configuracion(_env_file=None, auth_origenes_permitidos=["http://localhost:3000"])
    with TestClient(crear_aplicacion(config)) as cliente:
        for ruta in ("users", "admin/users", "auth/login", "auth/logout"):
            assert cliente.post("/api/v1/" + ruta).status_code == 404
        assert cliente.get("/api/v1/auth/me").status_code == 404
        assert cliente.get("/api/v1/auth/csrf", headers={"Origin":"http://localhost:3000"}).status_code == 503


@pytest.mark.parametrize("ensayar", [False, True])
def test_prompt_distingue_alta_persistente_de_ensayo(monkeypatch, ensayar):
    from types import SimpleNamespace
    esperado = "destino-controlado"
    class Falso:
        destino = esperado
        def __init__(self, config): pass
        def verificar_destino(self): return SimpleNamespace(confirmacion=esperado)
        def _destino_ensayo(self, valor): pass
        def cerrar(self): pass
    prompts = []
    def cancelar(prompt):
        prompts.append(prompt)
        raise EOFError
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(cli, "ServicioBootstrapAdmin", Falso)
    monkeypatch.setattr(cli, "seleccionar_configuracion_bd", lambda _: object())
    monkeypatch.setattr("builtins.input", cancelar)
    assert cli.main(["--base", "testing" if ensayar else "principal"] + (["--ensayar"] if ensayar else [])) == 2
    assert ("ensayo reversible" in prompts[0]) == ensayar
    assert ("creación del administrador inicial" in prompts[0]) == (not ensayar)


@pytest.fixture
def unidad_alta(servicio, monkeypatch):
    """Aísla decisiones del coordinador; la atomicidad se prueba en PostgreSQL."""
    import app.seguridad.creacion_usuarios as modulo
    e = dict(rol="admin", codigo=None, filas=[], eventos=[], commits=[])
    e["actor_id"], e["sesion_id"] = uuid4(), uuid4()

    def consultar(credencial):
        if e["codigo"]:
            raise ErrorSeguridad(e["codigo"])
        return SimpleNamespace(id=e["sesion_id"], usuario=SimpleNamespace(
            id=e["actor_id"], role=e["rol"]))

    def flush():
        for fila in e["filas"]:
            if fila.id is None:
                fila.id = uuid4()

    db = SimpleNamespace(execute=lambda *a: None, scalar=lambda *a: None,
                         add=e["filas"].append, flush=flush)

    @contextmanager
    def sesion(*args):
        yield db

    @contextmanager
    def transaccion(db):
        yield
        e["commits"].append(True)

    def registrar(**datos_evento):
        e["eventos"].append(datos_evento)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(modulo, "Session", sesion)
    monkeypatch.setattr(modulo, "transaccion_seguridad", transaccion)
    monkeypatch.setattr(modulo, "ServicioSesiones", lambda *a: SimpleNamespace(consultar=consultar))
    monkeypatch.setattr(modulo, "ServicioAuditoria", lambda *a: SimpleNamespace(registrar=registrar))
    e["crear"] = lambda rol: servicio.crear(ReferenciaSesion(generar_secreto()),
                                            servicio.preparar(datos(rol=rol)))
    return e


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_admin_crea_rol_aprobado_y_auditoria_sin_secretos(unidad_alta, rol):
    from app.seguridad.auditoria import ActorUsuario, MotivoEvento, ResultadoEvento
    e = unidad_alta
    resultado = e["crear"](rol)
    assert e["commits"] == [True]
    assert resultado.model_dump() == dict(id=e["filas"][0].id, email="nueva@example.invalid", role=rol)
    evento, = e["eventos"]
    assert evento["tipo"] is TipoEvento.USUARIO_CREADO
    assert evento["actor"] == ActorUsuario(e["actor_id"])
    assert evento["usuario_id"] == resultado.id and evento["sesion_id"] == e["sesion_id"]
    assert evento["rol_asignado"] == rol and evento["resultado"] is ResultadoEvento.EXITO
    assert evento["motivo"] is MotivoEvento.ALTA_ADMINISTRATIVA
    assert e["filas"][0].activo is True
    assert not {"contrasena", "hash_contrasena", "token", "cookie"} & evento.keys()
    assert e["filas"][0].hash_contrasena not in resultado.model_dump_json() + repr(evento)


@pytest.mark.parametrize("rol", ["admin", "agent"])
def test_agent_rechazado_sin_insertar_o_auditar(unidad_alta, rol):
    e = unidad_alta
    e["rol"] = "agent"
    with pytest.raises(ErrorCreacionUsuario) as error:
        e["crear"](rol)
    assert error.value.codigo == C.NO_AUTORIZADO
    assert not e["filas"] and not e["eventos"] and not e["commits"]


@pytest.mark.parametrize("codigo", [CodigoSeguridad.SESION_INEXISTENTE,
    CodigoSeguridad.SESION_VENCIDA, CodigoSeguridad.SESION_REVOCADA,
    CodigoSeguridad.USUARIO_INACTIVO])
def test_sesion_no_vigente_rechazada_antes_de_insertar(unidad_alta, codigo):
    e = unidad_alta
    e["codigo"] = codigo
    with pytest.raises(ErrorSeguridad) as error:
        e["crear"]("agent")
    assert error.value.codigo == codigo
    assert not e["filas"] and not e["eventos"] and not e["commits"]


def test_rol_modificado_no_usa_identidad_anterior(unidad_alta):
    e = unidad_alta
    e["rol"] = "agent"
    with pytest.raises(ErrorCreacionUsuario):
        e["crear"]("admin")
    assert not e["filas"]


@pytest.mark.parametrize("referencia", [None, True, uuid4(), "admin"])
def test_crear_exige_referencia_tipificada_antes_de_conectar(servicio, referencia):
    with pytest.raises(ErrorSeguridad) as error:
        servicio.crear(referencia, servicio.preparar(datos()))
    assert error.value.codigo == CodigoSeguridad.SESION_INEXISTENTE
    assert servicio._motor.pool.checkedout() == 0


@pytest.mark.parametrize("campo,valor", [("actor", None), ("actor", True),
    ("rol_asignado", None), ("rol_asignado", "root"), ("rol_asignado", []),
    ("usuario_id", None), ("motivo", None)])
def test_user_created_exige_actor_sujeto_rol_y_motivo(campo, valor):
    from app.seguridad.auditoria import ActorUsuario, MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria
    from sqlalchemy.orm import Session
    entrada = dict(tipo=TipoEvento.USUARIO_CREADO, resultado=R.EXITO, motivo=M.ALTA_ADMINISTRATIVA,
                   actor=ActorUsuario(uuid4()), usuario_id=uuid4(), rol_asignado="agent")
    entrada[campo] = valor
    with Session() as db, pytest.raises(ValueError) as error:
        ServicioAuditoria(db).registrar(**entrada)
    assert str(error.value) == "Actor de autenticación inválido."
