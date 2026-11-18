"""Controles reproducibles de documentación, secretos y configuración de CI.

Solo usa archivos de Git, más candidatos explícitos para validación sin staging.
No concede confianza a informes auxiliares por el hecho de existir localmente.
"""

import argparse
import ast
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = ".github/workflows/backend-auth-ci.yml"
TIPOS_PULL_REQUEST = ["opened", "synchronize", "reopened", "edited", "ready_for_review"]
JOBS = {"unitarias", "postgresql", "tls", "alembic", "documentacion"}
ACCIONES = {"actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"}
ENLACE = re.compile(r'!?\[[^\]\n]*\]\((<[^>]+>|(?:[^()\s]|\([^()\s]*\))+)(?:\s+"[^"]*")?\)')


class ErrorControl(ValueError):
    """Mensaje propio saneado: nunca DSN, valores sospechosos o excepciones ajenas."""


def git(*args):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=RAIZ)


def inventario(incluir=()):
    archivos = set(filter(None, git("ls-files", "-z").decode("utf-8").split("\0")))
    for ruta in incluir:
        candidato = (RAIZ / ruta).resolve()
        relativo = candidato.relative_to(RAIZ).as_posix()
        ignorado = subprocess.run(["git", "check-ignore", "--quiet", "--", relativo],
                                  cwd=RAIZ, check=False).returncode
        if not candidato.is_file() or ignorado != 1:
            raise ErrorControl("Candidato ausente o excluido de Git.")
        archivos.add(relativo)
    return archivos


def markdown(texto):
    """Separa bloques cercados; el código no define enlaces ni encabezados."""
    visible, ejemplos, bloque = [], [], []
    cerca, lenguaje = None, ""
    for linea in texto.splitlines():
        if cerca:
            if re.fullmatch(r" {0,3}" + re.escape(cerca[0]) + "{" + str(len(cerca)) + r",}\s*", linea):
                if lenguaje == "json":
                    ejemplos.append("\n".join(bloque))
                cerca, bloque = None, []
            else:
                bloque.append(linea)
            visible.append("")
            continue
        apertura = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", linea)
        if apertura:
            cerca, lenguaje = apertura[1], apertura[2].strip().lower()
            visible.append("")
        else:
            visible.append(linea)
    if cerca:
        raise ErrorControl("Bloque Markdown sin cerrar.")
    return "\n".join(visible), ejemplos


def anclas(texto):
    visible, _ = markdown(texto)
    usados = set()
    lineas = visible.splitlines()
    for indice, linea in enumerate(lineas):
        titulo = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", linea)
        contenido = titulo[1] if titulo else None
        if contenido is None and indice and re.fullmatch(r" {0,3}(?:=+|-+)\s*", linea):
            contenido = lineas[indice - 1].strip() or None
        if contenido is None:
            continue
        contenido = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", contenido)
        contenido = html.unescape(re.sub(r"<[^>]+>", "", contenido))
        contenido = contenido.replace("`", "").replace("*", "").replace("~", "")
        base = re.sub(r"[^\w\- ]", "", contenido.lower()).replace(" ", "-")
        candidato, numero = base, 0
        while candidato in usados:
            numero += 1
            candidato = f"{base}-{numero}"
        usados.add(candidato)
    usados.update(re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', visible))
    return usados


def validar_enlace(origen, destino, archivos):
    url = urlsplit(destino.strip("<>"))
    if url.scheme or url.netloc:
        return False
    archivo = RAIZ / origen
    candidato = ((RAIZ / unquote(url.path).lstrip("/")) if url.path.startswith("/")
                 else archivo.parent / unquote(url.path)) if url.path else archivo
    candidato = candidato.resolve()
    relativo = candidato.relative_to(RAIZ).as_posix()
    if relativo not in archivos:
        if not any(p.startswith(relativo + "/") for p in archivos):
            raise ErrorControl("Destino no versionado.")
        if url.fragment:
            candidato /= "README.md"
            if candidato.relative_to(RAIZ).as_posix() not in archivos:
                raise ErrorControl("Ancla de directorio sin README versionado.")
    if not candidato.exists():
        raise ErrorControl("Destino ausente.")
    if url.fragment and (candidato.suffix.lower() != ".md"
                         or unquote(url.fragment) not in anclas(candidato.read_text(encoding="utf-8"))):
        raise ErrorControl("Ancla inexistente o tipo no admitido.")
    return True


def contratos():
    texto = (RAIZ / "docs/contratos/auth07d3-compatibilidad-y-plan-integracion.md").read_text(encoding="utf-8")
    politicas = re.findall(r"^\| (P\d+) \|", texto, re.M)
    if politicas != [f"P{i}" for i in range(1, 11)]:
        raise ErrorControl("Las políticas P1–P10 deben estar formalizadas una vez.")
    decisiones = re.findall(r"^\| (C\d+) \| ([^|]+)\|", texto, re.M)
    if ([fila[0] for fila in decisiones] != [f"C{i:02}" for i in range(1, 10)]
            or any(not estado.strip().startswith(("PROPUESTA", "PENDIENTE")) for _, estado in decisiones)):
        raise ErrorControl("Se alteró el estado pendiente de C01–C09.")
    p4 = next(linea for linea in texto.splitlines() if linea.startswith("| P4 |"))
    if "todavía no implementada" not in p4:
        raise ErrorControl("Revisar explícitamente el estado contractual vigente de P4.")
    arbol = ast.parse((RAIZ / "backend/app/api/esquemas_auth.py").read_text(encoding="utf-8"))
    for clase, esperado in {"ApiErrorBody": {"code", "message", "details", "requestId"},
                            "AuthUser": {"id", "email", "role"}}.items():
        nodo = next(n for n in arbol.body if isinstance(n, ast.ClassDef) and n.name == clase)
        campos = {n.target.id for n in nodo.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
        if campos != esperado:
            raise ErrorControl("DTO incompatible con el contrato vigente.")


def documentacion(archivos):
    documentos = sorted(p for p in archivos if p.endswith(".md") and (
        p in {"CONTRIBUTING.md", "docs/auditorias/auth07-sec01a-bootstrap-csrf.md"}
        or p.startswith(("backend/", "docs/contratos/", "docs/arquitectura/", ".github/"))))
    enlaces = locales = ejemplos = 0
    for ruta in documentos:
        texto = (RAIZ / ruta).read_text(encoding="utf-8")
        visible, bloques = markdown(texto)
        destinos = ENLACE.findall(visible)
        destinos.extend(re.findall(r"^ {0,3}\[[^\]]+\]:\s*(\S+)", visible, re.M))
        for destino in destinos:
            try:
                locales += int(validar_enlace(ruta, destino, archivos))
            except ValueError:
                raise ErrorControl(f"Enlace o ancla inválidos en {ruta}.") from None
            enlaces += 1
        for bloque in bloques:
            json.loads(bloque)
            ejemplos += 1
    jsons = [p for p in archivos if p.endswith(".json")]
    for ruta in jsons:
        json.loads((RAIZ / ruta).read_text(encoding="utf-8-sig"))
    contratos()
    return {"markdown": len(documentos), "enlaces": enlaces, "enlaces_locales": locales,
            "urls_externas_sin_solicitud": enlaces - locales, "ejemplos_json": ejemplos,
            "archivos_json": len(jsons), "contratos": "P1–P10, C01–C09, P4 y DTO vigentes"}


PATRONES = {
    "clave_privada": rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    "token_github": rb"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b",
    "clave_aws": rb"\bAKIA[A-Z0-9]{16}\b",
    "url_postgresql": rb"postgres(?:ql)?(?:\+psycopg)?://[^\s:/]+:[^\s@]+@",
    "variable_secreta": rb"^\s*(?:POSTGRES(?:_TEST)?_PASSWORD|AUTH_[A-Z_]*(?:SECRET|TOKEN))\s*=\s*\S+",
}
# Excepciones exactas, públicas y limitadas a la plantilla; no se ignoran tests.
PLANTILLAS = {
    b"POSTGRES_PASSWORD=reemplazar_con_clave_local",
    b"POSTGRES_TEST_PASSWORD=reemplazar_con_clave_testing_local",
}
PLANTILLA_URL = (b"SYNAPDESK_SEMANTIC_DATABASE_URL=postgresql" +
                 b"://synapdesk_test:reemplazar_con_clave_testing_local@localhost:5433/synapdesk_semantic_test")


def alcance_secretos(ruta):
    return (ruta in {".env.example", ".gitignore", "CONTRIBUTING.md", "compose.yaml",
                     "docs/auditorias/auth07-sec01a-bootstrap-csrf.md"}
            or Path(ruta).name.startswith(".env")
            or ruta.startswith(("backend/", ".github/", "docs/contratos/", "docs/arquitectura/", "infra/postgres/")))


def hallazgos(ruta, datos):
    encontrados = []
    for numero, linea in enumerate(datos.splitlines(), 1):
        for regla, patron in PATRONES.items():
            if not re.search(patron, linea):
                continue
            plantilla = ruta == ".env.example" and (
                linea.strip() in PLANTILLAS or (
                    regla == "url_postgresql" and
                    linea == PLANTILLA_URL))
            if not plantilla:
                encontrados.append({"path": ruta, "line": numero, "rule": regla})
    return encontrados


def secretos(archivos, base=None):
    encontrados = []
    seleccionados = sorted(p for p in archivos if alcance_secretos(p))
    for ruta in seleccionados:
        if Path(ruta).name != ".env.example" and (Path(ruta).name.startswith(".env")
                or Path(ruta).suffix in {".key", ".pem", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3"}):
            encontrados.append({"path": ruta, "rule": "archivo_privado"})
        encontrados.extend(hallazgos(ruta, (RAIZ / ruta).read_bytes()))
    objetos = 0
    if base:
        if not re.fullmatch(r"[a-f0-9]{40}", base) or base == "0" * 40:
            raise ErrorControl("El intervalo histórico requiere un SHA base válido.")
        for linea in git("rev-list", "--objects", base + "..HEAD").decode("utf-8").splitlines():
            partes = linea.split(" ", 1)
            if (len(partes) != 2 or not alcance_secretos(partes[1])
                    or git("cat-file", "-t", partes[0]).strip() != b"blob"):
                continue
            objetos += 1
            encontrados.extend(hallazgos(partes[1], git("cat-file", "blob", partes[0])))
    resultado = {"archivos": len(seleccionados), "blobs_historicos": objetos, "hallazgos": encontrados,
                 "alcance": "Backend/auth, contratos, arquitectura, CI, infraestructura PG y archivos de entorno."}
    if encontrados:
        print(json.dumps(resultado))  # Solo ruta, línea y regla; nunca el valor.
        raise ErrorControl("Revisar los posibles secretos, sin aprobación automática.")
    return resultado


def cargar_workflow(texto):
    import yaml

    class SinDuplicados(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        resultado = {}
        for clave, valor in node.value:
            key = loader.construct_object(clave, deep=deep)
            if key in resultado:
                raise ErrorControl("Clave YAML duplicada.")
            resultado[key] = loader.construct_object(valor, deep=deep)
        return resultado

    SinDuplicados.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return yaml.load(texto, Loader=SinDuplicados)


def workflow(datos):
    if set(datos["on"]) != {"pull_request", "push"} or datos["permissions"] != {"contents": "read"}:
        raise ErrorControl("Eventos o permisos inseguros.")
    if (datos["on"]["pull_request"] != {"branches": ["main"], "types": TIPOS_PULL_REQUEST}
            or datos["on"]["push"] != {"branches": ["main"]}):
        raise ErrorControl("No se admiten filtros o eventos que omitan checks obligatorios.")
    if set(datos["jobs"]) != JOBS or "secrets." in json.dumps(datos):
        raise ErrorControl("Jobs o acceso a secretos inesperados.")
    for nombre, job in datos["jobs"].items():
        if (job.get("runs-on") != "ubuntu-24.04" or not job.get("timeout-minutes")
                or any(k in job for k in ("if", "needs", "permissions", "continue-on-error"))):
            raise ErrorControl("Un check obligatorio podría omitirse.")
        comandos = []
        for paso in job["steps"]:
            if "if" in paso or "continue-on-error" in paso:
                raise ErrorControl("Un paso obligatorio podría omitirse.")
            if "uses" in paso:
                if paso["uses"] not in ACCIONES:
                    raise ErrorControl("Acción inesperada o sin SHA fijo.")
                if paso["uses"].startswith("actions/checkout@") and paso.get("with") != {
                        "persist-credentials": False, "fetch-depth": 0}:
                    raise ErrorControl("Checkout debe ser de solo lectura y conservar historial.")
                if paso["uses"].startswith("actions/setup-python@") and paso["with"]["python-version"] != "3.12":
                    raise ErrorControl("Python fuera de la versión comprobada.")
            comandos.extend(paso.get("run", "").splitlines())
        requeridos = ["python -m pip install -r requirements-dev.txt", "python -m pip check"]
        requeridos += (["python -m herramientas.validar_ci " + modo for modo in (
            "documentacion", "secretos", "workflow")] if nombre == "documentacion" else [
                "python -m herramientas.ci_backend " + ("migraciones" if nombre == "alembic" else nombre)])
        if not set(requeridos).issubset(linea.strip() for linea in comandos):
            raise ErrorControl("Falta una validación obligatoria.")
        if nombre == "documentacion" and '"$RUNNER_TEMP/actionlint" ../.github/workflows/backend-auth-ci.yml' not in comandos:
            raise ErrorControl("Falta la comprobación del esquema de Actions.")
        if nombre in {"postgresql", "alembic"}:
            servicio = job["services"]["postgres"]
            if (servicio["image"] != "pgvector/pgvector:0.8.6-pg17-bookworm"
                    or servicio["ports"] != ["127.0.0.1:5433:5432"] or "volumes" in servicio
                    or "--health-cmd" not in servicio["options"]
                    or job["env"]["POSTGRES_TEST_HOST"] != "127.0.0.1"
                    or job["env"]["POSTGRES_TEST_PORT"] != "5433"
                    or servicio["env"]["POSTGRES_DB"] != job["env"]["POSTGRES_TEST_DB"]
                    or servicio["env"]["POSTGRES_USER"] != job["env"]["POSTGRES_TEST_USER"]
                    or servicio["env"]["POSTGRES_PASSWORD"] != "${{ github.run_id }}-${{ github.run_attempt }}-backend-tests"
                    or job["steps"][0].get("working-directory") != "${{ runner.temp }}"):
                raise ErrorControl("Servicio PostgreSQL no aislado.")
        elif "services" in job:
            raise ErrorControl("Infraestructura inesperada.")
    muestras = ["backend/app/api/cookies_auth.py", "backend/pruebas/test_cookies_estrictas_http.py",
                "backend/migraciones/versiones/0006_user_created.py", "docs/contratos/autenticacion-v1.md", WORKFLOW]
    return {"jobs": sorted(JOBS), "eventos": ["pull_request/main", "push/main"],
            "tipos_pull_request": list(TIPOS_PULL_REQUEST),
            "activacion_exclusiva": {ruta: True for ruta in muestras}, "filtros_de_rutas": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modo", choices=("documentacion", "secretos", "workflow"))
    parser.add_argument("--incluir", nargs="*", default=[], help="Candidatos explícitos, sin staging.")
    parser.add_argument("--base", default=None, help="SHA base del intervalo a escanear.")
    args = parser.parse_args()
    try:
        archivos = inventario(args.incluir)
        if args.modo == "workflow":
            resultado = workflow(cargar_workflow((RAIZ / WORKFLOW).read_text(encoding="utf-8")))
        elif args.modo == "documentacion":
            resultado = documentacion(archivos)
        else:
            import os
            resultado = secretos(archivos, args.base or os.environ.get("CI_BASE_SHA"))
        print(json.dumps(resultado, ensure_ascii=False))
    except ErrorControl as error:
        print("CI_VALIDATION_FAILED: " + str(error), file=sys.stderr)
        return 1
    except Exception as error:
        print("CI_VALIDATION_FAILED: " + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
