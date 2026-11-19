"""Regresiones del verificador; el socket real se acredita en el runner HTTP."""

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
import secrets
from types import SimpleNamespace
from uuid import uuid4

from fastapi import Request
from pydantic import SecretBytes
import pytest
from sqlalchemy import create_engine

from app.api.adaptadores_auth import AdaptadorAuth
from app.api.cookies_auth import preparar_perfil
from app.aplicacion import crear_aplicacion
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.transacciones import ErrorSeguridad
from herramientas.ingreso_local.evidencia import CABECERA, DOMINIO, VerificadorIngresoLocal, huella_controles
from pruebas.intermediario_auxiliar import ORIGEN, cabeceras, credencial, politica
from pruebas.login_auxiliar import configuracion_login


@pytest.fixture
def ingreso():
    token = credencial()
    config = configuracion_login(postgres_host="127.0.0.1", postgres_port=5433,
        postgres_db="synapdesk_auth07_sec01a_" + uuid4().hex, postgres_user="testing",
        postgres_password=credencial(), auth_proxies_autorizados=["127.0.0.1/32"],
        auth_intermediario=politica([token]), auth_origenes_permitidos=[ORIGEN])
    clave, audiencia = SecretBytes(secrets.token_bytes(32)), uuid4().hex
    reloj = [1000.5]
    verificador = VerificadorIngresoLocal(config, clave, audiencia,
        ventana_segundos=30, capacidad_nonces=8, reloj=lambda: reloj[0])
    return dict(config=config, token=token, clave=clave, audiencia=audiencia, reloj=reloj, verificar=verificador)


def solicitud(e, *, headers=(), scheme="https", method="GET", path="/api/v1/auth/csrf", peer="127.0.0.1"):
    return Request(dict(type="http", scheme=scheme, method=method, path=path, raw_path=path.encode(),
        query_string=b"", client=(peer, 1234), server=("localhost", 443),
        app=SimpleNamespace(state=SimpleNamespace(configuracion=e["config"])),
        headers=[(k.lower().encode(), v.encode("latin-1")) for k, v in [*cabeceras(e["token"]).items(), *headers]]))


def prueba(e, request, **cambios):
    datos = dict(v=1, aud=e["audiencia"], ip="198.51.100.3", ts=1000, nonce=uuid4().hex,
                 method=request.method, path=request.scope["raw_path"].decode(), controls=huella_controles(request))
    datos.update(cambios)
    raw = json.dumps(datos, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    firma = hmac.digest(e["clave"].get_secret_value(), DOMINIO + payload.encode(), "sha256").hex()
    return payload + "." + firma


def agregar(request, sello):
    request.scope["headers"].append((CABECERA.encode(), sello.encode()))
    return request


def test_firma_y_binding_son_independientes_de_servicio_y_peer(ingreso):
    e = ingreso
    request = solicitud(e)
    resultado = e["verificar"](agregar(request, prueba(e, request)))
    assert resultado.digest == ServicioIdentificadores(e["config"]).ip_verificada("198.51.100.3")
    assert "198.51.100.3" not in repr(resultado)


@pytest.mark.parametrize("cambio", [dict(aud="a"*32), dict(v=True), dict(ip="no-ip"),
    dict(ip="::ffff:198.51.100.3"), dict(ts=970), dict(ts=1001), dict(ts=True),
    dict(nonce="cliente"), dict(method="POST"), dict(path="/otra"), dict(controls="0"*64)])
def test_sello_firmado_incompatible_falla(ingreso, cambio):
    request = solicitud(ingreso)
    with pytest.raises(ErrorSeguridad):
        ingreso["verificar"](agregar(request, prueba(ingreso, request, **cambio)))


@pytest.mark.parametrize("caso", ["ausente", "duplicada", "firma", "http", "peer", "forwarded", "ip_declarada", "cookie_reparada"])
def test_no_acepta_localhost_servicio_o_cabecera_como_prueba(ingreso, caso):
    e = ingreso
    request = solicitud(e, scheme="http" if caso == "http" else "https",
        peer="192.0.2.8" if caso == "peer" else "127.0.0.1")
    if caso == "cookie_reparada":
        request.scope["headers"].append((b"cookie", b"synapdesk_session_dev=abc\xa0"))
    sello = prueba(e, request)
    if caso != "ausente":
        agregar(request, sello[:-1] + ("0" if sello[-1] != "0" else "1") if caso == "firma" else sello)
    if caso == "duplicada":
        agregar(request, sello)
    if caso in {"forwarded", "ip_declarada"}:
        request.scope["headers"].append((b"x-forwarded-for" if caso == "forwarded" else b"x-synapdesk-client-ip", b"198.51.100.3"))
    if caso == "cookie_reparada":
        request.scope["headers"] = [(k, b"synapdesk_session_dev=abc" if k == b"cookie" else v)
                                      for k, v in request.scope["headers"]]
    with pytest.raises(ErrorSeguridad):
        e["verificar"](request)


def test_nonce_consumido_una_vez_bajo_concurrencia(ingreso):
    e = ingreso
    request = solicitud(e)
    agregar(request, prueba(e, request))
    def verificar(_):
        try:
            e["verificar"](request)
            return True
        except ErrorSeguridad:
            return False
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(verificar, range(4))).count(True) == 1


def test_capacidad_agotada_cierra_sin_expulsar_pruebas_vigentes(ingreso):
    e = ingreso
    for _ in range(8):
        req = solicitud(e)
        e["verificar"](agregar(req, prueba(e, req)))
    req = solicitud(e)
    with pytest.raises(ErrorSeguridad):
        e["verificar"](agregar(req, prueba(e, req)))
    e["reloj"][0] += 31
    req = solicitud(e)
    e["verificar"](agregar(req, prueba(e, req, ts=1031)))


@pytest.mark.parametrize("entorno", ["development", "staging", "production"])
def test_no_habilita_ensayo_en_otros_entornos(ingreso, entorno):
    config = ingreso["config"].model_copy(update={"app_env": entorno})
    with pytest.raises(ErrorSeguridad):
        VerificadorIngresoLocal(config, ingreso["clave"], ingreso["audiencia"], ventana_segundos=30, capacidad_nonces=8)


def test_no_proveedor_productivo_ni_registro_en_fabrica(ingreso):
    config = ingreso["config"].model_copy(update={"app_env": "production"})
    motor = create_engine("postgresql+psycopg://", hide_parameters=True)
    try:
        with pytest.raises(ErrorSeguridad):
            AdaptadorAuth(motor, config, preparar_perfil(ingreso["config"], origen_publico=ORIGEN,
                nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev"),
                capacidad_argon2=1, procedencia_ip=ingreso["verificar"])
    finally:
        motor.dispose()
    assert set(crear_aplicacion(ingreso["config"]).openapi()["paths"]) == {
        "/api/v1/health", "/api/v1/ready", "/api/v1/auth/csrf", "/api/v1/search",
        "/api/v1/tickets/{ticket_id}/recommendations",
        "/api/v1/tickets/{ticket_id}/prediction", "/api/v1/documents", "/api/v1/documents/{document_id}",
        "/api/v1/recommendations/{recommendation_id}",
        "/api/v1/recommendations/{recommendation_id}/reviews"}


@pytest.mark.parametrize("ruta", ["/api/v1/tickets", "/api/v1/tickets/00000000-0000-4000-8000-000000000001"])
def test_lectura_local_no_reclasifica_cookie_ambigua_como_validacion(ingreso, ruta):
    # Unidad de precedencia/representación; no acredita SQL (lo hace el runner real).
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from herramientas.ingreso_local.aplicacion import crear_aplicacion_local
    e = ingreso
    motor = MagicMock()
    motor.dialect.name = "postgresql"
    db = motor.connect.return_value.__enter__.return_value
    db.execute.return_value.one.return_value = (e["config"].postgres_db, e["config"].postgres_user)
    db.scalar.return_value = "0008_predicciones_ticket"
    perfil = preparar_perfil(e["config"], origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    app = crear_aplicacion_local(e["config"], motor, perfil, e["verificar"],
        capacidad_argon2=1, max_cuerpo_bytes=65536)
    with TestClient(app, base_url="https://localhost") as cliente:
        respuesta = cliente.get(ruta, headers={**cabeceras(e["token"]), "Cookie": "synapdesk_session_dev"})
    assert respuesta.status_code == 500
    assert respuesta.json()["error"]["code"] == "INTERNAL_ERROR"
    assert respuesta.headers["cache-control"] == "no-store"
    assert "synapdesk_session_dev" not in respuesta.text
    motor.connect.assert_called_once()
