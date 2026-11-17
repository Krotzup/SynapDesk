"""Altas AUTH-07C.2B y regresiones en una base temporal exclusiva de 5433."""

import sys

from validar_bootstrap_csrf import validar


if __name__ == "__main__":
    sys.exit(validar(nombre_reporte="auth07c2b-usuarios-validacion.json"))
