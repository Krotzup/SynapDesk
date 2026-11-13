"""Regresión AUTH-07B.2 en base exclusiva local:5433, sin tocar informes SEC-01B."""

import sys

from validar_bootstrap_csrf import validar


if __name__ == "__main__":
    sys.exit(validar(nombre_reporte="auth07b2-login-validacion.json"))
