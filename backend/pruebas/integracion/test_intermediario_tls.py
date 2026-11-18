"""Conexiones TLS reales a Uvicorn; no certifican despliegue ni IP Render."""

import http.client
import shutil
import socket
import ssl
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn

from app.aplicacion import crear_aplicacion
from app.api.dependencias_auth import IntermediarioHttp
from pruebas.intermediario_auxiliar import cabeceras, configuracion, credencial


@pytest.fixture(scope="module")
def certificado(tmp_path_factory):
    openssl = shutil.which("openssl")
    if openssl is None:
        # Git for Windows puede no exponer sus herramientas Unix en PATH.
        git = shutil.which("git")
        candidato = Path(git).resolve().parents[1] / "usr/bin/openssl.exe" if git else Path("no-existe")
        openssl = str(candidato) if candidato.is_file() else None
    assert openssl, "Las pruebas de TLS real requieren OpenSSL (incluido con Git for Windows)."
    carpeta = tmp_path_factory.mktemp("tls-intermediario")
    clave, cert = carpeta / "efimera.key", carpeta / "efimero.crt"
    resultado = subprocess.run([
        openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
        "-keyout", str(clave), "-out", str(cert),
    ], capture_output=True, timeout=30)
    assert resultado.returncode == 0, "No se pudo crear el certificado efímero de prueba."
    try:
        yield clave, cert
    finally:
        clave.unlink(missing_ok=True)
        cert.unlink(missing_ok=True)


@contextmanager
def listener(config, certificado=None, *, proxy_headers=False):
    app = crear_aplicacion(config)

    @app.get("/ensayo-servicio")
    def ensayo(identidad: IntermediarioHttp):
        return {"servicio": identidad.servicio}

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    argumentos = {} if certificado is None else dict(
        ssl_keyfile=str(certificado[0]), ssl_certfile=str(certificado[1]))
    servidor = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                                           proxy_headers=proxy_headers, **argumentos))
    hilo = Thread(target=servidor.run, kwargs={"sockets": [sock]}, daemon=True)
    try:
        hilo.start()
        limite = monotonic() + 10
        while not servidor.started and hilo.is_alive() and monotonic() < limite:
            sleep(0.01)
        assert servidor.started, "El listener de prueba no arrancó."
        yield sock.getsockname()[1]
    finally:
        servidor.should_exit = True
        hilo.join(timeout=10)
        sock.close()
        assert not hilo.is_alive(), "El listener de prueba no se cerró."


def pedir(puerto, headers, *, contexto=None, host="localhost", ruta="/ensayo-servicio"):
    cliente = (http.client.HTTPSConnection(host, puerto, context=contexto, timeout=5)
               if contexto else http.client.HTTPConnection(host, puerto, timeout=5))
    try:
        cliente.putrequest("GET", ruta)
        for nombre, valor in headers:
            cliente.putheader(nombre, valor)
        cliente.endheaders()
        respuesta = cliente.getresponse()
        return respuesta.status, dict(respuesta.getheaders()), respuesta.read().decode()
    finally:
        cliente.close()


def test_tls_real_credenciales_duplicados_concurrencia_y_csrf_cerrado(certificado):
    token = credencial()
    contexto = ssl.create_default_context(cafile=str(certificado[1]))
    headers = list(cabeceras(token).items())
    with listener(configuracion([token]), certificado) as puerto:
        assert pedir(puerto, headers, contexto=contexto)[0] == 200
        assert pedir(puerto, [], contexto=contexto)[0] == 503
        assert pedir(puerto, list(cabeceras(credencial()).items()), contexto=contexto)[0] == 503
        assert pedir(puerto, headers + [("Authorization", headers[0][1])], contexto=contexto)[0] == 503
        estado, respuesta, cuerpo = pedir(puerto, headers, contexto=contexto, ruta="/api/v1/auth/csrf")
        assert estado == 503 and respuesta["cache-control"] == "no-store"
        assert token.get_secret_value() not in cuerpo
        assert "set-cookie" not in respuesta
        with ThreadPoolExecutor(max_workers=8) as grupo:
            resultados = list(grupo.map(lambda _: pedir(puerto, headers, contexto=contexto)[0], range(16)))
        assert resultados == [200] * 16


def test_cliente_tls_verifica_ca_y_hostname(certificado):
    token = credencial()
    with listener(configuracion([token]), certificado) as puerto:
        with pytest.raises(ssl.SSLCertVerificationError):
            pedir(puerto, list(cabeceras(token).items()), contexto=ssl.create_default_context())
        with pytest.raises(ssl.SSLCertVerificationError):
            pedir(puerto, list(cabeceras(token).items()), host="127.0.0.1",
                  contexto=ssl.create_default_context(cafile=str(certificado[1])))


@pytest.mark.parametrize("proxy_headers", [False, True])
def test_http_real_no_acepta_loopback_ni_scheme_falsificado(proxy_headers):
    token = credencial()
    with listener(configuracion([token]), proxy_headers=proxy_headers) as puerto:
        headers = list(cabeceras(token).items())
        assert pedir(puerto, headers)[0] == 503
        assert pedir(puerto, headers + [("X-Forwarded-Proto", "https")])[0] == 503
