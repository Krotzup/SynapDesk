from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.aplicacion import crear_aplicacion
from app.api.dependencias_auth import IntermediarioHttp, obtener_intermediario, obtener_token_csrf
from app.configuracion import Configuracion
from app.seguridad.intermediario import (
    PoliticaIntermediario, ServicioIntermediario, digest_credencial_servicio,
)
from app.seguridad.proxies import IpVerificada
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad
from pruebas.intermediario_auxiliar import ORIGEN, cabeceras, configuracion, credencial, politica

RUTA = "/api/v1/auth/csrf"
AHORA = datetime(2026, 11, 12, tzinfo=UTC)


def aplicacion(config):
    app = crear_aplicacion(config)

    @app.get("/solo-servicio")
    def solo_servicio(identidad: IntermediarioHttp):
        return {"entorno": identidad.entorno, "servicio": identidad.servicio}

    @app.post("/csrf-previo", dependencies=[Depends(obtener_intermediario), Depends(obtener_token_csrf)])
    def csrf_previo():
        return {}

    return app


def verificar(servicio, valores, **cambios):
    return servicio.verificar(valores, **(dict(esquema="https", cabeceras_reenviadas=False) | cambios))


def test_credencial_correcta_es_servicio_sin_ip_ni_sesion():
    token = credencial()
    identidad = verificar(ServicioIntermediario(configuracion([token])), [cabeceras(token)["Authorization"]])
    assert identidad.servicio == "nextjs" and identidad.entorno == "testing"
    assert not isinstance(identidad, IpVerificada)
    assert not hasattr(identidad, "usuario") and not hasattr(identidad, "digest")
    assert token.get_secret_value() not in repr(identidad)


@pytest.mark.parametrize("valor", [
    None, "", "Bearer", "Bearer ", "Basic abc", "bearer " + "A" * 43,
    "Bearer " + "A" * 42, "Bearer " + "A" * 44, "Bearer " + "A" * 43 + "=",
    "Bearer " + "A" * 43 + ",Bearer " + "A" * 43,
    " Bearer " + "A" * 43, "Bearer  " + "A" * 43, "Bearer\t" + "A" * 43,
    "Bearer " + "A" * 43 + " ", "Bearer " + "A" * 42 + "é",
    "Bearer " + "A" * 42 + "B",  # bits de padding no canónicos
])
def test_ausencia_y_formatos_invalidos(valor):
    servicio = ServicioIntermediario(configuracion([credencial()]))
    with pytest.raises(ErrorSeguridad) as error:
        verificar(servicio, [] if valor is None else [valor])
    assert error.value.codigo == C.INFRAESTRUCTURA
    assert not valor or valor not in str(error.value)


def test_credencial_incorrecta_y_duplicada():
    token = credencial()
    servicio = ServicioIntermediario(configuracion([token]))
    for valores in ([cabeceras(credencial())["Authorization"]], [cabeceras(token)["Authorization"]] * 2):
        with pytest.raises(ErrorSeguridad):
            verificar(servicio, valores)


def test_rotacion_compara_todas_las_claves_y_retira_por_vencimiento():
    tokens = [credencial(), credencial()]
    datos = politica(tokens, ahora=AHORA)
    datos["credenciales"][0]["vence_en"] = AHORA
    servicio = ServicioIntermediario(configuracion(tokens, auth_intermediario=datos))
    import hmac
    comparar = hmac.compare_digest
    for token in tokens:
        verificar(servicio, [cabeceras(token)["Authorization"]], ahora=AHORA - timedelta(seconds=1))
    for indice, token in enumerate(tokens):
        with patch("app.seguridad.intermediario.hmac.compare_digest", wraps=comparar) as comparacion:
            if indice == 0:
                with pytest.raises(ErrorSeguridad):
                    verificar(servicio, [cabeceras(token)["Authorization"]], ahora=AHORA)
            else:
                verificar(servicio, [cabeceras(token)["Authorization"]], ahora=AHORA)
            assert comparacion.call_count == 2
            assert all(len(arg) == 32 for llamada in comparacion.call_args_list for arg in llamada.args)
    with patch("app.seguridad.intermediario.hmac.compare_digest", wraps=comparar) as comparacion:
        with pytest.raises(ErrorSeguridad):
            verificar(servicio, [cabeceras(credencial())["Authorization"]], ahora=AHORA)
        assert comparacion.call_count == 2
    # La eliminación explícita también retira una clave antes de su vencimiento.
    servicio = ServicioIntermediario(configuracion([tokens[1]]))
    with pytest.raises(ErrorSeguridad):
        verificar(servicio, [cabeceras(tokens[0])["Authorization"]])


@pytest.mark.parametrize("entorno", ["development", "staging", "production"])
def test_digest_y_configuracion_de_otro_entorno_no_autentican(entorno):
    token = credencial()
    datos = politica([token], entorno=entorno)
    with pytest.raises(ErrorSeguridad):
        ServicioIntermediario(configuracion([token], auth_intermediario=datos))
    datos["entorno"] = "testing"  # copiar solo el digest no lo convierte en testing
    servicio = ServicioIntermediario(configuracion([token], auth_intermediario=datos))
    with pytest.raises(ErrorSeguridad):
        verificar(servicio, [cabeceras(token)["Authorization"]])


@pytest.mark.parametrize("cambio", [
    dict(credenciales=[]), dict(credenciales=[{}, {}, {}]), dict(habilitado="true"),
    dict(transporte="http"), dict(politica_ip="render"), dict(politica_ip="loopback"),
    dict(entorno="local"), dict(permitir_http=True),
])
def test_configuracion_invalida_rechazada(cambio):
    datos = politica([credencial()]) | cambio
    with pytest.raises(ValidationError):
        PoliticaIntermediario(**datos)


@pytest.mark.parametrize("campo,valor", [("digest", "digest_privado_invalido"),
    ("identificador", "no valido"), ("vence_en", AHORA.replace(tzinfo=None))])
def test_credenciales_invalidas_no_filtran_entradas(campo, valor):
    datos = politica([credencial()])
    datos["credenciales"][0][campo] = valor
    with pytest.raises(ValidationError) as error:
        PoliticaIntermediario(**datos)
    assert "digest_privado_invalido" not in str(error.value)


def test_duplicados_configurados_y_mutacion_no_permitidos():
    datos = politica([credencial()])
    datos["credenciales"].append(datos["credenciales"][0].copy())
    with pytest.raises(ValidationError):
        PoliticaIntermediario(**datos)
    datos["credenciales"][1]["identificador"] = "otro"
    with pytest.raises(ValidationError):
        PoliticaIntermediario(**datos)
    modelo = PoliticaIntermediario(**politica([credencial()]))
    with pytest.raises(ValidationError):
        modelo.habilitado = True
    assert isinstance(modelo.credenciales, tuple)


def test_no_hay_activacion_implicita_ni_dependencia_de_hmac_o_bd():
    token = credencial()
    for config in (Configuracion(_env_file=None), configuracion([token],
                   auth_intermediario=politica([token]) | {"habilitado": False})):
        with pytest.raises(ErrorSeguridad):
            ServicioIntermediario(config)
        with TestClient(crear_aplicacion(config)) as cliente:
            assert cliente.get("/api/v1/health").status_code == 200
    assert configuracion([token]).auth_hmac_clave is None
    ServicioIntermediario(configuracion([token]))


@pytest.mark.parametrize("esquema,reenviadas", [("http", False), ("", False), ("https", True)])
def test_transporte_inadecuado_rechazado(esquema, reenviadas):
    token = credencial()
    with pytest.raises(ErrorSeguridad):
        verificar(ServicioIntermediario(configuracion([token])), [cabeceras(token)["Authorization"]],
                  esquema=esquema, cabeceras_reenviadas=reenviadas)


@pytest.mark.parametrize("cabecera", ["Forwarded", "X-Forwarded-Proto", "X-Forwarded-For",
                                      "X-Forwarded-Host", "X-Real-IP"])
def test_http_no_acredita_tls_con_cabeceras_y_https_rechaza_ambiguedad(cabecera):
    token = credencial()
    for base in ("http://testserver", "https://testserver"):
        with TestClient(aplicacion(configuracion([token])), base_url=base) as cliente:
            respuesta = cliente.get("/solo-servicio", headers=cabeceras(token) | {cabecera: "https"})
            assert respuesta.status_code == 503


def test_http_servicio_distinto_de_usuario_csrf_origin_y_no_filtra(caplog):
    token = credencial()
    config = configuracion([token])
    app = aplicacion(config)
    with TestClient(app, base_url="https://testserver") as cliente:
        assert cliente.get("/solo-servicio", headers=cabeceras(token)).status_code == 200
        assert cliente.post("/csrf-previo", headers=cabeceras(token)).status_code == 403
        assert cliente.post("/csrf-previo", headers=cabeceras(token) | {
            "X-CSRF-Token": credencial().get_secret_value()}).status_code == 200
        assert cliente.get(RUTA, headers=cabeceras(token) | {"Origin": "null"}).status_code == 403
        for headers in ({}, cabeceras(credencial()), cabeceras(token),
                        cabeceras(token) | {"X-SynapDesk-Client-IP": "198.51.100.99"}):
            respuesta = cliente.get(RUTA, headers={"Origin": ORIGEN} | headers)
            assert respuesta.status_code == 503
            assert respuesta.headers["cache-control"] == "no-store"
            assert "set-cookie" not in respuesta.headers and "retry-after" not in respuesta.headers
            assert set(respuesta.json()["error"]) == {"code", "message", "details", "requestId"}
            assert respuesta.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
            for secreto in (token.get_secret_value(), "198.51.100.99",
                            config.auth_intermediario.credenciales[0].digest.get_secret_value()):
                assert secreto not in respuesta.text + caplog.text + repr(config) + config.model_dump_json()


@pytest.mark.parametrize("ip", ["127.0.0.1", "::1", "198.51.100.12"])
def test_ip_sin_servicio_no_autentica_y_servicio_sin_ip_no_emite(ip):
    token = credencial()
    with TestClient(aplicacion(configuracion([token])), base_url="https://testserver", client=(ip, 2000)) as cliente:
        assert cliente.get("/solo-servicio", headers={"X-SynapDesk-Client-IP": ip}).status_code == 503
        for headers in ([('Authorization', cabeceras(token)['Authorization'])] * 2,
                        [("Authorization", cabeceras(token)["Authorization"])] + [("X-SynapDesk-Client-IP", ip)] * 2):
            assert cliente.get(RUTA, headers=[("Origin", ORIGEN), *headers]).status_code == 503


def test_verificador_es_reutilizable_y_concurrente_sin_antireplay():
    token = credencial()
    servicio = ServicioIntermediario(configuracion([token]))
    with ThreadPoolExecutor(max_workers=8) as grupo:
        identidades = list(grupo.map(lambda _: verificar(servicio, [cabeceras(token)["Authorization"]]), range(32)))
    assert len(identidades) == 32 and all(i.entorno == "testing" for i in identidades)


def test_digest_de_servicio_no_usa_dominio_de_sesion_ni_hmac():
    from app.seguridad.secretos import digest_secreto
    token = credencial()
    assert bytes.fromhex(digest_credencial_servicio(token, "testing").get_secret_value()) != digest_secreto(token, C.TOKEN_INVALIDO)
    with pytest.raises(ValueError):
        digest_credencial_servicio(SecretStr("contraseña humana"), "testing")


def test_configuracion_json_exclusiva_de_servidor_se_carga_sin_exponer_digest(monkeypatch):
    import json
    token = credencial()
    datos = politica([token])
    entrada = datos["credenciales"][0]
    digest = entrada["digest"].get_secret_value()
    entrada["digest"] = digest
    entrada["vence_en"] = entrada["vence_en"].isoformat()
    monkeypatch.setenv("AUTH_INTERMEDIARIO", json.dumps(datos))
    config = Configuracion(_env_file=None, app_env="testing")
    verificar(ServicioIntermediario(config), [cabeceras(token)["Authorization"]])
    assert digest not in repr(config) + config.model_dump_json()
    assert token.get_secret_value() not in repr(config) + config.model_dump_json()


@pytest.mark.parametrize("cabecera", ["X-Forwarded-For", "Forwarded", "X-Real-IP",
    "X-SynapDesk-Client-IP", "X-SynapDesk-IP-Source"])
def test_metadatos_ip_unicos_o_ambiguos_no_crean_ip_verificada(cabecera):
    token = credencial()
    with TestClient(aplicacion(configuracion([token])), base_url="https://testserver") as cliente:
        for valores in (["198.51.100.2"], ["198.51.100.2", "198.51.100.3"],
                        ["198.51.100.2, 198.51.100.3"]):
            respuesta = cliente.get(RUTA, headers=[*cabeceras(token).items(),
                *((cabecera, valor) for valor in valores)])
            assert respuesta.status_code == 503
            assert "set-cookie" not in respuesta.headers
