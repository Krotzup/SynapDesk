"""Regresión AUTH-07C.1B exclusivamente en base temporal de localhost:5433."""

import sys

from validar_bootstrap_csrf import validar


if __name__ == "__main__":
    sys.exit(validar(nombre_reporte="auth07c1b-bootstrap-validacion.json"))
