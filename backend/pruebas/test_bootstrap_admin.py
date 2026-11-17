import getpass
from io import StringIO
import warnings

import pytest
from pydantic import SecretStr

from app.configuracion import Configuracion
from app.seguridad.bootstrap_admin import (
    CodigoBootstrap as C, ErrorBootstrap, ServicioBootstrapAdmin,
)
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.secretos import generar_secreto
from herramientas import bootstrap_admin as cli


@pytest.fixture
def servicio():
    # Motor perezoso: las unitarias no conectan ni escriben en PostgreSQL.
    config = Configuracion(_env_file=None, app_env="testing", postgres_host="localhost",
        postgres_port=5433, postgres_db="synapdesk_auth07_sec01a_" + "a" * 32,
        postgres_user="ensayo", postgres_password=generar_secreto(),
        auth_argon2_memoria_kib=1024, auth_argon2_iteraciones=1, auth_argon2_paralelismo=1)
    servicio = ServicioBootstrapAdmin(config)
    yield servicio
    servicio.cerrar()


def datos(**cambios):
    clave = generar_secreto()
    return dict(nombre="Administrador de ensayo", correo="  ADMIN@Example.Invalid  ",
                contrasena=clave, confirmacion=clave) | cambios


def test_preparacion_normaliza_y_hash_no_mantiene_contrasena(servicio):
    entrada = datos()
    preparado = servicio.preparar(**entrada)
    assert preparado.correo == "admin@example.invalid"
    assert preparado.hash_contrasena.get_secret_value().startswith("$argon2id$")
    assert servicio._contrasenas.verificar(preparado.hash_contrasena.get_secret_value(),
                                          entrada["contrasena"].get_secret_value())
    assert entrada["contrasena"].get_secret_value() not in repr(preparado)
    assert preparado.hash_contrasena.get_secret_value() not in repr(preparado)
    assert not hasattr(preparado, "contrasena")


@pytest.mark.parametrize("correo", [None, "", "sin-arroba", "a@@b", "@a", "a@", "a b@c", "a\x00@b"])
def test_correo_invalido(servicio, correo):
    with pytest.raises(ErrorBootstrap) as error:
        servicio.preparar(**datos(correo=correo))
    assert error.value.codigo == C.ENTRADA


@pytest.mark.parametrize("clave", [None, "texto", SecretStr(""), SecretStr("\ud800")])
def test_contrasena_invalida(servicio, clave):
    with pytest.raises(ErrorBootstrap) as error:
        servicio.preparar(**datos(contrasena=clave))
    assert error.value.codigo == C.ENTRADA


@pytest.mark.parametrize("nombre", [None, "", "  ", "a\x00b", "\ud800"])
def test_nombre_requerido_por_modelo(servicio, nombre):
    with pytest.raises(ErrorBootstrap):
        servicio.preparar(**datos(nombre=nombre))


def test_confirmacion_distinta_sin_hash(servicio, monkeypatch):
    def no_hash(self, clave):
        pytest.fail("No se debe calcular Argon2 antes de confirmar.")
    monkeypatch.setattr(ServicioContrasenas, "generar_hash", no_hash)
    with pytest.raises(ErrorBootstrap) as error:
        servicio.preparar(**datos(confirmacion=generar_secreto()))
    assert error.value.codigo == C.CONFIRMACION


def test_hash_fuera_de_conexion_y_error_saneado(servicio, monkeypatch):
    clave = generar_secreto()

    def fallar(self, texto):
        assert servicio._motor.pool.checkedout() == 0
        raise ErrorContrasena(clave.get_secret_value())

    monkeypatch.setattr(ServicioContrasenas, "generar_hash", fallar)
    with pytest.raises(ErrorBootstrap) as error:
        servicio.preparar(**datos(contrasena=clave, confirmacion=clave))
    assert error.value.codigo == C.HASH
    assert clave.get_secret_value() not in str(error.value)
    assert error.value.__cause__ is None


def test_configuracion_ausente_no_proporciona_destino_implicito():
    with pytest.raises(ErrorBootstrap) as error:
        ServicioBootstrapAdmin(Configuracion(_env_file=None))
    assert error.value.codigo == C.CONFIGURACION


def test_creacion_requiere_destino_acreditado_sin_flags(servicio, monkeypatch):
    with pytest.raises(ErrorBootstrap) as error:
        servicio.crear(servicio.preparar(**datos()))
    assert error.value.codigo == C.DESTINO
    monkeypatch.setenv("AUTH_BOOTSTRAP_HABILITADO", "1")
    with pytest.raises(ErrorBootstrap) as error:
        servicio.verificar_destino()
    assert error.value.codigo == C.CANAL


def test_parser_no_repite_secretos_en_argumentos(capsys):
    secreto = generar_secreto().get_secret_value()
    assert cli.main(["--base", "testing", "--password", secreto]) == 2
    salida = capsys.readouterr()
    assert secreto not in salida.out + salida.err


def test_entrada_no_interactiva_no_lee_secretos(monkeypatch):
    monkeypatch.setattr(cli.sys, "stdin", StringIO())
    with pytest.raises(ErrorBootstrap):
        cli.leer_datos()


def test_getpass_falla_sin_degradar_a_eco(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "ensayo")

    def sin_terminal(prompt):
        warnings.warn("No hay terminal seguro", getpass.GetPassWarning)
        pytest.fail("No degradar a lectura visible.")

    monkeypatch.setattr(getpass, "getpass", sin_terminal)
    with pytest.raises(ErrorBootstrap) as error:
        cli.leer_datos()
    assert error.value.codigo == C.ENTRADA


def test_captura_oculta_dos_veces_y_confirma_sin_imprimir(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    entradas = iter(["admin@example.invalid", "Administrador"])
    monkeypatch.setattr("builtins.input", lambda _: next(entradas))
    clave = generar_secreto().get_secret_value()
    llamadas = []

    def oculto(prompt):
        llamadas.append(prompt)
        return clave

    monkeypatch.setattr(getpass, "getpass", oculto)
    entrada = cli.leer_datos()
    assert len(llamadas) == 2 and entrada["contrasena"] == entrada["confirmacion"]
    assert clave not in str(capsys.readouterr())


def test_destino_inexacto_o_principal_rechazado(servicio, capsys):
    with pytest.raises(ErrorBootstrap) as error:
        servicio.ensayar(servicio.preparar(**datos()), confirmar_destino="desconocido")
    assert error.value.codigo == C.DESTINO
    assert cli.main(["--base", "principal", "--ensayar"]) == 2


def test_cli_sanea_error_configuracion(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    secreto = generar_secreto().get_secret_value()

    def fallar(base):
        raise ValueError(secreto)

    monkeypatch.setattr(cli, "seleccionar_configuracion_bd", fallar)
    assert cli.main(["--base", "testing", "--ensayar"]) == 2
    assert secreto not in str(capsys.readouterr())
