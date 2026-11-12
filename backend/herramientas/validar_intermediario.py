"""Regresión SEC-01B sin sobrescribir la evidencia histórica de SEC-01A.

Reutiliza el creador/validador de bases exclusivas y su prefijo SEC-01A,
requerido por los fixtures de commits reales. Solo usa localhost:5433.
"""

import sys

from validar_bootstrap_csrf import validar


if __name__ == "__main__":
    sys.exit(validar(nombre_reporte="auth07-sec01b-validacion.json"))
