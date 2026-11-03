import base64
import binascii
import hashlib
import secrets

from pydantic import SecretStr

from app.seguridad.transacciones import CodigoSeguridad, ErrorSeguridad


def generar_secreto(longitud: int = 32) -> SecretStr:
    return SecretStr(base64.urlsafe_b64encode(secrets.token_bytes(longitud)).decode("ascii").rstrip("="))


def digest_secreto(credencial: str | SecretStr, error: CodigoSeguridad) -> bytes:
    valor = credencial.get_secret_value() if isinstance(credencial, SecretStr) else credencial
    if not isinstance(valor, str):
        raise ErrorSeguridad(error)
    try:
        bruto = base64.b64decode(valor + "=" * (-len(valor) % 4), altchars=b"-_", validate=True)
        if len(bruto) < 32 or base64.urlsafe_b64encode(bruto).decode("ascii").rstrip("=") != valor:
            raise ValueError
    except (ValueError, binascii.Error):
        raise ErrorSeguridad(error) from None
    return hashlib.sha256(bruto).digest()
