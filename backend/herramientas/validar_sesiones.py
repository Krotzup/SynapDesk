"""Regresión AUTH-07B.3 en base exclusiva local:5433; preserva informes previos."""

import sys

from validar_bootstrap_csrf import validar


if __name__ == "__main__":
    sys.exit(validar(nombre_reporte="auth07b3-sesiones-validacion.json"))
