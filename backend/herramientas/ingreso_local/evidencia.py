"""IP observada por ingreso Node, autenticada y ligada a una petición.

No basta SEC-01B, loopback o una dirección declarada. El productor confiable
posee otra clave efímera y observa el socket original. Solo perfil testing propio.
"""

import base64
from collections.abc import Callable
import hashlib
import hmac
import json
import re
from threading import Lock
import time

from fastapi import Request
from pydantic import SecretBytes

from app.api.dependencias_auth import obtener_intermediario
from app.configuracion import Configuracion
from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.proxies import IpVerificada, ServicioIpConfiable, ip_canonica
from app.seguridad.transacciones import CodigoSeguridad as C, ErrorSeguridad

CABECERA = "x-synapdesk-ingress-evidence"
CONTROLES = ("cookie", "origin", "sec-fetch-site", "x-csrf-token")
DOMINIO = b"synapdesk:ingreso-local:v1\x00"


def exigir_testing_propio(config: Configuracion) -> None:
    if (config.app_env != "testing" or config.postgres_host not in {"127.0.0.1", "localhost", "::1"}
            or config.postgres_port != 5433
            or not re.fullmatch(r"synapdesk_auth07_sec01a_[a-f0-9]{32}", config.postgres_db or "")
            or config.auth_bootstrap is None or config.auth_bootstrap.perfil != "ensayo"):
        raise ErrorSeguridad(C.INFRAESTRUCTURA)


def huella_controles(request: Request) -> str:
    datos = [[nombre, [v.decode("latin-1") for k, v in request.scope["headers"]
              if k.lower() == nombre.encode("ascii")]] for nombre in CONTROLES]
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class VerificadorIngresoLocal:
    def __init__(self, config: Configuracion, clave: SecretBytes, audiencia: str, *,
                 ventana_segundos: int, capacidad_nonces: int,
                 reloj: Callable[[], float] = time.time) -> None:
        exigir_testing_propio(config)
        if (type(clave) is not SecretBytes or len(clave.get_secret_value()) != 32
                or not re.fullmatch(r"[a-f0-9]{32}", audiencia)
                or type(ventana_segundos) is not int or not 1 <= ventana_segundos <= 60
                or type(capacidad_nonces) is not int or not 1 <= capacidad_nonces <= 10000
                or hmac.compare_digest(clave.get_secret_value(), config.obtener_clave_hmac())):
            raise ErrorSeguridad(C.INFRAESTRUCTURA)
        self._config = config.model_copy(deep=True)
        self._clave = clave
        self._audiencia = audiencia
        self._ventana = ventana_segundos
        self._capacidad = capacidad_nonces
        self._reloj = reloj
        self._nonces: dict[str, int] = {}
        self._lock = Lock()
        self.estadisticas: dict[str, int] = {}
        self._ips = ServicioIpConfiable(config, ServicioIdentificadores(config))

    def __call__(self, request: Request) -> IpVerificada:
        fase = "configuracion"
        try:
            if request.app.state.configuracion != self._config:
                raise ValueError
            fase = "servicio"
            obtener_intermediario(request)  # Credencial/canal independientes de la evidencia IP.
            fase = "cabeceras"
            if any(k.lower() in {b"x-synapdesk-client-ip", b"x-synapdesk-ip-source"}
                   for k, _ in request.scope["headers"]):
                raise ValueError
            valores = request.headers.getlist(CABECERA)
            if len(valores) != 1 or len(valores[0]) > 2048:
                raise ValueError
            codificado, firma = valores[0].split(".")
            fase = "firma"
            if not re.fullmatch(r"[A-Za-z0-9_-]+", codificado) or not re.fullmatch(r"[a-f0-9]{64}", firma):
                raise ValueError
            esperada = hmac.digest(self._clave.get_secret_value(), DOMINIO + codificado.encode("ascii"), "sha256").hex()
            if not hmac.compare_digest(esperada, firma):
                raise ValueError
            raw = base64.urlsafe_b64decode(codificado + "=" * (-len(codificado) % 4))
            if base64.urlsafe_b64encode(raw).decode().rstrip("=") != codificado:
                raise ValueError
            datos = json.loads(raw)
            fase = "vinculo_peticion"
            if (type(datos) is not dict or set(datos) != {"v", "aud", "ip", "ts", "nonce", "method", "path", "controls"}
                    or type(datos["v"]) is not int or datos["v"] != 1
                    or datos["aud"] != self._audiencia or type(datos["ts"]) is not int
                    or type(datos["nonce"]) is not str or not re.fullmatch(r"[a-f0-9]{32}", datos["nonce"])
                    or type(datos["ip"]) is not str or str(ip_canonica(datos["ip"])) != datos["ip"]
                    or datos["method"] != request.method
                    or datos["path"] != (request.scope.get("raw_path", b"").decode("ascii")
                        + ("?" + request.scope["query_string"].decode("ascii") if request.scope.get("query_string") else ""))
                    or not hmac.compare_digest(str(datos["controls"]), huella_controles(request))):
                raise ValueError
            ahora = self._reloj()
            fase = "tiempo"
            if not datos["ts"] <= ahora < datos["ts"] + self._ventana:
                raise ValueError
            # Peer real sin proxy_headers; su pertenencia no basta sin firma.
            fase = "peer"
            ip = self._ips.identificar(par_transporte=request.client.host if request.client else None,
                valores_ip_cliente=[datos["ip"]])
            with self._lock:
                fase = "nonce"
                self._nonces = {n: exp for n, exp in self._nonces.items() if exp > ahora}
                if datos["nonce"] in self._nonces or len(self._nonces) >= self._capacidad:
                    raise ValueError
                self._nonces[datos["nonce"]] = datos["ts"] + self._ventana
                self.estadisticas["aceptada"] = self.estadisticas.get("aceptada", 0) + 1
            return ip
        except ErrorSeguridad:
            with self._lock:
                self.estadisticas[fase] = self.estadisticas.get(fase, 0) + 1
            raise
        except (ValueError, TypeError, KeyError, UnicodeError):
            with self._lock:
                self.estadisticas[fase] = self.estadisticas.get(fase, 0) + 1
            raise ErrorSeguridad(C.IP_NO_VERIFICABLE) from None
