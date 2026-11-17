from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.aplicacion import crear_aplicacion
from app.api import csrf_auth
from app.configuracion import Configuracion

RUTA = "/api/v1/auth/csrf"
ORIGEN = "http://localhost:3000"


def configuracion(**cambios):
    return Configuracion(_env_file=None, auth_origenes_permitidos=[ORIGEN], **cambios)


def comprobar_rechazo(respuesta, estado, codigo):
    assert respuesta.status_code == estado
    assert set(respuesta.json()) == {"error"}
    error = respuesta.json()["error"]
    assert set(error) == {"code", "message", "details", "requestId"}
    assert error["code"] == codigo and error["details"] is None
    UUID(error["requestId"])
    assert respuesta.headers["cache-control"] == "no-store"
    assert "set-cookie" not in respuesta.headers
    assert "retry-after" not in respuesta.headers
    assert "csrfToken" not in respuesta.text and "expiresAt" not in respuesta.text


@pytest.mark.parametrize("cabeceras,estado", [
    ([("Origin", ORIGEN)], 503),
    ([("Sec-Fetch-Site", "same-origin")], 503),
    ([("Origin", ORIGEN), ("Sec-Fetch-Site", "cross-site")], 503),
    ([], 403),
    ([("Origin", "null"), ("Sec-Fetch-Site", "same-origin")], 403),
    ([("Origin", "https://externo.invalid")], 403),
    ([("Origin", ORIGEN), ("Origin", ORIGEN)], 403),
    ([("Origin", ORIGEN + ", " + ORIGEN)], 403),
    ([("Origin", "http://localhost:3001")], 403),
    ([("Origin", "https://localhost:3000")], 403),
    ([("Sec-Fetch-Site", "same-site")], 403),
    ([("Sec-Fetch-Site", "cross-site")], 403),
    ([("Sec-Fetch-Site", "none")], 403),
    ([("Sec-Fetch-Site", "same-origin"), ("Sec-Fetch-Site", "same-origin")], 403),
    ([("Sec-Fetch-Site", "same-origin, same-origin")], 403),
    ([("Referer", ORIGEN), ("X-Forwarded-Host", "localhost:3000")], 403),
])
def test_bootstrap_respeta_origen_y_permanece_cerrado(cabeceras, estado):
    with TestClient(crear_aplicacion(configuracion())) as cliente:
        respuesta = cliente.get(RUTA, headers=cabeceras)
    comprobar_rechazo(respuesta, estado, "ORIGIN_INVALID" if estado == 403 else "SERVICE_UNAVAILABLE")


@pytest.mark.parametrize("cabecera", [
    "X-Forwarded-For", "X-Real-IP", "Forwarded", "X-SynapDesk-Client-IP",
])
def test_metadatos_falsificados_y_loopback_no_habilitan_emision(cabecera, caplog):
    with TestClient(crear_aplicacion(configuracion()), client=("127.0.0.1", 1234)) as cliente:
        respuesta = cliente.get(RUTA, headers={"Origin": ORIGEN, cabecera: "198.51.100.79"})
    comprobar_rechazo(respuesta, 503, "SERVICE_UNAVAILABLE")
    assert "198.51.100.79" not in respuesta.text + caplog.text


@pytest.mark.parametrize("cookie", [
    "synapdesk_csrf_context_dev=credencial_antigua_ficticia",
    "synapdesk_csrf_context_dev=",
    'synapdesk_csrf_context_dev="malformada"',
    "synapdesk_csrf_context_dev=uno; synapdesk_csrf_context_dev=dos",
    "synapdesk_session_dev=sesion_presentada_ficticia",
    "__Host-synapdesk_session=sesion_produccion_ficticia",
])
def test_cookies_no_evitan_el_control_ni_se_modifican(cookie, caplog):
    with TestClient(crear_aplicacion(configuracion())) as cliente:
        respuesta = cliente.get(RUTA, headers={"Origin": ORIGEN, "Cookie": cookie})
    comprobar_rechazo(respuesta, 503, "SERVICE_UNAVAILABLE")
    assert cookie not in respuesta.text + caplog.text


@pytest.mark.parametrize("cabeceras", [{"Origin": ORIGEN}, {"Sec-Fetch-Site": "same-origin"}])
def test_origenes_sin_configurar_no_se_aceptan(cabeceras):
    with TestClient(crear_aplicacion(Configuracion(_env_file=None))) as cliente:
        respuesta = cliente.get(RUTA, headers=cabeceras)
    comprobar_rechazo(respuesta, 500, "INTERNAL_ERROR")


def test_resolver_solo_ip_no_habilita_emision_sin_politica(monkeypatch):
    # Simula únicamente el avance futuro del adaptador. No autoriza emisión.
    monkeypatch.setattr(csrf_auth, "obtener_ip_verificada", lambda request: None)
    with TestClient(crear_aplicacion(configuracion())) as cliente:
        respuesta = cliente.get(RUTA, headers={"Origin": ORIGEN})
    comprobar_rechazo(respuesta, 503, "SERVICE_UNAVAILABLE")


def test_cuotas_login_configuradas_no_equivalen_a_limite_bootstrap():
    cuotas = {f"auth_limite_{tipo}_{campo}": valor for tipo in ("cuenta", "ip")
              for campo, valor in (("intentos", 2), ("ventana_segundos", 30), ("bloqueo_segundos", 10))}
    with TestClient(crear_aplicacion(configuracion(**cuotas))) as cliente:
        respuestas = [cliente.get(RUTA, headers={"Origin": ORIGEN}) for _ in range(12)]
    for respuesta in respuestas:
        comprobar_rechazo(respuesta, 503, "SERVICE_UNAVAILABLE")
    assert len({r.json()["error"]["requestId"] for r in respuestas}) == 12


def test_no_se_exponen_otros_endpoints_ni_se_adopta_request_id():
    with TestClient(crear_aplicacion(configuracion())) as cliente:
        respuesta = cliente.get(RUTA, headers={"Origin": ORIGEN, "X-Request-ID": "dato_cliente_ficticio"})
        assert "dato_cliente_ficticio" not in respuesta.text
        for ruta in ("login", "me", "logout"):
            assert cliente.get("/api/v1/auth/" + ruta).status_code == 404
        assert cliente.get("/api/v1/health").status_code == 200
        assert cliente.post(RUTA, headers={"Origin": ORIGEN}).status_code == 405
