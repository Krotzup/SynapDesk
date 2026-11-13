from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.seguridad.auditoria import (
    ActorExterno, MotivoEvento as M, ResultadoEvento as R, ServicioAuditoria, TipoEvento as T,
)
from app.seguridad.bootstrap_admin import (
    CodigoBootstrap as C, DestinoAutorizado, ErrorBootstrap, IdentidadDestino,
)
from herramientas import bootstrap_admin as cli
from pruebas.test_bootstrap_admin import datos, servicio


@pytest.mark.parametrize("destino", [None, True, "host", uuid4()])
def test_identidad_no_es_booleano_o_entrada_cliente(servicio, destino):
    with pytest.raises(ErrorBootstrap) as error:
        servicio.crear(servicio.preparar(**datos()), destino=destino, confirmar_destino="si")
    assert error.value.codigo == C.DESTINO


def test_evidencia_de_otro_motor_o_confirmacion_inexacta_no_conecta(servicio):
    identidad = IdentidadDestino("1", 1, 1, 1, 1)
    for emisor, confirmacion in ((object(), "destino"), (servicio._emisor, "incorrecto")):
        destino = DestinoAutorizado(identidad, "destino", emisor)
        with pytest.raises(ErrorBootstrap):
            servicio.crear(servicio.preparar(**datos()), destino=destino, confirmar_destino=confirmacion)
    assert servicio._motor.pool.checkedout() == 0


@pytest.mark.parametrize("modo", ["disable", "allow", "prefer", "require", "verify-ca"])
def test_canal_sin_verificar_hostname_cierra_antes_conexion(servicio, modo):
    servicio._config = servicio._config.model_copy(update=dict(postgres_sslmode=modo))
    with pytest.raises(ErrorBootstrap) as error:
        servicio.verificar_destino()
    assert error.value.codigo == C.CANAL


def test_pin_ausente_no_se_sustituye_por_loopback(servicio):
    servicio._config = servicio._config.model_copy(update=dict(postgres_sslmode="verify-full"))
    with pytest.raises(ErrorBootstrap) as error:
        servicio.verificar_destino()
    assert error.value.codigo == C.CONFIGURACION


@pytest.mark.parametrize("oid", [0, -1, True, "1", 2**32])
def test_actor_externo_rechaza_identidades_invalidas(oid):
    with pytest.raises(ValueError):
        ActorExterno(oid)


def test_evento_bootstrap_requiere_actor_y_no_falsea_sesion():
    with Session() as db:
        auditoria = ServicioAuditoria(db)
        for cambios in ({}, dict(actor=ActorExterno(1), sesion_id=uuid4()),
                        dict(actor=ActorExterno(1), motivo=M.CREACION)):
            with pytest.raises(ValueError):
                auditoria.registrar(**(dict(tipo=T.ADMIN_BOOTSTRAP, resultado=R.EXITO,
                    motivo=M.ADMIN_INICIAL_CREADO, usuario_id=uuid4()) | cambios))
        with pytest.raises(ValueError):
            auditoria.registrar(tipo=T.LOGIN, resultado=R.EXITO, actor=ActorExterno(1))


@pytest.mark.parametrize("fallar", [False, True])
def test_cli_confirmacion_y_exito_solo_despues_crear(monkeypatch, capsys, fallar):
    orden = []

    class ServicioFalso:
        def __init__(self, config):
            pass
        def verificar_destino(self):
            orden.append("verificado")
            return SimpleNamespace(confirmacion="destino-verificado")
        def preparar(self, **datos):
            orden.append("hash")
            return object()
        def crear(self, preparado, **datos):
            orden.append("commit")
            if fallar:
                raise RuntimeError("detalle privado")
        def cerrar(self):
            orden.append("cerrado")

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(cli, "ServicioBootstrapAdmin", ServicioFalso)
    monkeypatch.setattr(cli, "seleccionar_configuracion_bd", lambda _: object())
    monkeypatch.setattr("builtins.input", lambda _: "destino-verificado")
    monkeypatch.setattr(cli, "leer_datos", lambda: datos())
    assert cli.main(["--base", "principal"]) == (2 if fallar else 0)
    salida = capsys.readouterr()
    assert ("auditoría confirmados" in salida.out) == (not fallar)
    assert "detalle privado" not in salida.err
    assert orden == ["verificado", "hash", "commit", "cerrado"]


@pytest.mark.parametrize("bandera", ["--yes", "--force", "--skip-confirmation"])
def test_cli_no_ofrece_salto_confirmacion(bandera, capsys):
    assert cli.main(["--base", "principal", bandera]) == 2
