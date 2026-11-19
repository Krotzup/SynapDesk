"""Aplicación local real y aislada. No habilita app.aplicacion ni producción.

python -m herramientas.ingreso_local.demo --frontend RUTA --reporte RUTA
Agregar --browser-driver RUTA para ejecutar la comprobación de navegador.
Sin driver mantiene la aplicación abierta hasta Enter y conserva credenciales
de prueba solo en un archivo privado temporal, nunca en la salida.
"""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
from time import monotonic, sleep
from uuid import UUID, uuid4

from pydantic import SecretBytes
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.api.cookies_auth import preparar_perfil
from app.configuracion import Configuracion
from app.persistencia.entornos import seleccionar_configuracion_bd
from app.persistencia.modelos import Sesion, Usuario, Ticket, EventoAutenticacion
from app.seguridad.contrasenas import ServicioContrasenas
from app.seguridad.transacciones import transaccion_seguridad
from app.tickets.esquemas import TicketCreate
from app.tickets.repositorio import RepositorioTickets
from herramientas.arnes_http_seguro.infraestructura import (
    BACKEND, base_propia, borrar_temporal, certificados, detener, listener, puerto_libre,
)
from herramientas.ingreso_local.aplicacion import crear_aplicacion_local
from herramientas.ingreso_local.evidencia import VerificadorIngresoLocal
from pruebas.intermediario_auxiliar import credencial, politica
from pruebas.login_auxiliar import configuracion_login


def escribir(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)


def comprobar_punto_sql(motor, solicitud, cuentas, evidencia):
    """Solo el supervisor del ensayo accede a SQL; Edge no recibe credenciales BD."""
    cuenta = next(c for c in cuentas if c["role"] == solicitud["role"])
    fase = solicitud["phase"]
    with Session(motor) as db:
        fila = db.get(Ticket, UUID(solicitud["ticketId"]))
        assert fila is not None and str(fila.creado_por_id) == cuenta["id"]
        assert fila.titulo == solicitud["title"] and fila.descripcion == solicitud["description"]
        assert fila.estado == solicitud["status"]
        assert db.scalar(select(func.count(Ticket.id)).where(Ticket.titulo == fila.titulo)) == 1
        evidencia.setdefault("sql_checkpoints", []).append(dict(role=cuenta["role"], phase=fase,
            ticket_id=str(fila.id), status=fila.estado, unique_row=True))
        if fase == "logged_out":
            sesiones = list(db.scalars(select(Sesion).where(Sesion.usuario_id == UUID(cuenta["id"]))))
            assert len(sesiones) == 1 and sesiones[0].revocada_en is not None
            evidencia["sql_checkpoints"][-1]["session_revoked"] = True
        elif fase == "revoke":
            db.execute(update(Sesion).where(Sesion.usuario_id == UUID(cuenta["id"])).values(
                revocada_en=func.clock_timestamp(), motivo_revocacion="individual"))
            db.commit()
        elif fase == "deactivate":
            db.execute(update(Usuario).where(Usuario.id == UUID(cuenta["id"])).values(activo=False))
            db.commit()
        else:
            assert fase in {"created", "updated", "reloaded", "negative_unchanged"}


@contextmanager
def next_local(frontend, carpeta, control, evidencia, ocultos):
    node = shutil.which("node")
    if not node or not (frontend / "node_modules/next/package.json").is_file():
        raise ValueError("Next y Node deben estar instalados en la copia de integración.")
    if (frontend / "src/lib/backend-proxy.ts").read_text(encoding="utf-8").find("part.trim()") >= 0:
        raise ValueError("El transporte todavía normaliza cookies: usar la corrección estricta.")
    rutas = ["src/lib/backend-proxy.ts", "src/lib/api.ts", "src/lib/csrf.ts",
        "src/lib/transport/client.ts", "src/lib/transport/server.ts", "src/services/auth.ts",
        "src/services/tickets.ts", "src/app/api/v1/[...path]/route.ts",
        "src/app/api/local/csrf/route.ts", "src/components/auth/LoginForm.tsx",
        "src/components/tickets/TicketStatusControl.tsx", "src/app/(dashboard)/layout.tsx",
        "src/app/(dashboard)/tickets/page.tsx", "src/app/(dashboard)/tickets/[id]/page.tsx",
        "src/app/(dashboard)/inicio/page.tsx"]
    evidencia["frontend_sources"] = [dict(path=p, sha256=hashlib.sha256((frontend / p).read_bytes()).hexdigest()) for p in rutas]
    archivo = carpeta / "next-control.json"
    escribir(archivo, dict(control, repo=str(frontend.parent), project=str(frontend)))
    env = os.environ.copy()
    for nombre in ("NODE_TLS_REJECT_UNAUTHORIZED", "NODE_OPTIONS", "NODE_EXTRA_CA_CERTS"):
        env.pop(nombre, None)
    env.update(NODE_PATH=str(frontend / "node_modules"), NEXT_TELEMETRY_DISABLED="1",
        NEXT_PUBLIC_USE_MOCKS="false", NEXT_PUBLIC_TRUSTED_LOCAL_INGRESS="true",
        AUTH_COOKIE_PROFILE="local", BACKEND_INTERNAL_URL=control["backend"],
        BACKEND_SERVICE_CREDENTIAL=control["credential"], NODE_EXTRA_CA_CERTS=str(carpeta / "ca.pem"))
    with (carpeta / "next.log").open("wb") as salida:
        proceso = subprocess.Popen([node, str(Path(__file__).with_name("servidor_next.mjs")), str(archivo)],
            cwd=frontend, env=env, stdout=salida, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            limite = monotonic() + 60
            listo = False
            while proceso.poll() is None and monotonic() < limite:
                cliente = http.client.HTTPConnection("127.0.0.1", control["port"], timeout=2)
                try:
                    cliente.request("GET", "/_mvp04/ready")
                    response = cliente.getresponse()
                    listo = response.status == 200 and json.loads(response.read()).get("harness") == control["identity"]
                    if listo:
                        break
                except (OSError, ValueError, http.client.HTTPException):
                    pass
                finally:
                    cliente.close()
                sleep(.1)
            if not listo:
                raise RuntimeError("No inició la aplicación Next local.")
            yield env
        finally:
            detener(proceso)
            evidencia["next_stopped"] = proceso.poll() is not None
            salida.flush()
            logs = (carpeta / "next.log").read_text(encoding="utf-8", errors="replace")
            evidencia["next_logs_without_secrets"] = not any(s and s in logs for s in ocultos)
            evidencia["next_diagnostics"] = [line for line in logs.splitlines()
                if line.startswith(("MVP04_", "LOCAL_BRIDGE_"))]
            assert evidencia["next_logs_without_secrets"], "Secreto en registro Next."


def ejecutar(frontend: Path, reporte: Path, driver: Path | None):
    if reporte.exists():
        raise ValueError("El reporte ya existe; conservar evidencia anterior.")
    carpeta = BACKEND / (".arnes-auth07d2-" + uuid4().hex)
    carpeta.mkdir()
    evidencia = dict(task="SYNAPDESK-MVP12B-RESOLVE-PR52-REVIEW",
        source_sha="9271d90ad812f62b95c93aa2dfc87d3aa071aaed",
        logout_sha="c81367aae9a7213581afb02f69976e91ba39a5a0",
        reconciliation_sha="9c13277635e3e0838c46a05b863a502cd2ec7fef",
        main_merge_sha="800a723034279c12ff0e26b970d7b554fe50d151",
        production_enabled=False, base_main="4acec0992b246ed78898c06d1007a626230e51cc", browser_verified=False)
    fuentes = [BACKEND / p for p in (
        "app/api/adaptadores_auth.py", "app/api/adaptadores_tickets.py",
        "app/tickets/servicio.py", "app/tickets/repositorio.py",
        "herramientas/ingreso_local/aplicacion.py", "herramientas/ingreso_local/evidencia.py",
        "herramientas/ingreso_local/protocolo.mjs", "herramientas/ingreso_local/servidor_next.mjs",
        "herramientas/ingreso_local/demo.py")]
    evidencia["backend_sources"] = [dict(path=str(p.relative_to(BACKEND.parent)).replace("\\", "/"),
        sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in fuentes]
    ocultos = []
    try:
        certificados(carpeta)
        with base_propia(carpeta, evidencia) as (motor, nombre):
            with motor.connect() as db:
                evidencia["pgvector"] = db.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
                assert evidencia["pgvector"] == "0.8.6"
                assert 170000 <= int(evidencia["database"]["version"]) < 180000
            puerto = puerto_libre()
            origen = f"http://127.0.0.1:{puerto}"
            servicio, clave = credencial(), SecretBytes(secrets.token_bytes(32))
            audiencia = uuid4().hex
            datos = seleccionar_configuracion_bd("testing").model_dump()
            datos.update({k: v for k, v in configuracion_login().model_dump().items() if k.startswith("auth_")})
            datos.update(postgres_db=nombre, auth_intermediario=politica([servicio]),
                auth_origenes_permitidos=[origen], auth_proxies_autorizados=["127.0.0.1/32"])
            config = Configuracion(_env_file=None, **datos)
            assert config.app_env == "testing"
            evidencia["app_env"] = config.app_env
            perfil = preparar_perfil(config, origen_publico=origen,
                nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
            verificador = VerificadorIngresoLocal(config, clave, audiencia, ventana_segundos=30, capacidad_nonces=2048)
            app = crear_aplicacion_local(config, motor, perfil, verificador, capacidad_argon2=1, max_cuerpo_bytes=65536)
            cuentas, tickets = [], []
            with Session(motor) as db, transaccion_seguridad(db):
                for rol in ("agent", "admin"):
                    password = secrets.token_urlsafe(32)
                    usuario = Usuario(nombre="Operador de demostración " + rol, correo=f"{uuid4()}@example.invalid",
                        hash_contrasena=ServicioContrasenas(config).generar_hash(password), rol=rol, activo=True)
                    db.add(usuario); db.flush()
                    cuentas.append(dict(id=str(usuario.id), email=usuario.correo, password=password, role=rol))
                    ocultos.extend([password, usuario.hash_contrasena])
                    # Datos iniciales propios; no crean sesiones ni simulan una operación HTTP.
                    for indice in range(6):
                        ticket = RepositorioTickets(db).crear(TicketCreate(
                            title=f"Solicitud persistida de {rol} {indice + 1}",
                            description="Registro real PostgreSQL para verificar listado paginado y detalle desde el navegador."), creador_id=usuario.id)
                        tickets.append(dict(id=str(ticket.id), title=ticket.title, description=ticket.description))
            with motor.connect() as db:
                assert db.scalar(select(func.count(Sesion.id))) == 0
                assert set(map(str, db.scalars(select(Ticket.id)))) == {t["id"] for t in tickets}
            ocultos.extend([servicio.get_secret_value(), clave.get_secret_value().hex(),
                base64.urlsafe_b64encode(clave.get_secret_value()).decode().rstrip("=")])
            evidencia["seed_committed_before_browser"] = True
            with listener(app, carpeta, evidencia) as privado:
                cliente_tls = http.client.HTTPSConnection("localhost", privado,
                    context=ssl.create_default_context(cafile=str(carpeta / "ca.pem")), timeout=15)
                try:
                    cliente_tls.request("GET", "/api/v1/auth/me", headers={
                        "Authorization": "Bearer " + secrets.token_urlsafe(32)})
                    respuesta = cliente_tls.getresponse()
                    assert respuesta.status == 503
                    assert json.loads(respuesta.read())["error"]["code"] == "SERVICE_UNAVAILABLE"
                    evidencia["sec01b_invalid_rejected_over_tls"] = True
                finally:
                    cliente_tls.close()
                control = dict(appEnv="testing", database=nombre, backend=f"https://localhost:{privado}",
                    port=puerto, identity=uuid4().hex, audience=audiencia,
                    ingressKey=base64.urlsafe_b64encode(clave.get_secret_value()).decode().rstrip("="),
                    credential=servicio.get_secret_value())
                privado_browser = carpeta / "browser-input.json"
                escribir(privado_browser, dict(origin=origen, accounts=cuentas, tickets=tickets,
                    backend=control["backend"], ca=str(carpeta / "ca.pem"), output=str(carpeta / "browser-result.json"),
                    privateCookies=str(carpeta / "cookies-private.json"),
                    checkpointRequest=str(carpeta / "checkpoint-request.json"),
                    checkpointReply=str(carpeta / "checkpoint-reply.json"),
                    screenshotBase=str(reporte.with_suffix(""))))
                with next_local(frontend, carpeta, control, evidencia, ocultos) as env:
                    if driver is None:
                        print(json.dumps(dict(url=origen + "/login", private_credentials_file=str(privado_browser))))
                        input("Enter para cerrar solo los recursos de esta demostración: ")
                    else:
                        with (carpeta / "driver-private.log").open("wb") as log:
                            run = subprocess.Popen([shutil.which("node"), str(driver), str(privado_browser)],
                                cwd=frontend, env=env, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                            try:
                                limite, procesado = monotonic() + 480, None
                                while run.poll() is None:
                                    assert monotonic() < limite, "Agotado el plazo del navegador."
                                    punto = carpeta / "checkpoint-request.json"
                                    if punto.exists():
                                        pedido = json.loads(punto.read_text(encoding="utf-8"))
                                        if pedido["sequence"] != procesado:
                                            comprobar_punto_sql(motor, pedido, cuentas, evidencia)
                                            procesado = pedido["sequence"]
                                            escribir(carpeta / "checkpoint-reply.json", dict(sequence=procesado, passed=True))
                                    sleep(.05)
                            finally:
                                detener(run)
                        assert not any(s and s in (carpeta / "driver-private.log").read_text(
                            encoding="utf-8", errors="replace") for s in ocultos)
                        result_path = carpeta / "browser-result.json"
                        if result_path.exists():
                            evidencia["browser"] = json.loads(result_path.read_text(encoding="utf-8"))
                        assert run.returncode == 0, "Falló la validación de navegador; consultar casos saneados."
                        evidencia["browser_verified"] = evidencia["browser"]["passed"]
                        cookies = json.loads((carpeta / "cookies-private.json").read_text(encoding="utf-8"))
                        ocultos.extend(par.split("=", 1)[1] for cuenta in cookies
                            for par in cuenta["cookie"].split("; ") if "=" in par)
                        with motor.begin() as db:
                            db.execute(update(Sesion).where(Sesion.usuario_id == cuentas[0]["id"]).values(
                                revocada_en=func.clock_timestamp(), motivo_revocacion="individual"))
                            db.execute(update(Usuario).where(Usuario.id == cuentas[1]["id"]).values(activo=False))
                        negativos = []
                        for cuenta in cookies:
                            for ruta in ("/api/v1/tickets", "/api/v1/tickets/" + tickets[0]["id"]):
                                cliente = http.client.HTTPConnection("127.0.0.1", puerto, timeout=15)
                                try:
                                    cliente.request("GET", ruta, headers={"Cookie": cuenta["cookie"]})
                                    response = cliente.getresponse()
                                    response.read()
                                    assert response.status == 401
                                    negativos.append(dict(role=cuenta["role"], path=ruta, status=401))
                                finally:
                                    cliente.close()
                        evidencia["revoked_or_inactive_http_rejected"] = negativos
                    with motor.connect() as db:
                        evidencia["persisted_sessions_from_http"] = db.scalar(select(func.count(Sesion.id)))
                        evidencia["persisted_tickets"] = db.scalar(select(func.count(Ticket.id)))
                        evidencia["persisted_login_audits"] = db.scalar(select(func.count(EventoAutenticacion.id)).where(
                            EventoAutenticacion.tipo_evento == "login", EventoAutenticacion.resultado == "success"))
                    evidencia["ip_proof_statistics"] = dict(verificador.estadisticas)
    except Exception as error:
        evidencia["error_type"] = type(error).__name__
        raise
    finally:
        if "verificador" in locals():
            evidencia["ip_proof_statistics"] = dict(verificador.estadisticas)
        # Preservar el resultado saneado incluso si Windows impide limpiar un recurso.
        serializado = json.dumps(evidencia)
        assert not any(s and s in serializado for s in ocultos)
        escribir(reporte, evidencia)
        borrar_temporal(carpeta)
        evidencia["temporary_deleted"] = not carpeta.exists()
        serializado = json.dumps(evidencia)
        assert not any(s and s in serializado for s in ocultos)
        escribir(reporte, evidencia)
    return evidencia


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--reporte", type=Path, required=True)
    parser.add_argument("--browser-driver", type=Path)
    args = parser.parse_args()
    result = ejecutar(args.frontend.resolve(), args.reporte.resolve(), args.browser_driver.resolve() if args.browser_driver else None)
    print(json.dumps({k: result.get(k) for k in ("browser_verified", "persisted_sessions_from_http",
        "persisted_tickets", "database_deleted", "next_stopped", "fastapi_stopped", "temporary_deleted")}))


if __name__ == "__main__":
    main()
