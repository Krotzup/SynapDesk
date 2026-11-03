import base64
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.configuracion import Configuracion
from app.seguridad.auditoria import MotivoEvento, ResultadoEvento, ServicioAuditoria, TipoEvento
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.limites import DecisionLimite, ServicioLimites
from app.seguridad.origenes import ErrorConfiguracionSeguridad, ServicioOrigen
from app.seguridad.proxies import ServicioIpConfiable
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad


@pytest.fixture
def configuracion_c():
    return Configuracion(
        _env_file=None, app_env="testing", auth_origenes_permitidos=["http://localhost:3000"],
        auth_proxies_autorizados=["192.0.2.8/32", "2001:db8::8/128"],
        auth_hmac_clave=base64.b64encode(bytes(range(32))).decode("ascii"), auth_hmac_id_clave="prueba",
    )


@pytest.mark.parametrize("valor", ["http://localhost:3000", "HTTP://LOCALHOST:3000"])
def test_origin_permitido(configuracion_c, valor):
    ServicioOrigen(configuracion_c).validar([valor])


@pytest.mark.parametrize("valores", [
    None, [], [""], ["null"], ["https://localhost:3000"], ["http://localhost"],
    ["http://localhost:3001"], ["http://127.0.0.1:3000"], ["http://otro.localhost:3000"],
    ["http://localhost:3000", "http://localhost:3000"],
    ["http://localhost:3000 http://otro.invalid"], ["http://localhost:3000,http://otro.invalid"],
    [" http://localhost:3000"], ["http://localhost:3000/"], ["http://localhost:3000?"],
    ["http://localhost:3000#"], ["http://user@localhost:3000"], ["http://localhost:03000"],
    ["http://localhost:3000\r\n"], ["http://localhost.:3000"], "http://localhost:3000", [42],
])
def test_origin_rechazado_sin_reflejar_entrada(configuracion_c, valores, caplog):
    with pytest.raises(ErrorSeguridad) as error:
        ServicioOrigen(configuracion_c).validar(valores)
    assert error.value.codigo == C.ORIGIN_INVALIDO
    assert str(error.value) == "Operación de seguridad rechazada: ORIGIN_INVALIDO."
    assert not caplog.records


@pytest.mark.parametrize("origen", [
    "*", "null", "https://*.example.invalid", "http://localhost:3000/", "http://localhost:",
    "http://localhost:0", "http://localhost:65536", "ftp://localhost", "https://-host.invalid",
    "https://host..invalid", "https://höst.invalid", "http://999.1.1.1", "http://[:::1]",
    "https://user:secret@host.invalid", "https://host.invalid/path", "https://host.invalid\n",
])
def test_origin_configuracion_invalida(origen, caplog):
    with pytest.raises(ValidationError) as error:
        Configuracion(_env_file=None, auth_origenes_permitidos=[origen])
    assert origen not in str(error.value)
    assert not caplog.records


def test_origin_configuracion_distingue_ausencia_y_duplicados():
    with pytest.raises(ErrorConfiguracionSeguridad):
        ServicioOrigen(Configuracion(_env_file=None))
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None, auth_origenes_permitidos=["https://example.invalid", "https://example.invalid:443"])


@pytest.mark.parametrize("configurado,recibido", [
    ("https://EXAMPLE.invalid", "https://example.invalid:443"),
    ("http://example.invalid:80", "http://EXAMPLE.invalid"),
    ("https://[2001:db8::1]", "https://[2001:0db8:0:0:0:0:0:1]:443"),
])
def test_origen_compara_esquema_host_y_puerto_efectivos(configurado, recibido):
    ServicioOrigen(Configuracion(_env_file=None, auth_origenes_permitidos=[configurado])).validar([recibido])


def test_origen_local_configurado_por_entorno(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGENES_PERMITIDOS", '["http://localhost:3000"]')
    ServicioOrigen(Configuracion(_env_file=None)).validar(["http://localhost:3000"])


@pytest.mark.parametrize("par,cliente,canonica", [
    ("192.0.2.8", "198.51.100.7", "198.51.100.7"),
    ("2001:0db8::8", "2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
    ("::ffff:192.0.2.8", "::ffff:198.51.100.7", "198.51.100.7"),
])
def test_ip_procedencia_confiable_hmac_canonico(configuracion_c, par, cliente, canonica, caplog):
    identificadores = ServicioIdentificadores(configuracion_c)
    resultado = ServicioIpConfiable(configuracion_c, identificadores).identificar(
        par_transporte=par, valores_ip_cliente=[cliente])
    assert resultado.digest == identificadores.ip_verificada(canonica)
    assert len(resultado.digest) == 32
    assert resultado.digest != identificadores.cuenta(canonica + "@example.invalid")
    assert cliente not in repr(resultado)
    assert not caplog.records


@pytest.mark.parametrize("par,valores", [
    (None, ["198.51.100.7"]), ("203.0.113.9", ["198.51.100.7"]),
    ("192.0.2.8", None), ("192.0.2.8", []), ("192.0.2.8", ["198.51.100.7", "198.51.100.8"]),
    ("192.0.2.8", ["198.51.100.7, 198.51.100.8"]), ("192.0.2.8", ["unknown"]),
    ("192.0.2.8", ["fe80::1%eth0"]), ("192.0.2.8", ["198.51.100.7:80"]),
    ("192.0.2.8", [" 198.51.100.7"]), ("192.0.2.8", ["198.051.100.7"]),
])
def test_ip_rechaza_cabeceras_falsificadas_y_ambiguedad(configuracion_c, par, valores):
    servicio = ServicioIpConfiable(configuracion_c, ServicioIdentificadores(configuracion_c))
    with pytest.raises(ErrorSeguridad) as error:
        servicio.identificar(par_transporte=par, valores_ip_cliente=valores)
    assert error.value.codigo == C.IP_NO_VERIFICABLE


def test_ip_sin_proxies_no_atribuye_ip(configuracion_c):
    configuracion_c.auth_proxies_autorizados = []
    with pytest.raises(ErrorSeguridad):
        ServicioIpConfiable(configuracion_c, ServicioIdentificadores(configuracion_c)).identificar(
            par_transporte="192.0.2.8", valores_ip_cliente=["198.51.100.7"])


@pytest.mark.parametrize("red", ["0.0.0.0/0", "::/0", "*", "localhost", "192.0.2.8/24", "fe80::1%eth0", "::ffff:192.0.2.8/128"])
def test_proxies_sin_configuracion_permisiva(red):
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None, auth_proxies_autorizados=[red])


@pytest.mark.parametrize("campo,valor", [
    ("auth_limite_cuenta_intentos", 0), ("auth_limite_ip_intentos", -1),
    ("auth_limite_cuenta_ventana_segundos", 0), ("auth_limite_ip_bloqueo_segundos", True),
    ("auth_limite_reintentos_version", 6), ("auth_limite_reintentos_version", True),
])
def test_limites_configurables_validan_entrada(campo, valor):
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None, **{campo: valor})


def test_limites_no_inventan_cuotas(configuracion_c):
    with Session() as db, pytest.raises(ErrorConfiguracionSeguridad):
        ServicioLimites(db, configuracion_c, ServicioIdentificadores(configuracion_c))


@pytest.mark.parametrize("espera,segundos", [(0.000001, 1), (1, 1), (1.000001, 2), (60, 60)])
def test_retry_after_redondea_espera_verificable(espera, segundos):
    ahora = datetime(2026, 11, 3, tzinfo=UTC)
    decision = DecisionLimite(False, ahora, ahora + timedelta(seconds=espera))
    assert decision.codigo == "RATE_LIMITED"
    assert decision.retry_after == segundos
    assert DecisionLimite(True, ahora).retry_after is None


@pytest.mark.parametrize("campo", ["tipo", "resultado", "motivo", "request_id", "usuario_id", "sesion_id", "ip"])
def test_auditoria_no_acepta_texto_libre_ni_secretos(campo, caplog):
    datos = dict(tipo=TipoEvento.LOGIN, resultado=ResultadoEvento.RECHAZO, motivo=MotivoEvento.CREDENCIALES_INVALIDAS)
    secreto = "password-cookie-csrf-session-hmac-no-registrar"
    datos[campo] = secreto
    with Session() as db, pytest.raises(ValueError) as error:
        ServicioAuditoria(db).registrar(**datos)
    assert secreto not in str(error.value)
    assert not caplog.records
