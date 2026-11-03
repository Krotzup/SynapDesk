"""Origin público estricto; sin Request, Host ni cabeceras de proxy."""

import re
from ipaddress import ip_address
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad

if TYPE_CHECKING:
    from app.configuracion import Configuracion


class ErrorConfiguracionSeguridad(ValueError):
    """Error de configuración del servidor, distinto de un rechazo de cliente."""


def origen_canonico(valor: str) -> tuple[str, str, int]:
    # No permitir que urlsplit elimine controles o interprete rutas/credenciales.
    if not isinstance(valor, str) or not re.fullmatch(
        r"https?://(?:\[[0-9a-fA-F:]+\]|[A-Za-z0-9.-]+)(?::[1-9][0-9]{0,4})?",
        valor, re.IGNORECASE | re.ASCII,
    ):
        raise ValueError("Origen inválido.")
    try:
        partes = urlsplit(valor)
        host = partes.hostname
        puerto = partes.port
        if host is None:
            raise ValueError
        if ":" in host or re.fullmatch(r"[0-9.]+", host):
            host = str(ip_address(host))
        elif any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", etiqueta)
                 for etiqueta in host.split(".")) or len(host) > 253:
            raise ValueError
    except ValueError:
        raise ValueError("Origen inválido.") from None
    return partes.scheme.lower(), host, puerto or (443 if partes.scheme.lower() == "https" else 80)


def validar_origenes_configurados(valores: list[str]) -> list[str]:
    try:
        canonicos = [origen_canonico(valor) for valor in valores]
        if len(set(canonicos)) != len(canonicos):
            raise ValueError
    except ValueError:
        raise ErrorConfiguracionSeguridad("La lista de orígenes de autenticación es inválida.") from None
    return valores


class ServicioOrigen:
    def __init__(self, configuracion: "Configuracion") -> None:
        valores = validar_origenes_configurados(configuracion.auth_origenes_permitidos)
        if not valores:
            raise ErrorConfiguracionSeguridad("Falta configurar los orígenes de autenticación.")
        self._permitidos = frozenset(origen_canonico(valor) for valor in valores)

    def validar(self, valores: tuple[str, ...] | list[str] | None) -> None:
        """Recibe TODAS las ocurrencias originales, sin unirlas ni tomar la primera."""
        if not isinstance(valores, (tuple, list)) or len(valores) != 1:
            raise ErrorSeguridad(CodigoSeguridad.ORIGIN_INVALIDO)
        try:
            origen = origen_canonico(valores[0])
        except ValueError:
            raise ErrorSeguridad(CodigoSeguridad.ORIGIN_INVALIDO) from None
        if origen not in self._permitidos:
            raise ErrorSeguridad(CodigoSeguridad.ORIGIN_INVALIDO)
