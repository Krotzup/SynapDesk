"""Arranque explícito: python -m herramientas.arnes_http_seguro.ejecutar.

No modifica frontend, app, entorno privado o confianza global. Usa dependencias
ya instaladas. Las sondas no emiten credenciales HTTP ni acreditan IP.
"""

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from time import monotonic, sleep
from uuid import uuid4

from sqlalchemy.orm import Session

from app.seguridad.csrf import ServicioCsrf
from app.seguridad.secretos import generar_secreto
from app.seguridad.transacciones import transaccion_seguridad
from pruebas.intermediario_auxiliar import credencial, politica
from pruebas.login_auxiliar import configuracion_login
from .aplicacion_ensayo import ORIGEN, crear_ensayo
from .infraestructura import (
    BACKEND, REPO, PR30, PR32, base_propia, borrar_temporal,
    certificados, detener, listener, puerto_libre,
)


def escribir_json(path, datos):
    path.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)


def entorno_node():
    env = os.environ.copy()
    for nombre in ("NODE_TLS_REJECT_UNAUTHORIZED", "NODE_EXTRA_CA_CERTS", "NODE_OPTIONS"):
        env.pop(nombre, None)
    env["NODE_PATH"] = str(REPO / "frontend/node_modules")
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    return env


@contextmanager
def next_real(carpeta, control, perfil, evidencia, secretos):
    node = shutil.which("node")
    assert node, "Se requiere Node.js instalado."
    proyecto = carpeta / ("next-" + perfil)
    proyecto.mkdir()
    datos = dict(control, project=str(proyecto))
    privado = carpeta / ("control-" + perfil + ".json")
    escribir_json(privado, datos)
    herramienta = Path(__file__).parent
    preparado = subprocess.run([node, str(herramienta / "preparar_next.mjs"), str(privado)],
        env=entorno_node(), cwd=BACKEND, capture_output=True, timeout=30)
    assert preparado.returncode == 0, "No se preparó la aplicación Next de ensayo."
    evidencia.setdefault("next_preparation", []).append(json.loads(preparado.stdout))
    port = puerto_libre()
    env = entorno_node()
    env.update(BACKEND_INTERNAL_URL=control["backend"],
        AUTH_COOKIE_PROFILE="production" if perfil == "production" else "local", HARNESS_PRIVATE_FILE=str(privado))
    if perfil != "untrusted":
        env["NODE_EXTRA_CA_CERTS"] = str(carpeta / "ca.pem")
    log = carpeta / ("next-" + perfil + ".log")
    with log.open("wb") as salida:
        proceso = subprocess.Popen([node, str(REPO / "frontend/node_modules/next/dist/bin/next"),
            "dev", "--webpack", "--hostname", "127.0.0.1", "--port", str(port), str(proyecto)],
            cwd=proyecto, env=env, stdout=salida, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            limite = monotonic() + 55
            listo = False
            while proceso.poll() is None and monotonic() < limite:
                cliente = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                try:
                    cliente.request("GET", "/ensayo-listo")
                    r = cliente.getresponse()
                    listo = r.status == 200 and json.loads(r.read()).get("harness") == control["identity"]
                    if listo:
                        break
                except (OSError, ValueError, http.client.HTTPException):
                    pass
                finally:
                    cliente.close()
                sleep(0.1)
            assert listo, "Next.js no completó su arranque aislado."
            evidencia.setdefault("next_processes", []).append(dict(pid=proceso.pid, profile=perfil, port=port))
            yield "http://127.0.0.1:" + str(port), privado
        finally:
            detener(proceso)
    contenido = log.read_text(encoding="utf-8", errors="replace")
    assert not any(s and s in contenido for s in secretos), "Un secreto apareció en el log de ensayo."
    evidencia.setdefault("next_stopped", []).append(dict(profile=perfil, pid=proceso.pid,
        stopped=proceso.poll() is not None, log_without_secrets=True))


def fuentes_pr(carpeta, evidencia):
    fuentes = {
        "frontend/src/lib/backend-proxy.ts": "lib/backend-proxy.js",
        "frontend/src/lib/transport/server.ts": "lib/transport/server.js",
        "frontend/src/app/api/v1/[...path]/route.ts": "app/api/v1/[...path]/route.js",
    }
    salida = {}
    evidencia["pr30_sources"] = []
    for i, (nombre, destino) in enumerate(fuentes.items()):
        raw = subprocess.check_output(["git", "show", PR30 + ":" + nombre], cwd=REPO)
        path = carpeta / ("original-" + str(i) + ".ts")
        path.write_bytes(raw)
        salida[str(path)] = destino
        evidencia["pr30_sources"].append(dict(path=nombre, sha256=hashlib.sha256(raw).hexdigest(),
            git_blob=subprocess.check_output(["git", "rev-parse", PR30 + ":" + nombre], cwd=REPO,
                                              text=True).strip()))
    return salida


def ejecutar(nombre_reporte="auth07d2-arnes.json"):
    if not re.fullmatch(r"auth07d2-arnes(?:-[a-z0-9]+)?\.json", nombre_reporte):
        raise ValueError("Nombre de evidencia de arnés inválido.")
    reporte = REPO / "docs/auditorias" / nombre_reporte
    if reporte.exists():
        raise ValueError("La evidencia ya existe; elija un nombre nuevo.")
    carpeta = BACKEND / (".arnes-auth07d2-" + uuid4().hex)
    carpeta.mkdir()
    evidencia = dict(task="SYNAPDESK-AUTH07D2-LOCAL-END-TO-END-SECURE-HARNESS",
        pr30_head=PR30, pr32_head=PR32, harness_results=[], client_ip_render="NO_ACREDITADA",
        client_ip_local="Socket del ingreso local; no propagado ni convertido en IpVerificada",
        node_version=subprocess.check_output(["node", "--version"], text=True).strip(),
        production_routes_enabled=False)
    try:
        certificados(carpeta)
        fuentes = fuentes_pr(carpeta, evidencia)
        tokens = [credencial(), credencial()]
        config = configuracion_login(auth_intermediario=politica(tokens), auth_origenes_permitidos=[ORIGEN])
        secreto_cookie = generar_secreto()
        secretos = dict(cookie=secreto_cookie)
        with base_propia(carpeta, evidencia) as (motor, nombre):
            pares = []
            for antiguo in (False, True):
                reloj = (lambda db: datetime.now(UTC) - timedelta(hours=1)) if antiguo else None
                with Session(motor) as db, transaccion_seguridad(db):
                    servicio = ServicioCsrf(db, config, reloj) if reloj else ServicioCsrf(db, config)
                    contexto = servicio.crear_anonimo()
                    token = servicio.emitir_token(anonimo=contexto.secreto)
                pares.append((contexto.secreto.get_secret_value(), token.token.get_secret_value()))
            identidad = uuid4().hex
            app = crear_ensayo(config, motor, nombre, secretos, identidad)
            with listener(app, carpeta, evidencia) as puerto:
                control = dict(repo=str(REPO), sources=fuentes, identity=identidad,
                    backend=f"https://localhost:{puerto}", unavailable=f"https://localhost:{puerto_libre()}", ca=str(carpeta / "ca.pem"),
                    origin=ORIGEN, tokens=[t.get_secret_value() for t in tokens],
                    wrong=credencial().get_secret_value(), cookie=secreto_cookie.get_secret_value(),
                    context=pares[0][0], csrf=pares[0][1], expiredContext=pares[1][0], expiredCsrf=pares[1][1])
                ocultos = [*control["tokens"], control["wrong"], control["cookie"], *pares[0], *pares[1]]
                for perfil in ("local", "production", "unavailable", "hostname", "untrusted"):
                    print("EJECUTANDO Node/Next/FastAPI TLS: " + perfil, flush=True)
                    escenario = control.copy()
                    if perfil == "unavailable":
                        escenario["backend"] = control["unavailable"]
                    elif perfil == "hostname":
                        escenario["backend"] = control["backend"].replace("localhost", "127.0.0.1")
                    with next_real(carpeta, escenario, perfil, evidencia, ocultos) as (url, privado):
                        datos = json.loads(privado.read_text(encoding="utf-8"))
                        datos["next"] = url
                        escribir_json(privado, datos)
                        resultado = subprocess.run([shutil.which("node"), str(Path(__file__).parent / "casos_node.mjs"),
                            str(privado), perfil], env=entorno_node(), cwd=BACKEND,
                            capture_output=True, timeout=200)
                        assert not any(s.encode() in resultado.stdout + resultado.stderr for s in ocultos)
                        fase = json.loads(resultado.stdout)
                        evidencia["harness_results"].extend(fase["results"])
                        reporte.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        print(json.dumps(dict(profile=perfil, passed=fase["passed"], failed=fase["failed"])), flush=True)
        evidencia["passed"] = sum(r["passed"] for r in evidencia["harness_results"])
        evidencia["failed"] = sum(not r["passed"] for r in evidencia["harness_results"])
    except Exception as error:
        evidencia["error_type"] = type(error).__name__
        # No serializar excepción del driver, configuración, solicitudes o secretos.
        print("Arnés interrumpido: " + type(error).__name__, flush=True)
    finally:
        evidencia["passed"] = sum(r["passed"] for r in evidencia["harness_results"])
        evidencia["failed"] = sum(not r["passed"] for r in evidencia["harness_results"])
        try:
            borrar_temporal(carpeta)
        except Exception as error:
            evidencia["cleanup_error_type"] = type(error).__name__
        evidencia["temporary_files_deleted"] = not carpeta.exists()
        evidencia["temporary_path"] = str(carpeta)
        reporte.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if (evidencia.get("passed", 0) and not evidencia.get("failed")
                 and not evidencia.get("error_type") and not evidencia.get("cleanup_error_type")) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reporte", default="auth07d2-arnes.json")
    args = parser.parse_args()
    raise SystemExit(ejecutar(args.reporte))
