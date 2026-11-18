"""El comando documentado y CI deben descubrir juntas ambas suites."""

from collections import defaultdict
from pathlib import Path
import subprocess
import sys


def test_recoleccion_completa_sin_colisiones():
    backend = Path(__file__).resolve().parents[1]
    resultado = subprocess.run(
        [sys.executable, "-m", "pytest", "pruebas", "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        cwd=backend, capture_output=True, text=True, timeout=60,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    recolectados = {linea.split("::")[0].replace("\\", "/")
                   for linea in resultado.stdout.splitlines() if "::" in linea}
    nombres = defaultdict(set)
    for ruta in (backend / "pruebas").rglob("test_*.py"):
        nombres[ruta.name].add(ruta.relative_to(backend).as_posix())
    duplicados = set().union(*(rutas for rutas in nombres.values() if len(rutas) > 1))
    assert duplicados  # La regresión conserva el escenario que originó el fallo.
    assert duplicados <= recolectados
