"""Regresiones F1: bytes HTTP reales de h11, sin normalizar credenciales.

Los secretos de prueba son vectores públicos deterministas, no credenciales.
El OWS exterior del campo pertenece a HTTP y h11 lo retira; el whitespace
anterior a un punto y coma sí permanece dentro del valor de la cookie.
"""

import base64
import hashlib

from fastapi import Request
import h11
import pytest

from app.api.adaptadores_auth import extraer_cookies
from app.api.cookies_auth import CookieAmbigua, PerfilCookies, leer_cookie
from app.api.errores_auth import respuesta_error, traducir_error
from app.seguridad.secretos import digest_secreto
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad


BRUTO = bytes(range(32))
CANONICO = base64.urlsafe_b64encode(BRUTO).rstrip(b"=")
OTRO = base64.urlsafe_b64encode(bytes(reversed(BRUTO))).rstrip(b"=")
PERFILES = {
    "local": PerfilCookies("testing", "http://localhost:3000",
                           "synapdesk_session_dev", "synapdesk_csrf_context_dev"),
    "production": PerfilCookies("production", "https://app.example.invalid",
                                "__Host-synapdesk_session", "__Host-synapdesk_csrf_context"),
}


@pytest.fixture(params=["local", "production"])
def perfil(request):
    return PERFILES[request.param]


@pytest.fixture(params=["sesion", "contexto"])
def tipo(request):
    return request.param


def nombre(perfil, tipo):
    return (perfil.nombre_sesion if tipo == "sesion" else perfil.nombre_contexto).encode("ascii")


def desde_http(*cookies):
    """La misma frontera h11 -> headers ASGI (bytes) -> Starlette (latin-1)."""
    parser = h11.Connection(h11.SERVER)
    parser.receive_data(b"GET /api/v1/auth/me HTTP/1.1\r\nHost: localhost\r\n"
                        + b"".join(b"Cookie: " + valor + b"\r\n" for valor in cookies)
                        + b"\r\n")
    evento = parser.next_event()
    assert isinstance(evento, h11.Request)
    return Request({"type": "http", "headers": list(evento.headers)})


@pytest.mark.parametrize("antes,despues", [
    (b"", b""), (b"otra=a; ", b""), (b"otra=a;  ", b""),
    (b"otra=a;\t", b""), (b"otra=a; \t", b"; otra=b"), (b"", b"; otra=b"),
], ids=["canonica", "separador-sp", "separador-dos-sp", "separador-htab",
        "separador-ows", "cookie-posterior"])
def test_canonicas_y_separadores_http_conservan_secreto_y_digest(perfil, tipo, antes, despues):
    campo = antes + nombre(perfil, tipo) + b"=" + CANONICO + despues
    request = desde_http(campo)
    assert request.headers["cookie"].encode("latin-1") == campo
    leida = leer_cookie(request, perfil, tipo)
    extraidas = extraer_cookies(request, perfil)
    assert getattr(extraidas, tipo) == leida
    assert leida.get_secret_value().encode("ascii") == CANONICO
    assert digest_secreto(leida, CodigoSeguridad.SESION_INEXISTENTE) == hashlib.sha256(BRUTO).digest()
    assert CANONICO.decode() not in repr(extraidas) + repr(leida)


@pytest.mark.parametrize("ows", [b" ", b"\t", b"  ", b" \t"],
                         ids=["sp", "htab", "dos-sp", "sp-htab"])
def test_ows_exterior_retirado_por_h11_no_es_parte_del_secreto(perfil, tipo, ows):
    campo = nombre(perfil, tipo) + b"=" + CANONICO
    request = desde_http(ows + campo + ows)
    assert request.headers["cookie"].encode("latin-1") == campo
    assert leer_cookie(request, perfil, tipo).get_secret_value().encode() == CANONICO


@pytest.mark.parametrize("antes,despues", [
    (b"\xa0", b""), (b"", b"\xa0"), (b" ", b""), (b"", b" "),
    (b"\t", b""), (b"", b"\t"), (b"\x01", b""), (b"", b"\x01"),
    (b"\x7f", b""), (b"", b"\x7f"), (b"\xc2\xa0", b""), (b"", b"\xc2\xa0"),
], ids=["nbsp-inicial", "nbsp-final", "sp-inicial", "sp-final", "htab-inicial",
        "htab-final", "soh-inicial", "soh-final", "del-inicial", "del-final",
        "utf8-nbsp-inicial", "utf8-nbsp-final"])
def test_bytes_invalidos_preservados_por_h11_se_rechazan_sin_reparacion(
        perfil, tipo, antes, despues):
    # La cookie posterior impide confundir el sufijo del valor con OWS del campo.
    campo = nombre(perfil, tipo) + b"=" + antes + CANONICO + despues + b"; otra=a"
    request = desde_http(campo)
    assert request.headers["cookie"].encode("latin-1") == campo
    with pytest.raises(CookieAmbigua) as rechazo:
        extraer_cookies(request, perfil)
    assert CANONICO.decode() not in str(rechazo.value) + repr(rechazo.value)
    respuesta = respuesta_error(request, traducir_error(rechazo.value))
    assert respuesta.status_code == 500  # Traducción existente, sin catálogo nuevo.
    assert respuesta.headers["cache-control"] == "no-store"
    assert CANONICO not in respuesta.body
    assert "set-cookie" not in respuesta.headers


def test_nbsp_final_de_cabecera_original_no_se_convierte_en_credencial(perfil, tipo):
    campo = nombre(perfil, tipo) + b"=" + CANONICO + b"\xa0"
    request = desde_http(campo)
    assert request.headers["cookie"].encode("latin-1") == campo
    with pytest.raises(CookieAmbigua):
        leer_cookie(request, perfil, tipo)


@pytest.mark.parametrize("control", [b"\x00", b"\x0b", b"\x0c", b"\r"],
                         ids=["nul", "vtab", "form-feed", "cr"])
def test_controles_no_representables_se_rechazan_en_h11(perfil, tipo, control):
    with pytest.raises(h11.RemoteProtocolError):
        desde_http(nombre(perfil, tipo) + b"=" + CANONICO + control + b"; otra=a")


@pytest.mark.parametrize("forma", ["vacia", "sin-igual", "nombre-sp", "nombre-nbsp",
                                   "comillas", "sp-interior", "htab-interior", "porcentaje", "padding"])
def test_pares_malformados_no_se_normalizan(perfil, tipo, forma):
    clave = nombre(perfil, tipo)
    campo = {
        "vacia": clave + b"=", "sin-igual": clave, "nombre-sp": clave + b" =" + CANONICO,
        "nombre-nbsp": b"\xa0" + clave + b"=" + CANONICO,
        "comillas": clave + b'="' + CANONICO + b'"',
        "sp-interior": clave + b"=" + CANONICO[:10] + b" " + CANONICO[10:],
        "htab-interior": clave + b"=" + CANONICO[:10] + b"\t" + CANONICO[10:],
        "porcentaje": clave + b"=%41" + CANONICO[1:], "padding": clave + b"=" + CANONICO + b"=",
    }[forma]
    request = desde_http(campo + b"; otra=a")
    assert request.headers["cookie"].encode("latin-1") == campo + b"; otra=a"
    with pytest.raises(CookieAmbigua):
        extraer_cookies(request, perfil)


@pytest.mark.parametrize("forma", ["mismo-campo", "dos-campos", "duplicado-nbsp"])
def test_duplicados_no_se_reducen_a_una_cookie(perfil, tipo, forma):
    par = nombre(perfil, tipo) + b"=" + CANONICO
    campos = (par, par) if forma == "dos-campos" else (
        par + b"; " + par + (b"\xa0" if forma == "duplicado-nbsp" else b""),)
    with pytest.raises(CookieAmbigua):
        extraer_cookies(desde_http(*campos), perfil)


@pytest.mark.parametrize("forma", ["mismo-campo", "dos-campos", "otro-tipo", "invalida"])
def test_perfiles_mezclados_no_se_convierten_en_solicitud_valida(perfil, tipo, forma):
    otro = next(p for p in PERFILES.values() if p != perfil)
    otro_tipo = ("contexto" if tipo == "sesion" else "sesion") if forma == "otro-tipo" else tipo
    par = nombre(perfil, tipo) + b"=" + CANONICO
    ajena = nombre(otro, otro_tipo) + b"=" + OTRO + (b"\xa0" if forma == "invalida" else b"")
    campos = (par, ajena) if forma == "dos-campos" else (par + b"; " + ajena,)
    with pytest.raises(CookieAmbigua):
        extraer_cookies(desde_http(*campos), perfil)


def test_base64_no_canonica_con_mismos_bytes_no_se_repara_en_digest(perfil, tipo):
    alfabeto = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    variante = CANONICO[:-1] + bytes([alfabeto[alfabeto.index(CANONICO[-1]) ^ 1]])
    assert base64.urlsafe_b64decode(variante + b"=") == BRUTO
    leida = leer_cookie(desde_http(nombre(perfil, tipo) + b"=" + variante), perfil, tipo)
    # El lector conserva la representación; el validador canónico existente la rechaza.
    assert leida.get_secret_value().encode() == variante
    with pytest.raises(ErrorSeguridad):
        digest_secreto(leida, CodigoSeguridad.SESION_INEXISTENTE)


@pytest.mark.parametrize("separador", [b"; ", b";\t", b";  "])
def test_sesion_y_contexto_mantienen_su_asociacion(perfil, separador):
    request = desde_http(nombre(perfil, "sesion") + b"=" + CANONICO + separador
                         + nombre(perfil, "contexto") + b"=" + OTRO)
    cookies = extraer_cookies(request, perfil)
    assert cookies.sesion.get_secret_value().encode() == CANONICO
    assert cookies.contexto.get_secret_value().encode() == OTRO
