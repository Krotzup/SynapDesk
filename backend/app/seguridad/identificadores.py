import hashlib
import hmac
from ipaddress import ip_address

from app.configuracion import Configuracion
from app.seguridad.cuentas import normalizar_cuenta


class ServicioIdentificadores:
    """HMAC de 32 bytes; el llamador acredita la IP, nunca este componente.

    Cada instancia usa una sola clave. Su identificador permite al futuro
    coordinador distinguir versiones; no rota ni busca claves automáticamente.
    """

    def __init__(self, configuracion: Configuracion) -> None:
        self._clave = configuracion.obtener_clave_hmac()
        self.id_clave = configuracion.auth_hmac_id_clave

    def _derivar(self, dominio: bytes, valor: str) -> bytes:
        mensaje = b"synapdesk:auth:v1\x00" + dominio + b"\x00" + valor.encode("utf-8")
        return hmac.digest(self._clave, mensaje, hashlib.sha256)

    def cuenta(self, cuenta: str) -> bytes:
        return self._derivar(b"cuenta", normalizar_cuenta(cuenta))

    def ip_verificada(self, direccion: str) -> bytes:
        # No recibe Request ni inspecciona cabeceras. Sin puertos/CIDR/zone IDs.
        if not isinstance(direccion, str) or "%" in direccion:
            raise ValueError("La IP verificada no tiene una representación válida.")
        try:
            ip = ip_address(direccion)
        except ValueError:
            raise ValueError("La IP verificada no tiene una representación válida.") from None
        # IPv4 mapeada en IPv6 representa la misma IP para esta derivación.
        mapeada = getattr(ip, "ipv4_mapped", None)
        canonica = str(mapeada if mapeada is not None else ip)
        return self._derivar(b"ip", canonica)
