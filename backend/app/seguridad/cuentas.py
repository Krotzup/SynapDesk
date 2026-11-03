def normalizar_cuenta(valor: str) -> str:
    """Comparte la normalización de Usuario; no sustituye validar el correo."""
    if not isinstance(valor, str):
        raise ValueError("La cuenta debe ser texto no vacío compatible con PostgreSQL.")
    cuenta = valor.strip().lower()
    try:
        cuenta.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("La cuenta debe ser texto no vacío compatible con PostgreSQL.") from None
    if not cuenta or "\x00" in cuenta:
        raise ValueError("La cuenta debe ser texto no vacío compatible con PostgreSQL.")
    return cuenta
