"""Primitiva de un solo salto, sin elegir una topología de despliegue."""

from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network
from typing import TYPE_CHECKING

from app.seguridad.identificadores import ServicioIdentificadores
from app.seguridad.origenes import ErrorConfiguracionSeguridad
from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad

if TYPE_CHECKING:
    from app.configuracion import Configuracion


def ip_canonica(valor: str) -> IPv4Address | IPv6Address:
    if not isinstance(valor, str) or "%" in valor:
        raise ValueError("Dirección IP inválida.")
    try:
        ip = ip_address(valor)
    except ValueError:
        raise ValueError("Dirección IP inválida.") from None
    return getattr(ip, "ipv4_mapped", None) or ip


def redes_autorizadas(valores: list[str]):
    redes = []
    try:
        for valor in valores:
            if not isinstance(valor, str) or "%" in valor:
                raise ValueError
            red = ip_network(valor, strict=True)
            if red.prefixlen == 0 or red.is_multicast or red.is_unspecified:
                raise ValueError
            # Evita políticas distintas para IPv4 y su representación mapeada.
            if isinstance(red.network_address, IPv6Address) and red.network_address.ipv4_mapped:
                raise ValueError
            redes.append(red)
    except ValueError:
        raise ErrorConfiguracionSeguridad("La lista de proxies autorizados es inválida.") from None
    return tuple(redes)


@dataclass(frozen=True)
class IpVerificada:
    digest: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.digest, bytes) or len(self.digest) != 32:
            raise ValueError("Identificador de IP inválido.")


class ServicioIpConfiable:
    def __init__(self, configuracion: "Configuracion", identificadores: ServicioIdentificadores) -> None:
        self._redes = redes_autorizadas(configuracion.auth_proxies_autorizados)
        self._identificadores = identificadores

    def identificar(self, *, par_transporte: str | None,
                    valores_ip_cliente: tuple[str, ...] | list[str] | None) -> IpVerificada:
        """El adaptador futuro acredita el peer REAL y metadato reconstruido.

        No pasar Request.client si el servidor lo reescribió desde forwarded headers.
        No se interpreta X-Forwarded-For ni se aceptan cadenas de varios saltos.
        """
        try:
            par = ip_canonica(par_transporte)
            if not any(par in red for red in self._redes):
                raise ValueError
            if not isinstance(valores_ip_cliente, (tuple, list)) or len(valores_ip_cliente) != 1:
                raise ValueError
            cliente = ip_canonica(valores_ip_cliente[0])
        except ValueError:
            raise ErrorSeguridad(CodigoSeguridad.IP_NO_VERIFICABLE) from None
        return IpVerificada(self._identificadores.ip_verificada(str(cliente)))
